"""Suzuki Samurai SJ413 en MDF: placas planas con lengüetas/ranuras, desde las medidas del plano (no de una malla).
Móviles: 2 puertas y porton trasero (bisagras de nudillo + pasador), capo (pasadores atras), ruedas (eje de palito de pincho).

Uso: ~/laser-env/bin/python -I samurai_caja.py [--ranura 3.0] [--eje 3.0] [--pasador 1.5] [--out .]
Ejes: X = largo (atras +), Y = ancho, Z = alto. Todo se define en mm reales y se escala con S.
Capas DXF: CORTE (rojo), GRABAR (azul, cara que va hacia afuera), ETIQUETAS (verde, no cortar ni grabar).
"""
import argparse, itertools, os
import numpy as np, ezdxf
from shapely import affinity
from shapely.geometry import Polygon, box, Point, LineString
from shapely.ops import unary_union

ap = argparse.ArgumentParser()
ap.add_argument("--largo", type=float, default=300, help="mm, largo total aprox. (con MDF de 5 mm no bajar de ~270)")
ap.add_argument("--esp", type=float, default=5.0, help="mm, espesor real del MDF")
ap.add_argument("--kerf", type=float, default=0.15, help="mm que quema el laser (ancho de la linea de corte)")
ap.add_argument("--ranura", type=float, default=None, help="mm, ancho DIBUJADO de ranura si ya lo mediste con el peine (si no: esp - kerf)")
ap.add_argument("--eje", type=float, default=3.0, help="mm, palito de pincho de las ruedas")
ap.add_argument("--pasador", type=float, default=1.5, help="mm, alambre/alfiler de bisagras y capo")
ap.add_argument("--cama", type=float, nargs=2, default=[600, 400])
ap.add_argument("--out", default=os.path.expanduser("~/laser/out_caja"))
A = ap.parse_args()

S = A.largo / 3430            # real -> maqueta (el plano dice 3430 mm de largo)
F = A.largo / 300             # factor para medidas de diseno pensadas a 300 mm (el MDF y los pasadores NO escalan)
K = A.kerf
T = A.esp
G = A.largo / (100 * T)         # tamano relativo al material (1.0 = 300 mm con MDF de 3 mm)
U = T / 3.0                     # factor de medidas ligadas al espesor (bisagras, margenes)
R = A.ranura or T - K           # ranura dibujada: tras el corte queda = espesor (ajuste a presion)
hueco = lambda d: (d - K) / 2   # radio DIBUJADO para que el agujero cortado mida d
W = 1530 * S                  # ancho total
BW = W / 2 - T                # cara interior de las placas laterales
TL = T - 0.1                  # largo de lengüeta: queda a ras de la cara exterior
HOLG = 0.2                    # holgura lateral del capo y porton (mas el kerf)
RIM, MARGEN, GAP, TH = max(3.0 * U, 4.0 * F), 2.2 * U, 3.0, max(8.0 * U, 10.0 * F)   # borde sobre cubiertas, alma minima, separacion, alto de lengüeta
RP_FIJO = hueco(A.pasador - .05)   # pasador apretado: no se sale
RP_MOV = hueco(A.pasador + .2)     # pasador suelto: la pieza gira sin juego grande
RB = (3.0 if G >= .8 else 2.6) * U   # radio del nudillo de bisagra
RING = (3.5 if G >= .8 else 2.5) * U  # ancho del pasarueda alrededor del arco
s = lambda pts: [(x * S, z * S) for x, z in pts]
sp = lambda pts: Polygon(s(pts))
redondo = lambda g, r: g.buffer(-r, join_style=1).buffer(r, join_style=1)

# --- perfil lateral (x, z) en mm reales ---
PERFIL = redondo(sp([(3.06 * U / S, 330), (3.06 * U / S, 560), (6.12 * U / S, 560), (6.12 * U / S, 950), (9.62 * U / S, 990), (1000, 1010), (1060, 1040), (1360, 1640),
                     (1400, 1680), (3180, 1680), (3310, 1670), (3330, 1640), (3330, 330)]), 0.8)
