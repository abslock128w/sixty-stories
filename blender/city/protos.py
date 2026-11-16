"""Prototype meshes (shared mesh data) for props, rooftop kit and vehicles.
Every prototype is a single multi-material mesh; instances are linked duplicates."""
import math
import random
import bpy
import bmesh

import materials as MAT
from cutil import MB

_protos = {}


def get(name):
    if name not in _protos:
        _protos[name] = BUILD[name](name)
    return _protos[name]


def _finish(mb, name, mats, bevel=0.0, smooth=False):
    me = mb.build("P_" + name, [MAT.get(m) for m in mats])
    if bevel > 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(35)]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect='EDGES', profile=0.5)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return me


def cyl(mb, cx, cy, z0, z1, r0, r1=None, n=12, mat=0, cap=True, axis='z'):
    r1 = r0 if r1 is None else r1
    ring0, ring1 = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        ring0.append((math.cos(a), math.sin(a)))
    for k in range(n):
        a, b = ring0[k], ring0[(k + 1) % n]
        if axis == 'z':
            P = [(cx + a[0] * r0, cy + a[1] * r0, z0), (cx + b[0] * r0, cy + b[1] * r0, z0),
                 (cx + b[0] * r1, cy + b[1] * r1, z1), (cx + a[0] * r1, cy + a[1] * r1, z1)]
        elif axis == 'x':  # cx = y centre, cy = z centre, z0..z1 along x
            P = [(z0, cx + a[0] * r0, cy + a[1] * r0), (z0, cx + b[0] * r0, cy + b[1] * r0),
                 (z1, cx + b[0] * r1, cy + b[1] * r1), (z1, cx + a[0] * r1, cy + a[1] * r1)]
            P = [P[1], P[0], P[3], P[2]]
        mb.poly(P, mat, None, None, smooth=True)
    if cap:
        if axis == 'z':
            mb.poly([(cx + p[0] * r1, cy + p[1] * r1, z1) for p in ring0], mat)
        else:
            mb.poly([(z1, cx + p[0] * r1, cy + p[1] * r1) for p in ring0], mat)
            mb.poly([(z0, cx + p[0] * r0, cy + p[1] * r0) for p in reversed(ring0)], mat)


# ----------------------------------------------------------------- rooftop kit
def p_water_tower(name):
    mb = MB()
    # legs + platform (steel), tank (wood staves via bark-ish material), conical roof
    for (x, y) in ((-1.6, -1.6), (1.6, -1.6), (1.6, 1.6), (-1.6, 1.6)):
        mb.box(x - 0.12, x + 0.12, y - 0.12, y + 0.12, 0, 4.0, 0)
    mb.box(-2.2, 2.2, -2.2, 2.2, 4.0, 4.2, 0)
    cyl(mb, 0, 0, 4.2, 9.2, 2.2, 2.05, n=20, mat=1)
    cyl(mb, 0, 0, 9.2, 10.8, 2.25, 0.15, n=20, mat=2, cap=True)
    for z in (5.0, 6.3, 7.6, 8.8):
        cyl(mb, 0, 0, z, z + 0.08, 2.24, 2.22, n=20, mat=0, cap=False)
    return _finish(mb, name, ['metal_dark', 'plywood', 'roof'])


def p_hvac(name):
    mb = MB()
    mb.box(-1.5, 1.5, -1.0, 1.0, 0, 1.6, 0)
    for x in (-0.75, 0.75):
        cyl(mb, x, 0, 1.6, 1.75, 0.55, 0.55, n=16, mat=1)
    return _finish(mb, name, ['metal_alu', 'metal_dark'], bevel=0.03)


def p_antenna(name):
    mb = MB()
    cyl(mb, 0, 0, 0, 22.0, 0.35, 0.06, n=8, mat=0)
    for z in (6, 12, 17):
        mb.box(-1.2, 1.2, -0.04, 0.04, z, z + 0.08, 0)
    cyl(mb, 0, 0, 22.0, 22.4, 0.12, 0.12, n=8, mat=1)
    return _finish(mb, name, ['metal_dark', 'sig_red'])


