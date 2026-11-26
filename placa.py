"""Placa 'Ingenieria en Sistemas - Promo 2026' en MDF por capas (engranaje + circuito + birrete/laptop/servidores).

Uso: ~/laser-env/bin/python -I placa.py [--diam 150] [--esp 5] [--out DIR]
Capas DXF: CORTE (rojo) | GRABAR (relleno: texto, hojas, engranajes) | TRAZOS (lineas finas: circuito) | ETIQUETAS (no enviar)
Pila (de atras hacia adelante): C1 base, C2 fondo (circuito), C3 anillo (texto), E1 piezas pegadas (toca, PC, torres, engranajes, diploma), E2 relieve, E3 laureles.
"""
import argparse, math, os, random
import numpy as np, ezdxf
from shapely.geometry import Polygon, Point, LineString, box
from shapely.geometry.polygon import orient
from shapely import affinity
from shapely.ops import unary_union
from shapely import offset_curve
from matplotlib.textpath import TextPath, text_to_path
from matplotlib.font_manager import FontProperties

ap = argparse.ArgumentParser()
ap.add_argument("--diam", type=float, default=150, help="mm, diametro punta a punta de los dientes")
ap.add_argument("--esp", type=float, default=5.0, help="mm, espesor del MDF")
ap.add_argument("--cama", type=float, nargs=2, default=[600, 400])
ap.add_argument("--out", default=os.path.expanduser("~/Escritorio/placa_ingenieria"))
A = ap.parse_args()
assert 130 <= A.diam <= 190, "fuera del rango donde el texto y los detalles se leen bien"
k = A.diam / 150
redondo = lambda g, r: g.buffer(-r, join_style=1).buffer(r, join_style=1)
pol = lambda r, d: (r * math.cos(math.radians(d)), r * math.sin(math.radians(d)))
RO, RR, RV = 75 * k, 66.5 * k, 40 * k          # punta de diente, raiz, radio de la ventana
FB = FontProperties(family="DejaVu Sans", weight="bold"); FM = FontProperties(family="DejaVu Sans Mono", weight="bold")


def engranaje(ro, rr, n, tip, base, rad):
    pts, p = [], 360 / n
    for i in range(n):
        a = i * p
        pts += [pol(rr, a - base / 2), pol(ro, a - tip / 2), pol(ro, a + tip / 2), pol(rr, a + base / 2)]
        pts += [pol(rr, t) for t in np.linspace(a + base / 2, a + p - base / 2, 5)[1:-1]]
    return redondo(Polygon(pts), rad)


def glifo(ch, fp, h):
    """Poligono del caracter, centrado en x (por avance) y en y (por altura de mayuscula h). Devuelve (geom, avance)."""
    size = h / 0.729
    adv = text_to_path.get_text_width_height_descent(ch, fp, ismath=False)[0] * size / fp.get_size_in_points()
    g = Polygon()
    if ch.isspace(): return g, adv
    for r in TextPath((0, 0), ch, size=size, prop=fp).to_polygons():
        if len(r) >= 3: g = g.symmetric_difference(Polygon(r).buffer(0))
    return affinity.translate(g, -adv / 2, -h / 2), adv


def arco(texto, fp, h, r, centro, sentido, extra=0.0):
    """Texto en arco: r = radio del centro de las letras; sentido +1 arriba (horario, base hacia el centro), -1 abajo (antihorario, cabeza al centro)."""
    gl = [(c,) + glifo(c, fp, h) for c in texto]
    tot = sum(a + extra for _, _, a in gl); s = 0; out = []
    for c, g, a in gl:
        cs = s + (a + extra) / 2; s += a + extra
        th = centro + sentido * math.degrees((tot / 2 - cs) / r)
        if not g.is_empty:
            g = affinity.rotate(g, th - 90 if sentido > 0 else th + 90, origin=(0, 0))
            out.append(affinity.translate(g, *pol(r, th)))
    return unary_union(out), math.degrees(tot / r)


