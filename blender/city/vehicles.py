"""Vehicle prototypes v2: lofted rounded bodies with raked glass, pillars, wheel arches, tyres with
rims, mirrors, grilles, plates, lamp units; liveried vans/trucks; motorcycles and bicycle riders.
Front of every vehicle faces +Y. Overrides the earlier box prototypes by name."""
import math
import random

import materials as MAT
import protos as PR
from protos import cyl, _finish as _finish0


def _finish(mb, name, mats, bevel=0.0):
    """Weld coincident vertices so smooth-shaded body panels get averaged normals."""
    import bmesh
    me = _finish0(mb, name, mats, bevel=bevel)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    me.set_sharp_from_angle(angle=math.radians(40)) if hasattr(me, 'set_sharp_from_angle') else None
    return me
from cutil import MB

PAINT, GLASS, RUB, CHROME, HEAD, TAIL, SIGN, DARK, PLATE, RIM = range(10)
MATS = ['car_paint', 'car_glass', 'rubber', 'chrome', 'headlight', 'taillight', 'sign_white', 'room_dark', 'paint_white',
        'metal_alu']


def _profile(kind):
    """Side profile: list of (t in -1..1 along length, z_bottom, z_belt, z_top, plan half-width factor)."""
    if kind == 'sedan':
        # rear .. front
        return [(-1.0, 0.42, 0.78, 0.80, 0.80), (-0.96, 0.33, 0.90, 0.92, 0.94), (-0.85, 0.28, 0.95, 0.97, 1.0),
                (-0.62, 0.27, 0.96, 0.99, 1.0), (-0.48, 0.26, 0.96, 1.30, 1.0), (-0.36, 0.26, 0.96, 1.44, 1.0),
                (0.05, 0.26, 0.95, 1.46, 1.0), (0.22, 0.26, 0.94, 1.38, 1.0), (0.42, 0.27, 0.92, 1.0, 1.0),
                (0.70, 0.28, 0.88, 0.90, 1.0), (0.90, 0.32, 0.80, 0.82, 0.95), (1.0, 0.42, 0.66, 0.68, 0.80)]
    if kind == 'suv':
        return [(-1.0, 0.50, 0.95, 1.05, 0.85), (-0.95, 0.40, 1.05, 1.62, 0.96), (-0.85, 0.38, 1.07, 1.75, 1.0),
                (0.15, 0.38, 1.06, 1.78, 1.0), (0.35, 0.38, 1.05, 1.62, 1.0), (0.52, 0.38, 1.03, 1.12, 1.0),
                (0.85, 0.40, 1.00, 1.04, 0.98), (1.0, 0.50, 0.85, 0.88, 0.85)]
    if kind == 'hatch':
        return [(-1.0, 0.40, 0.85, 1.05, 0.85), (-0.94, 0.32, 0.93, 1.40, 0.97), (-0.82, 0.29, 0.95, 1.48, 1.0),
                (0.10, 0.28, 0.93, 1.48, 1.0), (0.30, 0.28, 0.91, 1.25, 1.0), (0.50, 0.29, 0.88, 0.94, 1.0),
                (0.88, 0.32, 0.80, 0.84, 0.95), (1.0, 0.42, 0.66, 0.70, 0.80)]
    if kind == 'pickup':
        return [(-1.0, 0.55, 1.02, 1.04, 0.95), (-0.95, 0.45, 1.05, 1.07, 1.0), (-0.12, 0.45, 1.05, 1.07, 1.0),
                (-0.10, 0.45, 1.06, 1.80, 1.0), (0.22, 0.45, 1.06, 1.82, 1.0), (0.38, 0.45, 1.06, 1.20, 1.0),
                (0.85, 0.45, 1.03, 1.08, 0.98), (1.0, 0.55, 0.88, 0.90, 0.88)]
    raise ValueError(kind)