# ----------------------------------------------------------------- street furniture
def p_lamp(name):
    """NYC-style octagonal pole with a bishop's-crook style arm and a cobra-head luminaire.
    Built at origin, arm toward +X."""
    mb = MB()
    cyl(mb, 0, 0, 0, 0.9, 0.22, 0.17, n=8, mat=0)
    cyl(mb, 0, 0, 0.9, 8.6, 0.11, 0.075, n=8, mat=0)
    # arm: segments rising then horizontal
    pts = [(0, 8.4), (0.5, 8.9), (1.2, 9.15), (2.2, 9.2)]
    for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        mb.box(x0, x1 + 0.05, -0.05, 0.05, min(z0, z1) - 0.03, max(z0, z1) + 0.03, 0)
    # luminaire head
    mb.box(1.8, 2.9, -0.28, 0.28, 9.0, 9.32, 0)
    mb.box(1.9, 2.8, -0.22, 0.22, 8.96, 9.0, 1)
    return _finish(mb, name, ['metal_dark', 'lamp_emit'], bevel=0.02)


def _signal_head(mb, x, y, z, lit, facing=-1):
    """Three-aspect head; lit in ('red','green','amber'). facing -1: lenses toward -Y."""
    mb.box(x - 0.2, x + 0.2, y - 0.15, y + 0.15, z, z + 1.05, 0)
    for i, c in enumerate(('red', 'amber', 'green')):
        zz = z + 0.85 - i * 0.33
        m = {'red': 2, 'amber': 4, 'green': 3}[c] if c == lit else 5
        yy = y + facing * 0.152
        mb.quad((x - 0.12, yy, zz - 0.12), (x + 0.12, yy, zz - 0.12), (x + 0.12, yy, zz + 0.12), (x - 0.12, yy, zz + 0.12)
                if facing < 0 else (x - 0.12, yy, zz + 0.12), m) if False else None
        if facing < 0:
            mb.quad((x - 0.12, yy, zz - 0.12), (x + 0.12, yy, zz - 0.12), (x + 0.12, yy, zz + 0.12), (x - 0.12, yy, zz + 0.12), m)
        else:
            mb.quad((x + 0.12, yy, zz - 0.12), (x - 0.12, yy, zz - 0.12), (x - 0.12, yy, zz + 0.12), (x + 0.12, yy, zz + 0.12), m)
        # visor
        mb.box(x - 0.15, x + 0.15, yy + facing * 0.18 - 0.01, yy, zz + 0.12, zz + 0.15, 0)


def _p_signal(name, lit):
    """Mast arm signal: pole at origin on the east curb, arm spanning toward -X over the lanes,
    heads facing -Y (toward northbound traffic)."""
    mb = MB()
    cyl(mb, 0, 0, 0, 7.2, 0.16, 0.12, n=8, mat=1)
    mb.box(-14.5, 0.0, -0.08, 0.08, 6.6, 6.82, 1)
    mb.box(-6.0, 0.0, -0.05, 0.05, 6.82, 7.4, 1) if False else None
    for x in (-2.5, -6.0, -9.5, -13.0):
        _signal_head(mb, x, 0.0, 5.4, lit, facing=-1)
    # pedestrian head on pole
    mb.box(-0.2, 0.2, -0.45, -0.15, 2.6, 3.1, 0)
    mb.quad((-0.15, -0.452, 2.65), (0.15, -0.452, 2.65), (0.15, -0.452, 3.05), (-0.15, -0.452, 3.05), 4)
    # street name sign (green)
    mb.box(-3.0, -1.2, -0.02, 0.02, 7.3, 7.6, 6)
    return _finish(mb, name, ['metal_dark', 'metal_dark', 'sig_red', 'sig_green', 'sig_amber', 'rubber', 'fabric_green'])


def p_signal_red(name):
    return _p_signal(name, 'red')


def p_signal_green(name):
    return _p_signal(name, 'green')


