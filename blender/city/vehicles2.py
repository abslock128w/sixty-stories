"""Vehicles v5: subdivision-surface bodies from clean low-poly cages (Catmull-Clark applied at build).

Each body is a closed tube of cross-section rings (14 points per ring, never collapsed) lofted along Y
(front = +Y), with glass assigned on cage faces (side windows between pillars, windscreen and rear
glass) and smoothed by a Subdivision Surface modifier evaluated at build time. Details (lamp
clusters, wheels, interior, plates, handles, mirrors, contact shadow) come from vehicles.py.
"""
import math
import bpy
import bmesh

import vehicles as V
from vehicles import PAINT, GLASS, RUB, CHROME, HEAD, TAIL, SIGN, DARK, PLATE, RIM, MATS
from cutil import MB

EXT = ['sig_amber', 'paint_white', 'cloth_dark', 'cloth_var3', 'skin', 'contact_shadow', 'ad_print', 'bus_paint',
       'paint_blue']
AMBER, DRL, SEAT, TORSO, SKIN, SHADOW, ADP, BUSP, BLUE = range(10, 19)


def ring(w, zb, belt, ztop, wt):
    """Half ring from bottom centre to roof centre (10 points) with holding loops around the side glass."""
    z5 = max(belt + 0.05, ztop - 0.07)
    return [(0.0, zb), (0.86 * w, zb), (w, zb + 0.17), (w, belt - 0.09), (0.985 * w, belt),
            (0.98 * w - (0.985 * w - wt) * 0.04, belt + 0.012),
            (wt + (0.985 * w - wt) * 0.04, z5 - 0.008), (wt, z5), (0.62 * wt, ztop), (0.0, ztop + 0.01)]


def _lerp_st(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(6))


def _with_holding(stations, glass_side, glass_top, d=0.05):
    """Insert holding stations d metres inside both ends of every glass span so Catmull-Clark keeps the
    window shapes crisp. Returns (stations, side_spans, top_spans) re-indexed."""
    out, side, top = [stations[0]], set(), set()
    for i in range(len(stations) - 1):
        a, b = stations[i], stations[i + 1]
        g = i in glass_side or i in glass_top
        span = b[0] - a[0]
        if g and span > 4 * d:
            t0, t1 = d / span, 1 - d / span
            out.append(_lerp_st(a, b, t0))
            k = len(out) - 1
            out.append(_lerp_st(a, b, t1))
            if i in glass_side:
                side.add(k)
            if i in glass_top:
                top.add(k)
            out.append(b)
        else:
            if i in glass_side:
                side.add(len(out) - 1)
            if i in glass_top:
                top.add(len(out) - 1)
            out.append(b)
    return out, side, top


def cage(stations, glass_side, glass_top, name, mats, levels=2, dark_bottom=True):
    """stations: list of (y, w, zb, belt, ztop, wt). glass_side / glass_top: sets of span indices i (between
    station i and i+1) whose side band / top faces are glass. Returns a subdivided bpy mesh."""
    stations, glass_side, glass_top = _with_holding(stations, glass_side, glass_top)
    bm = bmesh.new()
    rings = []
    for (y, w, zb, belt, ztop, wt) in stations:
        half = ring(w, zb, belt, ztop, wt)
        full = half + [(-x, z) for (x, z) in reversed(half[1:-1])]
        rings.append([bm.verts.new((x, y, z)) for (x, z) in full])
    n = len(rings[0])
    nh = 9                   # segments per half

    def seg_of(j):
        return j if j < nh else (n - 1 - j)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(n):
            jj = (j + 1) % n
            f = bm.faces.new((a[j], a[jj], b[jj], b[j]))
            sg = seg_of(j)
            mat = PAINT
            if sg == 0 and dark_bottom:
                mat = DARK
            elif sg == 5 and i in glass_side:
                mat = GLASS
            elif sg in (7, 8) and i in glass_top:
                mat = GLASS
            f.material_index = mat
    f0 = bm.faces.new(list(reversed(rings[0])))
    f1 = bm.faces.new(rings[-1])
    f0.material_index = f1.material_index = PAINT
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_cage")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(bpy.data.materials.get(m) if isinstance(m, str) else m)
    ob = bpy.data.objects.new("_tmp_cage", me)
    bpy.context.scene.collection.objects.link(ob)
    md = ob.modifiers.new("s", 'SUBSURF')
    md.levels = levels
    md.render_levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    for p in me2.polygons:
        p.use_smooth = True
    return me2