def hoja(c, r, ang, largo=8.0, ancho=3.2):
    """Una hoja (elipse) centrada en radio r, angulo c, eje largo girado 'ang' respecto a la tangente. Devuelve (hoja, nervadura)."""
    g = affinity.scale(Point(0, 0).buffer(1, 16), largo / 2, ancho / 2)
    ax = LineString([(-largo / 2 * .85, 0), (largo / 2 * .85, 0)])
    f = lambda sh: affinity.translate(affinity.rotate(sh, c + 90 + ang, origin=(0, 0)), *pol(r, c))
    return f(g), f(ax)


def laurel(c0, c1, r=56 * k, n=6):
    """Rama de laurel de UNA pieza (tallo + hojas unidas) sobre el arco c0->c1, hojas apuntando hacia c1. Devuelve (cuerpo, nervaduras)."""
    ang = np.linspace(c0, c1, n + 1)[:-1] + (c1 - c0) / (2 * n)
    sg = 1 if c1 > c0 else -1
    hs, ven = [], []
    for a in ang:
        for lado in (-1, 1):
            rr = r + lado * 2.5 * k; o = pol(rr, a)
            h, ax = hoja(a, rr, 0, 8.4 * k, 3.4 * k)
            hs.append(affinity.rotate(h, sg * (-lado) * 38, origin=o)); ven.append(affinity.rotate(ax, sg * (-lado) * 38, origin=o))
    tallo = LineString([pol(r, t) for t in np.linspace(c0, c1, 24)])
    return redondo(unary_union(hs + [tallo.buffer(1.4 * k)]), .5), ven + [tallo]


def texto_recto(txt, fp, h, x, y, extra=0.0):
    """Texto recto centrado en (x, y)."""
    gl = [glifo(c, fp, h) for c in txt]; tot = sum(a + extra for _, a in gl); cur = -tot / 2; out = []
    for g, a in gl:
        if not g.is_empty: out.append(affinity.translate(g, cur + (a + extra) / 2 + x, y))
        cur += a + extra
    return unary_union(out)


def chip(cx, cy, w, h, nx, ny):
    """Circuito integrado: cuerpo + patas. Devuelve (lineas, relleno, patas por lado, huella)."""
    cuerpo = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2); lin = [cuerpo.exterior]; pins = {"N": [], "S": [], "E": [], "W": []}
    for i in range(nx):
        x = cx - w / 2 + (i + .5) * w / nx
        for lado, sg in (("N", 1), ("S", -1)): lin.append(LineString([(x, cy + sg * h / 2), (x, cy + sg * (h / 2 + 1.4))])); pins[lado].append((x, cy + sg * (h / 2 + 1.4)))
    for j in range(ny):
        y = cy - h / 2 + (j + .5) * h / ny
        for lado, sg in (("E", 1), ("W", -1)): lin.append(LineString([(cx + sg * w / 2, y), (cx + sg * (w / 2 + 1.4), y)])); pins[lado].append((cx + sg * (w / 2 + 1.4), y))
    return lin, [Point(cx - w / 2 + 1.2, cy + h / 2 - 1.2).buffer(.5, 8)], pins, cuerpo.buffer(1.4)