ZMIN, ZTECHO = 330 * S, 1680 * S
Z_TECHO_C = ZTECHO - RIM - T / 2           # centro de la cubierta del techo
Z_CAPO_C = 1000 * S - RIM - T / 2          # centro del capo
Z_PCH = 560 * S                            # alto de parachoques
X_GRILLE, X_TRAS = 6.12 * U, 3330 * S        # cara de la parrilla y borde trasero
RUEDAS = [(640 * S, 340 * S), (2670 * S, 340 * S)]; R_RUEDA = 340 * S; R_ARCO = R_RUEDA + (1.5 if G >= .8 else 1.2)
ARCOS = unary_union([Point(c).buffer(R_ARCO, 64) for c in RUEDAS])
ZV = min(1520 if G >= .8 else 1490, (Z_TECHO_C - R / 2 - 3.0 * U) / S)          # tope de ventanas (a escala chica el marco no baja de ~4 mm)
VENT_TRAS = redondo(sp([(2320, 1150), (3060, 1150), (3060, ZV + 10), (2320, ZV + 10)]), 1.0)
PUERTA = sp([(1440, 420), (2230, 420), (2230, 1575), (1700, 1575), (1440, 1150)])
VENT_PUERTA = redondo(sp([(1500, 1150), (2180, 1150), (2180, ZV), (1500 + (ZV - 1150) * .646, ZV)]), 1.0)
BASE = PERFIL.difference(ARCOS).difference(VENT_TRAS)
INT = BASE.difference(PUERTA).buffer(-MARGEN)          # donde puede ir una ranura en la carroceria fija

# bisagras (z del nudillo de la pieza movil; los fijos van arriba y abajo)
XF, YA = 1440 * S, W / 2 + RB + .6             # eje de la puerta: borde delantero, por fuera
Z_BIS_PUERTA = [47.0 * F, 88.0 * F]
Y_PORTON = BW - HOLG                       # borde del porton del lado de la bisagra (+Y, lado derecho)
XA_PORTON = X_TRAS + RB + .6
Z_BIS_PORTON = [62.0 * F, (128.0 if G >= .8 else 118.0) * F]
DZ = T + HOLG                              # paso entre nudillos apilados
XB2 = (1220 if G >= .8 else 1190) * S         # B2 (tapa del compartimento del motor)
X_CAPO1 = XB2 - 7.5 * U                   # fin del capo (detras va B2)
PIN_CAPO = (X_CAPO1 + 2.5 * U, Z_CAPO_C - T / 2 - RB - .5)   # (x, z) pasador del capo
Y_NUD_CAPO = BW - 4.5 * U


def dentro(g, zona=None): return (INT if zona is None else zona).contains(g)


def ranura_h(x0, x1, z): return box(x0, z - R / 2, x1, z + R / 2)    # ranura horizontal para lengüeta de placa horizontal


def costilla(nombre, x, zt, lenguetas=True, zb=ZMIN, th=TH):
    """Costilla (plano YZ, coords y,z) con lengüetas en los extremos; devuelve pieza y ranuras para los lados."""
    zs = []
    if lenguetas:
        ok = [z for z in np.arange(zb + th / 2 + 1, zt - th / 2 - .5, 0.5) if dentro(box(x - R / 2, z - th / 2, x + R / 2, z + th / 2))]
        assert ok, f"{nombre}: no hay donde poner lengüetas"
        zs = [ok[0]] if ok[-1] - ok[0] < th + 6 else [ok[0], ok[-1]]
    g = box(-BW, zb, BW, zt)
    for z in zs: g = g.union(box(BW, z - th / 2, BW + TL, z + th / 2)).union(box(-BW - TL, z - th / 2, -BW, z + th / 2))
    cortes = [box(x - R / 2, z - th / 2, x + R / 2, z + th / 2) for z in zs]
    return dict(nombre=nombre, poly=g, plano="X", pos=x, p3=[("X", x)]), cortes