def _interp(prof, t):
    for a, b in zip(prof[:-1], prof[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
            return tuple(a[i] + (b[i] - a[i]) * u for i in range(1, 5))
    return prof[-1][1:]


def _section(w, zb, zbelt, ztop, tumble=0.78):
    """Half section (x >= 0) from bottom centre round to top centre: 9 points."""
    green = ztop > zbelt + 0.12
    wt = w * tumble
    pts = [(0.0, zb), (w * 0.82, zb), (w * 0.98, zb + 0.10), (w, zb + (zbelt - zb) * 0.55), (w * 0.99, zbelt - 0.02)]
    if green:
        pts += [(w * 0.93, zbelt + 0.03), (wt, ztop - 0.07), (wt * 0.86, ztop), (0.0, ztop)]
    else:
        pts += [(w * 0.95, ztop - 0.005), (w * 0.85, ztop), (w * 0.4, ztop), (0.0, ztop)]
    return pts


def body(mb, kind, L, W, paint_slot=PAINT, cabin=None):
    prof = _profile(kind)
    n = 26
    ts = [math.sin(math.pi / 2 * (-1 + 2 * i / (n - 1))) for i in range(n)]
    rings = []
    for t in ts:
        zb, zbelt, ztop, pw = _interp(prof, t)
        sec = _section(W / 2 * pw, zb, zbelt, ztop)
        full = [(-x, z) for (x, z) in reversed(sec[1:-1])] + sec
        rings.append([(x, t * L / 2, z) for (x, z) in full] + [(-sec[-1][0], t * L / 2, sec[-1][1])])
    m = len(rings[0])
    # cabin y-range for glass
    gy = [t * L / 2 for t, _, zbelt, ztop, _ in prof if ztop > zbelt + 0.12]
    y0g, y1g = (min(gy), max(gy)) if gy else (0, 0)
    bpil = y0g + (y1g - y0g) * 0.52
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(m - 1):
            q = [a[i], a[i + 1], b[i + 1], b[i]]
            cx = sum(p[0] for p in q) / 4
            cy = sum(p[1] for p in q) / 4
            cz = sum(p[2] for p in q) / 4
            t = cy / (L / 2)
            zb, zbelt, ztop, pw = _interp(prof, t)
            mat = paint_slot
            if ztop > zbelt + 0.12 and zbelt + 0.04 < cz < ztop - 0.05:
                side = abs(cx) > W / 2 * 0.55
                pillar = side and (abs(cy - bpil) < 0.07 or abs(cy - y0g) < 0.12 or abs(cy - y1g) < 0.12)
                if not pillar:
                    mat = GLASS
            if cz < zb + 0.12 and abs(cx) < W / 2 * 0.9:
                mat = DARK
            mb.poly(q[::-1], mat, smooth=True)
    # end caps
    for r, flip in ((rings[0], False), (rings[-1], True)):
        mb.poly(r if flip else r[::-1], paint_slot)
    return prof


def wheel(mb, x, y, r=0.33, w=0.22, side=1):
    """Tyre with rounded shoulders + 5-spoke rim, axis along X."""
    n = 18
    prof = [(-w / 2, r * 0.80), (-w / 2, r * 0.93), (-w * 0.42, r), (w * 0.42, r), (w / 2, r * 0.93), (w / 2, r * 0.80)]
    for (xa, ra), (xb, rb) in zip(prof[:-1], prof[1:]):
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            q = [(x + xa, y + math.cos(a0) * ra, r + math.sin(a0) * ra), (x + xa, y + math.cos(a1) * ra, r + math.sin(a1) * ra),
                 (x + xb, y + math.cos(a1) * rb, r + math.sin(a1) * rb), (x + xb, y + math.cos(a0) * rb, r + math.sin(a0) * rb)]
            mb.poly(q if side > 0 else q[::-1], RUB, smooth=True)
    xf = x + side * w / 2 * 0.9
    # rim disc (dish) and spokes
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        tri = [(xf - side * 0.03, y, r), (xf, y + math.cos(a0) * r * 0.78, r + math.sin(a0) * r * 0.78),
               (xf, y + math.cos(a1) * r * 0.78, r + math.sin(a1) * r * 0.78)]
        mb.poly(tri if side > 0 else tri[::-1], DARK)
    for k in range(5):
        a = 2 * math.pi * k / 5
        ca, sa = math.cos(a), math.sin(a)
        p = [(xf + side * 0.005, y + ca * 0.06 - sa * 0.03, r + sa * 0.06 + ca * 0.03),
             (xf + side * 0.005, y + ca * 0.06 + sa * 0.03, r + sa * 0.06 - ca * 0.03),
             (xf + side * 0.005, y + ca * r * 0.74 + sa * 0.045, r + sa * r * 0.74 - ca * 0.045),
             (xf + side * 0.005, y + ca * r * 0.74 - sa * 0.045, r + sa * r * 0.74 + ca * 0.045)]
        mb.poly(p if side > 0 else p[::-1], RIM)
    cyl(mb, y, r, xf, xf + side * 0.01, 0.07, n=10, mat=RIM, axis='x')


def arch(mb, x, y, r, side):
    """Wheel opening: dark half-disc on the body side behind the tyre, with a lip."""
    n = 14
    R = r + 0.06
    xs = x + side * 0.002
    pts = [(xs, y + math.cos(math.pi * k / n) * R, r + math.sin(math.pi * k / n) * R) for k in range(n + 1)]
    pts = [(xs, y + R, 0.12)] + pts + [(xs, y - R, 0.12)]
    mb.poly(pts if side > 0 else pts[::-1], DARK)

def details(mb, L, W, prof, front_z, cab=False):
    y1, y0 = L / 2, -L / 2
    w = W / 2
    # head lamp units, grille, bumper, plate
    zb, zbelt, ztop, pw = _interp(prof, 0.97)
    zh = min(zbelt, ztop) - 0.12
    for s in (-1, 1):
        mb.box(s * w * 0.55 - 0.2, s * w * 0.55 + 0.2, y1 - 0.12, y1 - 0.04, zh - 0.06, zh + 0.05, HEAD)
        mb.box(s * w * 0.55 - 0.21, s * w * 0.55 + 0.21, y1 - 0.13, y1 - 0.06, zh - 0.07, zh + 0.06, CHROME)
    mb.box(-w * 0.32, w * 0.32, y1 - 0.1, y1 - 0.03, zh - 0.18, zh + 0.03, DARK)                        # grille
    mb.box(-w * 0.33, w * 0.33, y1 - 0.11, y1 - 0.025, zh + 0.03, zh + 0.045, CHROME)
    mb.box(-w * 0.9, w * 0.9, y1 - 0.2, y1 + 0.02, zb + 0.05, zb + 0.2, DARK)                         # bumper
    mb.box(-0.26, 0.26, y1 + 0.02, y1 + 0.03, zb + 0.08, zb + 0.19, PLATE)
    zb, zbelt, ztop, pw = _interp(prof, -0.97)
    zt = min(zbelt, ztop) - 0.12
    for s in (-1, 1):
        mb.box(s * w * 0.62 - 0.26, s * w * 0.62 + 0.26, y0 - 0.03, y0 + 0.12, zt - 0.08, zt + 0.07, TAIL)
        mb.box(s * w * 0.62 - 0.27, s * w * 0.62 + 0.27, y0 - 0.025, y0 + 0.11, zt - 0.09, zt + 0.08, DARK)
    mb.box(-w * 0.9, w * 0.9, y0 - 0.02, y0 + 0.2, zb + 0.05, zb + 0.2, DARK)
    mb.box(-0.26, 0.26, y0 - 0.03, y0 - 0.02, zb + 0.22, zb + 0.33, PLATE)
    # mirrors at the A pillar base
    gy = [t * L / 2 for t, _, zbl, zt_, _ in prof if zt_ > zbl + 0.12]
    if gy:
        ya = max(gy) - 0.1
        zbl = _interp(prof, ya / (L / 2))[1]
        for s in (-1, 1):
            mb.box(s * w * 0.97, s * (w + 0.17), ya - 0.06, ya + 0.04, zbl + 0.06, zbl + 0.17, DARK if not cab else PAINT)
    # door shut lines (thin dark strips on the sides)
    zb, zbelt, ztop, pw = _interp(prof, 0.0)
    for yy in (-0.15 * L / 2, 0.38 * L / 2):
        for s in (-1, 1):
            mb.box(s * (w + 0.002) - 0.004, s * (w + 0.002) + 0.004, yy - 0.006, yy + 0.006, zb + 0.15, zbelt - 0.03, DARK)


def _subdivided(mbb, name, mats, levels=1):
    """Catmull-Clark the welded body shell (curved panels), via a temporary object."""
    import bpy
    me = _finish(mbb, name + "_body", mats)
    ob = bpy.data.objects.new("_tmp_sub", me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new("s", 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    for poly in me2.polygons:
        poly.use_smooth = True
    return me2


def _join(me_a, me_b):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me_a)
    bm.from_mesh(me_b)
    bm.to_mesh(me_a)
    bm.free()
    return me_a


SPEC = {  # belt, roof, hood length, trunk/bed length, windscreen rake, rear-glass rake, sill z
    'sedan': (0.92, 1.44, 1.25, 0.95, 0.80, 0.55, 0.30),
    'hatch': (0.92, 1.48, 0.95, 0.22, 0.75, 0.25, 0.30),
    'suv': (1.08, 1.76, 1.00, 0.22, 0.62, 0.15, 0.40),
    'pickup': (1.08, 1.82, 1.40, 1.95, 0.55, 0.08, 0.45),
}


def _extrude_profile(mb, prof, w, mat):
    """Side profile (y, z) CCW extruded across x in [-w, w] as a closed solid."""
    n = len(prof)
    for i in range(n):
        a, b = prof[i], prof[(i + 1) % n]
        mb.poly([(w, a[0], a[1]), (w, b[0], b[1]), (-w, b[0], b[1]), (-w, a[0], a[1])], mat)
    mb.poly([(-w, p[0], p[1]) for p in prof], mat)
    mb.poly([(w, p[0], p[1]) for p in reversed(prof)], mat)


def _bevelled(mb, name, mats, offset, segs=3, glass_rule=False, taper=None):
    import bmesh
    me = _finish0(mb, name, mats)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    if taper:   # (z_from, z_to, scale at z_to): tumblehome / body-side curvature
        z0, z1, k = taper
        for v in bm.verts:
            t = min(1.0, max(0.0, (v.co.z - z0) / (z1 - z0)))
            v.co.x *= 1.0 - (1.0 - k) * t
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=offset, segments=segs, affect='EDGES', profile=0.5,
                    clamp_overlap=True)
    for f in bm.faces:
        f.smooth = True
        if glass_rule:
            nz, nx, ny = abs(f.normal.z), abs(f.normal.x), abs(f.normal.y)
            f.material_index = PAINT if (nz > 0.75 or (nx > 0.25 and ny > 0.25) or nz > 0.5 and ny < 0.3) else GLASS
    bm.to_mesh(me)
    bm.free()
    return me


def body2(name, kind, L, W, mats):
    """Lower body + greenhouse as two bevelled solids (clean rounded forms, no pinching)."""
    belt, roof, hood, trunk, rf, rr, zs = SPEC[kind]
    y0, y1 = -L / 2, L / 2
    w = W / 2
    lower = MB()
    nose = 0.72 if kind in ('sedan', 'hatch') else 0.85
    prof = [(y0 + 0.08, zs), (y1 - 0.12, zs), (y1, zs + 0.14), (y1 + 0.02, nose - 0.08), (y1 - 0.12, nose),
            (y1 - hood * 0.85, belt - 0.02), (y1 - hood, belt), (y0 + trunk, belt), (y0 + 0.12, belt - 0.03),
            (y0, belt - 0.12), (y0 - 0.02, zs + 0.15)]
    _extrude_profile(lower, prof, w, PAINT)
    me_l = _bevelled(lower, name + "_lo", mats, 0.08, 3, taper=(zs + 0.3, belt, 0.95))
    gh = MB()
    g0, g1 = y0 + trunk - 0.05, y1 - hood + 0.05
    gprof = [(g0, belt - 0.05), (g1, belt - 0.05), (g1 - rf, roof), (g0 + rr, roof)]
    _extrude_profile(gh, gprof, w * 0.9, GLASS)
    me_g = _bevelled(gh, name + "_gh", mats, 0.07, 3, glass_rule=True, taper=(belt, roof, 0.78))
    _join(me_l, me_g)
    import bpy
    bpy.data.meshes.remove(me_g)
    # B pillars + roof-rail seam
    mb = MB()
    ym = (g0 + rr + g1 - rf) / 2
    for s_ in (-1, 1):
        for (za, zb_, xa) in ((belt, (belt + roof) / 2, w * 0.9), ((belt + roof) / 2, roof - 0.06, w * 0.8)):
            x = s_ * (xa + 0.012)
            mb.box(min(x, x - s_ * 0.05), max(x, x - s_ * 0.05), ym - 0.05, ym + 0.05, za, zb_, PAINT)
        # character line along the body side
        x = s_ * (w * 0.985)
        mb.box(min(x, x + s_ * 0.012), max(x, x + s_ * 0.012), y0 + 0.4, y1 - 0.5, belt - 0.2, belt - 0.185, DARK)
    me_p = _finish0(mb, name + "_p", mats)
    _join(me_l, me_p)
    bpy.data.meshes.remove(me_p)
    return me_l


def car(name, kind, L, W, paint='car_paint', roof_sign=False):
    import bpy
    mats = list(MATS)
    mats[0] = paint
    prof = _profile(kind)
    me_body = body2(name, kind, L, W, mats)
    mb = MB()
    r = 0.34 if kind in ('sedan', 'hatch') else 0.40
    for yy in (-L / 2 + L * 0.19, L / 2 - L * 0.18):
        for s in (-1, 1):
            arch(mb, s * W / 2 * 0.975, yy, r, s)
            wheel(mb, s * (W / 2 - 0.09), yy, r=r, w=0.22, side=s)
    details(mb, L, W, prof, 0.7, cab=roof_sign)
    if kind == 'pickup':   # open load bed
        mb.box(-W / 2 + 0.08, W / 2 - 0.08, -L / 2 + 0.15, -0.12 * L / 2 - 0.1, 0.75, 1.075, DARK)
    if roof_sign:
        zt = SPEC[kind][1]
        mb.box(-0.3, 0.3, -0.08, 0.08, zt, zt + 0.2, SIGN)
        mb.box(-0.32, 0.32, -0.1, 0.1, zt - 0.005, zt + 0.02, DARK)
    me_det = _finish(mb, name, mats)
    _join(me_det, me_body)
    bpy.data.meshes.remove(me_body)
    return me_det


def _livery_quad(mb, x, y0, y1, z0, z1, side, ad):
    u0, v0, u1, v1 = ad['uv']
    if side > 0:
        pts = [(x, y1, z0), (x, y0, z0), (x, y0, z1), (x, y1, z1)]
    else:
        pts = [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
    mb.quad(*pts, mat=10, uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])


def boxtruck(name, L, W, H, cabL, paint, ad=None, step=False):
    mb = MB()
    w = W / 2
    y0, y1 = -L / 2, L / 2
    zb = 0.55
    # cab: raked windscreen, rounded front corners
    cy0 = y1 - cabL
    mb.box(-w, w, cy0, y1 - 0.25, zb, H * 0.62, PAINT)
    mb.poly([(-w, y1 - 0.25, zb), (w, y1 - 0.25, zb), (w, y1, zb + 0.1), (-w, y1, zb + 0.1)][::-1], PAINT)
    mb.box(-w + 0.05, w - 0.05, y1 - 0.25, y1, zb + 0.1, zb + 0.75, PAINT)
    ws = [(-w + 0.08, y1 - 0.02, zb + 0.78), (w - 0.08, y1 - 0.02, zb + 0.78), (w - 0.1, y1 - 0.42, H * 0.62 - 0.05),
          (-w + 0.1, y1 - 0.42, H * 0.62 - 0.05)]
    mb.poly(ws[::-1], GLASS)
    mb.poly([(-w, y1 - 0.25, zb + 0.75), (-w + 0.05, y1, zb + 0.75), (-w, y1 - 0.42, H * 0.62)], PAINT)
    mb.poly([(w, y1 - 0.42, H * 0.62), (w - 0.05, y1, zb + 0.75), (w, y1 - 0.25, zb + 0.75)], PAINT)
    for s in (-1, 1):
        x = s * (w + 0.004)
        q = [(x, cy0 + 0.25, zb + 0.85), (x, y1 - 0.45, zb + 0.85), (x, y1 - 0.6, H * 0.62 - 0.1), (x, cy0 + 0.25, H * 0.62 - 0.1)]
        mb.poly(q if s > 0 else q[::-1], GLASS)
        mb.box(s * w, s * (w + 0.22), y1 - 0.55, y1 - 0.45, H * 0.45, H * 0.58, DARK)   # mirror
    mb.box(-w * 0.6, w * 0.6, y1 - 0.01, y1 + 0.02, zb + 0.2, zb + 0.6, DARK)              # grille
    for s in (-1, 1):
        mb.box(s * w * 0.8 - 0.15, s * w * 0.8 + 0.15, y1, y1 + 0.03, zb + 0.35, zb + 0.55, HEAD)
    mb.box(-w, w, y1 - 0.05, y1 + 0.12, zb - 0.15, zb + 0.15, DARK)
    mb.box(-0.26, 0.26, y1 + 0.12, y1 + 0.13, zb - 0.1, zb + 0.02, PLATE)
    # cargo box
    by1 = cy0 - (0.12 if not step else -0.02)
    mb.box(-w - 0.05, w + 0.05, y0, by1, zb + 0.1, H, 11 if ad else PAINT)
    if ad:
        for s in (-1, 1):
            _livery_quad(mb, s * (w + 0.055), y0 + 0.3, by1 - 0.3, zb + 0.4, H - 0.25, s, ad)
    mb.box(-w - 0.06, w + 0.06, y0 - 0.06, y0, zb + 0.1, H, DARK)
    for s in (-1, 1):
        mb.box(s * w * 0.8 - 0.1, s * w * 0.8 + 0.1, y0 - 0.08, y0 - 0.06, zb + 0.3, zb + 0.6, TAIL)
    mb.box(-w, w, y0 - 0.1, y0 + 0.3, zb - 0.2, zb + 0.05, DARK)
    for yy in (y0 + 1.1, y1 - 0.85):
        for s in (-1, 1):
            arch(mb, s * w * 0.995, yy, 0.47, s)
            wheel(mb, s * (w - 0.12), yy, r=0.47, w=0.28, side=s)
    mats = list(MATS)
    mats[0] = paint
    mats.append('ad_print')
    mats.append('bus_paint')
    return _finish(mb, name, mats, bevel=0.035)


def bus(name):
    mb = MB()
    L, W, H = 12.2, 2.55, 3.2
    w = W / 2
    y0, y1 = -L / 2, L / 2
    zb = 0.35
    mb.box(-w, w, y0, y1, zb, H, 11)
    for s in (-1, 1):
        x = s * (w + 0.004)
        q = [(x, y0 + 0.8, 1.25), (x, y1 - 0.5, 1.25), (x, y1 - 0.5, H - 0.4), (x, y0 + 0.8, H - 0.4)]
        mb.poly(q if s > 0 else q[::-1], GLASS)
        for yy in range(-5, 6):
            mb.box(x - 0.01, x + 0.01, yy - 0.04, yy + 0.04, 1.25, H - 0.4, DARK)
        q = [(x, y0 + 0.5, 0.6), (x, y1 - 0.5, 0.6), (x, y1 - 0.5, 1.15), (x, y0 + 0.5, 1.15)]
        mb.poly(q if s > 0 else q[::-1], 12)
    mb.quad((w - 0.1, y1 + 0.005, 0.95), (-w + 0.1, y1 + 0.005, 0.95), (-w + 0.1, y1 + 0.005, H - 0.42), (w - 0.1, y1 + 0.005, H - 0.42), GLASS)
    mb.quad((w - 0.3, y1 + 0.01, H - 0.38), (-w + 0.3, y1 + 0.01, H - 0.38), (-w + 0.3, y1 + 0.01, H - 0.12), (w - 0.3, y1 + 0.01, H - 0.12), 13)
    for s in (-1, 1):
        mb.box(s * w * 0.75 - 0.15, s * w * 0.75 + 0.15, y1, y1 + 0.03, 0.6, 0.8, HEAD)
        mb.box(s * w * 0.8 - 0.1, s * w * 0.8 + 0.1, y0 - 0.03, y0, 0.6, 1.1, TAIL)
        mb.box(s * w, s * (w + 0.3), y1 - 0.3, y1 - 0.2, H - 0.9, H - 0.6, DARK)
    mb.box(-w, w, y1 - 0.05, y1 + 0.1, 0.25, 0.55, DARK)
    for yy in (y0 + 2.6, y1 - 2.4):
        for s in (-1, 1):
            arch(mb, s * w * 0.995, yy, 0.5, s)
            wheel(mb, s * (w - 0.13), yy, r=0.5, w=0.3, side=s)
    mats = list(MATS) + ['ad_print', 'bus_paint', 'paint_blue', 'sig_amber']
    return _finish(mb, name, mats, bevel=0.06)


def motorcycle(name, rider=True):
    mb = MB()
    for yy in (-0.72, 0.72):
        wheel(mb, -0.06, yy, r=0.31, w=0.12, side=1)
    mb.box(-0.12, 0.12, -0.45, 0.35, 0.35, 0.65, PAINT)        # engine/tank block
    mb.box(-0.14, 0.14, -0.1, 0.45, 0.62, 0.82, PAINT)         # tank
    mb.box(-0.13, 0.13, -0.75, -0.05, 0.72, 0.82, DARK)        # seat
    mb.box(-0.03, 0.03, 0.55, 0.72, 0.3, 0.95, CHROME)         # forks
    mb.box(-0.38, 0.38, 0.6, 0.66, 0.98, 1.02, DARK)           # bars
    mb.box(-0.1, 0.1, 0.72, 0.78, 0.82, 0.95, HEAD)
    mb.box(-0.08, 0.08, -0.88, -0.84, 0.72, 0.8, TAIL)
    if rider:
        _rider(mb, 0.0, -0.3, 0.82, (0.6, 0.2))
    mats = list(MATS) + ['cloth_var3', 'skin']
    return _finish(mb, name, mats)


def _rider(mb, x, y, zs, lean):
    CL, SK = 10, 11
    mb.box(x - 0.18, x + 0.18, y - 0.15, y + 0.15, zs, zs + 0.15, CL)                       # hips
    for s in (-1, 1):
        mb.box(x + s * 0.12 - 0.07, x + s * 0.12 + 0.07, y, y + 0.45, zs - 0.05, zs + 0.1, CL)   # thighs
        mb.box(x + s * 0.12 - 0.06, x + s * 0.12 + 0.06, y + 0.4, y + 0.5, zs - 0.45, zs, CL)    # shins
    # torso leaning forward
    import math as _m
    a = lean[0]
    for k in range(4):
        z0 = zs + 0.12 + k * 0.14
        yy = y + k * 0.14 * _m.tan(a)
        mb.box(x - 0.19, x + 0.19, yy - 0.12, yy + 0.12, z0, z0 + 0.15, CL)
    yy = y + 0.56 * _m.tan(a)
    for s in (-1, 1):
        mb.box(x + s * 0.22 - 0.05, x + s * 0.22 + 0.05, yy, yy + 0.5, zs + 0.5, zs + 0.58, CL)
    cyl(mb, x, yy + 0.05, zs + 0.72, zs + 0.95, 0.12, 0.1, n=10, mat=SK if lean[1] < 0.5 else DARK)


def bicycle_rider(name):
    mb = MB()
    for yy in (-0.55, 0.55):
        n = 18
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            p0 = (yy + math.cos(a0) * 0.34, 0.34 + math.sin(a0) * 0.34)
            p1 = (yy + math.cos(a1) * 0.34, 0.34 + math.sin(a1) * 0.34)
            mb.box(-0.015, 0.015, min(p0[0], p1[0]) - 0.015, max(p0[0], p1[0]) + 0.015, min(p0[1], p1[1]) - 0.015,
                   max(p0[1], p1[1]) + 0.015, RUB)
    for (a, b) in (((-0.55, 0.34), (-0.1, 0.8)), ((-0.1, 0.8), (0.45, 0.82)), ((0.45, 0.82), (0.55, 0.34)),
                   ((-0.55, 0.34), (0.0, 0.34)), ((0.0, 0.34), (-0.1, 0.8)), ((0.0, 0.34), (0.45, 0.82))):
        for i in range(6):
            y0 = a[0] + (b[0] - a[0]) * i / 6
            z0 = a[1] + (b[1] - a[1]) * i / 6
            y1 = a[0] + (b[0] - a[0]) * (i + 1) / 6
            z1 = a[1] + (b[1] - a[1]) * (i + 1) / 6
            mb.box(-0.02, 0.02, min(y0, y1) - 0.02, max(y0, y1) + 0.02, min(z0, z1) - 0.02, max(z0, z1) + 0.02, PAINT)
    mb.box(-0.28, 0.28, 0.45, 0.48, 1.0, 1.03, DARK)
    _rider(mb, 0.0, -0.15, 0.92, (0.45, 0.2))
    mats = list(MATS) + ['cloth_var3', 'skin']
    return _finish(mb, name, mats)


def register(ads):
    r = random.Random(3)
    PR.BUILD.update(
        sedan=lambda n: car(n, 'sedan', 4.75, 1.84),
        town_car=lambda n: car(n, 'sedan', 5.25, 1.9, paint='paint_black'),
        hatch=lambda n: car(n, 'hatch', 4.2, 1.78),
        suv=lambda n: car(n, 'suv', 4.95, 1.95),
        pickup=lambda n: car(n, 'pickup', 5.6, 2.0),
        cab=lambda n: car(n, 'sedan', 4.85, 1.85, paint='cab_yellow', roof_sign=True),
        cab_suv=lambda n: car(n, 'suv', 4.75, 1.9, paint='cab_yellow', roof_sign=True),
        van=lambda n: boxtruck(n, 6.0, 2.05, 2.7, 1.7, 'bus_paint', ad=ads[0], step=True),
        step_van=lambda n: boxtruck(n, 6.6, 2.3, 3.2, 1.3, 'paint_brown', ad=None, step=True),
        truck=lambda n: boxtruck(n, 8.0, 2.45, 3.5, 2.2, 'car_paint', ad=ads[1]),
        bus=bus,
        motorcycle=lambda n: motorcycle(n),
        bike_rider=bicycle_rider,
    )