def pcb(rng, rmax, obst):
    """Circuito impreso: circuitos integrados con patas, buses de pistas paralelas que salen a 45 grados y pistas sueltas con pastillas."""
    libre = Point(0, 0).buffer(rmax - 1.5).difference(obst.buffer(.6)); lin, rel, chips, hu = [], [], [], []
    for w, h, nx, ny in ((9, 7, 4, 3), (8, 8, 4, 4), (7, 6, 3, 3), (10, 6, 5, 3), (7, 7, 3, 3), (6, 6, 3, 3), (6, 5, 3, 2), (5, 5, 2, 2), (5, 5, 2, 2), (8, 5, 4, 2)):
        for _ in range(500):
            cx, cy = rng.uniform(-rmax, rmax), rng.uniform(-rmax, rmax)
            fp = box(cx - w / 2 - 1.4, cy - h / 2 - 1.4, cx + w / 2 + 1.4, cy + h / 2 + 1.4).buffer(.7)
            if libre.contains(fp) and all(fp.distance(o) > 2.0 for o in hu):
                c = chip(cx, cy, w, h, nx, ny); lin += c[0]; rel += c[1]; chips.append((cx, cy, w, h, nx, ny, c[2])); hu.append(c[3]); break
    todos = unary_union(hu + [obst.buffer(.3)]); disco = Point(0, 0).buffer(rmax)
    for cx, cy, w, h, nx, ny, pins in chips:
        phi = math.degrees(math.atan2(cy, cx)); lado, h0 = max((("E", 0), ("N", 90), ("W", 180), ("S", 270)), key=lambda t: math.cos(math.radians(phi - t[1])))
        n = min(4, len(pins[lado])); i0 = (len(pins[lado]) - n) // 2; sel = pins[lado][i0:i0 + n]
        pit = (w / nx) if lado in "NS" else (h / ny)
        a0 = np.array([sum(p[0] for p in sel) / n, sum(p[1] for p in sel) / n])
        sg = 1 if math.sin(math.radians(phi - h0)) < 0 else -1; hs = [h0, h0 + sg * 45]; Ls = [2.5, rng.uniform(5, 9), 45]
        pts = [a0]
        for hh, L in zip(hs + [hs[1]], Ls): pts.append(pts[-1] + L * np.array([math.cos(math.radians(hh)), math.sin(math.radians(hh))]))
        eje = LineString(pts)
        for i in range(n):
            t = offset_curve(eje, (i - (n - 1) / 2) * pit, join_style="mitre", mitre_limit=3)
            t = t.intersection(disco).difference(todos)
            lin += [g for g in getattr(t, "geoms", [t]) if g.geom_type == "LineString" and g.length > 1.5]
        v = eje.interpolate(Ls[0] + 3.0); lin.append(Point(v.x, v.y).buffer(1.0, 12).exterior); rel.append(Point(v.x, v.y).buffer(.35, 8))
    for a0, a1 in ((12, 62), (112, 160), (198, 250), (292, 345)):       # bus en arco junto al borde de la ventana
        for r in (rmax - 4.3, rmax - 3.1, rmax - 1.9):
            t = LineString([pol(r, a) for a in np.linspace(a0, a1, 40)]).difference(todos)
            lin += [g for g in getattr(t, "geoms", [t]) if g.geom_type == "LineString" and g.length > 2.0]
        for a in (a0, a1): lin.append(Point(*pol(rmax - 3.1, a)).buffer(1.0, 12).exterior); rel.append(Point(*pol(rmax - 3.1, a)).buffer(.35, 8))
    for i in range(30):                                       # pistas sueltas de relleno
        th = i * 360 / 30 + rng.uniform(-6, 6); p = np.array(pol(rmax, th)); d = round((th + 180) / 45) * 45; pts = [p.copy()]
        for _ in range(3):
            p = p + rng.uniform(4, 9) * np.array([math.cos(math.radians(d)), math.sin(math.radians(d))]); pts.append(p.copy()); d += rng.choice([-45, 45])
        t = LineString(pts).intersection(disco).difference(todos)
        lin += [g for g in getattr(t, "geoms", [t]) if g.geom_type == "LineString" and g.length > 1.5]
        e = Point(pts[-1])
        if disco.buffer(-1).contains(e) and e.distance(todos) > 1.8: lin.append(e.buffer(.9, 12).exterior); rel.append(e.buffer(.3, 8))
    return lin, rel


def pieza(nombre, corte=None, relleno=(), lineas=(), org=(0, 0), capa=""):
    return dict(nombre=nombre, corte=corte, relleno=[g for g in relleno if not g.is_empty], lineas=list(lineas), org=org, capa=capa)