def techo():
    x0, x1, tl = 1385 * S, X_TRAS - T - 0.2, (14.0 if G >= .8 else 12.0) * U          # termina justo delante del porton: le sirve de tope
    ok = [x for x in np.arange(x0 + tl / 2 + 1, x1 - tl / 2 - 1, 0.5) if dentro(ranura_h(x - tl / 2, x + tl / 2, Z_TECHO_C))]
    xs = [ok[0], ok[len(ok) // 2], ok[-1]]
    g = box(x0, -BW, x1, BW)
    for x in xs: g = g.union(box(x - tl / 2, BW, x + tl / 2, BW + TL)).union(box(x - tl / 2, -BW - TL, x + tl / 2, -BW))
    return dict(nombre="TECHO", poly=g, p3=[("Z", Z_TECHO_C)]), [ranura_h(x - tl / 2, x + tl / 2, Z_TECHO_C) for x in xs]


LETRAS = {"S": [[(.6, .85), (.5, 1), (.1, 1), (0, .85), (0, .6), (.1, .5), (.5, .5), (.6, .4), (.6, .15), (.5, 0), (.1, 0), (0, .15)]],
          "U": [[(0, 1), (0, .15), (.1, 0), (.5, 0), (.6, .15), (.6, 1)]], "Z": [[(0, 1), (.6, 1), (0, 0), (.6, 0)]],
          "K": [[(0, 0), (0, 1)], [(.6, 1), (0, .45)], [(.18, .6), (.6, 0)]], "I": [[(.05, 0), (.05, 1)]]}


def texto(t, cx, z0, h):
    adv = .9 * h; x0 = cx - (len(t) * adv - .3 * h) / 2
    return [LineString([(x0 + i * adv + u * h, z0 + v * h) for u, v in st]) for i, c in enumerate(t) for st in LETRAS[c]]


def lineas(gs):
    out = []
    for g in gs:
        if g.geom_type == "Polygon": out += [LineString(g.exterior.coords)] + [LineString(r.coords) for r in g.interiors]
        elif g.geom_type in ("LineString", "LinearRing"): out.append(LineString(g.coords))
        elif hasattr(g, "geoms"): out += lineas(list(g.geoms))
    return out


def recortar(gs, poly): return [l for l in lineas([g.intersection(poly) for g in lineas(gs)]) if l.length > .2]


def rueda(nombre, r, hueco, grabada):
    g = Point(0, 0).buffer(r, 64)
    if hueco: g = g.difference(Point(0, 0).buffer(hueco / 2, 24))
    gr = []
    if grabada:
        gr = [Point(0, 0).buffer(k * r, 64).exterior for k in (.93, .62, .22)]
        gr += [Point(.36 * r * np.cos(a), .36 * r * np.sin(a)).buffer(.035 * r + .4, 16).exterior for a in np.arange(5) * 2 * np.pi / 5]
    return dict(nombre=nombre, poly=g, grab=recortar(gr, g))


def nudillo(nombre, cuerpo, eje, movil):
    """Plaquita horizontal de bisagra: cuerpo + barril alrededor del eje, con agujero de pasador."""
    g = unary_union(cuerpo + [Point(eje).buffer(RB, 32)]).difference(Point(eje).buffer(RP_MOV if movil else RP_FIJO, 16))
    return dict(nombre=nombre, poly=g)


def armar():
    P = []
    # --- costillas (B3 y B4 quedan detras de la puerta: sin lengüetas, solo trabadas en la quilla) ---
    cs = [costilla("B1", X_GRILLE + T / 2, Z_CAPO_C - T / 2 - .1, th=TH if G >= .8 else 6.0 * U), costilla("B2", XB2, Z_CAPO_C - T / 2 - .5),
          costilla("B3", 1700 * S, 800 * S, False), costilla("B4", 2150 * S, 760 * S, False),
          costilla("B5", (3090 if G >= .8 else 3140) * S, 720 * S), costilla("B6", X_TRAS - 1.5 * T, Z_PCH)]
    te = techo()
    cortes = [c for _, cc in cs for c in cc] + te[1]

    # --- bisagras de puerta: ranuras en puerta (nudillo movil) y carroceria (2 fijos por bisagra) ---
    cortes_puerta = [ranura_h(XF + 3 * U, XF + 8 * U, z) for z in Z_BIS_PUERTA]
    for z in Z_BIS_PUERTA:
        for zz in (z - DZ, z + DZ):
            c = ranura_h(XF - 8 * U, XF - 3 * U, zz); assert dentro(c), "ranura de bisagra de puerta"; cortes.append(c)
    cortes += [Point(PIN_CAPO).buffer(RP_FIJO, 16)]                      # agujero del pasador del capo en los lados
    cortes_porton = []
    for z in Z_BIS_PORTON:
        for zz in (z - DZ, z + DZ):
            c = ranura_h(X_TRAS - 9.2 * U, X_TRAS - 4.2 * U, zz); assert dentro(c), "ranura de bisagra del porton"; cortes_porton.append(c)

    lado_i = BASE.difference(VENT_PUERTA)
    for c in cortes + cortes_puerta: lado_i = lado_i.difference(c)
    lado_d = lado_i
    for c in cortes_porton: lado_d = lado_d.difference(c)            # el porton cuelga del lado derecho
    puerta = PUERTA.intersection(lado_i)
    for g in (lado_i, lado_d, puerta, lado_i.difference(PUERTA)): assert g.geom_type == "Polygon", "lado partido"
    assert PUERTA.buffer(-MARGEN).contains(unary_union(cortes_puerta)), "ranura de bisagra muy al borde de la puerta"

    # grabado lateral (se recorta a la placa; cruza la linea de la puerta sin problema)
    gl = [LineString(s([(110, 1060), (3330, 1060)])), LineString(s([(1400, 1650), (3180, 1650)]))]
    gl += [Point(c).buffer(R_ARCO + RING, 64).exterior for c in RUEDAS]                         # guardabarros
    gl += [sp([(150, 700), (260, 700), (260, 760), (150, 760)]), Point(2850 * S, 1000 * S).buffer(45 * S, 32),  # cocuyo, tapa gasolina
           sp([(3260, 620), (3315, 620), (3315, 900), (3260, 900)]), sp([(2070, 1080), (2160, 1080), (2160, 1105), (2070, 1105)])]  # stop, manija
    yl = W / 2 - T / 2
    P.append(dict(nombre="LADO-I", poly=lado_i, hijos=[("PUERTA-I", puerta)], grab=recortar(gl, lado_i), p3=[("Y", -yl)], g3=lado_i))
    P.append(dict(nombre="LADO-D", poly=lado_d, hijos=[("PUERTA-D", puerta)], grab=recortar(gl, lado_d), p3=[("Y", yl)], g3=lado_d, espejo=True))

    P += [c[0] for c in cs] + [te[0]]
    P.append(dict(nombre="QUILLA", poly=box(150 * S, RUEDAS[0][1] + A.eje / 2 + 1.7, 3200 * S, 700 * S), plano="Y", pos=0.0, p3=[("Y", 0)]))  # alta: el eje pasa por debajo

    # --- frente SJ413 (segun el plano): franja de parrilla a todo lo ancho; faros redondos en marco cuadrado;
    #     7 ranuras verticales redondeadas CORTADAS al centro; SUZUKI encima; direccionales en las puntas del parachoques
    b1 = P[2]; assert b1["nombre"] == "B1"
    ZG0, ZG1, YG = 54.0 * F, 74.0 * F, 34.5 * F         # franja de parrilla (z) y borde interior de los marcos de faro
    N = 7 if G >= .8 else 5                              # a escala chica: menos ranuras para que no queden mas finas que ~4 mm
    paso = 2 * (YG - 1.5 * F) / N; ancho = paso - 3.4 * U    # barras de 3.4 mm: no se quiebran
    for i in range(N):
        y = -(YG - 1.5 * F) + paso * (i + .5)
        b1["poly"] = b1["poly"].difference(LineString([(y, ZG0 + 2 * F + ancho / 2), (y, ZG1 - 2 * F - ancho / 2)]).buffer(ancho / 2, 16))
    gf = [box(-61 * F, ZG0, 61 * F, ZG1)]                                                 # contorno de la franja
    gf += [redondo(box(sg * YG, ZG0 + F, sg * 60 * F, ZG1 - F), 1.0) for sg in (-1, 1)]   # marcos cuadrados
    gf += [Point(sg * 47.2 * F, (ZG0 + ZG1) / 2).buffer(r * F, 48).exterior for sg in (-1, 1) for r in (8.0, 6.3)]   # faros
    gf += texto("SUZUKI", 0, ZG1 + 1.6 * F, 3.2 * F)
    b1["grab"] = recortar(gf, b1["poly"])
    pch = box(-BW, ZMIN, BW, Z_PCH)
    gp = [box(-14 * F, 35 * F, 14 * F, 43 * F)] + [box(sg * 46 * F, 39 * F, sg * 60 * F, 45 * F) for sg in (-1, 1)] + [LineString([(-BW, 47 * F), (BW, 47 * F)])]
    P.append(dict(nombre="PARACHOQUES", poly=pch, grab=recortar(gp, pch), p3=[("X", X_GRILLE - T / 2)]))
    P.append(dict(nombre="PARACHOQ-T", poly=pch, grab=recortar([box(-14 * F, 35 * F, 14 * F, 43 * F)], pch), p3=[("X", X_TRAS - T / 2)]))

    # --- capo movil: sin lengüetas, apoya en B1, gira sobre 2 pasadores cortos atras ---
    capo = box(X_GRILLE, -(BW - HOLG), X_CAPO1, BW - HOLG)
    for sg in (-1, 1): capo = capo.difference(box(X_CAPO1 - 7.5 * U - .1, sg * Y_NUD_CAPO - R / 2, X_CAPO1 - 2.5 * U + .1, sg * Y_NUD_CAPO + R / 2))
    P.append(dict(nombre="CAPO", poly=capo, grab=recortar([LineString([(12 * F, y * F), (X_CAPO1 - 9, y * F)]) for y in (-22, 22)], capo), p3=[("Z", Z_CAPO_C)]))
    zc0, zc1 = Z_CAPO_C - T / 2, Z_CAPO_C + T / 2
    for i in (1, 2):
        P.append(nudillo(f"BIS-CAPO{i}", [box(X_CAPO1 - 7.5 * U, zc0, X_CAPO1 - 2.5 * U, zc1 - .1), box(X_CAPO1 - 7.5 * U, PIN_CAPO[1] - RB, PIN_CAPO[0], zc0)], PIN_CAPO, True))

    # --- porton trasero movil (bisagra al lado derecho) ---
    porton = redondo(box(-Y_PORTON, Z_PCH + HOLG, Y_PORTON, Z_TECHO_C + T / 2 - .5), .8).difference(redondo(box(-42 * F, 112 * F, 42 * F, 132 * F), 1.5))
    for z in Z_BIS_PORTON: porton = porton.difference(ranura_h(Y_PORTON - 8 * U, Y_PORTON - 3 * U, z))
    P.append(dict(nombre="PORTON", poly=porton, grab=recortar([box(-48 * F, 95 * F, -38 * F, 99 * F)], porton), p3=[("X", X_TRAS - T / 2)]))
    eje_p = (XA_PORTON, Y_PORTON)
    for i, z in enumerate(Z_BIS_PORTON, 1):
        P.append(nudillo(f"BIS-PORT{i}", [box(X_TRAS - T + .1, Y_PORTON - 8 * U, X_TRAS, Y_PORTON - 3 * U), box(X_TRAS, Y_PORTON - 8 * U, XA_PORTON, Y_PORTON)], eje_p, True))
        for k in "ab":
            P.append(nudillo(f"BIS-PORT{i}{k}", [box(X_TRAS - 9.2 * U, BW + .1, X_TRAS - 4.2 * U, W / 2), box(X_TRAS - 9.2 * U, W / 2, eje_p[0] + RB, W / 2 + RB + .6),
                                                 box(X_TRAS + .2, Y_PORTON, eje_p[0] + RB, W / 2 + RB + .6)], eje_p, False))
    # --- bisagras de puertas: por puerta 2 nudillos moviles + 4 fijos ---
    for lado in "ID":
        for i in (1, 2):
            P.append(nudillo(f"BIS-P{lado}{i}", [box(XF + 3 * U, BW + .1, XF + 8 * U, W / 2), box(XF, W / 2, XF + 8 * U, YA)], (XF, YA), True))
            for k in "ab":
                P.append(nudillo(f"BIS-P{lado}{i}{k}", [box(XF - 8 * U, BW + .1, XF - 3 * U, W / 2), box(XF - 8 * U, W / 2, XF, YA)], (XF, YA), False))

    # --- ruedas que giran: pasarueda interno con agujero holgado, 2 discos por rueda pegados al eje ---
    for i in range(4):
        pr = Point(0, 0).buffer(R_ARCO + RING, 64).intersection(box(-99, 22 * F - RUEDAS[0][1], 99, 99)).difference(Point(0, 0).buffer(hueco(A.eje + .25), 24))
        P.append(dict(nombre=f"PASARUEDA{i+1}", poly=pr))
        P.append(rueda(f"RUEDA{i+1}A", R_RUEDA, 2 * hueco(A.eje - .05), False))
        P.append(rueda(f"RUEDA{i+1}B", R_RUEDA, 2 * hueco(A.eje - .05), True))
    P.append(rueda("REPUESTO1", 325 * S, 0, False)); P.append(rueda("REPUESTO2", 325 * S, 0, True))
    return P


def media_madera(P):
    """Medios cortes entre la quilla (Y=0) y las costillas que la cruzan; ranuras abiertas al borde."""
    n = 0; q = next(p for p in P if p["nombre"] == "QUILLA")
    for b in [p for p in P if p.get("plano") == "X"]:
        gq = q["poly"].intersection(LineString([(b["pos"], -1e4), (b["pos"], 1e4)]))
        gb = b["poly"].intersection(LineString([(0, -1e4), (0, 1e4)]))
        if gq.is_empty or gb.is_empty: continue
        (_, q0, _, q1), (_, b0, _, b1) = gq.bounds, gb.bounds; lo, hi = max(q0, b0), min(q1, b1); mid = (lo + hi) / 2
        assert hi - lo > 2 * R and q1 <= b1 + 1e-6 and b0 <= q0 + 1e-6, f"{b['nombre']}: roles de media madera"
        q["poly"] = q["poly"].difference(box(b["pos"] - R / 2, mid, b["pos"] + R / 2, hi + 200))       # quilla: desde arriba
        b["poly"] = b["poly"].difference(box(-R / 2, lo - 200, R / 2, mid)); n += 1                    # costilla: desde abajo
    return n


def transformar(p, f):
    q = dict(p, poly=f(p["poly"]), grab=[f(g) for g in p.get("grab", [])])
    q["hijos"] = [(n, f(g)) for n, g in p.get("hijos", [])]
    return q


def acomodar(ps, paso=2.0):
    """Abajo-izquierda con contornos reales (aprovecha huecos), probando 0 y 90 grados."""
    W_, H_ = A.cama; hojas, pend = [], sorted(ps, key=lambda p: -p["poly"].area)
    while pend:
        cajas, ocup, hoja, resto = np.empty((0, 4)), [], [], []
        for p in pend:
            mejor = None
            for ang in (0, 90):
                g = affinity.rotate(p["poly"], ang, origin=(0, 0)); x0, y0, x1, y1 = g.bounds; w, h = x1 - x0, y1 - y0
                gb = g.buffer(GAP / 2, 4); hallado = False
                for y in np.arange(5, H_ - 5 - h, paso):
                    if mejor and y > mejor[0][0]: break
                    for x in np.arange(5, W_ - 5 - w, paso):
                        c = np.array([x - GAP, y - GAP, x + w + GAP, y + h + GAP])
                        sel = np.where((cajas[:, 0] < c[2]) & (c[0] < cajas[:, 2]) & (cajas[:, 1] < c[3]) & (c[1] < cajas[:, 3]))[0]
                        if len(sel):
                            gt = affinity.translate(gb, x - x0, y - y0)
                            if any(ocup[i].intersects(gt) for i in sel): continue
                        if mejor is None or (y, x) < mejor[0]: mejor = ((y, x), ang, x - x0, y - y0, (x, y, x + w, y + h))
                        hallado = True; break
                    if hallado: break
            if mejor is None: resto.append(p); continue
            _, ang, dx, dy, c = mejor
            q = transformar(p, lambda g, a=ang, dx=dx, dy=dy: affinity.translate(affinity.rotate(g, a, origin=(0, 0)), dx, dy))
            cajas = np.vstack([cajas, c]); ocup.append(q["poly"].buffer(GAP / 2, 4)); hoja.append(q)
        assert hoja, f"{resto[0]['nombre']} no cabe en la cama"
        hojas.append(hoja); pend = resto
    return hojas


def exportar(hojas):
    os.makedirs(A.out, exist_ok=True)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    for n, h in enumerate(hojas, 1):
        doc = ezdxf.new(units=4); msp = doc.modelspace()
        for nom, col in (("CORTE", 1), ("GRABAR", 5), ("ETIQUETAS", 3)): doc.layers.add(nom, color=col)
        fig, ax = plt.subplots(figsize=(12, 8))
        def cortar(ring): msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "CORTE"}); ax.plot(*ring.xy, "k", lw=.6)
        def etiqueta(nom, g):
            c = g.representative_point(); msp.add_text(nom, height=3, dxfattribs={"layer": "ETIQUETAS", "insert": (c.x, c.y)})
            ax.text(c.x, c.y, nom, fontsize=5, color="g", ha="center")
        for p in h:
            for r in [p["poly"].exterior, *p["poly"].interiors]: cortar(r)
            for nom, g in p["hijos"]: cortar(g.exterior); etiqueta(nom, g)        # linea compartida: se corta una sola vez
            for l in p["grab"]: msp.add_lwpolyline(list(l.coords), dxfattribs={"layer": "GRABAR"}); ax.plot(*l.xy, "b", lw=.4)
            etiqueta(p["nombre"], p["poly"].difference(unary_union([g for _, g in p.get("hijos", [])])) if p["hijos"] else p["poly"])
        ax.set_xlim(0, A.cama[0]); ax.set_ylim(0, A.cama[1]); ax.set_aspect("equal"); ax.set_title(f"Hoja {n}  (negro=corte, azul=grabado)")
        fig.savefig(f"{A.out}/hoja{n}.png", dpi=110); plt.close(fig); doc.saveas(f"{A.out}/hoja{n}.dxf")
    return len(hojas)