# ----------------------------------------------------------------- body designs
def sedan_stations(L, W):
    w = W / 2
    s = L / 4.8
    return [(-2.40 * s, w * 0.80, 0.42, 0.80, 0.84, w * 0.78),
            (-2.28 * s, w * 0.93, 0.32, 0.93, 0.97, w * 0.90),
            (-1.85 * s, w, 0.30, 0.99, 1.01, w * 0.92),
            (-1.12 * s, w, 0.30, 0.99, 1.43, w * 0.76),
            (-0.26 * s, w, 0.30, 0.99, 1.46, w * 0.77),
            (-0.13 * s, w, 0.30, 0.99, 1.46, w * 0.77),
            (0.52 * s, w, 0.30, 0.98, 1.43, w * 0.77),
            (1.32 * s, w, 0.30, 0.95, 0.98, w * 0.93),
            (2.05 * s, w * 0.95, 0.31, 0.86, 0.89, w * 0.90),
            (2.40 * s, w * 0.80, 0.40, 0.70, 0.74, w * 0.78)], {3, 5, 6}, {2, 6}


def crossover_stations(L, W):
    """Crossover / compact-MPV taxi: short hood, tall cabin, near-vertical tailgate."""
    w = W / 2
    s = L / 4.7
    return [(-2.35 * s, w * 0.84, 0.45, 1.00, 1.72, w * 0.80),
            (-2.22 * s, w * 0.97, 0.38, 1.06, 1.80, w * 0.86),
            (-1.40 * s, w, 0.37, 1.06, 1.82, w * 0.86),
            (-0.40 * s, w, 0.37, 1.06, 1.83, w * 0.86),
            (-0.27 * s, w, 0.37, 1.06, 1.83, w * 0.86),
            (0.75 * s, w, 0.37, 1.05, 1.80, w * 0.85),
            (1.45 * s, w, 0.38, 1.02, 1.08, w * 0.93),
            (2.10 * s, w * 0.95, 0.40, 0.95, 0.99, w * 0.90),
            (2.35 * s, w * 0.82, 0.46, 0.80, 0.85, w * 0.80)], {1, 2, 4, 5}, {5}


def van_stations(L, W):
    """Panel van (cab glass only at the front, flat sides behind)."""
    w = W / 2
    s = L / 6.0
    return [(-3.00 * s, w * 0.92, 0.50, 1.15, 2.42, w * 0.90),
            (-2.88 * s, w, 0.42, 1.18, 2.52, w * 0.95),
            (1.30 * s, w, 0.42, 1.18, 2.55, w * 0.95),
            (1.95 * s, w, 0.42, 1.15, 2.30, w * 0.92),
            (2.45 * s, w * 0.98, 0.42, 1.10, 1.25, w * 0.95),
            (2.90 * s, w * 0.94, 0.44, 1.00, 1.05, w * 0.90),
            (3.00 * s, w * 0.84, 0.50, 0.90, 0.94, w * 0.82)], {2}, {3}


def truck_cab_stations(W, y0, y1):
    w = W / 2
    L = y1 - y0
    return [(y0, w * 0.97, 0.55, 1.45, 3.05, w * 0.96),
            (y0 + 0.08, w, 0.55, 1.45, 3.10, w * 0.97),
            (y0 + L * 0.45, w, 0.55, 1.45, 3.08, w * 0.96),
            (y1 - 0.45, w, 0.55, 1.42, 2.80, w * 0.94),
            (y1 - 0.12, w * 0.98, 0.55, 1.35, 1.45, w * 0.95),
            (y1, w * 0.92, 0.58, 1.25, 1.30, w * 0.88)], {1, 2}, {3}


