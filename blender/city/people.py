"""Pedestrians v3: subdivision-smoothed bodies with real proportions (8-head figure), clothing variants
(coat, jacket, dress), hair, shoes, bags, and several poses. Overrides pp_* / ped_* prototypes."""
import math
import random
import bpy

import protos as PR
import materials as MAT
import vehicles as V
from protos import cyl
from cutil import MB

SKIN, PANTS, TOP, SHOE, HAIR, BAG = range(6)
MATS = ['skin', 'cloth_var2', 'cloth_var3', 'rubber', 'hair', 'fabric_navy']
MAT.BUILDERS['hair'] = lambda n: _hair(n)


def _hair(name):
    nb, m = MAT._new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    col = nb.ramp(oi.outputs['Random'], [(0.0, (0.02, 0.015, 0.01)), (0.4, (0.08, 0.04, 0.02)), (0.7, (0.25, 0.15, 0.07)),
                                         (0.88, (0.45, 0.35, 0.2)), (0.95, (0.4, 0.4, 0.4))], interp='CONSTANT')
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.45, 'Sheen Weight': 0.4})
    nb.out(p.outputs[0])
    return m


def _loft(mb, rings, mat, n=8, cap0=True, cap1=True):
    """rings: list of (cx, cy, z, rx, ry); elliptical cross-sections stacked."""
    pts = []
    for (cx, cy, z, rx, ry) in rings:
        pts.append([(cx + math.cos(2 * math.pi * k / n) * rx, cy + math.sin(2 * math.pi * k / n) * ry, z) for k in range(n)])
    for a, b in zip(pts[:-1], pts[1:]):
        for k in range(n):
            mb.poly([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]], mat, smooth=True)
    if cap0:
        mb.poly(list(reversed(pts[0])), mat)
    if cap1:
        mb.poly(pts[-1], mat)


def _limb(mb, p0, p1, r0, r1, mat, n=8):
    """Tapered tube between two points (any direction)."""
    import mathutils
    a, b = mathutils.Vector(p0), mathutils.Vector(p1)
    d = (b - a).normalized()
    up = mathutils.Vector((0, 0, 1)) if abs(d.z) < 0.9 else mathutils.Vector((1, 0, 0))
    u = d.cross(up).normalized()
    v = d.cross(u).normalized()
    ra = [a + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * r0 for k in range(n)]
    rb = [b + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * r1 for k in range(n)]
    for k in range(n):
        mb.poly([tuple(ra[k]), tuple(ra[(k + 1) % n]), tuple(rb[(k + 1) % n]), tuple(rb[k])], mat, smooth=True)
    mb.poly([tuple(p) for p in reversed(ra)], mat)
    mb.poly([tuple(p) for p in rb], mat)