def p_hydrant(name):
    mb = MB()
    cyl(mb, 0, 0, 0, 0.12, 0.17, 0.17, n=10, mat=0)
    cyl(mb, 0, 0, 0.12, 0.62, 0.12, 0.12, n=10, mat=0)
    cyl(mb, 0, 0, 0.62, 0.78, 0.13, 0.05, n=10, mat=0)
    cyl(mb, 0.0, 0.42, 0.12, 0.24, 0.05, 0.05, n=8, mat=0, axis='x')
    return _finish(mb, name, ['fabric_red'])


def p_trash(name):
    mb = MB()
    cyl(mb, 0, 0, 0, 0.95, 0.28, 0.3, n=12, mat=0)
    return _finish(mb, name, ['fabric_green'])


def p_newsbox(name):
    mb = MB()
    mb.box(-0.25, 0.25, -0.22, 0.22, 0.3, 1.2, 0)
    for x in (-0.2, 0.2):
        mb.box(x - 0.03, x + 0.03, -0.18, 0.18, 0, 0.3, 1)
    return _finish(mb, name, ['fabric_navy', 'metal_dark'], bevel=0.015)


def p_manhole(name):
    mb = MB()
    cyl(mb, 0, 0, 0.0, 0.006, 0.33, 0.33, n=16, mat=0)
    return _finish(mb, name, ['metal_dark'])


def p_vent(name):
    """Con Ed style orange/white striped steam chimney."""
    mb = MB()
    for i in range(5):
        cyl(mb, 0, 0, i * 0.7, (i + 1) * 0.7, 0.42 - i * 0.03, 0.42 - (i + 1) * 0.03, n=14, mat=i % 2, cap=(i == 4))
    return _finish(mb, name, ['fabric_cream', 'sig_amber'])


def p_bus_shelter(name):
    mb = MB()
    for x in (-2.0, 2.0):
        for y in (-0.7, 0.7):
            mb.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0, 2.5, 0)
    mb.box(-2.1, 2.1, -0.8, 0.8, 2.5, 2.62, 0)
    mb.quad((-2.0, 0.7, 0.1), (2.0, 0.7, 0.1), (2.0, 0.7, 2.4), (-2.0, 0.7, 2.4), 1)
    mb.quad((2.0, 0.7, 0.1), (-2.0, 0.7, 0.1), (-2.0, 0.7, 2.4), (2.0, 0.7, 2.4), 1)
    mb.quad((2.0, -0.7, 0.1), (2.0, 0.7, 0.1), (2.0, 0.7, 2.4), (2.0, -0.7, 2.4), 2)
    mb.quad((2.0, 0.7, 0.1), (2.0, -0.7, 0.1), (2.0, -0.7, 2.4), (2.0, 0.7, 2.4), 2)
    mb.box(-1.5, 1.5, 0.3, 0.6, 0.45, 0.5, 0)
    return _finish(mb, name, ['metal_alu', 'glass_clear', 'sign_white'])