# ----------------------------------------------------------------- assemblies
def car(name, design, L, W, paint='car_paint', roof_sign=False, driver=True):
    mats = list(MATS)
    mats[0] = paint
    mats += EXT
    st, gs, gt = design(L, W)
    body = cage(st, gs, gt, name, mats)
    belt = max(s[3] for s in st)
    roof = max(s[4] for s in st)
    w = W / 2
    y0, y1 = st[0][0], st[-1][0]
    # lamp clusters tucked into the body corners
    for front in (True, False):
        end = st[-2] if front else st[1]          # station just inside the bumper end
        mc = V._cluster(name, (y1 - y0) - 0.1, W * 0.9, end[3] + (0.02 if front else -0.02), mats, front)
        V._join(body, mc)
        bpy.data.meshes.remove(mc)
    mb = MB()
    r = 0.36 if roof < 1.6 else 0.39
    yf, yr = y1 - (y1 - y0) * 0.19, y0 + (y1 - y0) * 0.18
    for yy in (yr, yf):
        for s_ in (-1, 1):
            V.arch(mb, s_ * (w * 0.985), yy, r, s_)
            V.wheel(mb, s_ * (w - 0.09), yy, r=r, w=0.23, side=s_)
    hood = y1 - [s[0] for s in st if s[4] > s[3] + 0.2][-1]
    trunk = [s[0] for s in st if s[4] > s[3] + 0.2][0] - y0
    V._cabin(mb, L, W * 0.98, belt, roof, hood, trunk, driver=driver)
    # grille, bumpers (rounded via bevel later), plates
    zb = 0.38
    mb.box(-w * 0.5, w * 0.5, y1 - 0.2, y1 - 0.1, belt - 0.4, belt - 0.24, DARK)          # grille (set into nose)
    mb.box(-0.26, 0.26, y1 - 0.035, y1 - 0.02, zb + 0.06, zb + 0.17, PLATE)
    mb.box(-0.26, 0.26, y0 + 0.02, y0 + 0.035, zb + 0.24, zb + 0.35, PLATE)
    mb.box(-w * 0.85, w * 0.85, y0 + 0.03, y0 + 0.3, zb - 0.02, zb + 0.12, DARK)              # rear diffuser
    if roof > 1.65:   # crossover tailgate glass + rear wiper
        mb.box(-w * 0.7, w * 0.7, y0 + 0.02, y0 + 0.06, belt + 0.1, roof - 0.16, GLASS)
        mb.box(-0.02, 0.35, y0 + 0.1, y0 + 0.11, belt + 0.12, belt + 0.14, DARK)
    # mirrors: stalk + rounded housing hugging the A-pillar base (no free-floating blocks)
    ya = [s[0] for s in st if s[4] > s[3] + 0.2][-1] - 0.05
    for s_ in (-1, 1):
        x0 = s_ * (w * 0.93)
        mb.box(min(x0, x0 + s_ * 0.1), max(x0, x0 + s_ * 0.1), ya - 0.03, ya + 0.02, belt + 0.04, belt + 0.07, DARK)
        mb.box(min(x0 + s_ * 0.08, x0 + s_ * 0.2), max(x0 + s_ * 0.08, x0 + s_ * 0.2), ya - 0.07, ya + 0.02, belt + 0.03,
               belt + 0.16, PAINT)
        mb.box(min(x0 + s_ * 0.09, x0 + s_ * 0.19), max(x0 + s_ * 0.09, x0 + s_ * 0.19), ya - 0.075, ya - 0.065,
               belt + 0.045, belt + 0.145, CHROME)
    # door handles + shut lines
    for yy in (0.08 * L, -0.22 * L):
        for s_ in (-1, 1):
            x = s_ * (w * 0.985)
            mb.box(min(x, x + s_ * 0.022), max(x, x + s_ * 0.022), yy - 0.1, yy + 0.05, belt - 0.13, belt - 0.095, CHROME)
    if roof_sign:
        mb.box(-0.32, 0.32, -0.09, 0.09, roof, roof + 0.2, SIGN)
        mb.box(-0.34, 0.34, -0.11, 0.11, roof - 0.01, roof + 0.02, DARK)
    mb.quad((-w - 0.25, y0 - 0.3, 0.012), (w + 0.25, y0 - 0.3, 0.012), (w + 0.25, y1 + 0.3, 0.012), (-w - 0.25, y1 + 0.3, 0.012),
            mat=SHADOW)
    det = V._finish(mb, name, mats, bevel=0.015)
    V._join(det, body)
    bpy.data.meshes.remove(body)
    return det


