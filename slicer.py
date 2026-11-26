"""Modelo 3D -> placas planas de MDF con ranuras de encaje (DXF para RDWorks).

Uso: ~/laser-env/bin/python -I slicer.py modelo.obj [--largo 300] [--ranura 3.0] [--nx 9] [--ny 3]
Ejes tras orientar: X = largo, Y = ancho, Z = alto. Placas en X (transversales) y en Y (longitudinales).
"""
import argparse, itertools, os
import numpy as np, trimesh, ezdxf
from shapely.geometry import Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union

ap = argparse.ArgumentParser()
ap.add_argument("modelo")
ap.add_argument("--largo", type=float, default=300, help="mm, largo del carro final")
ap.add_argument("--ranura", type=float, default=3.0, help="mm, ancho DIBUJADO de la ranura (sale del peine de kerf)")
ap.add_argument("--nx", type=int, default=9, help="placas transversales")
ap.add_argument("--ny", type=int, default=3, help="placas longitudinales")
ap.add_argument("--cama", type=float, nargs=2, default=[600, 400])
ap.add_argument("--min", type=float, default=3.0, help="mm, detalle minimo (se borra lo mas fino)")
ap.add_argument("--rotar", default="z,x,y", help="mapeo de ejes del archivo a (X,Y,Z) = (largo,ancho,alto)")
ap.add_argument("--out", default=os.path.expanduser("~/laser/out"))
A = ap.parse_args()
T, GAP, MARGEN = A.ranura, 3.0, 5.0


def cargar():
    m = trimesh.load(A.modelo, force="mesh")
    idx = ["xyz".index(c) for c in A.rotar.split(",")]
    m.vertices = m.vertices[:, idx]          # permutacion de ejes
    m.apply_translation(-m.bounds[0])
    m.apply_scale(A.largo / m.extents[0])
    m._vox = m.voxelized(1.0)
    return m


def silueta(m, eje, pos):
    """Corte macizo en el plano eje=pos (rodaja de espesor T del mallado voxelizado) -> poligono 2D o None."""
    from scipy import ndimage as nd
    import contourpy
    V = m._vox; p = V.pitch[0]; i = int(round((pos - V.translation[eje]) / p)); k = max(1, int(round(T / p / 2)))
    sl = [slice(None)] * 3; sl[eje] = slice(max(i - k, 0), i + k + 1)
    a = V.matrix[tuple(sl)].any(axis=eje)
    cols = [c for c in range(3) if c != eje]
    a = np.pad(a, 8)
    a = nd.binary_closing(a, iterations=int(A.min * 1.5)); a = nd.binary_fill_holes(a)
    a = nd.binary_opening(a, iterations=max(1, int(A.min / 2)))
    if not a.any(): return None
    lines = contourpy.contour_generator(z=a.T.astype(float)).lines(0.5)   # (col=eje cols[0], fila=cols[1])
    org = V.translation[cols] - 8 * p
    ps = [Polygon(np.asarray(l) * p + org).buffer(0) for l in lines if len(l) >= 4]
    ps = [q for q in ps if q.area > 50]
    return max(ps, key=lambda q: q.area).simplify(0.3) if ps else None   # ponytail: solo la pieza mas grande; partes sueltas se pierden


def intervalos(poly, c):
    """Tramos z donde la vertical en coordenada c cruza el poligono."""
    g = poly.intersection(LineString([(c, -1e4), (c, 1e4)]))
    segs = getattr(g, "geoms", [g])
    return [(s.bounds[1], s.bounds[3]) for s in segs if s.geom_type == "LineString" and s.length > 1e-6]


def comunes(ia, ib):
    """Tramos z compartidos entre ambas placas, con los extremos de cada una."""
    out = []
    for (a0, a1), (b0, b1) in itertools.product(ia, ib):
        lo, hi = max(a0, b0), min(a1, b1)
        if hi - lo > 2 * T: out.append((lo, hi, a0, a1, b0, b1))     # tramos mas bajos que 2T no sostienen una ranura
    return out