# ----------------------------------------------------------------- tree
def _tree(name, seed, h, crown_r, n_leaves):
    rng = random.Random(seed)
    mb = MB()
    # trunk + main limbs
    cyl(mb, 0, 0, 0, h * 0.45, 0.16, 0.11, n=8, mat=0)
    limbs = []
    for k in range(5):
        a = rng.uniform(0, 2 * math.pi)
        el = rng.uniform(0.5, 1.1)
        L = rng.uniform(1.5, 2.6)
        x1, y1 = math.cos(a) * L * math.cos(el), math.sin(a) * L * math.cos(el)
        z0 = h * 0.42
        z1 = z0 + L * math.sin(el) + 0.6
        mb.poly([(0.06 * math.cos(a + 1.5), 0.06 * math.sin(a + 1.5), z0), (-0.06 * math.cos(a + 1.5), -0.06 * math.sin(a + 1.5), z0),
                 (x1, y1, z1)], 0)
        limbs.append((x1, y1, z1))
    # leaf clusters: small quads clustered in lumps around limb ends and the crown volume
    cz = h * 0.68
    lumps = [(x * 1.1, y * 1.1, z + 0.4) for (x, y, z) in limbs] + [
        (rng.uniform(-1, 1) * crown_r * 0.6, rng.uniform(-1, 1) * crown_r * 0.6, cz + rng.uniform(-0.8, 1.6)) for _ in range(7)]
    per = n_leaves // len(lumps)
    for (lx, ly, lz) in lumps:
        lr = rng.uniform(0.9, 1.6)
        for _ in range(per):
            # point in a squashed sphere
            while True:
                p = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
                if p[0] ** 2 + p[1] ** 2 + p[2] ** 2 <= 1:
                    break
            cx, cy, cz2 = lx + p[0] * lr, ly + p[1] * lr, lz + p[2] * lr * 0.75
            s = rng.uniform(0.09, 0.15)
            a = rng.uniform(0, math.pi)
            t = rng.uniform(-0.8, 0.8)
            ux, uy, uz = math.cos(a) * s, math.sin(a) * s, 0.0
            vx, vy, vz = -math.sin(a) * s * math.cos(t), math.cos(a) * s * math.cos(t), s * math.sin(t) * 1.5
            mb.poly([(cx - ux - vx, cy - uy - vy, cz2 - uz - vz), (cx + ux - vx, cy + uy - vy, cz2 + uz - vz),
                     (cx + ux + vx, cy + uy + vy, cz2 + uz + vz), (cx - ux + vx, cy - uy + vy, cz2 - uz + vz)], 1)
    # tree pit grate
    mb.box(-0.7, 0.7, -0.7, 0.7, 0.0, 0.02, 2)
    return _finish(mb, name, ['bark', 'leaves', 'metal_dark'])


def p_tree_a(name):
    return _tree(name, 11, 8.5, 2.6, 6000)


def p_tree_b(name):
    return _tree(name, 23, 7.0, 2.2, 4500)


def p_tree_c(name):
    return _tree(name, 37, 10.0, 3.0, 7000)


# ----------------------------------------------------------------- pedestrians
def _ped(name, seed, h):
    rng = random.Random(seed)
    mb = MB()
    s = h / 1.75
    # legs
    for x in (-0.09, 0.09):
        mb.box((x - 0.065) * s, (x + 0.065) * s, -0.07 * s, 0.07 * s, 0, 0.86 * s, 1)
    # torso (coat)
    mb.box(-0.2 * s, 0.2 * s, -0.12 * s, 0.12 * s, 0.82 * s, 1.45 * s, 2)
    # arms
    for x in (-0.25, 0.25):
        mb.box((x - 0.05) * s, (x + 0.05) * s, -0.06 * s, 0.06 * s, 0.85 * s, 1.42 * s, 2)
    # head
    cyl(mb, 0, 0, 1.47 * s, 1.72 * s, 0.1 * s, 0.09 * s, n=8, mat=0)
    return _finish(mb, name, ['skin', 'cloth_dark', 'cloth_var'], bevel=0.02)


def p_ped_a(name):
    return _ped(name, 1, 1.78)


def p_ped_b(name):
    return _ped(name, 2, 1.64)