def van(name, L, W, paint, ad=None):
    mats = list(MATS)
    mats[0] = paint
    mats += EXT
    st, gs, gt = van_stations(L, W)
    body = cage(st, gs, gt, name, mats)
    w = W / 2
    y0, y1 = st[0][0], st[-1][0]
    mb = MB()
    for yy in (y0 + 1.0, y1 - 0.95):
        for s_ in (-1, 1):
            V.arch(mb, s_ * w * 0.985, yy, 0.37, s_)
            V.wheel(mb, s_ * (w - 0.09), yy, r=0.37, w=0.24, side=s_)
    if ad:
        for s_ in (-1, 1):
            V._livery_quad(mb, s_ * (w + 0.012), y0 + 0.5, y1 - 2.2, 1.3, 2.2, s_, ad, mat=ADP)
    for s_ in (-1, 1):
        mb.box(s_ * w * 0.62 - 0.18, s_ * w * 0.62 + 0.18, y1 - 0.24, y1 - 0.13, 0.85, 1.0, HEAD)
        mb.box(s_ * (w - 0.12), s_ * (w - 0.02), y0 - 0.03, y0 + 0.05, 1.0, 1.5, TAIL)
        x0 = s_ * w * 0.95
        mb.box(min(x0, x0 + s_ * 0.24), max(x0, x0 + s_ * 0.24), y1 - 1.1, y1 - 1.0, 1.55, 1.85, DARK)
    mb.box(-w * 0.6, w * 0.6, y1 - 0.22, y1 - 0.12, 0.6, 0.82, DARK)
    mb.box(-w * 0.9, w * 0.9, y1 - 0.34, y1 - 0.1, 0.4, 0.56, DARK)
    mb.box(-w * 0.9, w * 0.9, y0 + 0.08, y0 + 0.3, 0.42, 0.56, DARK)
    mb.box(-0.26, 0.26, y1 - 0.1, y1 - 0.09, 0.41, 0.53, PLATE)
    V._cabin(mb, L, W * 0.97, 1.15, 2.4, 0.9, 4.0, driver=True)
    mb.quad((-w - 0.3, y0 - 0.3, 0.012), (w + 0.3, y0 - 0.3, 0.012), (w + 0.3, y1 + 0.3, 0.012), (-w - 0.3, y1 + 0.3, 0.012),
            mat=SHADOW)
    det = V._finish(mb, name, mats, bevel=0.015)
    V._join(det, body)
    bpy.data.meshes.remove(body)
    return det