def piezas(m):
    ex = m.extents
    xs = np.linspace(0.08, 0.92, A.nx) * ex[0]
    ys = np.linspace(0.25, 0.75, A.ny) * ex[1]
    PX = [dict(nombre=f"X{i+1}", pos=x, poly=silueta(m, 0, x)) for i, x in enumerate(xs)]   # coords (y,z)
    PY = [dict(nombre=f"Y{i+1}", pos=y, poly=silueta(m, 1, y)) for i, y in enumerate(ys)]   # coords (x,z)
    PX = [p for p in PX if p["poly"] is not None]; PY = [p for p in PY if p["poly"] is not None]
    nranuras = omitidos = 0
    for a, b in itertools.product(PX, PY):
        for lo, hi, a0, a1, b0, b1 in comunes(intervalos(a["poly"], b["pos"]), intervalos(b["poly"], a["pos"])):
            mid = (lo + hi) / 2
            ra = box(b["pos"] - T / 2, mid, b["pos"] + T / 2, hi + 200)      # ranura de A desde arriba
            rb = box(a["pos"] - T / 2, lo - 200, a["pos"] + T / 2, mid)      # ranura de B desde abajo
            if a1 >= hi - 1e-6 and b0 <= lo + 1e-6: pass
            elif b1 >= hi - 1e-6 and a0 <= lo + 1e-6:                       # roles invertidos
                ra = box(b["pos"] - T / 2, lo - 200, b["pos"] + T / 2, mid); rb = box(a["pos"] - T / 2, mid, a["pos"] + T / 2, hi + 200)
            else: omitidos += 1; continue                                    # ranura quedaria cerrada: no encajaria
            na, nb = a["poly"].difference(ra), b["poly"].difference(rb)
            if na.geom_type != "Polygon" or nb.geom_type != "Polygon" or na.interiors or nb.interiors: omitidos += 1; continue   # parte la placa o deja hueco cerrado
            a["poly"], b["poly"] = na, nb; nranuras += 1
    print(f"{omitidos} cruces sin ranura (cerrada o parte la placa)")
    return PX + PY, nranuras


def acomodar(ps):
    """Estantes simples sobre la cama; devuelve lista de hojas, cada una [(pieza, dx, dy)]."""
    W, H = A.cama
    hojas, cur, x, y, fila = [], [], MARGEN, MARGEN, 0
    for p in sorted(ps, key=lambda p: -p["poly"].bounds[3] + p["poly"].bounds[1]):
        x0, y0, x1, y1 = p["poly"].bounds; w, h = x1 - x0, y1 - y0
        assert w <= W - 2 * MARGEN and h <= H - 2 * MARGEN, f"{p['nombre']} no cabe en la cama ({w:.0f}x{h:.0f})"
        if x + w > W - MARGEN: x, y, fila = MARGEN, y + fila + GAP, 0
        if y + h > H - MARGEN: hojas.append(cur); cur, x, y, fila = [], MARGEN, MARGEN, 0
        cur.append((p, x - x0, y - y0)); x += w + GAP; fila = max(fila, h)
    return hojas + [cur]


def exportar(hojas):
    os.makedirs(A.out, exist_ok=True)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from shapely import affinity
    for n, h in enumerate(hojas, 1):
        doc = ezdxf.new(units=4); msp = doc.modelspace(); doc.layers.add("GRABAR", color=5)
        fig, ax = plt.subplots(figsize=(10, 6.7))
        for p, dx, dy in h:
            g = affinity.translate(p["poly"], dx, dy)
            for pg in getattr(g, "geoms", [g]):
                for ring in [pg.exterior, *pg.interiors]:
                    msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "0"})
                    ax.plot(*ring.xy, "k", lw=0.8)
            c = g.representative_point()
            msp.add_text(p["nombre"], height=5, dxfattribs={"layer": "GRABAR", "insert": (c.x, c.y)})
            ax.text(c.x, c.y, p["nombre"], fontsize=8, color="b")
        ax.set_xlim(0, A.cama[0]); ax.set_ylim(0, A.cama[1]); ax.set_aspect("equal"); ax.set_title(f"Hoja {n}")
        fig.savefig(f"{A.out}/hoja{n}.png", dpi=90); plt.close(fig)
        doc.saveas(f"{A.out}/hoja{n}.dxf")
    return len(hojas)


def demo(ps, hojas, nranuras):
    """Chequeos minimos: piezas de un solo cuerpo, ranuras = cruces, sin traslapes ni salirse de la cama."""
    for p in ps:
        assert p["poly"].geom_type == "Polygon", f"{p['nombre']} se partio en {len(p['poly'].geoms)} (ranura corta una zona fina)"
        assert p["poly"].is_valid and not p["poly"].interiors, f"{p['nombre']} tiene hueco cerrado"
    assert nranuras > 0
    from shapely import affinity
    for h in hojas:
        gs = [affinity.translate(p["poly"], dx, dy) for p, dx, dy in h]
        for g in gs: assert box(0, 0, *A.cama).contains(g)
        for g1, g2 in itertools.combinations(gs, 2): assert not g1.intersects(g2)


if __name__ == "__main__":
    m = cargar(); ps, nr = piezas(m); hojas = [h for h in acomodar(ps) if h]
    print(f"modelo {m.extents.round(1)} mm | {len(ps)} placas | {nr} cruces con ranura")
    try: demo(ps, hojas, nr); print("chequeos OK")
    except AssertionError as e: print("AVISO:", e)
    print(f"{exportar(hojas)} hoja(s) en {A.out}")