def construir():
    rng = random.Random(11); P = []
    gear = engranaje(RO, RR, 16, 7.0, 13.0, 1.2)
    # ---- elementos que se pegan (coordenadas = posicion final en la ventana, origen = centro de la placa) ----
    board = Polygon([(-18, 13), (0, 21), (18, 13), (0, 5)]); cap = Polygon([(-8, 11), (-8, 3), (0, .5), (8, 3), (8, 11), (0, 8)])
    birrete = redondo(unary_union([board, cap]), .6)
    laptop = redondo(unary_union([box(-34, -4, -17, 8), Polygon([(-36, -9), (-15, -9), (-17, -4), (-34, -4)])]), .6)
    srv1, srv2 = redondo(box(18, -12, 28, 8), .6), redondo(box(30, -8, 36, 2), .6)
    gcs = ((-6, -20), (11, -17), (-24, -21)); gpar = ((9, 7, 7, 18, 28), (6.5, 5, 6, 22, 34), (6, 4.6, 6, 22, 34)); hubr = (2.9, 2.3, 2.2)
    gears = [affinity.translate(engranaje(*gp, .3), *c) for gp, c in zip(gpar, gcs)]
    rot = lambda g: affinity.translate(affinity.rotate(g, 25, origin=(0, 0)), 17, -28)
    scroll = rot(redondo(box(-10, -3.75, 10, 3.75), 2.2))
    # detalles grabados (TRAZOS) y rellenos (GRABAR) de cada pieza
    det_b = [LineString([(0, 13), (15, 11), (15, 4)]), Point(15, 3.1).buffer(1.0).exterior, LineString([(-8, 7.4), (0, 4.4), (8, 7.4)])]
    teclas = [LineString([(x, y), (x + 1.5, y)]) for y, x0 in ((-5.8, -33.2), (-7.3, -34.4)) for x in np.arange(x0, -16.5 - (0 if y == -5.8 else 0), 2.3) if x + 1.5 < (-17.2 if y == -5.8 else -15.8)]
    det_l = [LineString([(-36, -4.2), (-15.4, -4.2)]), LineString([(-31, -8.4), (-21, -8.4)])] + teclas
    det_s1 = [LineString([(18.9, y), (27.1, y)]) for y in (-10.9,)] + [Point(23, 6.8).buffer(.4, 8).exterior]
    det_s2 = [LineString([(31.2, y), (34.8, y)]) for y in (-4.8, -1.8, .6)] + [Point(33, -6.6).buffer(.5).exterior]
    det_r = [rot(LineString([(-5.8, yy), (-3.0, yy)])) for yy in (-1.9, 0, 1.9)] + [rot(LineString([(3.0, yy), (5.8, yy)])) for yy in (-1.9, 0, 1.9)] + \
            [rot(Point(-7.8, 0).buffer(1.5).exterior), rot(Point(7.8, 0).buffer(1.5).exterior)]
    det_g = [Point(c).buffer(h + 1.3).exterior for c, h in zip(gcs, hubr)]
    elems = [("E1-BIRRETE", birrete, det_b), ("E1-LAPTOP", laptop, det_l), ("E1-TORRE1", srv1, det_s1), ("E1-TORRE2", srv2, det_s2), ("E1-DIPLOMA", scroll, det_r)] + \
            [(f"E1-ENGRANAJE{i + 1}", g, [d]) for i, (g, d) in enumerate(zip(gears, det_g))]
    obst = unary_union([e[1] for e in elems]).buffer(.8)
    # C1 base
    P.append(pieza("C1-BASE", gear, capa="C1"))
    # C2 fondo: circuito impreso completo (se ve entre las piezas pegadas)
    lin, rel = pcb(rng, RV - 1, obst)
    P.append(pieza("C2-FONDO", gear, rel, lin + [Point(0, 0).buffer(RV).exterior], capa="C2"))
    # C3 anillo: ventana, texto exterior, remaches en los dientes, marcas
    t_sup, a_sup = arco("INGENIERÍA EN SISTEMAS", FB, 6.0 * k, 56 * k, 90, +1, .5)
    t_inf, a_inf = arco("PROMO 2026", FB, 7.0 * k, 56 * k, 270, -1, .7)
    remaches = [Point(*pol(70.5 * k, i * 22.5)).buffer(1.1 * k, 10) for i in range(16)]
    ticks = [LineString([pol(64.3 * k, a), pol(65.5 * k, a)]) for a in range(0, 360, 3)]
    guias = [Point(0, 0).buffer(r).exterior for r in (49.8 * k, 50.9 * k, 63.6 * k)]
    assert a_sup < 140 and a_inf < 80, (a_sup, a_inf)
    P.append(pieza("C3-ANILLO", gear.difference(Point(0, 0).buffer(RV, 96)), [t_sup, t_inf] + remaches, guias + ticks, capa="C3"))
    # C4 anillo interior elevado con el codigo
    c_cod, a_cod = arco("CÓDIGO, ESFUERZO Y FUTURO", FB, 4.0 * k, 44.5 * k, 270, -1, .25)
    c_p, _ = arco('print("¡Hola Mundo!");', FM, 4.0 * k, 44.5 * k, 128, +1, .3)
    c_w, _ = arco("while(true)", FM, 4.0 * k, 44.5 * k, 40, +1, .3)
    c_b, _ = arco("01101", FM, 4.0 * k, 44.5 * k, -5, +1, .3)
    assert a_cod < 135, a_cod
    P.append(pieza("C4-ANILLO-INT", Point(0, 0).buffer(48.6 * k, 96).difference(Point(0, 0).buffer(41.2 * k, 96)), [c_cod, c_p, c_w, c_b], [], capa="C4"))
    # E1 elementos pegados sobre C2
    for nm, g, d in elems: P.append(pieza(nm, g, [], d, capa="E1"))
    # E2 segundo nivel
    tap = redondo(board.buffer(-1.0), .5)
    P.append(pieza("E2-BIRRETE-TAPA", tap, [], [LineString([(0, 5.8), (0, 20)])], capa="E2"))
    P.append(pieza("E2-PANTALLA", redondo(box(-32.2, -2.2, -18.8, 6.2), .4), [texto_recto("</>", FM, 2.4, -25.5, 3.6)],
                   [LineString([(-31, 0.9), (-31 + w, 0.9 - dy)]) for w, dy in ((9, 0), (6, 1.4))], capa="E2"))
    pan = redondo(box(19, -10.6, 27, 6.6), .4)
    bay = [box(19.8, y, 26.2, y + 2.2).exterior for y in (2.6, -.2, -3.0)]
    P.append(pieza("E2-PANEL-TORRE", pan, [Point(25.3, y + 1.1).buffer(.4, 8) for y in (2.6, -.2, -3.0)],
                   bay + [LineString([(20, y), (26, y)]) for y in (-5.6, -6.6, -7.6)] + [Point(23, -9.4).buffer(.8).exterior], capa="E2"))
    for i, (c, h) in enumerate(zip(gcs, hubr)): P.append(pieza(f"E2-CUBO{i + 1}", Point(c).buffer(h, 24), [], [affinity.translate(LineString([(-h + .6, 0), (h - .6, 0)]), *c), affinity.translate(LineString([(0, -h + .6), (0, h - .6)]), *c)], capa="E2"))
    P.append(pieza("E2-CINTA", rot(redondo(box(-1.8, -3.75, 1.8, 3.75), .3)), [], [], capa="E2"))
    # E3 laureles: una pieza por rama, se pegan sobre C3
    lc, lv = laurel(205, 160)
    P.append(pieza("E3-LAUREL-I", lc, [], lv, capa="E3"))
    P.append(pieza("E3-LAUREL-D", affinity.scale(lc, -1, 1, origin=(0, 0)), [], [affinity.scale(v, -1, 1, origin=(0, 0)) for v in lv], capa="E3"))
    # E4 remate
    P.append(pieza("E4-BOTON", Point(0, 13).buffer(2.3, 24), [], [Point(0, 13).buffer(1.1).exterior], capa="E4"))
    # comprobaciones
    for p in P:
        if p["capa"] in ("E1", "E2", "E4"): assert max(math.hypot(x, y) for x, y in p["corte"].exterior.coords) <= RV - 1.5, f"{p['nombre']} se sale de la ventana"
    e1 = [p for p in P if p["capa"] == "E1"]; e1u = unary_union([p["corte"] for p in e1]).buffer(.05)
    for i in range(len(e1)):
        for j in range(i + 1, len(e1)): assert e1[i]["corte"].distance(e1[j]["corte"]) >= 1.5, f"{e1[i]['nombre']} y {e1[j]['nombre']} muy juntas"
    for p in P:
        if p["capa"] in ("E2", "E4"): assert e1u.union(tap.buffer(.05)).contains(p["corte"]), f"{p['nombre']} no apoya sobre una pieza E1"
    lau = lc; assert max(math.hypot(x, y) for x, y in lau.exterior.coords) < 63.6 * k and Point(0, 0).distance(lau) > 49.2 * k, "laurel fuera del aro"
    for p in P:
        if p["capa"] not in ("C1", "C2", "C3", "C4"):
            g = p["corte"]; fino = g.difference(g.buffer(-1.0).buffer(1.0)).buffer(-.15)
            if sum(z.area for z in getattr(fino, "geoms", [fino])) > 1.0: print(f"AVISO: {p['nombre']} tiene zonas de menos de 2 mm")
    print(f"texto: sup {a_sup:.0f} deg | inf {a_inf:.0f} deg | codigo {a_cod:.0f} deg; ventana r={RV:.0f} mm; pila 5 capas = {5 * A.esp:.0f} mm")
    return P


