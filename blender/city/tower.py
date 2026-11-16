"""THE TOWER: 60-storey Art Deco masonry skyscraper with a stone eagle gargoyle perch."""
import math
import random
import bpy
import bmesh

import materials as MAT
import buildings as BD
import lighting
from cutil import MB, new_object, bevel_mod
import layout as LY

T = LY.TOWER
EAST_X = T['x1']           # -16: east face glass plane = avenue west wall
TIERS = [
    dict(poly=BD.rect(-76.0, EAST_X, -332.0, -268.0), z0=0.0, z1=32.0),
    dict(poly=BD.rect(-72.0, EAST_X, -328.0, -272.0), z0=32.0, z1=152.0),
    dict(poly=BD.rect(-64.0, EAST_X, -321.0, -279.0), z0=152.0, z1=196.0),
    dict(poly=BD.rect(-54.0, EAST_X, -314.0, -286.0), z0=196.0, z1=240.0),
]
PERCH_Z = 228.0
PIER_DP = 0.55
GARG_Y = -287.7
GARG_BASE_X = EAST_X + PIER_DP          # pier front
SECTIONS = [  # body + head (u outward from pier face, half width, z_bottom, z_top), perch top = 0
    (-0.35, 0.64, -1.60, 0.0),
    (0.00, 0.62, -1.55, 0.0),
    (0.50, 0.59, -1.42, 0.0),
    (1.00, 0.55, -1.26, 0.0),
    (1.45, 0.50, -1.10, 0.0),
    (1.75, 0.45, -1.00, 0.0),
    (1.90, 0.40, -0.95, 0.08),
    (2.05, 0.36, -0.90, 0.19),
    (2.22, 0.32, -0.84, 0.22),
    (2.38, 0.28, -0.78, 0.17),
    (2.48, 0.24, -0.72, 0.08),
]
BEAK = [  # separate horn-like beak overlapping the head front (crisp junction line)
    (2.26, 0.25, -0.64, 0.14),
    (2.45, 0.235, -0.62, 0.12),
    (2.62, 0.205, -0.63, 0.07),
    (2.77, 0.15, -0.69, -0.08),
    (2.89, 0.10, -0.79, -0.27),
    (2.96, 0.06, -0.92, -0.47),
    (2.99, 0.03, -1.04, -0.66),
    (2.985, 0.012, -1.10, -0.80),
]


def tower_params():
    rng = random.Random(1)
    P = BD.style_params('deco', rng, 240.0)
    P.update(sh=4.0, gh=8.0, bay=2.05, pw=0.62, cw=3.2, dp=PIER_DP, ds=0.24, sill=0.85, head=3.15,
             wall='tower_stone', trim='trim', spandrel='tower_spandrel', cornice=0.45, major_every=3,
             frames_z=8.0, blind_p=0.35, cool_p=0.25, sills=True, lintels=False, pairs=False)
    return P


def build_tower(cols, lidx, protos_out):
    spec = dict(id=0, style='deco', seed=4242, lot=(T['x0'], T['x1'], T['y0'], T['y1']), height=240.0,
                kind='tower', ring='near', name='THE_TOWER')
    P = tower_params()
    tiers = [dict(t, inset=i > 0) for i, t in enumerate(TIERS)]
    bcol = (0.52, 0.43, 0.30, 0.3)
    me = BD.build_near(spec, lidx, protos_out, P=P, tiers=tiers, crown=None, bcol=bcol)
    me.name = "TOWER_body"
    ob = new_object("TOWER_body", me, cols['hero'])
    crown_top = build_crown(cols['hero'])
    import ornament
    ornament.build(cols['hero'], GARG_BASE_X, GARG_Y, PERCH_Z)
    build_lights(cols['hero'])
    spec['top_z'] = crown_top
    spec['roof_z'] = 240.0
    return spec


