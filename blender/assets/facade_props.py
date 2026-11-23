"""Prop kit for the facade asset: furniture, fixtures, bakery goods and shop products as real shapes.

Every function appends geometry to a facade MB (mesh builder) in asset space, so props merge into a few objects
(one draw per material) and stay instancing-friendly.  Shapes are built with bmesh (bevelled boxes, lathes,
deformed spheres, swept tubes) so silhouettes read as manufactured / baked objects instead of boxes.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector


# ----------------------------------------------------------------------------- low level
def emit(mb, bm, m, cell=(0.0, 0.0, 0.0), M=None):
    bm.verts.index_update()
    base = len(mb.v)
    for v in bm.verts:
        mb.add_v(M @ v.co if M is not None else v.co)
    for f in bm.faces:
        mb.face([base + v.index for v in f.verts], m, cell)
    bm.free()


def xform(loc, rz=0.0, rx=0.0, ry=0.0):
    return Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')


def rbox(mb, c, size, r, m, cell=(0, 0, 0), seg=3, rz=0.0, rx=0.0):
    """Box centred at c with full size (sx, sy, sz), edges rounded with radius r."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    r = min(r, 0.49 * min(size))
    if r > 1e-5:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=r, segments=seg, affect='EDGES', profile=0.5)
    emit(mb, bm, m, cell, xform(c, rz, rx))