# ----------------------------------------------------------------- vehicles (front toward +Y)
def _car(name, L, W, H, cab_h, glass_h, paint='car_paint', roof_sign=False, hood=1.1, trunk=0.8):
    mb = MB()
    PAINT, GLASS, RUB, CHR, HEAD, TAIL, SIGN = 0, 1, 2, 3, 4, 5, 6
    y0, y1 = -L / 2, L / 2
    zb, zm = 0.28, cab_h
    w = W / 2
    # lower body: side profile extruded across width (chamfered nose/tail)
    prof = [(y0, zb + 0.1), (y0 + 0.08, zb), (y1 - 0.08, zb), (y1, zb + 0.12), (y1, zm - 0.12), (y1 - 0.25, zm),
            (y0 + 0.2, zm), (y0, zm - 0.1)]
    n = len(prof)
    for i in range(n):
        a, b = prof[i], prof[(i + 1) % n]
        mb.poly([(w, a[0], a[1]), (w, b[0], b[1]), (-w, b[0], b[1]), (-w, a[0], a[1])][::-1], PAINT)
    mb.poly([(w, p[0], p[1]) for p in prof], PAINT)
    mb.poly([(-w, p[0], p[1]) for p in reversed(prof)], PAINT)
    # greenhouse: trapezoid prism
    gy0, gy1 = y0 + trunk, y1 - hood
    wt = w - 0.12
    top = zm + glass_h
    gp = [(gy0, zm), (gy1, zm), (gy1 - 0.55 * glass_h / 0.45, top), (gy0 + 0.35 * glass_h / 0.45, top)]
    for i in range(4):
        a, b = gp[i], gp[(i + 1) % 4]
        m = PAINT if i == 2 else GLASS
        mb.poly([(wt, a[0], a[1]), (wt, b[0], b[1]), (-wt, b[0], b[1]), (-wt, a[0], a[1])][::-1], m)
    mb.poly([(wt, p[0], p[1]) for p in gp], GLASS)
    mb.poly([(-wt, p[0], p[1]) for p in reversed(gp)], GLASS)
    # roof skin over the glass top
    mb.box(-wt + 0.02, wt - 0.02, gp[3][0] + 0.02, gp[2][0] - 0.02, top, top + 0.03, PAINT)
    # wheels
    for yy in (y0 + 0.85, y1 - 0.95):
        for xs in (-1, 1):
            cyl(mb, yy, 0.33, xs * (w - 0.24) - 0.0 + (0.0 if xs > 0 else -0.0), xs * (w + 0.01), 0.33, n=14, mat=RUB, axis='x') if False else None
            x0, x1 = (w - 0.22, w + 0.01) if xs > 0 else (-w - 0.01, -w + 0.22)
            cyl(mb, yy, 0.33, x0, x1, 0.33, n=14, mat=RUB, axis='x')
            xh = x1 + 0.002 if xs > 0 else x0 - 0.002
            cyl(mb, yy, 0.33, xh - 0.001, xh, 0.18, n=10, mat=CHR, axis='x')
    # lights
    for xs in (-1, 1):
        cx = xs * (w - 0.3)
        mb.quad((cx + 0.22, y1 + 0.004, zm - 0.32), (cx - 0.22, y1 + 0.004, zm - 0.32), (cx - 0.22, y1 + 0.004, zm - 0.18),
                (cx + 0.22, y1 + 0.004, zm - 0.18), HEAD)
        mb.quad((cx - 0.25, y0 - 0.004, zm - 0.3), (cx + 0.25, y0 - 0.004, zm - 0.3), (cx + 0.25, y0 - 0.004, zm - 0.14),
                (cx - 0.25, y0 - 0.004, zm - 0.14), TAIL)
    # bumpers
    mb.box(-w + 0.05, w - 0.05, y1 - 0.05, y1 + 0.06, zb, zb + 0.22, RUB)
    mb.box(-w + 0.05, w - 0.05, y0 - 0.06, y0 + 0.05, zb, zb + 0.22, RUB)
    if roof_sign:
        mb.box(-0.4, 0.4, -0.12 + (gp[3][0] + gp[2][0]) / 2, 0.12 + (gp[3][0] + gp[2][0]) / 2, top + 0.03, top + 0.33, SIGN)
    return _finish(mb, name, [paint, 'car_glass', 'rubber', 'chrome', 'headlight', 'taillight', 'sign_white'])


def p_sedan(name):
    return _car(name, 4.75, 1.84, 1.45, 0.95, 0.47)


def p_suv(name):
    return _car(name, 4.95, 1.95, 1.8, 1.15, 0.6, hood=1.0, trunk=0.35)


def p_cab(name):
    return _car(name, 4.85, 1.85, 1.5, 0.96, 0.5, paint='cab_yellow', roof_sign=True)


def p_cab_suv(name):
    return _car(name, 4.75, 1.9, 1.75, 1.1, 0.58, paint='cab_yellow', roof_sign=True, hood=0.95, trunk=0.4)