# ----------------------------------------------------------------- crown
def build_crown(col):
    mb = MB(attrs=('bcol',))
    A = {'bcol': (0.6, 0.55, 0.48, 0.3)}
    steps = [
        ((-51.0, -19.0, -311.0, -289.0), 240.0, 247.0, 0, 0.0),
        ((-47.0, -23.0, -308.0, -292.0), 247.0, 255.0, 1, 3.6),
        ((-43.0, -27.0, -305.0, -295.0), 255.0, 262.0, 1, 3.0),
        ((-39.5, -30.5, -302.5, -297.5), 262.0, 268.0, 1, 2.4),
    ]
    for (x0, x1, y0, y1), z0, z1, mat, gable in steps:
        mb.box(x0, x1, y0, y1, z0, z1, mat, skip=('-z',), attrs=A)
        # vertical ribs
        for (xa, xb, ya, yb, nx, ny) in ((x0, x1, y0, y0, 0, -1), (x0, x1, y1, y1, 0, 1), (x0, x0, y0, y1, -1, 0), (x1, x1, y0, y1, 1, 0)):
            L = math.hypot(xb - xa, yb - ya)
            nr = max(2, int(L / 2.0))
            for k in range(nr + 1):
                t = k / nr
                px, py = xa + (xb - xa) * t, ya + (yb - ya) * t
                if nx == 0:
                    mb.box(px - 0.2, px + 0.2, py, py + ny * 0.35, z0, z1 + 0.4, mat, attrs=A, skip=('-z',))
                else:
                    mb.box(px, px + nx * 0.35, py - 0.2, py + 0.2, z0, z1 + 0.4, mat, attrs=A, skip=('-z',))
        if gable > 0:
            # zig-zag gables on each face, with lit triangular windows
            for (xa, ya, xb, yb, nx, ny) in ((x0, y0, x1, y0, 0, -1), (x1, y0, x1, y1, 1, 0), (x1, y1, x0, y1, 0, 1), (x0, y1, x0, y0, -1, 0)):
                L = math.hypot(xb - xa, yb - ya)
                ng = max(2, int(round(L / (gable * 1.6))))
                for k in range(ng):
                    t0, t1 = k / ng, (k + 1) / ng
                    a = (xa + (xb - xa) * t0, ya + (yb - ya) * t0)
                    b = (xa + (xb - xa) * t1, ya + (yb - ya) * t1)
                    m_ = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    mb.poly([(a[0], a[1], z1), (b[0], b[1], z1), (m_[0], m_[1], z1 + gable)], 1, None, A)
                    mb.poly([(b[0], b[1], z1), (a[0], a[1], z1), (m_[0], m_[1], z1 + gable)], 1, None, A)
                    # triangular window inset slightly in front
                    o = 0.03
                    sh = 0.55
                    ca = (a[0] + (m_[0] - a[0]) * sh * 0.6 + nx * o, a[1] + (m_[1] - a[1]) * sh * 0.6 + ny * o)
                    cb = (b[0] + (m_[0] - b[0]) * sh * 0.6 + nx * o, b[1] + (m_[1] - b[1]) * sh * 0.6 + ny * o)
                    mb.poly([(ca[0], ca[1], z1 + 0.3), (cb[0], cb[1], z1 + 0.3), (m_[0] + nx * o, m_[1] + ny * o, z1 + gable * 0.68)], 2, None, A)
    # spire
    cx, cy = -35.0, -300.0
    n = 8
    r0, z0, z1 = 1.7, 268.0, 306.0
    ring = [(cx + r0 * math.cos(2 * math.pi * k / n), cy + r0 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    mid = [(cx + 0.7 * r0 * math.cos(2 * math.pi * k / n), cy + 0.7 * r0 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        c, d = mid[k], mid[(k + 1) % n]
        mb.quad((a[0], a[1], z0), (b[0], b[1], z0), (d[0], d[1], z0 + 8), (c[0], c[1], z0 + 8), 1, None, A)
        mb.poly([(c[0], c[1], z0 + 8), (d[0], d[1], z0 + 8), (cx, cy, z1)], 1, None, A)
    me = mb.build("TOWER_crown", [MAT.get('tower_stone'), MAT.get('steel_deco'), MAT.get('flood')])
    ob = new_object("TOWER_crown", me, col)
    return z1


# ----------------------------------------------------------------- gargoyle
def _ring(hw, zb, zt):
    """Cross-section ring (v, w) CCW when looking along +u; flat top with support loops."""
    H = zt - zb
    return [(-hw, zt), (-hw * 0.96, zt - 0.03), (-hw * 0.98, zt - H * 0.35), (-hw * 0.82, zb + H * 0.18),
            (-hw * 0.45, zb + 0.02), (0.0, zb), (hw * 0.45, zb + 0.02), (hw * 0.82, zb + H * 0.18),
            (hw * 0.98, zt - H * 0.35), (hw * 0.96, zt - 0.03), (hw, zt), (hw * 0.5, zt), (0.0, zt), (-hw * 0.5, zt)]


def _loft(sections, name, col, ring=None, levels=3, disp=0.012):
    ring = ring or _ring
    bm = bmesh.new()
    rings = []
    for (u, hw, zb, zt) in sections:
        rings.append([bm.verts.new((u, v, w)) for (v, w) in ring(hw, zb, zt)])
    n = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(MAT.get('gargoyle'))
    ob = new_object(name, me, col, loc=(GARG_BASE_X, GARG_Y, PERCH_Z))
    sub = ob.modifiers.new("subd", 'SUBSURF')
    sub.levels = 1
    sub.render_levels = levels
    tex = bpy.data.textures.get("garg_pits") or bpy.data.textures.new("garg_pits", 'CLOUDS')
    tex.noise_scale = 0.06
    tex.noise_depth = 3
    dsp = ob.modifiers.new("weather", 'DISPLACE')
    dsp.texture = tex
    dsp.texture_coords = 'GLOBAL'
    dsp.strength = disp
    dsp.mid_level = 0.5
    return ob


def _beak_ring(hw, zb, zt):
    """Keeled beak: narrow ridge on top, flat cheeks, rounded underside."""
    H = zt - zb
    return [(0.0, zt), (hw * 0.55, zt - H * 0.08), (hw * 0.95, zt - H * 0.35), (hw, zb + H * 0.35),
            (hw * 0.7, zb + H * 0.06), (0.0, zb), (-hw * 0.7, zb + H * 0.06), (-hw, zb + H * 0.35),
            (-hw * 0.95, zt - H * 0.35), (-hw * 0.55, zt - H * 0.08)]


def build_gargoyle(col):
    ob = _loft(SECTIONS, "GARGOYLE", col, levels=3)
    _loft(BEAK, "GARGOYLE_beak", col, ring=_beak_ring, levels=2, disp=0.006)
    # feathers, corbels, eyes, brow: separate bevelled pieces (same local frame)
    mb = MB()
    # plumage: thin tapered feather blades in staggered layers along each flank (Deco stepped plumage)
    for side in (-1, 1):
        for r, (w, u1) in enumerate(((-0.16, 1.80), (-0.36, 1.55), (-0.56, 1.30), (-0.76, 1.05), (-0.96, 0.80), (-1.16, 0.55))):
            hw = SECTIONS[2][1] - 0.018 * r + 0.02
            for k in range(3):
                ww = w - k * 0.06
                uu = u1 - k * 0.2
                th = 0.035
                v_in, v_out = side * (hw - 0.05), side * (hw + th - 0.008 * k)
                z0, z1 = ww - 0.15, ww
                tip = uu + 0.28
                zm = z0 + 0.03
                S_ = 1 if side > 0 else -1
                pts = [(-0.3, v_out, z0), (uu, v_out, z0), (tip, v_out, zm), (uu, v_out, z1), (-0.3, v_out, z1)]
                mb.poly(pts if side > 0 else pts[::-1], 0)
                mb.poly([(-0.3, v_in, z1), (uu, v_in, z1), (uu, v_out, z1), (-0.3, v_out, z1)][::S_], 0)
                mb.poly([(uu, v_in, z1), (tip, v_in, zm), (tip, v_out, zm), (uu, v_out, z1)][::S_], 0)
                mb.poly([(uu, v_out, z0), (tip, v_out, zm), (tip, v_in, zm), (uu, v_in, z0)][::S_], 0)
                mb.poly([(-0.3, v_out, z0), (uu, v_out, z0), (uu, v_in, z0), (-0.3, v_in, z0)][::S_], 0)
    # brow: angled overhang above each eye (wedge)
    for side in (-1, 1):
        v0, v1 = side * 0.25, side * 0.36
        a, b = (min(v0, v1), max(v0, v1))
        mb.poly([(1.98, a, 0.12), (2.34, a, 0.06), (2.34, b, 0.06), (1.98, b, 0.12)][::side], 0)
        mb.poly([(1.98, a, 0.04), (2.34, a, 0.0), (2.34, a, 0.06), (1.98, a, 0.12)], 0)
        mb.poly([(1.98, b, 0.12), (2.34, b, 0.06), (2.34, b, 0.0), (1.98, b, 0.04)], 0)
    # stepped corbel under the body
    mb.box(-0.3, 0.95, -0.78, 0.78, -1.95, -1.50, 0)
    mb.box(-0.3, 0.6, -0.68, 0.68, -2.35, -1.95, 0)
    mb.box(-0.3, 0.32, -0.58, 0.58, -2.75, -2.35, 0)
    # chevron plaque on the wall above the perch
    mb.box(-0.3, 0.08, -0.95, 0.95, 0.9, 1.25, 0)
    mb.box(-0.3, 0.14, -0.7, 0.7, 1.25, 1.55, 0)
    me2 = mb.build("GARGOYLE_parts", [MAT.get('gargoyle'), MAT.get('metal_dark')])
    ob2 = new_object("GARGOYLE_parts", me2, col, loc=(GARG_BASE_X, GARG_Y, PERCH_Z))
    bevel_mod(ob2, width=0.025, segments=2)
    # eyes
    for side in (-1, 1):
        bpy_me = _sphere_mesh(f"GARG_eye", 0.045)
        e = new_object("GARGOYLE_eye", bpy_me, col, loc=(GARG_BASE_X + 2.2, GARG_Y + side * 0.305, PERCH_Z - 0.02))
    return ob


_eye_mesh = None


def _sphere_mesh(name, r):
    global _eye_mesh
    if _eye_mesh is None:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r)
        _eye_mesh = bpy.data.meshes.new(name)
        bm.to_mesh(_eye_mesh)
        bm.free()
        for p in _eye_mesh.polygons:
            p.use_smooth = True
        _eye_mesh.materials.append(MAT.get('metal_dark'))
    return _eye_mesh


def build_lights(col):
    """Crown floodlights: spots on the setback roof aimed at the crown, driven by street_emit."""
    for i, (x, y) in enumerate(((-52, -312), (-18, -312), (-18, -288), (-52, -288))):
        ld = bpy.data.lights.new(f"TOWER_flood{i}", 'SPOT')
        ld.spot_size = math.radians(55)
        ld.spot_blend = 0.6
        ld.color = (1.0, 0.85, 0.65)
        ld.shadow_soft_size = 0.3
        ob = new_object(f"TOWER_flood{i}", ld, col, loc=(x, y, 241.0))
        import mathutils
        d = mathutils.Vector((-35 - x, -300 - y, 262 - 241.0))
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        fc = lighting.drive(ld, "energy", "street_emit")
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = "v*9000"


def perch_info():
    """Exact perch top-centre and outward vector (from the ornament's construction constants)."""
    import ornament
    return ornament.perch_info(GARG_BASE_X, GARG_Y, PERCH_Z)