def lathe(mb, c, prof, m, cell=(0, 0, 0), seg=20, sx=1.0, sy=1.0, rfun=None, M=None):
    """Surface of revolution around local Z. prof: [(r, z)] bottom->top; r == 0 ends are closed with a pole.
    rfun(theta, z) -> radius multiplier (crimps, flutes)."""
    bm = bmesh.new()
    rings = []
    for (r, z) in prof:
        if r <= 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            rr = r * (rfun(t, z) if rfun else 1.0)
            ring.append(bm.verts.new((math.cos(t) * rr * sx, math.sin(t) * rr * sy, z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for k in range(seg):
                bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
        elif len(b) == 1:
            for k in range(seg):
                bm.faces.new((a[k], b[0], a[(k + 1) % seg]))
        else:
            for k in range(seg):
                bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    emit(mb, bm, m, cell, (M if M is not None else Matrix.Translation(Vector(c))))


def blob(mb, c, radii, m, cell=(0, 0, 0), seg=18, rings=10, deform=None, M=None):
    """Deformed ellipsoid. deform(x, y, z) on the unit sphere returns a radial multiplier or a Vector offset."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        p = Vector((x * radii[0], y * radii[1], z * radii[2]))
        if deform:
            d = deform(x, y, z)
            if isinstance(d, Vector):
                p = p + d
            else:
                p = Vector((p.x * d, p.y * d, p.z * d))
        v.co = p
    emit(mb, bm, m, cell, M if M is not None else Matrix.Translation(Vector(c)))


def sweep(mb, pts, rad, m, cell=(0, 0, 0), seg=10, flat=1.0, M=None):
    """Tube along pts with per-point radius list rad (tapered ends close to a point)."""
    bm = bmesh.new()
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        p = Vector(p)
        t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        nx = t.cross(up).normalized()
        ny = nx.cross(t).normalized()
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new(p + nx * math.cos(a) * rad[i] + ny * math.sin(a) * rad[i] * flat))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    emit(mb, bm, m, cell, M)


def leg(mb, p0, p1, r, m, seg=8):
    mb.rod(p0, p1, r, m, seg=seg)


# ----------------------------------------------------------------------------- bakery goods
def _score(x, y, z, lines, depth=0.10, width=0.10):
    """Radial multiplier with blade scores: lines = [(angle, offset)] in the xy plane, only on the top."""
    if z < 0.15:
        return 1.0
    d = 0.0
    for ang, off in lines:
        dist = abs(-math.sin(ang) * x + math.cos(ang) * y - off)
        d = max(d, math.exp(-(dist / width) ** 2) * min(1.0, (z - 0.15) * 3))
    return 1.0 - depth * d


def _flat_bottom(z, k=0.35):
    return 1.0 if z > -k else (1.0 - (abs(z) - k) * 0.9)


def boule(mb, c, r, m, R, cell):
    kind = R.random()
    lines = [(0.0, 0.0), (math.pi / 2, 0.0)] if kind < 0.5 else [(0.4 + R.uniform(-0.2, 0.2), o) for o in (-0.35, 0.0, 0.35)]
    def d(x, y, z):
        return _score(x, y, z, lines, 0.10, 0.09) * _flat_bottom(z) * (1 + 0.025 * math.sin(7 * x + 5 * y))
    blob(mb, c, (r, r * R.uniform(0.92, 1.05), r * R.uniform(0.55, 0.68)), m, cell, seg=24, rings=14, deform=d,
         M=xform(c, R.uniform(0, 6.28)))


def batard(mb, c, L, m, R, cell, rz=0.0):
    lines = [(0.35, o) for o in (-0.5, -0.15, 0.2, 0.55)]
    def d(x, y, z):
        return _score(x, y, z, [(a, o) for a, o in lines], 0.08, 0.07) * _flat_bottom(z)
    blob(mb, c, (L / 2, L * 0.24, L * 0.17), m, cell, seg=24, rings=12, deform=d, M=xform(c, rz))


def baguette(mb, c, L, m, R, cell, rz=0.0, rx=0.0, ry=0.0):
    nsc = R.randint(5, 7)
    def d(x, y, z):
        # diagonal "grigne" cuts along the length; slight banana bend
        if z < 0.2:
            s = 1.0
        else:
            ph = (x * 0.5 + 0.5) * nsc + y * 0.25
            fr = ph - math.floor(ph)
            s = 1.0 - 0.12 * math.exp(-((fr - 0.5) / 0.08) ** 2) * (abs(x) < 0.92)
        return s * _flat_bottom(z, 0.5)
    blob(mb, c, (L / 2, 0.032, 0.026), m, cell, seg=28, rings=10, deform=d, M=xform(c, rz, rx, ry))


def roll(mb, c, r, m, R, cell):
    blob(mb, c, (r, r * 0.95, r * 0.62), m, cell, seg=14, rings=9,
         deform=lambda x, y, z: _score(x, y, z, [(R.uniform(0, 3), 0.0)], 0.12, 0.12) * _flat_bottom(z), M=xform(c, R.uniform(0, 6.28)))


def croissant(mb, c, s, m, R, cell, rz=0.0):
    pts, rad = [], []
    n = 17
    for i in range(n):
        t = -1 + 2 * i / (n - 1)
        a = t * 1.15
        pts.append((math.sin(a) * 0.055 * s, -math.cos(a) * 0.055 * s + 0.04 * s, 0.0))
        base = 0.026 * s * (1 - 0.78 * abs(t) ** 1.6)
        rad.append(base * (1 + 0.12 * math.cos(t * math.pi * 3.5)))   # rolled layers
    M = xform(c, rz) @ Matrix.Translation((0, 0, 0.02 * s))
    sweep(mb, pts, rad, m, cell, seg=12, flat=0.72, M=M)


def disc(mb, c, r, h, m, cell, seg=20, dome=0.3, rfun=None):
    prof = [(0.0, 0.0), (r * 0.96, 0.0), (r, h * 0.35), (r * 0.95, h * 0.85), (r * 0.6, h * (1 + dome * 0.5)), (0.0, h * (1 + dome))]
    lathe(mb, c, prof, m, cell, seg=seg, rfun=rfun)


def cinnamon_roll(mb, c, r, m, R, cell):
    def rf(t, z):
        return 1.0 + 0.05 * math.sin(t * 1.0 + z * 40)
    disc(mb, c, r, r * 0.55, m, cell, seg=24, dome=0.15, rfun=rf)


def danish(mb, c, r, m, mfill, R, cell):
    disc(mb, c, r, r * 0.35, m, cell, seg=20, dome=-0.3, rfun=lambda t, z: 1 + 0.07 * math.cos(4 * t))
    blob(mb, (c[0], c[1], c[2] + r * 0.32), (r * 0.42, r * 0.42, r * 0.12), mfill, cell, seg=12, rings=6)


def muffin(mb, c, r, m_cup, m_top, R, cell):
    lathe(mb, c, [(0.0, 0.0), (r * 0.78, 0.0), (r * 0.98, r * 0.95), (r * 1.0, r * 1.0)], m_cup, cell, seg=24,
          rfun=lambda t, z: 1 + 0.03 * math.cos(24 * t))
    blob(mb, (c[0], c[1], c[2] + r * 0.95), (r * 1.18, r * 1.18, r * 0.75), m_top, cell, seg=16, rings=10,
         deform=lambda x, y, z: (1 + 0.06 * math.sin(9 * x) * math.sin(8 * y)) if z > -0.1 else 0.3)


def donut(mb, c, r, m, m_glaze, cell):
    rr = r * 0.42
    prof = []
    for i in range(13):
        a = -math.pi / 2 + math.pi * 2 * i / 12
        prof.append((r - rr + math.cos(a) * rr, rr + math.sin(a) * rr * 0.8))
    lathe(mb, c, prof, m, cell, seg=24)
    gl = [(r - rr + math.cos(a) * rr * 1.04, rr + math.sin(a) * rr * 0.84) for a in [math.radians(x) for x in range(-20, 200, 20)]]
    lathe(mb, c, gl, m_glaze, cell, seg=24)


def cookie(mb, c, r, m, R, cell):
    disc(mb, c, r, 0.009, m, cell, seg=16, dome=0.2, rfun=lambda t, z: 1 + 0.04 * math.sin(5 * t + R.random()))


def cake(mb, c, r, h, m_sponge, m_icing, m_deco, R, cell):
    """Iced layer cake with piped rosettes on top rim."""
    lathe(mb, c, [(0.0, 0.0), (r, 0.0), (r * 1.01, h * 0.5), (r, h), (r * 0.97, h + 0.006), (0.0, h + 0.008)], m_icing, cell, seg=32)
    n = int(2 * math.pi * r / 0.03)
    for k in range(n):
        a = 2 * math.pi * k / n
        p = (c[0] + math.cos(a) * r * 0.86, c[1] + math.sin(a) * r * 0.86, c[2] + h + 0.004)
        lathe(mb, p, [(0.0, 0.0), (0.011, 0.0), (0.012, 0.006), (0.006, 0.014), (0.0, 0.019)], m_icing, cell, seg=8,
              rfun=lambda t, z: 1 + 0.25 * math.cos(6 * t))
    if R.random() < 0.6:
        for k in range(R.randint(5, 9)):
            a = 2 * math.pi * k / 8 + R.uniform(-0.2, 0.2)
            blob(mb, (c[0] + math.cos(a) * r * 0.5, c[1] + math.sin(a) * r * 0.5, c[2] + h + 0.014), (0.012, 0.012, 0.011), m_deco, cell, seg=8, rings=6)


def tart(mb, c, r, m_crust, m_fill, R, cell):
    lathe(mb, c, [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.022), (r * 0.98, 0.028), (r * 0.9, 0.026), (r * 0.88, 0.016), (0.0, 0.016)], m_crust, cell, seg=40,
          rfun=lambda t, z: 1 + (0.03 * math.cos(30 * t) if z > 0.015 else 0))
    lathe(mb, c, [(0.0, 0.017), (r * 0.88, 0.017), (r * 0.86, 0.024), (0.0, 0.025)], m_fill, cell, seg=32)


def cake_stand(mb, c, r, h, m):
    lathe(mb, c, [(0.0, 0.0), (r * 0.55, 0.0), (r * 0.55, 0.008), (r * 0.12, 0.02), (r * 0.08, h - 0.02), (r * 0.15, h - 0.01),
                  (r, h - 0.006), (r, h), (0.0, h)], m, seg=32)


def tray(mb, c, sx, sy, m):
    rbox(mb, (c[0], c[1], c[2] + 0.006), (sx, sy, 0.012), 0.003, m, seg=2)
    for s in (-1, 1):
        rbox(mb, (c[0] + s * sx / 2, c[1], c[2] + 0.012), (0.004, sy, 0.02), 0.0015, m, seg=1)
        rbox(mb, (c[0], c[1] + s * sy / 2, c[2] + 0.012), (sx, 0.004, 0.02), 0.0015, m, seg=1)


def basket(mb, c, sx, sy, h, m):
    lathe(mb, c, [(0.0, 0.0), (1.0, 0.0), (1.12, h), (1.15, h + 0.008), (1.08, h + 0.008), (0.95, 0.012), (0.0, 0.012)], m, seg=24,
          sx=sx / 2, sy=sy / 2, rfun=lambda t, z: 1 + 0.015 * math.cos(40 * t))


def pastry_box(mb, c, s, m, rz=0.0):
    rbox(mb, c, (s, s, s * 0.45), 0.002, m, seg=1, rz=rz)


def paper_bag(mb, c, w, d, h, m, rz=0.0):
    rbox(mb, (c[0], c[1], c[2] + h / 2), (w, d, h), 0.004, m, seg=2, rz=rz)
    rbox(mb, (c[0], c[1], c[2] + h + 0.02), (w * 0.98, d * 0.35, 0.04), 0.003, m, seg=2, rz=rz)


# ----------------------------------------------------------------------------- shop products (neighbour)
def can(mb, c, r, h, m, cell):
    lathe(mb, c, [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.006), (r, h - 0.006), (r * 0.92, h), (0.0, h)], m, cell, seg=16)


def bottle(mb, c, r, h, m, cell, wine=True):
    if wine:
        prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.62), (r * 0.45, h * 0.78), (r * 0.32, h * 0.82), (r * 0.32, h * 0.98), (r * 0.36, h), (0.0, h)]
    else:
        prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.7), (r * 0.8, h * 0.8), (r * 0.5, h * 0.88), (r * 0.5, h), (0.0, h)]
    lathe(mb, c, prof, m, cell, seg=14)


def jar(mb, c, r, h, m, m_lid, cell):
    lathe(mb, c, [(0.0, 0.0), (r * 0.92, 0.0), (r, 0.01), (r, h * 0.85), (r * 0.85, h * 0.92), (0.0, h * 0.92)], m, cell, seg=16)
    lathe(mb, (c[0], c[1], c[2] + h * 0.9), [(0.0, 0.0), (r * 0.88, 0.0), (r * 0.88, h * 0.1), (0.0, h * 0.1)], m_lid, cell, seg=16)


def carton(mb, c, w, d, h, m, cell, rz=0.0):
    rbox(mb, (c[0], c[1], c[2] + h / 2), (w, d, h), 0.002, m, cell, seg=1, rz=rz)


# ----------------------------------------------------------------------------- furniture
def sofa(mb, cx, y_back, z0, L, m, m_leg, R, cell=(0, 0, 0)):
    """Sofa against a wall at y_back (sofa faces -Y)."""
    D, H = 0.88, 0.42
    yc = y_back - D / 2
    rbox(mb, (cx, yc, z0 + 0.12 + 0.13), (L, D, 0.26), 0.04, m, cell)                    # base
    rbox(mb, (cx, y_back - 0.12, z0 + 0.38 + 0.2), (L - 0.04, 0.22, 0.48), 0.06, m, cell)  # back
    for s in (-1, 1):
        rbox(mb, (cx + s * (L / 2 - 0.09), yc, z0 + 0.12 + 0.24), (0.18, D, 0.48), 0.06, m, cell)
    n = 3 if L > 1.7 else 2
    cw = (L - 0.36) / n
    for k in range(n):
        x = cx - (L - 0.36) / 2 + cw * (k + 0.5)
        rbox(mb, (x, yc - 0.04, z0 + 0.38 + 0.06), (cw - 0.01, D - 0.26, 0.14), 0.05, m, cell)            # seat cushion
        rbox(mb, (x, y_back - 0.30, z0 + 0.62), (cw - 0.02, 0.16, 0.38), 0.06, m, cell, rx=-0.18)          # back cushion
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg(mb, (cx + sx * (L / 2 - 0.06), yc + sy * (D / 2 - 0.06), z0), (cx + sx * (L / 2 - 0.06), yc + sy * (D / 2 - 0.06), z0 + 0.12), 0.018, m_leg)
    if R.random() < 0.7:  # throw pillow
        rbox(mb, (cx - L / 2 + 0.35, y_back - 0.32, z0 + 0.62), (0.40, 0.12, 0.38), 0.06, 'fab_e' if m != 'fab_e' else 'fab_a', rx=-0.3, rz=0.2)


def armchair(mb, x, y, z0, rz, m, m_leg):
    M = xform((x, y, z0), rz)
    def p(v):
        return M @ Vector(v)
    sub = []
    rbox(mb, p((0, 0, 0.26)), (0.78, 0.80, 0.26), 0.04, m, rz=rz)
    rbox(mb, p((0, 0.31, 0.62)), (0.74, 0.18, 0.5), 0.06, m, rz=rz)
    for s in (-1, 1):
        rbox(mb, p((s * 0.33, 0, 0.45)), (0.14, 0.78, 0.30), 0.05, m, rz=rz)
    rbox(mb, p((0, -0.06, 0.44)), (0.52, 0.58, 0.12), 0.05, m, rz=rz)
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg(mb, p((sx * 0.32, sy * 0.33, 0)), p((sx * 0.32, sy * 0.33, 0.13)), 0.016, m_leg)


def table(mb, cx, cy, z0, sx, sy, h, m_top, m_leg, round_=False):
    if round_:
        lathe(mb, (cx, cy, z0 + h - 0.03), [(0.0, 0.0), (sx / 2, 0.0), (sx / 2, 0.03), (0.0, 0.03)], m_top, seg=32)
        lathe(mb, (cx, cy, z0), [(0.0, 0.0), (0.22, 0.0), (0.2, 0.03), (0.04, 0.06), (0.035, h - 0.05), (0.08, h - 0.03), (0.0, h - 0.03)], m_leg, seg=16)
        return
    rbox(mb, (cx, cy, z0 + h - 0.016), (sx, sy, 0.032), 0.004, m_top, seg=2)
    rbox(mb, (cx, cy, z0 + h - 0.07), (sx - 0.12, sy - 0.12, 0.08), 0.003, m_top, seg=1)  # apron
    for ax in (-1, 1):
        for ay in (-1, 1):
            px, py = cx + ax * (sx / 2 - 0.05), cy + ay * (sy / 2 - 0.05)
            rbox(mb, (px, py, z0 + (h - 0.03) / 2), (0.045, 0.045, h - 0.03), 0.004, m_leg, seg=1)


def chair(mb, x, y, z0, rz, m):
    M = xform((x, y, z0), rz)
    def p(v):
        return M @ Vector(v)
    rbox(mb, p((0, 0, 0.45)), (0.42, 0.42, 0.03), 0.006, m, seg=2, rz=rz)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.rod(p((sx * 0.18, sy * 0.18, 0)), p((sx * 0.18, sy * 0.18, 0.44)), 0.014, m, seg=8)
        mb.rod(p((sx * 0.18, 0.18, 0.45)), p((sx * 0.185, 0.21, 0.92)), 0.014, m, seg=8)
    for zz in (0.62, 0.75, 0.88):
        rbox(mb, p((0, 0.198, zz)), (0.36, 0.018, 0.04 if zz > 0.8 else 0.025), 0.004, m, seg=1, rz=rz)


def office_chair(mb, x, y, z0, rz, m_fab, m_base):
    M = xform((x, y, z0), rz)
    def p(v):
        return M @ Vector(v)
    for k in range(5):
        a = rz + 2 * math.pi * k / 5
        e = Vector((x + math.cos(a) * 0.30, y + math.sin(a) * 0.30, z0 + 0.06))
        mb.rod((x, y, z0 + 0.1), e, 0.016, m_base, seg=6)
        blob(mb, (e.x, e.y, z0 + 0.025), (0.025, 0.025, 0.025), m_base, seg=8, rings=5)
    mb.rod((x, y, z0 + 0.1), (x, y, z0 + 0.42), 0.025, m_base, seg=10)
    rbox(mb, p((0, 0, 0.46)), (0.48, 0.46, 0.08), 0.03, m_fab, rz=rz)
    rbox(mb, p((0, 0.24, 0.78)), (0.44, 0.06, 0.52), 0.03, m_fab, rz=rz, rx=0.12)


def bed(mb, cx, y_back, z0, W, m_frame, m_sheet, m_duvet, m_pillow, R):
    L = 2.05
    yc = y_back - L / 2
    rbox(mb, (cx, y_back - 0.04, z0 + 0.55), (W + 0.08, 0.06, 1.1), 0.01, m_frame, seg=2)                 # headboard
    rbox(mb, (cx, yc, z0 + 0.17), (W, L, 0.22), 0.01, m_frame, seg=2)                                     # base
    rbox(mb, (cx, yc, z0 + 0.38), (W - 0.04, L - 0.08, 0.22), 0.05, m_sheet)                              # mattress
    # duvet: rumpled, folded back at the head
    def wr(x, y, z):
        return Vector((0, 0, 0.012 * math.sin(9 * x + 4 * y) * (z > 0)))
    blob(mb, (cx, yc - 0.18, z0 + 0.50), (W / 2 + 0.06, (L - 0.55) / 2, 0.06), m_duvet, seg=20, rings=8, deform=wr)
    for s in ((-1, 1) if W > 1.2 else (0,)):
        rbox(mb, (cx + s * W / 4, y_back - 0.30, z0 + 0.56), (W / 2 - 0.1 if W > 1.2 else W - 0.2, 0.36, 0.14), 0.06, m_pillow, rx=-0.35)


def nightstand_lamp(mb, x, y, z0, m_wood, m_base, m_shade):
    rbox(mb, (x, y, z0 + 0.28), (0.45, 0.38, 0.56), 0.008, m_wood, seg=2)
    rbox(mb, (x, y - 0.19, z0 + 0.40), (0.38, 0.01, 0.16), 0.003, m_wood, seg=1)
    lathe(mb, (x, y, z0 + 0.56), [(0.0, 0.0), (0.07, 0.0), (0.08, 0.05), (0.06, 0.16), (0.012, 0.24), (0.008, 0.36), (0.0, 0.36)], m_base, seg=16)
    lathe(mb, (x, y, z0 + 0.86), [(0.15, 0.0), (0.10, 0.2), (0.0, 0.2)], m_shade, seg=24)
    return Vector((x, y, z0 + 0.98))


def floor_lamp(mb, x, y, z0, m_metal, m_shade):
    lathe(mb, (x, y, z0), [(0.0, 0.0), (0.15, 0.0), (0.14, 0.02), (0.02, 0.035), (0.0, 0.035)], m_metal, seg=20)
    mb.rod((x, y, z0), (x, y, z0 + 1.5), 0.011, m_metal, seg=8)
    lathe(mb, (x, y, z0 + 1.42), [(0.22, 0.0), (0.15, 0.28), (0.0, 0.28)], m_shade, seg=24)
    return Vector((x, y, z0 + 1.55))


def ceiling_fixture(mb, x, y, zc, m_glass, kind=0):
    if kind == 0:   # flush schoolhouse dome
        lathe(mb, (x, y, zc - 0.16), [(0.0, 0.0), (0.12, 0.02), (0.17, 0.08), (0.17, 0.13), (0.10, 0.16), (0.0, 0.16)], m_glass, seg=24)
    else:           # pendant drum
        mb.rod((x, y, zc), (x, y, zc - 0.55), 0.003, 'cord', seg=4)
        lathe(mb, (x, y, zc - 0.80), [(0.0, 0.25), (0.24, 0.25), (0.24, 0.0)], m_glass, seg=28)
    return Vector((x, y, zc - (0.1 if kind == 0 else 0.7)))


def radiator(mb, x0, x1, y, z0, m):
    """Cast-iron column radiator: a row of rounded sections on two feet (every pre-war NYC room has one under the window)."""
    n = int((x1 - x0) / 0.064)
    for k in range(n):
        x = x0 + 0.032 + k * 0.064
        rbox(mb, (x, y, z0 + 0.06 + 0.29), (0.048, 0.20, 0.58), 0.02, m, seg=2)
    mb.rod((x0, y, z0 + 0.12), (x1, y, z0 + 0.12), 0.02, m, seg=8)
    mb.rod((x0, y, z0 + 0.58), (x1, y, z0 + 0.58), 0.02, m, seg=8)
    mb.rod((x1 + 0.02, y, z0 + 0.12), (x1 + 0.08, y, z0 + 0.12), 0.012, 'brass', seg=8)
    lathe(mb, (x1 + 0.10, y, z0 + 0.10), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.06), (0.012, 0.09), (0.0, 0.09)], 'brass', seg=10)


def bookcase(mb, x0, x1, y_back, z0, h, m_wood, R, depth=0.32):
    yc = y_back - depth / 2
    rbox(mb, ((x0 + x1) / 2, y_back - 0.01, z0 + h / 2), (x1 - x0, 0.02, h), 0.002, m_wood, seg=1)
    for x in (x0 + 0.01, x1 - 0.01):
        rbox(mb, (x, yc, z0 + h / 2), (0.02, depth, h), 0.003, m_wood, seg=1)
    nsh = max(3, int(h / 0.36))
    for s in range(nsh + 1):
        z = z0 + 0.05 + s * (h - 0.07) / nsh
        rbox(mb, ((x0 + x1) / 2, yc, z), (x1 - x0, depth, 0.02), 0.003, m_wood, seg=1)
        if s == nsh:
            break
        x = x0 + 0.03
        while x < x1 - 0.08:
            if R.random() < 0.08:  # gap / leaning book / object
                if R.random() < 0.5:
                    lathe(mb, (x + 0.05, yc, z + 0.01), [(0.0, 0.0), (0.04, 0.0), (0.05, 0.08), (0.03, 0.14), (0.0, 0.14)], R.choice(['pot_white', 'terracotta']), seg=12)
                x += 0.12
                continue
            w = R.uniform(0.018, 0.045)
            hh = R.uniform(0.17, 0.29)
            dd = R.uniform(0.15, 0.24)
            tilt = R.uniform(-0.12, 0.0) if R.random() < 0.1 else 0.0
            rbox(mb, (x + w / 2, y_back - 0.04 - dd / 2, z + 0.01 + hh / 2), (w, dd, hh), 0.002, R.choice(['book_a', 'book_b', 'book_c', 'book_d', 'book_c', 'cardboard']), seg=1, rx=0, rz=0)
            x += w + 0.002


def kitchen(mb, x0, x1, y_back, z0, R, m_cab, m_top):
    """Base cabinets + worktop + upper cabinets + fridge + range along the back wall."""
    D = 0.6
    yc = y_back - D / 2
    fx1 = x0 + 0.72
    # fridge
    rbox(mb, ((x0 + fx1) / 2, y_back - 0.36, z0 + 0.86), (0.68, 0.68, 1.72), 0.035, 'fixture_off')
    rbox(mb, (fx1 - 0.06, y_back - 0.71, z0 + 1.1), (0.02, 0.03, 0.4), 0.008, 'steel', seg=2)
    x = fx1 + 0.02
    k = 0
    while x < x1 - 0.3:
        w = min(0.6, x1 - 0.02 - x)
        rbox(mb, (x + w / 2, yc + 0.02, z0 + 0.1 + 0.39), (w - 0.006, D - 0.06, 0.78), 0.004, m_cab, seg=1)
        rbox(mb, (x + w / 2, y_back - D + 0.035, z0 + 0.05), (w, 0.03, 0.1), 0.002, 'void', seg=1)                    # toe kick shadow
        rbox(mb, (x + w / 2, y_back - D + 0.03, z0 + 0.75), (0.12, 0.025, 0.012), 0.004, 'steel', seg=2)                 # handle
        rbox(mb, (x + w / 2, y_back - 0.18, z0 + 1.45 + 0.35), (w - 0.006, 0.34, 0.7), 0.004, m_cab, seg=1)              # upper
        if k == 1:  # range: burners + oven window
            for bx in (-0.13, 0.13):
                for by in (-0.13, 0.12):
                    lathe(mb, (x + w / 2 + bx, yc + by, z0 + 0.92), [(0.0, 0.0), (0.09, 0.0), (0.09, 0.012), (0.0, 0.012)], 'iron', seg=16)
            rbox(mb, (x + w / 2, y_back - D + 0.005, z0 + 0.48), (w - 0.12, 0.012, 0.3), 0.01, 'screen', seg=2)
        x += w
        k += 1
    rbox(mb, ((fx1 + x1) / 2, yc, z0 + 0.905), (x1 - fx1, D + 0.02, 0.03), 0.004, m_top, seg=2)
    # stuff on the worktop
    for _ in range(R.randint(3, 6)):
        px = R.uniform(fx1 + 0.1, x1 - 0.2)
        if R.random() < 0.5:
            lathe(mb, (px, y_back - 0.2, z0 + 0.92), [(0.0, 0.0), (0.05, 0.0), (0.06, 0.12), (0.0, 0.12)], R.choice(['pot_white', 'steel', 'terracotta']), seg=14)
        else:
            rbox(mb, (px, y_back - 0.15, z0 + 0.92 + 0.12), (0.18, 0.05, 0.24), 0.004, R.choice(['wood_mid', 'cardboard', 'book_c']), seg=1)
    # backsplash tiles
    rbox(mb, ((fx1 + x1) / 2, y_back - 0.006, z0 + 1.2), (x1 - fx1, 0.01, 0.55), 0.0, 'tile', seg=1)


def picture(mb, cx, y_wall, zc, w, h, m_frame, m_art, side=None):
    """Framed picture on a back wall (y_wall, facing -Y)."""
    rbox(mb, (cx, y_wall - 0.015, zc), (w, 0.025, h), 0.004, m_frame, seg=1)
    rbox(mb, (cx, y_wall - 0.03, zc), (w - 0.07, 0.004, h - 0.07), 0.0, m_art, seg=1)


def plant(mb, x, y, z0, R, big=False):
    s = 2.0 if big else 1.0
    lathe(mb, (x, y, z0), [(0.0, 0.0), (0.07 * s, 0.0), (0.09 * s, 0.17 * s), (0.095 * s, 0.18 * s), (0.0, 0.18 * s)], R.choice(['terracotta', 'pot_white']), seg=16)
    for _ in range(int(9 * s)):
        a = R.uniform(0, 6.28)
        L = R.uniform(0.2, 0.42) * s
        base = Vector((x, y, z0 + 0.17 * s))
        mid = base + Vector((math.cos(a) * L * 0.3, math.sin(a) * L * 0.3, L * 0.7))
        tip = base + Vector((math.cos(a) * L * 0.75, math.sin(a) * L * 0.75, L * 0.65))
        sweep(mb, [base, mid, tip], [0.004 * s, 0.022 * s, 0.002], 'leaf', seg=6, flat=0.15)


def rug(mb, cx, cy, z0, sx, sy, m):
    rbox(mb, (cx, cy, z0 + 0.004), (sx, sy, 0.008), 0.003, m, seg=1)


def tv(mb, cx, y_back, z0, m_wood):
    rbox(mb, (cx, y_back - 0.22, z0 + 0.24), (1.4, 0.42, 0.48), 0.01, m_wood, seg=2)
    rbox(mb, (cx, y_back - 0.18, z0 + 0.48 + 0.36), (1.1, 0.04, 0.64), 0.008, 'screen', seg=2)
    rbox(mb, (cx, y_back - 0.18, z0 + 0.49), (0.3, 0.16, 0.02), 0.005, 'screen', seg=1)