def detalle(P):
    """Vistas lateral, frontal y trasera del carro armado, para revisar el realismo."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    pz = {p["nombre"]: p for p in P}
    fig, axs = plt.subplots(1, 3, figsize=(16, 5), gridspec_kw={"width_ratios": [3, 1.3, 1.3]})
    def dib(ax, g, c="k", lw=.8):
        for l in lineas([g]): ax.plot(*l.xy, c, lw=lw)
    ax = axs[0]; dib(ax, pz["LADO-I"]["poly"]); dib(ax, PUERTA.exterior, "k", .6)
    for l in pz["LADO-I"]["grab"]: dib(ax, l, "b", .5)
    for c in RUEDAS:
        rb = pz["RUEDA1B"]; dib(ax, affinity.translate(rb["poly"], *c), "k", 1)
        for l in rb["grab"]: dib(ax, affinity.translate(l, *c), "b", .5)
    ax.set_title("Lado"); ax.set_aspect("equal")
    ax = axs[1]
    for p, dz in (("B1", 0), ("PARACHOQUES", 0)):
        dib(ax, pz[p]["poly"]); [dib(ax, l, "b", .5) for l in pz[p].get("grab", [])]
    for sg in (-1, 1):
        dib(ax, box(sg * BW, ZMIN, sg * W / 2, 1000 * S)); dib(ax, box(sg * W / 2, 0, sg * (W / 2 + 2 * T), 2 * R_RUEDA))
    dib(ax, box(-(BW - HOLG), Z_CAPO_C - T / 2, BW - HOLG, Z_CAPO_C + T / 2)); ax.set_title("Frente"); ax.set_aspect("equal")
    ax = axs[2]; dib(ax, pz["PORTON"]["poly"]); [dib(ax, l, "b", .5) for l in pz["PORTON"]["grab"]]
    dib(ax, pz["PARACHOQ-T"]["poly"]); [dib(ax, l, "b", .5) for l in pz["PARACHOQ-T"]["grab"]]
    rp = pz["REPUESTO2"]; dib(ax, affinity.translate(rp["poly"], 0, 83 * F)); [dib(ax, affinity.translate(l, 0, 83 * F), "b", .5) for l in rp["grab"]]
    for sg in (-1, 1): dib(ax, box(sg * BW, ZMIN, sg * W / 2, 1640 * S)); dib(ax, box(sg * W / 2, 0, sg * (W / 2 + 2 * T), 2 * R_RUEDA))
    dib(ax, Point(XA_PORTON - X_TRAS + Y_PORTON, 62).buffer(.1)); ax.set_title("Atras"); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(f"{A.out}/detalle.png", dpi=110); plt.close(fig)


def vista3d(P):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    m = {"X": lambda v, a, b: (v, a, b), "Y": lambda v, a, b: (a, v, b), "Z": lambda v, a, b: (a, b, v)}
    fig = plt.figure(figsize=(12, 7)); ax = fig.add_subplot(111, projection="3d")
    for p in P:
        for k, v in p.get("p3", []):
            g = p.get("g3", p["poly"])
            ax.add_collection3d(Poly3DCollection([[m[k](v, *c) for c in g.exterior.coords]], facecolor="peru", edgecolor="k", alpha=.45, lw=.3))
            for r in g.interiors: ax.plot(*zip(*[m[k](v, *c) for c in r.coords]), "k", lw=.4)
            for l in p.get("grab", []) if not p.get("espejo") else lineas([]):
                ax.plot(*zip(*[m[k](v, *c) for c in l.coords]), "b", lw=.4)
    for sg in (-1, 1):
        for cx, cz in RUEDAS:
            t = np.linspace(0, 2 * np.pi, 40)
            ax.add_collection3d(Poly3DCollection([[(cx + R_RUEDA * np.cos(a), sg * (W / 2 + 1.5 * T), cz + R_RUEDA * np.sin(a)) for a in t]], facecolor="k", alpha=.6))
    ax.set_xlim(0, 300); ax.set_ylim(-110, 110); ax.set_zlim(0, 220); ax.set_box_aspect((300, 220, 220)); ax.view_init(18, -55)
    fig.savefig(f"{A.out}/ensamble.png", dpi=100); plt.close(fig)


def demo(P, hojas, nhalf):    # P tiene las piezas sin acomodar
    for p in P: assert p["poly"].geom_type == "Polygon" and p["poly"].is_valid, p["nombre"]
    assert nhalf == 4, nhalf                                 # B2..B5 cruzan la quilla
    assert YA - W / 2 > RB + .1 and XA_PORTON - X_TRAS > RB + .1, "la pieza movil roza el barril de la bisagra"
    assert PIN_CAPO[1] + RB < Z_CAPO_C - T / 2, "nudillo del capo choca con el capo"
    for p in P:
        if p.get("plano") == "X":
            for cx, _ in RUEDAS: assert abs(p["pos"] - cx) - T / 2 >= R_ARCO + RING - .2, f"{p['nombre']} choca con el pasarueda"
    for p in P:
        if p["nombre"].startswith(("LADO", "B", "CAPO", "PORTON", "PUERTA")) and not p["nombre"].startswith("BIS"):
            polys = [p["poly"]] + [g for _, g in p.get("hijos", [])]
            for g in polys:
                fino = g.difference(g.buffer(-1.1 * U).buffer(1.1 * U)).buffer(-.2)
                for z in getattr(fino, "geoms", [fino]):
                    if z.area > .3: print(f"AVISO: {p['nombre']} zona fina (<2.2 mm) cerca de x={z.centroid.x:.1f} z={z.centroid.y:.1f}")
    assert PIN_CAPO[0] + RB < XB2 - T / 2, "nudillo del capo choca con B2"
    for h in hojas:
        gs = [p["poly"] for p in h]
        for g in gs: assert box(0, 0, *A.cama).contains(g)
        for g1, g2 in itertools.combinations(gs, 2): assert not g1.intersects(g2)


if __name__ == "__main__":
    P = armar(); nh = media_madera(P)
    corte = [transformar(p, lambda g: affinity.scale(g, -1, 1, origin=(0, 0))) if p.get("espejo") else p for p in P]  # LADO-D en espejo: grabado afuera
    hojas = acomodar(corte)
    print(f"{len(P)} piezas (+2 puertas dentro de los lados) | ancho {W:.1f} | {nh} medias maderas | ranura {R} eje {A.eje} pasador {A.pasador}")
    demo(P, hojas, nh); print("chequeos OK")
    print(f"{exportar(hojas)} hoja(s) en {A.out}"); detalle(P); vista3d(P)