def truck(name, L, W, H, cabL, paint, ad=None):
    mats = list(MATS)
    mats[0] = paint
    mats += EXT
    w = W / 2
    y0, y1 = -L / 2, L / 2
    st, gs, gt = truck_cab_stations(W, y1 - cabL, y1)
    body = cage(st, gs, gt, name, mats)
    mb = MB()
    by1 = y1 - cabL - 0.1
    mb.box(-w - 0.06, w + 0.06, y0, by1, 0.85, H, BUSP)                                 # cargo box
    for k in range(int((by1 - y0) / 0.6)):                                             # side ribs
        yy = y0 + 0.3 + k * 0.6
        for s_ in (-1, 1):
            mb.box(s_ * (w + 0.06), s_ * (w + 0.075), yy - 0.02, yy + 0.02, 0.9, H - 0.05, BUSP)
    if ad:
        for s_ in (-1, 1):
            V._livery_quad(mb, s_ * (w + 0.08), y0 + 0.4, by1 - 0.4, 1.2, H - 0.3, s_, ad, mat=ADP)
    mb.box(-w - 0.07, w + 0.07, y0 - 0.06, y0, 0.85, H, DARK)                         # rear doors frame
    mb.box(-0.02, 0.02, y0 - 0.07, y0 - 0.06, 0.9, H - 0.05, CHROME)
    mb.box(-w, w, y0 - 0.25, y0 + 0.2, 0.45, 0.62, DARK)                              # under-ride bar
    mb.box(-w * 0.9, w * 0.9, y0 + 0.2, y1 - 0.4, 0.55, 0.85, DARK)                   # chassis
    for s_ in (-1, 1):
        mb.box(s_ * w * 0.8 - 0.12, s_ * w * 0.8 + 0.12, y0 - 0.08, y0 - 0.06, 0.95, 1.25, TAIL)
        mb.box(s_ * w * 0.62 - 0.2, s_ * w * 0.62 + 0.2, y1 - 0.06, y1 + 0.005, 0.95, 1.15, HEAD)
        x0 = s_ * w * 0.96
        mb.box(min(x0, x0 + s_ * 0.3), max(x0, x0 + s_ * 0.3), y1 - 0.5, y1 - 0.42, 2.0, 2.5, DARK)   # mirror
        mb.box(min(x0 + s_ * 0.05, x0 + s_ * 0.3), max(x0 + s_ * 0.05, x0 + s_ * 0.3), y1 - 2.15, y1 - 1.55, 0.62, 0.95, CHROME)  # fuel tank
    mb.box(-w * 0.7, w * 0.7, y1 - 0.06, y1 + 0.01, 0.75, 1.3, DARK)                  # grille
    mb.box(-w, w, y1 - 0.15, y1 + 0.1, 0.45, 0.72, DARK)
    mb.box(-0.26, 0.26, y1 + 0.1, y1 + 0.11, 0.5, 0.62, PLATE)
    for yy in (y0 + 1.2, y1 - 0.95):
        for s_ in (-1, 1):
            V.arch(mb, s_ * w * 0.99, yy, 0.5, s_)
            V.wheel(mb, s_ * (w - 0.12), yy, r=0.5, w=0.3, side=s_)
    mb.quad((-w - 0.3, y0 - 0.3, 0.012), (w + 0.3, y0 - 0.3, 0.012), (w + 0.3, y1 + 0.3, 0.012), (-w - 0.3, y1 + 0.3, 0.012),
            mat=SHADOW)
    det = V._finish(mb, name, mats, bevel=0.03)
    V._join(det, body)
    bpy.data.meshes.remove(body)
    return det