def person(name, h=1.75, pose='walk', garment='jacket', bag=False, seed=0):
    s = h / 1.75
    r = random.Random(seed)
    mb = MB()
    st = {'walk': 0.38, 'walk2': -0.38, 'stand': 0.06, 'phone': 0.04, 'wait': 0.0}[pose]
    hip = 0.93 * s
    # legs (thigh + shin as one bent tube each), shoes
    for side, sw in ((-1, st), (1, -st)):
        x = side * 0.095 * s
        knee = (x, math.sin(sw) * 0.44 * s, hip - math.cos(sw) * 0.44 * s)
        bend = sw * 0.6 if sw < 0 else 0.0
        ankle = (x, knee[1] + math.sin(sw - bend) * 0.43 * s, max(0.08 * s, knee[2] - math.cos(sw - bend) * 0.43 * s))
        legmat = TOP if garment == 'dress' else PANTS
        _limb(mb, (x, 0.0, hip), knee, 0.082 * s, 0.058 * s, legmat)
        _limb(mb, knee, ankle, 0.058 * s, 0.042 * s if garment != 'dress' else 0.035 * s, legmat if garment != 'dress' else SKIN)
        mb.box(x - 0.048 * s, x + 0.048 * s, ankle[1] - 0.06 * s, ankle[1] + 0.2 * s, 0.0, 0.085 * s, SHOE)
    # torso: hips -> waist -> chest -> shoulders (coat / dress skirts extend below the hip)
    rings = [(0, 0, hip - 0.04 * s, 0.17 * s, 0.11 * s), (0, 0, 1.05 * s, 0.15 * s, 0.10 * s), (0, 0.01, 1.28 * s, 0.185 * s, 0.12 * s),
             (0, 0, 1.43 * s, 0.205 * s, 0.11 * s), (0, 0, 1.48 * s, 0.09 * s, 0.07 * s)]
    if garment in ('coat', 'dress'):
        hem = (0.62 if garment == 'coat' else 0.55) * s
        rings = [(0, 0, hem, 0.21 * s, 0.15 * s)] + rings
    _loft(mb, rings, TOP)
    _limb(mb, (0, 0, 1.46 * s), (0, 0.01, 1.56 * s), 0.05 * s, 0.048 * s, SKIN)
    # arms
    for side, sw in ((-1, -st * 0.9), (1, st * 0.9)):
        sh = (side * 0.21 * s, 0.0, 1.41 * s)
        if pose == 'phone' and side > 0:
            el = (side * 0.24 * s, 0.05 * s, 1.15 * s)
            wr = (side * 0.13 * s, 0.14 * s, 1.42 * s)
        elif pose == 'wait' and side < 0:
            el = (side * 0.25 * s, 0.06 * s, 1.14 * s)
            wr = (side * 0.05 * s, 0.13 * s, 1.08 * s)
        else:
            el = (side * 0.235 * s, math.sin(sw) * 0.29 * s, 1.41 * s - math.cos(sw) * 0.29 * s)
            wr = (side * 0.24 * s, el[1] + math.sin(sw * 1.3) * 0.26 * s, el[2] - math.cos(sw * 1.3) * 0.26 * s)
        _limb(mb, sh, el, 0.052 * s, 0.042 * s, TOP)
        _limb(mb, el, wr, 0.042 * s, 0.034 * s, TOP)
        _limb(mb, wr, (wr[0], wr[1] + 0.02 * s, wr[2] - 0.08 * s), 0.03 * s, 0.025 * s, SKIN)
        if bag and side > 0 and pose in ('walk', 'walk2', 'stand'):
            mb.box(wr[0] - 0.05 * s, wr[0] + 0.05 * s, wr[1] - 0.17 * s, wr[1] + 0.17 * s, wr[2] - 0.42 * s, wr[2] - 0.1 * s, BAG)
    # head: ellipsoid + hair cap
    hz = 1.645 * s
    _loft(mb, [(0, 0.01, hz - 0.115 * s, 0.03 * s, 0.03 * s), (0, 0.01, hz - 0.08 * s, 0.08 * s, 0.09 * s),
               (0, 0.01, hz, 0.095 * s, 0.11 * s), (0, 0.0, hz + 0.07 * s, 0.085 * s, 0.10 * s),
               (0, -0.005, hz + 0.115 * s, 0.03 * s, 0.035 * s)], SKIN, n=10)
    hl = r.choice([0.0, 0.03, 0.12])
    _loft(mb, [(0, -0.01, hz + 0.0 * s - hl, 0.1 * s, 0.11 * s), (0, -0.01, hz + 0.06 * s, 0.097 * s, 0.112 * s),
               (0, -0.01, hz + 0.125 * s, 0.035 * s, 0.04 * s)], HAIR, n=10)
    if bag and pose in ('wait', 'phone'):   # backpack
        mb.box(-0.15 * s, 0.15 * s, -0.24 * s, -0.11 * s, 1.0 * s, 1.42 * s, BAG)
    return V._subdivided(mb, name, MATS, levels=1)


def register():
    variants = {
        'pp_walk_a': (1.78, 'walk', 'jacket', True), 'pp_walk_b': (1.66, 'walk2', 'coat', False),
        'pp_stand': (1.72, 'stand', 'jacket', False), 'pp_phone': (1.62, 'phone', 'dress', True),
        'pp_walk_c': (1.84, 'walk2', 'jacket', False), 'pp_stand_b': (1.60, 'wait', 'coat', True),
        'ped_a': (1.70, 'walk', 'dress', True), 'ped_b': (1.80, 'walk2', 'coat', True),
    }
    for i, (k, (h, pose, g, bag)) in enumerate(variants.items()):
        PR.BUILD[k] = (lambda h, p, g, b, sd: (lambda n: person(n, h, p, g, b, sd)))(h, pose, g, bag, i)