def acomodar(P):
    """Posiciones en la cama: tres engranajes en fila, grupos E1/E2/E4 debajo (misma disposicion que armados), laureles y anillo interior al lado."""
    d = 2 * RO; y1 = A.cama[1] - d / 2 - 12; gap = 12; y2 = y1 - d / 2 - 5 - RV
    pos = {"C1": (d / 2 + 12, y1), "C2": (1.5 * d + 12 + gap, y1), "C3": (2.5 * d + 12 + 2 * gap, y1), "E1": (d / 2 + 12, y2), "E2": (1.5 * d + 12 + gap, y2), "E4": (1.5 * d + 12 + gap, y2), "C4": (A.cama[0] - 48.6 * k - 12, y2)}
    x = 2.5 * d + 12 + 2 * gap - 40
    for p in P:
        if p["capa"] == "E3":
            c = p["corte"].centroid; p["org"] = (x - c.x, y2 - c.y); x += 40
        else: p["org"] = pos[p["capa"]]
    return P


def exportar(P):
    os.makedirs(A.out, exist_ok=True)
    doc = ezdxf.new(units=4); msp = doc.modelspace()
    for nm, col in (("CORTE", 1), ("GRABAR", 5), ("TRAZOS", 4), ("ETIQUETAS", 3)): doc.layers.add(nm, color=col)
    sh = lambda g, o: affinity.translate(g, *o)
    def anillos(g):
        return [r for pg in getattr(g, "geoms", [g]) if pg.geom_type == "Polygon" for r in [pg.exterior, *pg.interiors]]
    for p in P:
        o = p["org"]
        if p["corte"] is not None:
            for r in anillos(sh(p["corte"], o)): msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "CORTE"})
        for g in p["relleno"]:
            for r in anillos(sh(g, o)): msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "GRABAR"})
        for l in p["lineas"]:
            l = sh(l, o)
            for ls in getattr(l, "geoms", [l]): msp.add_lwpolyline(list(ls.coords), dxfattribs={"layer": "TRAZOS"})
        c = sh(p["corte"], o).bounds; msp.add_text(p["nombre"], height=3, dxfattribs={"layer": "ETIQUETAS", "insert": ((c[0] + c[2]) / 2 - 8, c[1] - 6 if p["capa"] in ("E1", "E2", "E3") else (c[1] + c[3]) / 2)})
    doc.saveas(f"{A.out}/placa.dxf")


