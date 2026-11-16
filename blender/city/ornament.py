"""The perch ornament on The Tower's north-east corner pier: an abstract streamlined Art Deco
winged prow in weathered stainless steel (no face), on a stepped carved-stone corbel.

Local frame: u = outward from the pier face (+X world), v = across (+Y world), w = up,
origin at the pier face on the perch's top plane. The flat perch deck is u 0..PERCH_L,
v -PERCH_HW..PERCH_HW, w = 0 exactly (same as the previous gargoyle contract)."""
import math
import bpy

import materials as MAT
from cutil import MB, new_object, bevel_mod

PERCH_L = 1.8
PERCH_HW = 0.47
NOSE = 2.55          # tip of the deck's pointed nose (its top slopes down from u=PERCH_L)
STEEL, STONE, DARK = 0, 1, 2


def _prism_uv(mb, plan, w0, w1, mat, top_slope=None):
    """Vertical extrusion of a CCW (u,v) plan from w0 to w1. top_slope(u) -> top w override."""
    n = len(plan)
    tw = (lambda p: w1) if top_slope is None else (lambda p: top_slope(p[0]))
    for i in range(n):
        a, b = plan[i], plan[(i + 1) % n]
        mb.poly([(a[0], a[1], w0), (b[0], b[1], w0), (b[0], b[1], tw(b)), (a[0], a[1], tw(a))], mat)
    mb.poly([(p[0], p[1], tw(p)) for p in plan], mat)
    mb.poly([(p[0], p[1], w0) for p in reversed(plan)], mat)


def _bar(mb, a, b, t, u0, u1, mat):
    """Relief bar in the wall (v,w) plane from a to b, thickness t, standing out u0..u1."""
    dv, dw = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dv, dw)
    nv, nw = -dw / L * t / 2, dv / L * t / 2
    q = [(a[0] - nv, a[1] - nw), (b[0] - nv, b[1] - nw), (b[0] + nv, b[1] + nw), (a[0] + nv, a[1] + nw)]
    for i in range(4):
        p, r = q[i], q[(i + 1) % 4]
        mb.poly([(u0, p[0], p[1]), (u0, r[0], r[1]), (u1, r[0], r[1]), (u1, p[0], p[1])][::-1], mat)
    mb.poly([(u1, p[0], p[1]) for p in q], mat)