def bus(name):
    """Low-floor city bus: subdivided body shell with a glazed belt, curved front, doors, wheels."""
    L, W = 12.2, 2.55
    w = W / 2
    mats = list(MATS) + EXT
    mats[0] = 'bus_paint'
    st = [(-6.10, w * 0.95, 0.40, 1.15, 3.05, w * 0.93),
          (-5.95, w, 0.32, 1.18, 3.15, w * 0.97),
          (-5.20, w, 0.32, 1.18, 3.18, w * 0.97),
          (4.80, w, 0.32, 1.18, 3.18, w * 0.97),
          (5.85, w, 0.32, 1.15, 3.12, w * 0.96),
          (6.10, w * 0.95, 0.38, 1.0, 2.95, w * 0.92)]
    body = cage(st, {2, 3}, set(), name, mats, levels=2)
    mb = MB()
    y0, y1 = -6.1, 6.1
    # windscreen (curved front glass panel), destination sign, livery stripe, doors
    mb.box(-w * 0.86, w * 0.86, y1 - 0.02, y1 + 0.03, 1.05, 2.75, GLASS)
    mb.box(-w * 0.7, w * 0.7, y1 - 0.02, y1 + 0.035, 2.8, 3.0, AMBER)
    for s_ in (-1, 1):
        x = s_ * (w + 0.008)
        q = [(x, y0 + 0.5, 0.55), (x, y1 - 0.5, 0.55), (x, y1 - 0.5, 0.95), (x, y0 + 0.5, 0.95)]
        mb.poly(q if s_ > 0 else q[::-1], BLUE)
        for yy in (-4.2, -2.4, -0.6, 1.2, 3.0):                                       # window mullions
            mb.box(min(x, x - s_ * 0.03), max(x, x - s_ * 0.03), yy - 0.05, yy + 0.05, 1.2, 2.95, DARK)
        mb.box(s_ * w, s_ * (w + 0.35), y1 - 0.4, y1 - 0.3, 2.3, 2.45, DARK)            # mirror arm
        mb.box(s_ * (w + 0.3), s_ * (w + 0.35), y1 - 0.42, y1 - 0.2, 1.8, 2.4, DARK)
    for yy in (4.6, -0.3):                                                             # doors (right side)
        mb.box(w - 0.01, w + 0.012, yy - 0.6, yy + 0.6, 0.35, 2.85, GLASS)
        mb.box(w + 0.012, w + 0.02, yy - 0.02, yy + 0.02, 0.35, 2.85, DARK)
    for s_ in (-1, 1):
        mb.box(s_ * w * 0.75 - 0.15, s_ * w * 0.75 + 0.15, y1 - 0.02, y1 + 0.04, 0.6, 0.78, HEAD)
        mb.box(s_ * w * 0.8 - 0.1, s_ * w * 0.8 + 0.1, y0 - 0.04, y0 + 0.02, 0.6, 1.15, TAIL)
    mb.box(-w, w, y1 - 0.12, y1 + 0.12, 0.25, 0.55, DARK)
    mb.box(-w, w, y0 - 0.12, y0 + 0.12, 0.25, 0.55, DARK)
    mb.box(-w * 0.9, w * 0.9, -3.0, 3.0, 3.15, 3.45, BUSP)                              # roof pods (HVAC)
    for yy in (y0 + 2.6, y1 - 2.4):
        for s_ in (-1, 1):
            V.arch(mb, s_ * w * 0.99, yy, 0.5, s_)
            V.wheel(mb, s_ * (w - 0.12), yy, r=0.5, w=0.3, side=s_)
    mb.quad((-w - 0.3, y0 - 0.3, 0.012), (w + 0.3, y0 - 0.3, 0.012), (w + 0.3, y1 + 0.3, 0.012), (-w - 0.3, y1 + 0.3, 0.012),
            mat=SHADOW)
    det = V._finish(mb, name, mats, bevel=0.03)
    V._join(det, body)
    bpy.data.meshes.remove(body)
    return det


def register(ads):
    import protos as PR
    PR.BUILD.update(
        sedan=lambda n: car(n, sedan_stations, 4.8, 1.86),
        town_car=lambda n: car(n, sedan_stations, 5.2, 1.9, paint='paint_black'),
        hatch=lambda n: car(n, crossover_stations, 4.3, 1.8),
        suv=lambda n: car(n, crossover_stations, 4.8, 1.92),
        cab=lambda n: car(n, sedan_stations, 4.85, 1.86, paint='cab_yellow', roof_sign=True),
        cab_suv=lambda n: car(n, crossover_stations, 4.7, 1.88, paint='cab_yellow', roof_sign=True),
        van=lambda n: van(n, 6.0, 2.05, 'bus_paint', ad=ads[0]),
        step_van=lambda n: van(n, 6.0, 2.1, 'paint_brown'),
        truck=lambda n: truck(n, 8.0, 2.45, 3.5, 2.2, 'car_paint', ad=ads[1]),
        bus=bus,
    )