def parche(g, **kw):
    from matplotlib.path import Path; from matplotlib.patches import PathPatch
    vs, cs = [], []
    for pg in getattr(g, "geoms", [g]):
        if pg.geom_type != "Polygon": continue
        pg = orient(pg, 1.0)
        for r in [pg.exterior, *pg.interiors]:
            c = np.asarray(r.coords); vs += list(c); cs += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(vs, cs), **kw)


def vistas(P):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    MDF, OSC = "#dcb98a", "#5a3920"
    def dib(ax, ps, lw=.7):
        for p in ps:
            if p["corte"] is not None: ax.add_patch(parche(p["corte"], fc=MDF, ec="k", lw=lw))
            for g in p["relleno"]: ax.add_patch(parche(g, fc=OSC, ec="none"))
            for l in p["lineas"]:
                for ls in getattr(l, "geoms", [l]): ax.plot(*ls.xy, color=OSC, lw=.5)
    titulos = {"C1": "C1 - Base (corte)", "C2": "C2 - Fondo con circuito impreso", "C3": "C3 - Anillo con texto y remaches", "C4": "C4 - Anillo interior elevado (sobre C3)", "E1": "E1 - Piezas pegadas sobre C2", "E2": "E2 - Segundo nivel (sobre E1)", "E3": "E3 - Laureles (sobre C3)", "E4": "E4 - Remate (boton de la toca)"}
    fig, axs = plt.subplots(3, 3, figsize=(18, 17))
    for ax, c in zip(axs.flat, titulos):
        dib(ax, [p for p in P if p["capa"] == c]); ax.set_title(titulos[c]); ax.set_aspect("equal"); ax.autoscale(); ax.axis("off")
    ax = axs.flat[8]; ax.axis("off"); ax.set_title("Pila (corte lateral, de atras hacia adelante)")
    e = A.esp; R_ = lambda x0, x1, z: ax.add_patch(plt.Rectangle((x0, z * e), x1 - x0, e, fc=MDF, ec="k"))
    R_(-RO, RO, 0); R_(-RO, RO, 1); R_(-RO, -RV, 2); R_(RV, RO, 2); R_(-36, 36, 2); R_(-41.2, -48.6, 3); R_(41.2, 48.6, 3); R_(-30, 30, 3); R_(-62, -50, 3); R_(50, 62, 3); R_(-3, 3, 4)
    for z, t in ((0, "C1 base"), (1, "C2 fondo (circuito)"), (2, "C3 anillo + E1 piezas (a ras)"), (3, "C4 aro interior, E2, E3 laureles"), (4, "E4 boton (remate)")):
        ax.text(RO + 4, z * e + e / 2, t, va="center", fontsize=8)
    ax.text(0, -e * 1.2, f"{5 * e:.0f} mm de pila total con MDF de {e:.0f} mm", ha="center", fontsize=8)
    ax.set_xlim(-RO - 5, RO + 95); ax.set_ylim(-e * 2, 5 * e + 4); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(f"{A.out}/vista_capas.png", dpi=80); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 9)); ax.set_facecolor("#cdb596")
    for c in ("C1", "C2", "C3", "C4", "E1", "E2", "E3", "E4"): dib(ax, [p for p in P if p["capa"] == c], lw=.9)
    ax.set_aspect("equal"); ax.set_xlim(-RO - 3, RO + 3); ax.set_ylim(-RO - 3, RO + 3); ax.axis("off")
    ax.set_title(f"Vista superior armada (diam {A.diam:.0f} mm)"); fig.savefig(f"{A.out}/vista_armado.png", dpi=100, bbox_inches="tight"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 8)); ax.set_aspect("equal")
    for p in P:
        g = affinity.translate(p["corte"], *p["org"])
        for pg in getattr(g, "geoms", [g]):
            for r in [pg.exterior, *pg.interiors]: ax.plot(*r.xy, "k", lw=.7)
        for g in p["relleno"]: ax.add_patch(parche(affinity.translate(g, *p["org"]), fc="#3060c0", ec="none"))
        for l in p["lineas"]:
            l = affinity.translate(l, *p["org"])
            for ls in getattr(l, "geoms", [l]): ax.plot(*ls.xy, color="#3060c0", lw=.4)
    ax.set_xlim(0, A.cama[0]); ax.set_ylim(0, A.cama[1]); ax.set_title("Hoja de corte (negro=CORTE, azul=GRABAR/TRAZOS)")
    fig.savefig(f"{A.out}/hoja_corte.png", dpi=90); plt.close(fig)


if __name__ == "__main__":
    P = acomodar(construir()); exportar(P); vistas(P); print("listo en", A.out)