def _boxveh(name, L, W, H, cabL, paint, windows=True, bus=False):
    mb = MB()
    PAINT, GLASS, RUB, CHR, HEAD, TAIL, SIGN = 0, 1, 2, 3, 4, 5, 6
    w = W / 2
    y0, y1 = -L / 2, L / 2
    zb = 0.35
    if bus:
        mb.box(-w, w, y0, y1, zb, H, PAINT)
        # window band both sides + windshield
        for xs in (-1, 1):
            x = xs * (w + 0.005)
            pts = [(x, y0 + 0.6, 1.25), (x, y1 - 0.4, 1.25), (x, y1 - 0.4, H - 0.45), (x, y0 + 0.6, H - 0.45)]
            mb.poly(pts if xs > 0 else pts[::-1], GLASS)
        mb.quad((w - 0.1, y1 + 0.005, 1.0), (-w + 0.1, y1 + 0.005, 1.0), (-w + 0.1, y1 + 0.005, H - 0.4), (w - 0.1, y1 + 0.005, H - 0.4), GLASS)
        mb.quad((w - 0.3, y1 + 0.01, H - 0.38), (-w + 0.3, y1 + 0.01, H - 0.38), (-w + 0.3, y1 + 0.01, H - 0.12), (w - 0.3, y1 + 0.01, H - 0.12), SIGN)
    else:
        # cab + cargo box
        mb.box(-w, w, y1 - cabL, y1, zb, H * 0.72, PAINT)
        mb.quad((w - 0.1, y1 + 0.005, H * 0.45), (-w + 0.1, y1 + 0.005, H * 0.45), (-w + 0.1, y1 + 0.005, H * 0.68), (w - 0.1, y1 + 0.005, H * 0.68), GLASS)
        for xs in (-1, 1):
            x = xs * (w + 0.005)
            pts = [(x, y1 - cabL + 0.3, H * 0.45), (x, y1 - 0.1, H * 0.45), (x, y1 - 0.1, H * 0.68), (x, y1 - cabL + 0.3, H * 0.68)]
            mb.poly(pts if xs > 0 else pts[::-1], GLASS)
        mb.box(-w - 0.05, w + 0.05, y0, y1 - cabL - 0.15, zb + 0.1, H, 7)
    for yy in (y0 + 1.0, y1 - 1.0):
        for xs in (-1, 1):
            x0, x1 = (w - 0.28, w + 0.01) if xs > 0 else (-w - 0.01, -w + 0.28)
            cyl(mb, yy, 0.45, x0, x1, 0.45, n=14, mat=RUB, axis='x')
    for xs in (-1, 1):
        cx = xs * (w - 0.3)
        mb.quad((cx + 0.2, y1 + 0.01, 0.7), (cx - 0.2, y1 + 0.01, 0.7), (cx - 0.2, y1 + 0.01, 0.9), (cx + 0.2, y1 + 0.01, 0.9), HEAD)
        mb.quad((cx - 0.15, y0 - 0.06, 0.7), (cx + 0.15, y0 - 0.06, 0.7), (cx + 0.15, y0 - 0.06, 1.0), (cx - 0.15, y0 - 0.06, 1.0), TAIL)
    return _finish(mb, name, [paint, 'car_glass', 'rubber', 'chrome', 'headlight', 'taillight', 'sig_amber', 'bus_paint'])


def p_bus(name):
    return _boxveh(name, 12.2, 2.55, 3.2, 0, 'bus_paint', bus=True)


def p_van(name):
    return _boxveh(name, 6.0, 2.05, 2.6, 1.6, 'bus_paint')


def p_truck(name):
    return _boxveh(name, 8.0, 2.45, 3.5, 2.2, 'car_paint')


BUILD = {
    'water_tower': p_water_tower, 'hvac': p_hvac, 'antenna': p_antenna,
    'lamp': p_lamp, 'signal_red': p_signal_red, 'signal_green': p_signal_green,
    'hydrant': p_hydrant, 'trash': p_trash, 'newsbox': p_newsbox, 'manhole': p_manhole, 'vent': p_vent,
    'bus_shelter': p_bus_shelter, 'tree_a': p_tree_a, 'tree_b': p_tree_b, 'tree_c': p_tree_c,
    'ped_a': p_ped_a, 'ped_b': p_ped_b,
    'sedan': p_sedan, 'suv': p_suv, 'cab': p_cab, 'cab_suv': p_cab_suv, 'bus': p_bus, 'van': p_van, 'truck': p_truck,
}
