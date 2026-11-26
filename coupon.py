"""Peine de prueba de kerf: 7 ranuras de (esp-0.3) a (esp+0.3) mm, izq->der. Se prueba con un retazo del MDF real.
Uso: python coupon.py [espesor_mm] [salida.dxf]   (por defecto 5.0)"""
import sys, ezdxf
T = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
OUT = sys.argv[2] if len(sys.argv) > 2 else "coupon_kerf.dxf"
W = [round(T - .3 + .1 * i, 1) for i in range(7)]; PITCH = T + 7; DEPTH = 15; H = 30
doc = ezdxf.new(units=4); msp = doc.modelspace()
x = PITCH; pts = [(0, H)]
for w in W:
    pts += [(x, H), (x, H - DEPTH), (x + w, H - DEPTH), (x + w, H)]; x += PITCH
pts += [(x, H), (x, 0), (0, 0)]
msp.add_lwpolyline(pts, close=True)
doc.saveas(OUT)
e = ezdxf.readfile(OUT).modelspace().query('LWPOLYLINE')[0]
assert e.closed and len(e) == 4 * len(W) + 4
print('ok', W, x, 'x', H, 'mm')