def build(col, base_x, y, z):
    steel = MB()
    stone = MB()
    rivets = MB()
    # ---- deck: flat perch rectangle + pointed nose whose top drops 0.14 m
    deck = [(-0.3, -PERCH_HW), (PERCH_L, -PERCH_HW), (NOSE, 0.0), (PERCH_L, PERCH_HW), (-0.3, PERCH_HW)]
    _prism_uv(steel, deck, -0.16, 0.0, STEEL,
              top_slope=lambda u: 0.0 if u <= PERCH_L + 1e-6 else -0.14 * (u - PERCH_L) / (NOSE - PERCH_L))
    # ---- stepped prow layers below (inverted ziggurat), each wider and shorter, with seams
    w = -0.19
    for k in range(1, 5):
        th = 0.20
        L = PERCH_L - 0.24 * k
        nose = NOSE - 0.30 * k
        hw = PERCH_HW + 0.055 * k
        plan = [(-0.3, -hw), (L, -hw), (nose, 0.0), (L, hw), (-0.3, hw)]
        _prism_uv(steel, plan, w - th, w, STEEL)
        # rivet rows along both flanks at mid height
        uu = 0.0
        while uu < L - 0.05:
            for s in (-1, 1):
                v = s * (hw + 0.006)
                rivets.box(uu - 0.011, uu + 0.011, min(v, v + s * 0.014), max(v, v + s * 0.014), w - th / 2 - 0.011,
                           w - th / 2 + 0.011, 0)
            uu += 0.16
        w -= th + 0.03
    # deck rivets around the top edge (sides only; the walking surface stays clean in the middle)
    uu = 0.05
    while uu < PERCH_L - 0.05:
        for s in (-1, 1):
            v = s * (PERCH_HW - 0.05)
            rivets.box(uu - 0.012, uu + 0.012, v - 0.012, v + 0.012, 0.0, 0.009, 0)
        uu += 0.15
    # central keel fin under the prow
    keel = [(-0.3, -0.04), (1.05, -0.04), (1.45, 0.0), (1.05, 0.04), (-0.3, 0.04)]
    _prism_uv(steel, keel, w - 0.35, w + 0.02, STEEL)
    # ---- swept wings: three stacked stainless blades per side, attached to the pier
    for s in (-1, 1):
        for k, (wz, span, reach) in enumerate(((-0.30, 1.05, 1.35), (-0.58, 0.85, 1.05), (-0.86, 0.62, 0.75))):
            root = PERCH_HW + 0.06 * (k + 1)
            pts = [(reach, s * root), (0.25, s * (root + span)), (-0.3, s * (root + span)), (-0.3, s * root)]
            if s < 0:
                pts = pts[::-1]
            _prism_uv(steel, pts, wz - 0.07, wz, STEEL)
    # ---- stepped stone corbel with carved chevrons
    stone.box(-0.3, 1.0, -0.82, 0.82, -1.48, -1.15, STONE)
    stone.box(-0.3, 0.66, -0.72, 0.72, -1.85, -1.48, STONE)
    stone.box(-0.3, 0.36, -0.62, 0.62, -2.22, -1.85, STONE)
    for k in range(3):   # chevrons carved on the corbel front faces
        u = (1.0, 0.66, 0.36)[k]
        wm = (-1.31, -1.66, -2.03)[k]
        for side in (-1, 1):
            _bar(stone, (0.0, wm + 0.08), (side * 0.45, wm - 0.06), 0.05, u - 0.01, u + 0.025, STONE) if False else None
    # ---- wall relief above and around: nested Deco chevrons, a sunburst plaque and a frieze
    for k, (h, wd) in enumerate(((0.95, 1.0), (1.25, 0.82), (1.55, 0.64))):
        apex = (0.0, h + 0.55)
        for s in (-1, 1):
            _bar(stone, apex, (s * wd, h), 0.09, -0.3, 0.06 + 0.02 * k, STONE)
    for k in range(9):   # sunburst rays below the chevrons
        a = math.radians(20 + k * 17.5)
        c = (0.0, 0.35)
        _bar(stone, c, (math.cos(a) * 0.95, 0.35 + math.sin(a) * 0.5), 0.045, -0.3, 0.035, STONE)
    for s in (-1, 1):    # vertical fluting on the corner pier either side
        for k in range(3):
            v = s * (1.0 + 0.16 * k)
            stone.box(-0.3, 0.04, v - 0.035, v + 0.035, -3.5, 2.6, STONE)
    zig = []             # zig-zag frieze band across the pier at w 2.7..3.1
    for k in range(12):
        v0 = -1.45 + k * 0.25
        _bar(stone, (v0, 2.75), (v0 + 0.125, 3.05), 0.05, -0.3, 0.05, STONE)
        _bar(stone, (v0 + 0.125, 3.05), (v0 + 0.25, 2.75), 0.05, -0.3, 0.05, STONE)
    stone.box(-0.3, 0.08, -1.5, 1.5, 2.62, 2.7, STONE)
    stone.box(-0.3, 0.08, -1.5, 1.5, 3.1, 3.18, STONE)
    loc = (base_x, y, z)
    me = steel.build("PERCH_prow", [MAT.get('steel_prow')])
    for p in me.polygons:
        p.use_smooth = False
    ob = new_object("PERCH_prow", me, col, loc=loc)
    m = bevel_mod(ob, width=0.022, segments=3, limit_angle=30)
    m.harden_normals = True
    me2 = stone.build("PERCH_stone", [MAT.get('tower_stone'), MAT.get('tower_stone')])
    at = me2.attributes.new('bcol', 'FLOAT_COLOR', 'FACE')
    for d in at.data:
        d.color = (0.50, 0.42, 0.30, 0.3)
    ob2 = new_object("PERCH_stone", me2, col, loc=loc)
    bevel_mod(ob2, width=0.012, segments=2)
    me3 = rivets.build("PERCH_rivets", [MAT.get('steel_prow')])
    ob3 = new_object("PERCH_rivets", me3, col, loc=loc)
    bevel_mod(ob3, width=0.006, segments=2)
    return ob


def perch_info(base_x, y, z):
    return dict(top_center=[base_x + PERCH_L / 2, y, z], outward=[1.0, 0.0, 0.0], size_outward=PERCH_L,
                size_across=2 * PERCH_HW, tip=[base_x + NOSE, y, z - 0.14], wall_x=base_x)
