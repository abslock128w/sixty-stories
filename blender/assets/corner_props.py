"""Sixty Stories - street corner hero asset: street furniture / props.

Every public function builds ONE prop into a new collection and returns it (not linked to
any scene).  Prop-local frame: base centre at the origin (z = 0 = the surface it stands on),
"front" toward -Y unless noted.  `seed` changes geometry details (litter, chips, stickers,
lean); materials also vary per instance through Object Info > Random, so one prop
collection instanced many times does not repeat exactly.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector

import corner_kit as K
from corner_kit import MB, finalize, srgb, frame, TAU

PI = math.pi


def _col(name):
    return bpy.data.collections.new(name)


def decal(mb, c, n, w, h, key, uv=(0, 0, 1, 1), up=(0, 0, 1), flip=False):
    c, n, u = Vector(c), Vector(n).normalized(), Vector(up).normalized()
    r = u.cross(n).normalized()
    u = n.cross(r).normalized()
    pts = [c - r * w / 2 - u * h / 2, c + r * w / 2 - u * h / 2, c + r * w / 2 + u * h / 2, c - r * w / 2 + u * h / 2]
    u0, v0, u1, v1 = uv
    if flip:
        u0, u1 = u1, u0
    mb.quad_uv(pts, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], key)


def atlas(px):
    """Pixel rect (x0, y0, x1, y1) in a 1024 atlas -> uv rect."""
    x0, y0, x1, y1 = px
    return (x0 / 1024, 1 - y1 / 1024, x1 / 1024, 1 - y0 / 1024)


STICK = {
    'glum': (20, 120, 236, 336), 'hi': (276, 140, 492, 300), 'moth': (540, 100, 740, 400), 'town': (790, 150, 1000, 330),
    'flyer': (20, 530, 492, 1004), 'ant': (532, 600, 748, 760), 'slap': (780, 560, 1004, 720), 'cab': (560, 800, 980, 980),
}


def wrap_decal(mb, key, rfun, zc, a_c, w, h, uvr, nu=6, nv=2, lift=0.0015, peel=0.0):
    """Decal wrapped around a vertical cylinder of radius rfun(z) centred at the origin."""
    u0, v0, u1, v1 = uvr
    ids = []
    for j in range(nv + 1):
        z = zc - h / 2 + h * j / nv
        row = []
        for i in range(nu + 1):
            R = rfun(z) + lift + (peel * (i / nu) ** 3 if j == nv else 0.0)
            a = a_c + (-0.5 + i / nu) * w / max(R, 1e-3)
            row.append(mb.add_v((R * math.cos(a), R * math.sin(a), z)))
        ids.append(row)
    for j in range(nv):
        for i in range(nu):
            uv = [(u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv), (u0 + (u1 - u0) * (i + 1) / nu, v0 + (v1 - v0) * j / nv),
                  (u0 + (u1 - u0) * (i + 1) / nu, v0 + (v1 - v0) * (j + 1) / nv), (u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * (j + 1) / nv)]
            mb.face([ids[j][i], ids[j][i + 1], ids[j + 1][i + 1], ids[j + 1][i]], key, uv=uv)


def chain(mb, key, p0, p1, sag=0.05, link=0.016, r=0.0022):
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    n = max(3, int(L * 1.3 / link))
    prev = None
    for i in range(n):
        t = (i + 0.5) / n
        p = p0.lerp(p1, t) + Vector((0, 0, -sag * 4 * t * (1 - t)))
        t2 = min(1.0, (i + 1.5) / n)
        q = p0.lerp(p1, t2) + Vector((0, 0, -sag * 4 * t2 * (1 - t2)))
        d = (q - p).normalized() if (q - p).length > 1e-6 else Vector((1, 0, 0))
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        nrm = side.normalized() if i % 2 == 0 else d.cross(side).normalized()
        q = d.to_track_quat('X', 'Z')
        M = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ (Matrix.Rotation(PI / 2, 4, 'X') if i % 2 else Matrix.Identity(4)) @ Matrix.Diagonal((1.5, 1, 1, 1))
        mb.ring_tube((0, 0, 0), link * 0.36, r, key, seg=8, rseg=4, M=M)
        prev = p


# ============================================================================ hydrant
def hydrant(name="PROP_hydrant", seed=0, color=(156, 26, 22)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_hyd_paint", srgb(color), chip=0.45, rust=True, gloss=True, grime_h=0.3)
    cap = K.m_paint("crn_hyd_cap", srgb((176, 174, 166)), chip=0.5, rust=True, grime_h=0.0, grime_amt=0.0)
    iron = K.m_iron("crn_iron", rust=0.8)
    chm = K.m_iron("crn_chain", rust=0.6, base=(70, 68, 64))
    mb = MB(name + "_body")
    prof = [(0, 0), (0.15, 0), (0.15, 0.035), (0.125, 0.045), (0.106, 0.065), (0.100, 0.10), (0.102, 0.29), (0.126, 0.295), (0.126, 0.33),
            (0.104, 0.338), (0.102, 0.54), (0.132, 0.548), (0.132, 0.578), (0.112, 0.592), (0.100, 0.635), (0.078, 0.672), (0.045, 0.695), (0, 0.70)]
    mb.lathe(prof, 'p', seg=36)
    # side outlets (±X) and pumper (-Y)
    caps = []
    for sx in (-1, 1):
        M = frame((sx * 0.092, 0, 0.47), (sx, 0, 0))
        mb.lathe([(0, 0), (0.048, 0), (0.048, 0.065), (0.058, 0.07), (0.058, 0.09), (0.048, 0.095), (0, 0.095)], 'p', seg=24, M=M)
        Mc = frame((sx * (0.092 + 0.095), 0, 0.47), (sx, 0, 0))
        mb.lathe([(0, 0), (0.054, 0), (0.056, 0.035), (0.05, 0.045), (0, 0.045)], 'c', seg=24, M=Mc)
        mb.hexnut((sx * (0.092 + 0.14), 0, 0.47), (sx, 0, 0), 0.018, 0.022, 'c', sides=5, rot=rng.uniform(0, 1))
        caps.append(Vector((sx * 0.21, 0, 0.47 - 0.05)))
    M = frame((0, -0.095, 0.41), (0, -1, 0))
    mb.lathe([(0, 0), (0.07, 0), (0.07, 0.07), (0.082, 0.078), (0.082, 0.1), (0.07, 0.106), (0, 0.106)], 'p', seg=28, M=M)
    Mc = frame((0, -0.2, 0.41), (0, -1, 0))
    mb.lathe([(0, 0), (0.078, 0), (0.08, 0.04), (0.072, 0.052), (0, 0.052)], 'c', seg=28, M=Mc)
    mb.hexnut((0, -0.25, 0.41), (0, -1, 0), 0.022, 0.026, 'c', sides=5)
    caps.append(Vector((0, -0.23, 0.41 - 0.07)))
    # operating nut + bonnet bolts + flange bolts
    mb.hexnut((0, 0, 0.695), (0, 0, 1), 0.026, 0.035, 'c', sides=5)
    for k in range(6):
        a = TAU * k / 6 + 0.3
        mb.hexnut((0.133 * math.cos(a), 0.133 * math.sin(a), 0.035), (0, 0, 1), 0.011, 0.016, 'b')
    for k in range(8):
        a = TAU * k / 8
        mb.hexnut((0.118 * math.cos(a), 0.118 * math.sin(a), 0.33), (0, 0, 1), 0.009, 0.013, 'b')
        mb.hexnut((0.118 * math.cos(a), 0.118 * math.sin(a), 0.295), (0, 0, -1), 0.009, 0.013, 'b')
    # cap chains to lugs on the barrel
    for i, cp in enumerate(caps):
        lug = Vector((cp.x * 0.45, cp.y * 0.45 - (0.02 if i < 2 else 0), 0.33 + 0.012))
        chain(mb, 'h', cp, lug, sag=0.06 + rng.uniform(0, 0.03))
    finalize(mb, col, {'p': paint, 'c': cap, 'b': iron, 'h': chm}, smooth=True)
    return col


# ============================================================================ litter bin
def _crumple(mb, c, r, key, rng, seg=10, cell=(0, 0, 0)):
    b = len(mb.v)
    mb.lathe([(0, -r), (r * 0.7, -r * 0.7), (r, 0), (r * 0.7, r * 0.7), (0, r)], key, seg=seg, M=Matrix.Translation(Vector(c)), cell=cell)
    for i in range(b, len(mb.v)):
        v = Vector(mb.v[i])
        d = v - Vector(c)
        f = 1 + rng.uniform(-0.28, 0.2)
        v = Vector(c) + d * f
        mb.v[i] = tuple(v)


def litter_bin(name="PROP_litter_bin", seed=0, color=(34, 70, 44)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_bin_paint", srgb(color), chip=0.6, rust=True, grime_h=0.35, scale=2.0)
    bag = K.m_plastic_bag("crn_bag")
    lit = K.m_attr("crn_litter", rough=0.6)
    mb = MB(name + "_basket")
    rt, rb, zt, zb = 0.30, 0.235, 0.90, 0.07

    def rr(z):
        return rb + (rt - rb) * (z - zb) / (zt - zb)
    mb.lathe([(0, 0.0), (0.20, 0.0), (0.24, 0.01), (0.245, 0.05), (0.238, 0.085), (0.22, 0.085), (0, 0.075)], 'p', seg=36)
    for k in range(40):
        a = TAU * k / 40
        mb.rod((rr(zb) * math.cos(a), rr(zb) * math.sin(a), zb), (rr(zt) * math.cos(a), rr(zt) * math.sin(a), zt), 0.0042, 'p', seg=5)
    for z in (0.20, 0.33, 0.46, 0.59, 0.72):
        mb.ring_tube((0, 0, z), rr(z) + 0.002, 0.0045, 'p', seg=48, rseg=5)
    mb.ring_tube((0, 0, zt), rt + 0.003, 0.012, 'p', seg=48, rseg=8)
    mb.ring_tube((0, 0, zt - 0.05), rt - 0.003, 0.008, 'p', seg=48, rseg=6)
    finalize(mb, col, {'p': paint}, smooth=True)
    # liner bag folded over the rim
    mb = MB(name + "_bag")
    prof = [(0, 0.09), (0.18, 0.09)] + [(rr(z) - 0.012, z) for z in (0.12, 0.3, 0.5, 0.7, 0.86)] + [(rt - 0.004, 0.915), (rt + 0.02, 0.905), (rt + 0.028, 0.86), (rt + 0.03, 0.78 + rng.uniform(-0.03, 0.03))]
    b = len(mb.v)
    mb.lathe(prof, 'g', seg=40)
    ph = [rng.uniform(0, TAU) for _ in range(6)]
    for i in range(b, len(mb.v)):
        x, y, z = mb.v[i]
        a = math.atan2(y, x)
        rad = math.hypot(x, y)
        if rad < 1e-4:
            continue
        w = 0.010 * math.sin(7 * a + ph[0] + z * 9) + 0.006 * math.sin(13 * a + ph[1] - z * 14) + 0.004 * math.sin(23 * a + ph[2])
        if z > 0.85:
            w *= 1.6
            z += 0.012 * math.sin(5 * a + ph[3])
        mb.v[i] = ((rad + w) * math.cos(a), (rad + w) * math.sin(a), z)
    # fill level + litter
    mb2 = MB(name + "_litter")
    fz = 0.80 + rng.uniform(-0.04, 0.06)
    mb2.lathe([(0, fz + 0.03), (rr(fz) - 0.02, fz), (rr(fz) - 0.02, fz - 0.05), (0, fz - 0.05)], 'g', seg=24)
    cols = [srgb((226, 222, 210)), srgb((200, 186, 150)), srgb((176, 40, 34)), srgb((236, 236, 232)), srgb((60, 110, 160)), srgb((120, 90, 60))]
    for k in range(7):
        a, d = rng.uniform(0, TAU), rng.uniform(0, 0.17)
        _crumple(mb2, (d * math.cos(a), d * math.sin(a), fz + 0.04), rng.uniform(0.03, 0.055), 'l', rng, cell=tuple(rng.choice(cols)[:3]))
    # coffee cup + bottle sticking out
    a = rng.uniform(0, TAU)
    M = Matrix.Translation((0.1 * math.cos(a), 0.1 * math.sin(a), fz + 0.02)) @ Matrix.Rotation(0.5, 4, 'X')
    mb2.lathe([(0, 0), (0.028, 0), (0.04, 0.11), (0.042, 0.115), (0, 0.115)], 'l', seg=16, M=M, cell=tuple(srgb((236, 232, 222))[:3]))
    M = Matrix.Translation((-0.08, 0.06, fz + 0.03)) @ Matrix.Rotation(-0.9, 4, 'Y')
    mb2.lathe([(0, 0), (0.032, 0), (0.033, 0.14), (0.014, 0.19), (0.013, 0.215), (0, 0.215)], 'l', seg=14, M=M, cell=(0.55, 0.62, 0.66))
    finalize(mb, col, {'g': bag}, smooth=True)
    finalize(mb2, col, {'g': bag, 'l': lit}, smooth=True)
    return col


# ============================================================================ newspaper box
def newspaper_box(name="PROP_newspaper_box", seed=0, color=(26, 70, 142)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_news_paint", srgb(color), chip=0.5, rust=True, gloss=True, grime_h=0.5)
    galv = K.m_galv("crn_galv")
    iron = K.m_iron("crn_iron", rust=0.8)
    glass = K.m_glass("crn_plexi", dirt=0.35, rough=0.05)
    dark = K.m_dark("crn_void")
    mb = MB(name + "_body")
    mb.box((-0.15, -0.15, 0), (0.15, 0.15, 0.012), 'i')
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.hexnut((sx * 0.115, sy * 0.115, 0.012), (0, 0, 1), 0.012, 0.014, 'i')
    mb.box((-0.035, -0.035, 0.012), (0.035, 0.035, 0.46), 'g')
    mb.box((-0.25, -0.2, 0.46), (0.25, 0.2, 1.0), 'p')
    mb.prism([(-0.26, -0.21, 1.0), (0.26, -0.21, 1.0), (0.26, 0.21, 1.0), (-0.26, 0.21, 1.0)], (0, 0, 0.018), 'p')
    # door (proud 4 mm) with window frame
    mb.box((-0.235, -0.205, 0.49), (0.235, -0.2, 0.975), 'p')
    for (x0, z0, x1, z1) in ((-0.235, 0.6, -0.19, 0.94), (0.19, 0.6, 0.235, 0.94), (-0.235, 0.94, 0.235, 0.975), (-0.235, 0.56, 0.235, 0.6)):
        mb.box((x0, -0.214, z0), (x1, -0.205, z1), 'p')
    mb.bar((-0.12, -0.225, 0.535), (0.12, -0.225, 0.535), 0.02, 0.018, 'g')
    mb.box((-0.13, -0.215, 0.52), (-0.11, -0.205, 0.55), 'g')
    mb.box((0.11, -0.215, 0.52), (0.13, -0.205, 0.55), 'g')
    # coin mechanism
    mb.box((-0.13, -0.19, 1.018), (0.13, -0.05, 1.11), 'p')
    mb.box((-0.11, -0.195, 1.04), (0.11, -0.188, 1.095), 'g')
    mb.box((0.02, -0.199, 1.06), (0.07, -0.195, 1.068), 'd')
    mb.rod((-0.06, -0.19, 1.065), (-0.06, -0.205, 1.065), 0.011, 'g', seg=12)
    finalize(mb, col, {'p': paint, 'g': galv, 'i': iron, 'd': dark}, bevel=0.003)
    mb = MB(name + "_glass")
    mb.quad([(-0.19, -0.207, 0.6), (0.19, -0.207, 0.6), (0.19, -0.207, 0.94), (-0.19, -0.207, 0.94)], 'q')
    finalize(mb, col, {'q': glass}, recalc=False)
    mb = MB(name + "_decals")
    decal(mb, (0, -0.12, 0.77), (0, -1, 0.35), 0.34, 0.42, 'n')
    for sx in (-1, 1):
        decal(mb, (sx * 0.2515, 0.0, 0.84), (sx, 0, 0), 0.36, 0.135, 'd')
    decal(mb, (0, 0.2015, 0.84), (0, 1, 0), 0.36, 0.135, 'd')
    k = rng.choice(['glum', 'moth', 'ant'])
    decal(mb, (0.2518, rng.uniform(-0.1, 0.1), 0.62), (1, 0, 0), 0.07, 0.07 * (STICK[k][3] - STICK[k][1]) / (STICK[k][2] - STICK[k][0]), 's', uv=atlas(STICK[k]))
    finalize(mb, col, {'n': K.m_image("crn_news_front", "news_front.png", rough=0.7, dirt=0.2),
                       'd': K.m_image("crn_news_decal", "news_decal.png", rough=0.35, dirt=0.5),
                       's': K.m_image("crn_stickers", "stickers.png", rough=0.4, alpha=True, dirt=0.4)}, recalc=False)
    return col


# ============================================================================ bollard
def bollard(name="PROP_bollard", seed=0, color=(214, 166, 24)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_bollard_paint", srgb(color), chip=0.7, rust=True, grime_h=0.45, grime_amt=0.85)
    refl = K.m_plain("crn_reflective", (220, 222, 220), 0.3, noise=0.25)
    grout = K.m_concrete("crn_grout", col=(120, 118, 112), use_cell=False, gum=0, stain=0.5)
    mb = MB(name + "_body")
    tilt = Matrix.Rotation(rng.uniform(-0.012, 0.012), 4, 'X') @ Matrix.Rotation(rng.uniform(-0.012, 0.012), 4, 'Y')
    mb.lathe([(0, -0.05), (0.084, -0.05), (0.084, 0.74)], 'p', seg=32, M=tilt)
    mb.lathe([(0.0845, 0.74), (0.0845, 0.82)], 'r', seg=32, M=tilt)
    mb.lathe([(0.084, 0.82), (0.084, 0.93), (0.07, 0.965), (0.04, 0.985), (0, 0.99)], 'p', seg=32, M=tilt)
    finalize(mb, col, {'p': paint, 'r': refl}, smooth=True)
    mb = MB(name + "_grout")
    mb.lathe([(0.0, 0.0), (0.12, 0.0), (0.118, 0.006), (0.09, 0.009), (0.085, 0.009), (0, 0.0)], 'g', seg=32)
    finalize(mb, col, {'g': grout}, smooth=True)
    return col


# ============================================================================ pay station
def pay_station(name="PROP_pay_station", seed=0, color=(50, 53, 58)):
    col = _col(name)
    paint = K.m_paint("crn_pay_paint", srgb(color), chip=0.3, rust=False, gloss=True, grime_h=0.4)
    galv = K.m_galv("crn_galv")
    dark = K.m_dark("crn_void")
    solar = K.m_plain("crn_solar", (18, 24, 40), 0.15, coat=1.0, noise=0.05)
    mb = MB(name + "_body")
    mb.box((-0.21, -0.16, 0), (0.21, 0.16, 0.05), 'p')
    mb.box((-0.17, -0.13, 0.05), (0.17, 0.13, 1.30), 'p')
    mb.box((-0.19, -0.15, 1.30), (0.19, 0.15, 1.52), 'p')
    mb.prism([(-0.21, -0.17, 1.52), (0.21, -0.17, 1.52), (0.21, 0.17, 1.58), (-0.21, 0.17, 1.58)], (0, 0, 0.02), 'p')
    mb.box((-0.17, -0.205, 1.25), (0.17, -0.15, 1.27), 'p')          # rain hood over screen
    for r_ in range(4):
        for c_ in range(3):
            x = -0.05 + c_ * 0.05
            z = 0.86 + r_ * 0.035
            mb.box((x - 0.016, -0.138, z - 0.012), (x + 0.016, -0.128, z + 0.012), 'g')
    mb.box((-0.08, -0.14, 1.005), (0.08, -0.13, 1.04), 'g')
    mb.box((-0.06, -0.142, 1.018), (0.06, -0.139, 1.026), 'd')
    mb.box((-0.165, -0.14, 0.12), (-0.07, -0.13, 0.25), 'g')        # receipt / coin return
    mb.box((-0.15, -0.142, 0.16), (-0.09, -0.139, 0.2), 'd')
    finalize(mb, col, {'p': paint, 'g': galv, 'd': dark}, bevel=0.004)
    mb = MB(name + "_panel")
    mb.prism([(-0.19, -0.16, 1.605), (0.19, -0.16, 1.605), (0.19, 0.16, 1.66), (-0.19, 0.16, 1.66)], (0, 0, 0.012), 's')
    finalize(mb, col, {'s': solar})
    mb = MB(name + "_decals")
    decal(mb, (0, -0.1315, 0.56), (0, -1, 0), 0.28, 0.42, 'd')
    decal(mb, (0, -0.1515, 1.17), (0, -1, 0), 0.16, 0.12, 's')
    finalize(mb, col, {'d': K.m_image("crn_pay_decal", "pay_decal.png", rough=0.4, dirt=0.4),
                       's': K.m_image("crn_pay_screen", "pay_screen.png", rough=0.1, emit=1.2, dirt=0.0)}, recalc=False)
    return col


# ============================================================================ bike rack + bicycle
def bike_rack(name="PROP_bike_rack", seed=0):
    col = _col(name)
    galv = K.m_galv("crn_galv_rack", col=(140, 142, 140), rough=0.35, grime_amt=0.7)
    iron = K.m_iron("crn_iron", rust=0.8)
    mb = MB(name + "_hoop")
    pts = [(-0.33, 0, 0.0), (-0.33, 0, 0.62)]
    for k in range(1, 12):
        a = PI - PI * k / 12
        pts.append((0.33 * math.cos(a), 0, 0.62 + 0.33 * math.sin(a)))
    pts += [(0.33, 0, 0.62), (0.33, 0, 0.0)]
    mb.ttube(pts, [0.024] * len(pts), 'g', seg=16)
    for sx in (-1, 1):
        mb.lathe([(0, 0), (0.065, 0), (0.065, 0.008), (0.03, 0.012), (0, 0.012)], 'g', seg=24, M=Matrix.Translation((sx * 0.33, 0, 0)))
        for k in range(3):
            a = TAU * k / 3 + 0.5
            mb.hexnut((sx * 0.33 + 0.048 * math.cos(a), 0.048 * math.sin(a), 0.008), (0, 0, 1), 0.008, 0.01, 'i')
    finalize(mb, col, {'g': galv, 'i': iron}, smooth=True)
    return col


def bicycle(name="PROP_bicycle", seed=0, color=(24, 80, 86), lean=0.05):
    """City bicycle, wheels in the local XZ plane (front toward +X), U-locked to a rack at local y=+0.33."""
    rng = random.Random(seed)
    col = _col(name)
    frame_m = K.m_paint("crn_bike_paint", srgb(color), chip=0.25, rust=True, gloss=True, grime_h=0.35)
    rub = K.m_plain("crn_rubber", (22, 22, 22), 0.75, noise=0.2, scale=30)
    alu = K.m_metal("crn_alu", (168, 170, 172), 0.32, 1.0)
    steel = K.m_metal("crn_steel", (120, 120, 122), 0.35, 1.0)
    saddle = K.m_plain("crn_saddle", (30, 26, 24), 0.5, noise=0.2, scale=40)
    lockm = K.m_paint("crn_lock", srgb((210, 170, 20)), chip=0.2, rust=False, grime_h=0)
    L = Matrix.Rotation(lean, 4, 'X')
    mb = MB(name + "_bike")
    ax_r, ax_f, wr = Vector((-0.52, 0, 0.345)), Vector((0.53, 0, 0.345)), 0.345
    Mw = Matrix.Rotation(PI / 2, 4, 'X')
    for ax in (ax_r, ax_f):
        T = L @ Matrix.Translation(ax) @ Mw
        mb.ring_tube((0, 0, 0), wr - 0.017, 0.0175, 'r', seg=64, rseg=10, M=T)
        mb.ring_tube((0, 0, 0), wr - 0.042, 0.009, 'a', seg=64, rseg=6, M=T)
        mb.lathe([(0, -0.05), (0.018, -0.05), (0.022, -0.035), (0.016, 0), (0.022, 0.035), (0.018, 0.05), (0, 0.05)], 'a', seg=14, M=T)
        for k in range(32):
            a = TAU * k / 32
            side = 0.032 if k % 2 else -0.032
            h = L @ (ax + Vector((0.02 * math.cos(a + 0.4), side, 0.02 * math.sin(a + 0.4))))
            rim = L @ (ax + Vector(((wr - 0.045) * math.cos(a), 0, (wr - 0.045) * math.sin(a))))
            mb.rod(h, rim, 0.0012, 's', seg=4, caps=False)
    bb = Vector((0, 0, 0.29))
    st = Vector((-0.13, 0, 0.80))
    ht0, ht1 = Vector((0.45, 0, 0.64)), Vector((0.42, 0, 0.78))

    def tube(a, b, r, key='f'):
        mb.rod(L @ Vector(a), L @ Vector(b), r, key, seg=12)
    tube(bb, st, 0.015)
    tube(st, ht1 - Vector((0, 0, 0.02)), 0.014)
    tube(bb, ht0, 0.018)
    tube(ht0 - Vector((0.01, 0, 0.03)), ht1 + Vector((-0.005, 0, 0.03)), 0.02)
    for sy in (-0.055, 0.055):
        tube(bb + Vector((0, sy * 0.6, 0)), ax_r + Vector((0, sy, 0)), 0.009)
        tube(st - Vector((0, 0, 0.03)), ax_r + Vector((0, sy, 0)), 0.008)
        tube(ht0 + Vector((0, sy * 0.4, -0.01)), ax_f + Vector((0, sy, 0)), 0.011)
    tube(st, st + Vector((-0.04, 0, 0.17)), 0.0135, 'a')
    S = L @ Matrix.Translation((-0.19, 0, 0.99)) @ Matrix.Diagonal((0.14, 0.08, 0.035, 1)) @ Matrix.Rotation(PI / 2, 4, 'Y')
    mb.lathe([(0, -1), (0.6, -0.9), (1, -0.3), (0.9, 0.5), (0.4, 1), (0, 1.05)], 'd', seg=16, M=S)
    stem = ht1 + Vector((0.07, 0, 0.06))
    tube(ht1 + Vector((0, 0, 0.02)), stem, 0.013, 'a')
    bar = [stem + Vector((0.0, -0.27, 0.03)), stem + Vector((0.02, -0.12, 0.0)), stem, stem + Vector((0.02, 0.12, 0.0)), stem + Vector((0.0, 0.27, 0.03))]
    mb.ttube([L @ p for p in bar], [0.011] * 5, 'a', seg=10)
    for sy in (-1, 1):
        g0 = stem + Vector((0, sy * 0.20, 0.025))
        tube(g0, g0 + Vector((-0.01, sy * 0.10, 0.008)), 0.016, 'r')
    # drivetrain
    T = L @ Matrix.Translation(bb + Vector((0, 0.06, 0))) @ Mw
    mb.lathe([(0, -0.003), (0.10, -0.003), (0.10, 0.003), (0, 0.003)], 's', seg=40, M=T)
    ca = rng.uniform(0, TAU)
    for sgn, yo in ((1, 0.075), (-1, -0.075)):
        pe = bb + Vector((0.17 * math.cos(ca) * sgn, yo, 0.17 * math.sin(ca) * sgn))
        tube(bb + Vector((0, yo, 0)), pe, 0.009, 'a')
        mb.box(tuple(L @ (pe + Vector((-0.045, yo * 0.2, -0.012)))), tuple(L @ (pe + Vector((0.045, yo * 1.3, 0.012)))), 'r')
    for zz in (0.10, -0.10):
        mb.rod(L @ (bb + Vector((0, 0.06, zz))), L @ (ax_r + Vector((0, 0.06, zz * 0.4))), 0.004, 's', seg=6)
    finalize(mb, col, {'f': frame_m, 'r': rub, 'a': alu, 's': steel, 'd': saddle}, smooth=True)
    # U-lock around the seat stay and the rack leg
    mb = MB(name + "_lock")
    z = 0.52
    pts = [(-0.44, -0.04, z), (-0.44, 0.30, z)]
    for k in range(1, 8):
        a = PI - PI * k / 8
        pts.append((-0.37 + 0.07 * math.cos(a), 0.30 + 0.07 * math.sin(a), z))
    pts += [(-0.30, 0.30, z), (-0.30, -0.04, z)]
    mb.ttube([L @ Vector(p) for p in pts], [0.0085] * len(pts), 's', seg=10)
    mb.rod(L @ Vector((-0.47, -0.045, z)), L @ Vector((-0.27, -0.045, z)), 0.02, 'k', seg=16)
    finalize(mb, col, {'s': steel, 'k': lockm}, smooth=True)
    return col


# ============================================================================ pedestal + cabinet
def electrical_pedestal(name="PROP_electrical_pedestal", seed=0, color=(118, 126, 116)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_ped_paint", srgb(color), chip=0.4, rust=True, grime_h=0.35)
    conc = K.m_concrete("crn_pad", col=(150, 146, 138), use_cell=False, gum=0, stain=1.0)
    galv = K.m_galv("crn_galv")
    mb = MB(name + "_pad")
    mb.box((-0.22, -0.17, -0.02), (0.22, 0.17, 0.06), 'c')
    finalize(mb, col, {'c': conc}, bevel=0.01)
    mb = MB(name + "_body")
    mb.box((-0.16, -0.11, 0.06), (0.16, 0.11, 0.80), 'p')
    mb.prism([(-0.175, -0.13, 0.80), (0.175, -0.13, 0.80), (0.175, 0.125, 0.84), (-0.175, 0.125, 0.84)], (0, 0, 0.012), 'p')
    mb.box((-0.145, -0.114, 0.10), (0.145, -0.11, 0.76), 'p')
    mb.box((0.10, -0.13, 0.40), (0.12, -0.114, 0.46), 'g')
    mb.ring_tube((0, 0, 0), 0.012, 0.0025, 'g', seg=12, rseg=4, M=Matrix.Translation((0.11, -0.135, 0.385)) @ Matrix.Rotation(PI / 2, 4, 'X'))
    mb.box((0.096, -0.15, 0.345), (0.124, -0.135, 0.377), 'g')
    finalize(mb, col, {'p': paint, 'g': galv}, bevel=0.003)
    mb = MB(name + "_label")
    decal(mb, (-0.05, -0.1155, 0.64), (0, -1, 0), 0.12, 0.12 * 0.43, 's', uv=atlas(STICK['cab']))
    finalize(mb, col, {'s': K.m_image("crn_stickers", "stickers.png", rough=0.4, alpha=True, dirt=0.4)}, recalc=False)
    return col


def control_cabinet(name="PROP_control_cabinet", seed=0, color=(150, 154, 140)):
    rng = random.Random(seed)
    col = _col(name)
    paint = K.m_paint("crn_cab_paint", srgb(color), chip=0.35, rust=True, grime_h=0.55, grime_amt=0.8)
    conc = K.m_concrete("crn_pad", col=(150, 146, 138), use_cell=False, gum=0, stain=1.0)
    galv = K.m_galv("crn_galv")
    iron = K.m_iron("crn_iron", rust=0.8)
    dark = K.m_dark("crn_void")
    mb = MB(name + "_pad")
    mb.box((-0.66, -0.44, -0.03), (0.66, 0.44, 0.12), 'c')
    finalize(mb, col, {'c': conc}, bevel=0.012)
    mb = MB(name + "_body")
    mb.box((-0.55, -0.33, 0.12), (0.55, 0.33, 1.52), 'p')
    mb.prism([(-0.58, -0.36, 1.52), (0.58, -0.36, 1.52), (0.58, 0.36, 1.53), (-0.58, 0.36, 1.53)], (0, 0, 0.03), 'p')
    mb.box((-0.56, -0.34, 1.50), (0.56, 0.34, 1.52), 'p')
    # door, proud 5 mm, with a 3 mm shadow gap
    mb.box((-0.505, -0.335, 0.19), (0.505, -0.330, 1.46), 'd')
    mb.box((-0.5, -0.338, 0.195), (0.5, -0.333, 1.455), 'p')
    # door louvres (lower) and side louvres (upper)
    mb.box((-0.32, -0.339, 0.30), (0.32, -0.336, 0.64), 'd')
    for k in range(11):
        z = 0.315 + k * 0.031
        mb.obox((0, -0.345, z), (0.31, 0, 0), (0, 0.012, -0.010), (0, 0.002, 0.003), 'p')
    for sx in (-1, 1):
        mb.box((sx * 0.553 - 0.002, -0.2, 1.05), (sx * 0.553 + 0.002, 0.2, 1.35), 'd')
        for k in range(9):
            z = 1.065 + k * 0.032
            mb.obox((sx * 0.562, 0, z), (0.003 * sx, 0, 0.003), (0, 0.19, 0), (0.012 * sx, 0, -0.010), 'p')
    # hinges, handle, lock
    for z in (0.32, 0.82, 1.32):
        mb.rod((-0.505, -0.345, z - 0.05), (-0.505, -0.345, z + 0.05), 0.011, 'g', seg=10)
    mb.box((0.40, -0.36, 0.78), (0.43, -0.338, 0.98), 'g')
    mb.rod((0.415, -0.338, 1.03), (0.415, -0.36, 1.03), 0.016, 'g', seg=14)
    mb.box((0.408, -0.362, 1.022), (0.422, -0.360, 1.038), 'd')
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.hexnut((sx * 0.6, sy * 0.38, 0.12), (0, 0, 1), 0.014, 0.02, 'i')
    finalize(mb, col, {'p': paint, 'g': galv, 'i': iron, 'd': dark}, bevel=0.004)
    mb = MB(name + "_decals")
    sm = K.m_image("crn_stickers", "stickers.png", rough=0.4, alpha=True, dirt=0.4)
    decal(mb, (-0.2, -0.3395, 1.25), (0, -1, 0), 0.3, 0.3 * 180 / 420, 's', uv=atlas(STICK['cab']))
    picks = rng.sample(['glum', 'hi', 'moth', 'ant', 'slap', 'town'], 4)
    for i, k in enumerate(picks):
        px = STICK[k]
        w = 0.085 + rng.uniform(0, 0.04)
        h = w * (px[3] - px[1]) / (px[2] - px[0])
        decal(mb, (0.05 + i * 0.1 + rng.uniform(-0.02, 0.02), -0.3396 - i * 0.0002, 0.95 + rng.uniform(-0.15, 0.2)), (0, -1, 0), w, h, 's',
              uv=atlas(px), up=(rng.uniform(-0.15, 0.15), 0, 1))
    decal(mb, (0.5536, 0.05, 0.62), (1, 0, 0), 0.55, 0.275, 't')
    decal(mb, (0.0, 0.3306, 0.55), (0, 1, 0), 0.7, 0.35, 't', flip=True)
    finalize(mb, col, {'s': sm, 't': K.m_image("crn_tag", "tag.png", rough=0.5, alpha=True, dirt=0.2)}, recalc=False)
    return col


# ============================================================================ signal hardware
def signal_head(mb, base, face, sections, lit, keys):
    """Vehicle signal head: base = centre of the top of the housing, face = direction it looks."""
    f = Vector(face).normalized()
    up = Vector((0, 0, 1))
    r = up.cross(f).normalized()
    hs, w, d = 0.325, 0.33, 0.24
    H = hs * len(sections)
    c0 = Vector(base) - up * (H / 2)
    mb.obox(c0, r * (w / 2), f * (d / 2), up * (H / 2), keys['house'])
    # back plate with a retroreflective border
    bp = c0 - f * (d / 2 + 0.008)
    mb.obox(bp, r * 0.31, f * 0.005, up * (H / 2 + 0.1), keys['back'])
    for s in (-1, 1):
        mb.obox(bp + r * s * 0.285 + f * 0.006, r * 0.025, f * 0.001, up * (H / 2 + 0.1), keys['border'])
        mb.obox(bp + up * s * (H / 2 + 0.075) + f * 0.006, r * 0.31, f * 0.001, up * 0.025, keys['border'])
    for i, col_ in enumerate(sections):
        zc = Vector(base) - up * (hs * (i + 0.5))
        lc = zc + f * (d / 2)
        M = Matrix.Translation(lc) @ f.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        key = keys['lit_' + col_] if lit == i else keys['lens_' + col_]
        mb.lathe([(0, 0.012), (0.10, 0.008), (0.14, 0.0), (0, 0.0)], key, seg=28, M=M)
        mb.lathe([(0.143, 0.0), (0.152, 0.0), (0.152, 0.012), (0.143, 0.012)], keys['visor'], seg=28, M=M)
        # tunnel visor: open at the bottom
        n = 14
        ids_o, ids_i = [], []
        for k in range(n + 1):
            a = math.radians(-35 + 250 * k / n)
            for depth, lst in ((0.0, ids_o), (0.0, ids_i)):
                pass
        ring = []
        for k in range(n + 1):
            a = math.radians(-35 + 250 * k / n)
            dirv = r * math.cos(a) + up * math.sin(a)
            p0 = lc + dirv * 0.158
            p1 = lc + dirv * 0.150 + f * 0.24 - up * 0.02
            p0i = lc + dirv * 0.152
            p1i = lc + dirv * 0.145 + f * 0.24 - up * 0.02
            ring.append([mb.add_v(p) for p in (p0, p1, p1i, p0i)])
        for k in range(n):
            a, b = ring[k], ring[k + 1]
            for j in range(4):
                j2 = (j + 1) % 4
                mb.face([a[j], b[j], b[j2], a[j2]], keys['visor'])
        mb.face(ring[0], keys['visor'])
        mb.face(ring[-1][::-1], keys['visor'])


def ped_head(mb, dec, c, face, img_key, keys):
    f = Vector(face).normalized()
    up = Vector((0, 0, 1))
    r = up.cross(f).normalized()
    c = Vector(c)
    mb.obox(c, r * 0.235, f * 0.11, up * 0.235, keys['house'])
    fc = c + f * 0.112
    for s in (-1, 1):
        mb.obox(fc + r * s * 0.228 + f * 0.06, r * 0.006, f * 0.06, up * 0.235, keys['visor'])
    mb.obox(fc + up * 0.228 + f * 0.06, r * 0.235, f * 0.06, up * 0.006, keys['visor'])
    for k in range(1, 6):
        mb.obox(fc + up * (-0.23 + 0.0767 * k) + f * 0.04, r * 0.22, f * 0.04, up * 0.002, keys['visor'])
    decal(dec, fc + f * 0.001, f, 0.42, 0.42, img_key)


def signal_pole(name="PROP_signal_pole", seed=0, arm=8.2, heads=(2.25, 5.65), lit=0, walk=True):
    """Mast-arm signal pole.  Arm along local -Y, vehicle heads face local -X, ped head faces -Y,
    push button faces -X, street-name blades on top."""
    rng = random.Random(seed)
    col = _col(name)
    galv = K.m_galv("crn_galv_pole", col=(146, 148, 146), rough=0.45)
    iron = K.m_iron("crn_iron", rust=0.8)
    yellow = K.m_paint("crn_sig_yellow", srgb((214, 166, 22)), chip=0.25, rust=False, gloss=True, grime_h=0.0, grime_amt=0.0)
    black = K.m_paint("crn_sig_black", srgb((18, 18, 18)), chip=0.15, rust=False, grime_h=0.0, grime_amt=0.0)
    border = K.m_plain("crn_sig_border", (222, 196, 30), 0.35, noise=0.2)
    keys = dict(house='y', back='k', border='b', visor='k', lens_r='lr', lens_a='la', lens_g='lg', lit_r='Lr', lit_a='La', lit_g='Lg')
    mats = {'g': galv, 'i': iron, 'y': yellow, 'k': black, 'b': border,
            'lr': K.m_lens("crn_lens_r", (0.20, 0.015, 0.01)), 'la': K.m_lens("crn_lens_a", (0.22, 0.10, 0.0)), 'lg': K.m_lens("crn_lens_g", (0.01, 0.12, 0.08)),
            'Lr': K.m_emit("crn_lit_r", (1.0, 0.06, 0.02), 30.0), 'La': K.m_emit("crn_lit_a", (1.0, 0.45, 0.02), 30.0), 'Lg': K.m_emit("crn_lit_g", (0.1, 1.0, 0.55), 30.0)}
    H = 6.7

    def rp(z):
        return 0.15 - 0.05 * max(0.0, min(z, H)) / H
    mb = MB(name + "_pole")
    mb.box((-0.26, -0.26, 0.0), (0.26, 0.26, 0.032), 'i')
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = (sx * 0.2, sy * 0.2, 0.032)
            mb.rod(p, (p[0], p[1], 0.1), 0.014, 'i', seg=8)
            mb.hexnut(p, (0, 0, 1), 0.024, 0.03, 'i')
            mb.hexnut((p[0], p[1], 0.032), (0, 0, 1), 0.03, 0.006, 'i', sides=12)
    mb.lathe([(0, 0.032), (0.19, 0.032), (0.19, 0.06), (0.165, 0.09), (rp(0.2), 0.2)] + [(rp(z), z) for z in (1.5, 3.0, 4.5, 5.6, 6.0, H)] + [(0.085, H + 0.03), (0, H + 0.06)], 'g', seg=32)
    # handhole cover
    mb.obox((0, rp(0.5) + 0.004, 0.5), (0.06, 0, 0), (0, 0.006, 0), (0, 0, 0.1), 'g')
    for z in (0.42, 0.58):
        mb.hexnut((0, rp(z) + 0.01, z), (0, 1, 0), 0.007, 0.006, 'i')
    # mast arm with flange plate
    za = 5.75
    mb.obox((0, -rp(za) - 0.015, za), (0.2, 0, 0), (0, 0.015, 0), (0, 0, 0.2), 'g')
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.hexnut((sx * 0.15, -rp(za) - 0.03, za + sz * 0.15), (0, -1, 0), 0.016, 0.02, 'i')
    pts = [(0, -rp(za) - 0.03 - arm * t, za + 0.30 * t ** 1.4) for t in [i / 16 for i in range(17)]]
    mb.ttube(pts, [0.12 - 0.055 * i / 16 for i in range(17)], 'g', seg=20)
    finalize(mb, col, mats, smooth=True)
    # signal heads hung from the arm
    mb = MB(name + "_heads")
    for i, y in enumerate(heads):
        zt = za + 0.30 * (y / arm) ** 1.4
        top = Vector((0, -y, zt - 0.32))
        mb.rod((0, -y, zt - 0.1), (0, -y, zt - 0.32), 0.025, 'k', seg=10)
        mb.obox((0, -y, zt - 0.1), (0.13, 0, 0), (0, 0.06, 0), (0, 0, 0.025), 'k')
        signal_head(mb, top, (-1, 0, 0), ['r', 'a', 'g'], lit, keys)
    finalize(mb, col, mats, smooth=True, angle=50)
    # pedestrian head, push button, signs, stickers
    mb = MB(name + "_hw")
    dec = MB(name + "_faces")
    zp = 2.85
    mb.obox((0, -rp(zp) - 0.04, zp + 0.18), (0.04, 0, 0), (0, 0.05, 0), (0, 0, 0.02), 'k')
    mb.obox((0, -rp(zp) - 0.04, zp - 0.18), (0.04, 0, 0), (0, 0.05, 0), (0, 0, 0.02), 'k')
    ped_head(mb, dec, (0, -rp(zp) - 0.2, zp), (0, -1, 0), 'pw' if walk else 'ph', keys)
    # push button on the -X side
    zb = 1.08
    xb = -rp(zb)
    mb.obox((xb - 0.035, 0, zb), (0.035, 0, 0), (0, 0.065, 0), (0, 0, 0.095), 'k')
    mb.lathe([(0, 0.0), (0.03, 0.0), (0.03, 0.012), (0.024, 0.018), (0, 0.019)], 'g', seg=20, M=frame((xb - 0.07, 0, zb - 0.01), (-1, 0, 0)))
    mb.obox((xb - 0.008, 0, 1.40), (0.004, 0, 0), (0, 0.125, 0), (0, 0, 0.16), 'g')
    decal(dec, (xb - 0.0125, 0, 1.40), (-1, 0, 0), 0.23, 0.30, 'pb')
    # one-way sign (plane XZ, faces ±Y; arrow points +X in the world)
    zo = 3.55
    mb.obox((0.2, rp(zo) + 0.01, zo), (0.45, 0, 0), (0, 0.003, 0), (0, 0, 0.155), 'g')
    for sz in (-1, 1):
        mb.ring_tube((0, 0, 0), rp(zo) + 0.004, 0.006, 'g', seg=24, rseg=4, M=Matrix.Translation((0, 0, zo + sz * 0.1)))
    decal(dec, (0.2, rp(zo) + 0.0142, zo), (0, 1, 0), 0.9, 0.31, 'ow', flip=True)
    decal(dec, (0.2, rp(zo) + 0.0058, zo), (0, -1, 0), 0.9, 0.31, 'ow')
    # street-name blades on a top bracket
    zt = H + 0.05
    mb.rod((0, 0, H), (0, 0, H + 0.62), 0.03, 'g', seg=12)
    for zz, ax, img in ((H + 0.18, 'y', 'bav'), (H + 0.44, 'x', 'bcs')):
        if ax == 'y':
            mb.obox((0, 0, zz), (0.004, 0, 0), (0, 0.53, 0), (0, 0, 0.115), 'g')
            decal(dec, (-0.0045, 0, zz), (-1, 0, 0), 1.05, 0.224, img)
            decal(dec, (0.0045, 0, zz), (1, 0, 0), 1.05, 0.224, img)
        else:
            mb.obox((0, 0, zz), (0.53, 0, 0), (0, 0.004, 0), (0, 0, 0.115), 'g')
            decal(dec, (0, -0.0045, zz), (0, -1, 0), 1.05, 0.224, img)
            decal(dec, (0, 0.0045, zz), (0, 1, 0), 1.05, 0.224, img)
        mb.obox((0, 0, zz), (0.05, 0, 0), (0, 0.05, 0), (0, 0, 0.13), 'g')
    finalize(mb, col, mats, smooth=True, angle=50)
    # stickers + a rent flyer wrapped on the pole, mostly at hand height
    picks = ['glum', 'hi', 'moth', 'town', 'ant', 'slap', 'glum', 'moth']
    rng.shuffle(picks)
    for i, k in enumerate(picks[:7]):
        px = STICK[k]
        w = rng.uniform(0.06, 0.1)
        h = w * (px[3] - px[1]) / (px[2] - px[0])
        wrap_decal(dec, 'st', rp, rng.uniform(1.2, 2.1), rng.uniform(-2.4, 0.6) + (PI if i == 6 else 0), w, h, atlas(px), lift=0.0012 + 0.0002 * i)
    wrap_decal(dec, 'st', rp, 1.62, -2.0, 0.2, 0.2, atlas(STICK['flyer']), nu=8, nv=4, lift=0.0035, peel=0.02)
    smat = K.m_image("crn_stickers", "stickers.png", rough=0.4, alpha=True, dirt=0.45)
    finalize(dec, col, {'pw': K.m_image("crn_ped_walk", "ped_walk.png", rough=0.2, emit=5.0, dirt=0.0),
                        'ph': K.m_image("crn_ped_hand", "ped_hand.png", rough=0.2, emit=5.0, dirt=0.0),
                        'pb': K.m_image("crn_push_sign", "push_button.png", rough=0.4, dirt=0.5),
                        'ow': K.m_image("crn_one_way", "one_way.png", rough=0.35, dirt=0.35),
                        'bav': K.m_image("crn_blade_av", "blade_av.png", rough=0.35, dirt=0.3),
                        'bcs': K.m_image("crn_blade_cs", "blade_cs.png", rough=0.35, dirt=0.3),
                        'st': smat}, recalc=False)
    return col


def streetlight(name="PROP_streetlight", seed=0, H=8.6, arm=2.3, ped=True, lamp_on=0.0):
    """Cobra-head streetlight; arm along local -Y.  Optional pedestrian head (hand/countdown)
    facing -Y and a push button facing +X."""
    col = _col(name)
    galv = K.m_galv("crn_galv_pole", col=(146, 148, 146), rough=0.45)
    base = K.m_paint("crn_light_base", srgb((30, 34, 32)), chip=0.4, rust=True, grime_h=0.5)
    iron = K.m_iron("crn_iron", rust=0.8)
    black = K.m_paint("crn_sig_black", srgb((18, 18, 18)), chip=0.15, rust=False, grime_h=0.0, grime_amt=0.0)
    shell = K.m_paint("crn_lum_shell", srgb((120, 122, 118)), chip=0.1, rust=False, grime_h=0.0, grime_amt=0.0)
    refr = K.m_emit("crn_lum_lens", (1.0, 0.72, 0.42), lamp_on) if lamp_on > 0 else K.m_glass("crn_lum_glass", tint=(0.9, 0.88, 0.8), dirt=0.4, rough=0.15)
    mats = {'g': galv, 'b': base, 'i': iron, 'k': black, 's': shell, 'q': refr, 'y': K.m_paint("crn_sig_yellow", srgb((214, 166, 22)), chip=0.25, rust=False, gloss=True, grime_h=0.0, grime_amt=0.0)}

    def rp(z):
        return 0.115 - 0.045 * max(0.0, min(z, H)) / H
    mb = MB(name + "_pole")
    # octagonal cast base
    mb.lathe([(0, 0), (0.27, 0), (0.27, 0.06), (0.24, 0.09), (0.22, 0.5), (0.20, 0.55), (0.18, 0.95), (0.20, 1.0), (0.20, 1.05), (0.15, 1.12), (0, 1.12)], 'b', seg=8)
    mb.lathe([(0, 1.1)] + [(rp(z), z) for z in (1.1, 3.0, 5.0, 7.0, H)] + [(0, H)], 'g', seg=28)
    # davit arm
    pts = [Vector((0, 0, H - 0.25))]
    for k in range(1, 13):
        t = k / 12
        a = t * PI / 2
        pts.append(Vector((0, -0.75 * (1 - math.cos(a)) - arm * max(0, t - 0.6) / 0.4 * 0.0, H - 0.25 + 0.75 * math.sin(a))))
    end = pts[-1]
    for k in range(1, 7):
        pts.append(end + Vector((0, -(arm - 0.75) * k / 6, -0.04 * k / 6)))
    mb.ttube(pts, [0.07 - 0.025 * i / (len(pts) - 1) for i in range(len(pts))], 'g', seg=16)
    tip = pts[-1]
    finalize(mb, col, mats, smooth=True)
    mb = MB(name + "_lum")
    M = Matrix.Translation(tip + Vector((0, -0.38, -0.02))) @ Matrix.Diagonal((0.20, 0.44, 0.09, 1)) @ Matrix.Rotation(PI / 2, 4, 'X')
    mb.lathe([(0, -1), (0.55, -0.95), (0.9, -0.6), (1.0, 0.0), (0.9, 0.6), (0.55, 0.95), (0, 1)], 's', seg=20, M=M)
    M2 = Matrix.Translation(tip + Vector((0, -0.42, -0.07))) @ Matrix.Diagonal((0.15, 0.30, 0.05, 1))
    mb.lathe([(0, -1), (0.6, -0.85), (0.95, -0.4), (1.0, 0.0), (0, 0.0)], 'q', seg=20, M=M2)
    mb.rod(tip + Vector((0, -0.25, 0.07)), tip + Vector((0, -0.25, 0.12)), 0.03, 'k', seg=12)
    finalize(mb, col, mats, smooth=True)
    if ped:
        mb = MB(name + "_hw")
        dec = MB(name + "_faces")
        keys = dict(house='y', visor='k')
        zp = 2.8
        for dz in (0.18, -0.18):
            mb.obox((0, -rp(zp) - 0.04, zp + dz), (0.04, 0, 0), (0, 0.05, 0), (0, 0, 0.02), 'k')
        ped_head(mb, dec, (0, -rp(zp) - 0.2, zp), (0, -1, 0), 'ph', keys)
        zb = 1.25
        xb = rp(zb)
        mb.obox((xb + 0.035, 0, zb), (0.035, 0, 0), (0, 0.065, 0), (0, 0, 0.095), 'k')
        mb.lathe([(0, 0.0), (0.03, 0.0), (0.03, 0.012), (0.024, 0.018), (0, 0.019)], 'g', seg=20, M=frame((xb + 0.07, 0, zb - 0.01), (1, 0, 0)))
        mb.obox((xb + 0.008, 0, 1.58), (0.004, 0, 0), (0, 0.125, 0), (0, 0, 0.16), 'g')
        decal(dec, (xb + 0.0125, 0, 1.58), (1, 0, 0), 0.23, 0.30, 'pb')
        # pole number plate
        mb.obox((0, rp(2.2) + 0.002, 2.2), (0.04, 0, 0), (0, 0.002, 0), (0, 0, 0.09), 'k')
        finalize(mb, col, mats, smooth=True, angle=50)
        finalize(dec, col, {'ph': K.m_image("crn_ped_hand", "ped_hand.png", rough=0.2, emit=5.0, dirt=0.0),
                            'pb': K.m_image("crn_push_sign", "push_button.png", rough=0.4, dirt=0.5)}, recalc=False)
    return col


def sign_post(name="PROP_sign_post", seed=0, H=2.55):
    """Square perforated sign post with a no-parking sign facing local -Y."""
    col = _col(name)
    galv = K.m_galv("crn_galv_post", col=(156, 158, 156), rough=0.4)
    iron = K.m_iron("crn_iron", rust=0.8)
    mb = MB(name + "_post")
    mb.box((-0.025, -0.025, -0.05), (0.025, 0.025, H), 'g')
    for z in [0.1 + 0.0254 * k for k in range(0, int((H - 0.15) / 0.0254), 2)]:
        for x, y, n in ((0, -0.0255, (0, -1, 0)), (0, 0.0255, (0, 1, 0)), (-0.0255, 0, (-1, 0, 0)), (0.0255, 0, (1, 0, 0))):
            pass
    mb.obox((0, -0.03, H - 0.32), (0.15, 0, 0), (0, 0.002, 0), (0, 0, 0.225), 'g')
    for z in (H - 0.12, H - 0.52):
        mb.hexnut((0, -0.033, z), (0, -1, 0), 0.009, 0.008, 'i')
    finalize(mb, col, {'g': galv, 'i': iron}, bevel=0.002)
    mb = MB(name + "_face")
    decal(mb, (0, -0.0325, H - 0.32), (0, -1, 0), 0.3, 0.45, 'n')
    finalize(mb, col, {'n': K.m_image("crn_no_parking", "no_parking.png", rough=0.35, dirt=0.45)}, recalc=False)
    # perforation holes as dark dots (shader-free: tiny inset quads)
    mb = MB(name + "_holes")
    for z in [0.15 + 0.0254 * k for k in range(0, int((H - 0.4) / 0.0254))]:
        for n in ((0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)):
            c = Vector(n) * 0.0253 + Vector((0, 0, z))
            decal(mb, c, n, 0.009, 0.009, 'd')
    finalize(mb, col, {'d': K.m_dark("crn_void")}, recalc=False)
    return col


def traffic_cone(name="PROP_traffic_cone", seed=0):
    col = _col(name)
    org = K.m_paint("crn_cone_orange", srgb((236, 92, 18)), chip=0.0, rust=False, grime_h=0.35, grime_amt=0.9, rough=0.5)
    wht = K.m_plain("crn_reflective", (220, 222, 220), 0.3, noise=0.25)
    blk = K.m_plain("crn_rubber", (22, 22, 22), 0.75, noise=0.2, scale=30)
    mb = MB(name + "_cone")
    mb.box((-0.18, -0.18, 0), (0.18, 0.18, 0.03), 'k')

    def r(z):
        return 0.135 - (0.135 - 0.03) * (z - 0.03) / 0.67
    bands = [(0.03, 0.30, 'o'), (0.30, 0.40, 'w'), (0.40, 0.47, 'o'), (0.47, 0.54, 'w'), (0.54, 0.70, 'o')]
    for z0, z1, k in bands:
        mb.lathe([(r(z0), z0), (r(z1), z1)], k, seg=32)
    mb.lathe([(r(0.70), 0.70), (0.022, 0.70), (0.022, 0.65)], 'o', seg=32)
    finalize(mb, col, {'o': org, 'w': wht, 'k': blk}, smooth=True, bevel=0.004)
    return col


# ============================================================================ covers, inlet, ramp panel
def _disk_cover(name, col, image, R, h, mat, zbase, zamp, rot=0.0):
    """Cast-iron cover as a displaced disk from a height image; point attribute 'h'."""
    import numpy as np
    from PIL import Image
    import corner
    im = np.asarray(Image.open(f"{K.TEX}/{image}").convert("L"), np.float32) / 255.0
    n = im.shape[0]
    ca, sa = math.cos(rot), math.sin(rot)

    def hval(X, Y):
        u = (X * ca + Y * sa)
        v = (-X * sa + Y * ca)
        c = np.clip(((u / (2 * R) + 0.5) * (n - 1)).astype(int), 0, n - 1)
        r_ = np.clip(((0.5 - v / (2 * R)) * (n - 1)).astype(int), 0, n - 1)
        return im[r_, c]

    def zf(X, Y):
        return zbase + zamp * hval(X, Y)

    def project(X, Y):
        r_ = np.hypot(X, Y)
        out = r_ > R
        k = R / np.maximum(r_, 1e-6)
        return np.where(out, X * k, X), np.where(out, Y * k, Y), out
    ob = corner.grid_mesh(name, col, mat, -R, -R, R, R, h, zf, project=project, skirt=0.03, attr=('h', lambda X, Y: hval(X, Y) / 0.93))
    return ob


def manhole(name="PROP_manhole", seed=0, rot=None):
    """Cast-iron manhole cover (Ø 0.71 m) in a ring frame and concrete collar; z=0 = road surface."""
    rng = random.Random(seed)
    col = _col(name)
    cov = K.m_iron("crn_cover_iron", rust=0.4, polish=True)
    iron = K.m_iron("crn_iron", rust=0.8)
    conc = K.m_concrete("crn_collar", col=(128, 126, 120), use_cell=False, gum=0.5, stain=1.0)
    _disk_cover(name + "_cover", col, "manhole_h.png", 0.355, 0.0024, cov, -0.012, 0.0135, rot=rng.uniform(0, TAU) if rot is None else rot)
    mb = MB(name + "_frame")
    mb.lathe([(0.357, -0.06), (0.357, -0.001), (0.362, 0.0015), (0.425, 0.0015), (0.432, -0.004), (0.432, -0.06)], 'i', seg=72)
    finalize(mb, col, {'i': iron}, smooth=True)
    mb = MB(name + "_collar")
    mb.lathe([(0.432, -0.08), (0.432, 0.0005), (0.45, 0.002), (0.6, 0.001), (0.625, -0.006), (0.625, -0.08)], 'c', seg=72)
    b = len(mb.v)
    finalize(mb, col, {'c': conc}, smooth=True)
    return col


def valve_cover(name="PROP_valve_cover", seed=0):
    col = _col(name)
    cov = K.m_iron("crn_cover_iron", rust=0.4, polish=True)
    iron = K.m_iron("crn_iron", rust=0.8)
    _disk_cover(name + "_cover", col, "valve_h.png", 0.10, 0.0016, cov, -0.008, 0.01, rot=0.3)
    mb = MB(name + "_frame")
    mb.lathe([(0.102, -0.05), (0.102, 0.0), (0.135, 0.001), (0.15, -0.004), (0.15, -0.05)], 'i', seg=40)
    finalize(mb, col, {'i': iron}, smooth=True)
    return col


def storm_inlet(name="PROP_storm_inlet", seed=0):
    """Gutter grate (0.58 x 0.88 opening) with frame and dark basin; bars across traffic."""
    rng = random.Random(seed)
    col = _col(name)
    iron = K.m_iron("crn_grate_iron", rust=0.9)
    dark = K.m_dark("crn_void")
    water = K.m_water("crn_water")
    mb = MB(name + "_grate")
    ox, oy = 0.29, 0.44
    mb.box((-ox - 0.07, -oy - 0.06, -0.03), (-ox, oy + 0.06, 0.008), 'i')
    mb.box((ox, -oy - 0.06, -0.03), (ox + 0.07, oy + 0.06, 0.008), 'i')
    mb.box((-ox, -oy - 0.06, -0.03), (ox, -oy, 0.008), 'i')
    mb.box((-ox, oy, -0.03), (ox, oy + 0.06, 0.008), 'i')
    n = 19
    for k in range(n):
        y = -oy + (k + 0.5) * (2 * oy) / n
        mb.box((-ox, y - 0.011, -0.04), (ox, y + 0.011, 0.004), 'i')
    for x in (-0.1, 0.1):
        mb.box((x - 0.012, -oy, -0.05), (x + 0.012, oy, -0.01), 'i')
    finalize(mb, col, {'i': iron}, bevel=0.002)
    mb = MB(name + "_basin")
    mb.box((-ox, -oy, -0.75), (ox + 0.3, oy, -0.04), 'd')
    finalize(mb, col, {'d': dark})
    mb = MB(name + "_water")
    mb.quad([(-ox, -oy, -0.55), (ox, -oy, -0.55), (ox, oy, -0.55), (-ox, oy, -0.55)], 'w')
    finalize(mb, col, {'w': water}, recalc=False)
    pts = [(rng.uniform(-ox, ox), rng.uniform(-oy, oy), 0.006, 'grate') for _ in range(26)]
    leaf_litter(col, pts, seed=seed + 3, name=name + "_leaves")
    return col


def ramp_tactile(col, zfun, name="crn_tactile"):
    """Truncated-dome warning panel on the corner ramp (annular sector around the return centre)."""
    import numpy as np
    paint = K.m_paint("crn_tactile_paint", srgb((206, 158, 30)), chip=0.6, rust=False, grime_h=0.0, grime_amt=0.0, rough=0.5, scale=3.0,
                      under=srgb((64, 60, 56)))
    c = Vector((2.0, 2.0))
    r0, r1, half = 1.16, 1.76, math.radians(22)
    mb = MB(name)
    na, nr = 20, 5
    ids = []
    for j in range(nr + 1):
        r = r0 + (r1 - r0) * j / nr
        row = []
        for i in range(na + 1):
            a = math.radians(225) - half + 2 * half * i / na
            x, y = c.x + r * math.cos(a), c.y + r * math.sin(a)
            row.append(mb.add_v((x, y, float(zfun(x, y)) + 0.004)))
        ids.append(row)
    for j in range(nr):
        for i in range(na):
            mb.face([ids[j][i], ids[j + 1][i], ids[j + 1][i + 1], ids[j][i + 1]], 'p')
    # rim
    ring = [ids[0][i] for i in range(na + 1)] + [ids[j][na] for j in range(1, nr + 1)] + [ids[nr][i] for i in range(na - 1, -1, -1)] + [ids[j][0] for j in range(nr - 1, 0, -1)]
    low = [mb.add_v((mb.v[v][0], mb.v[v][1], mb.v[v][2] - 0.008)) for v in ring]
    for k in range(len(ring)):
        k2 = (k + 1) % len(ring)
        mb.face([ring[k2], low[k2], low[k], ring[k]], 'p')
    d = Vector((1, 1)).normalized()
    e = Vector((1, -1)).normalized()
    s = 0.06
    for i in range(-30, 31):
        for j in range(-40, 41):
            p = c - d * 1.47 + d * (j * s) + e * (i * s)
            v = p - c
            r = v.length
            a = math.atan2(v.y, v.x) % TAU
            if not (r0 + 0.03 < r < r1 - 0.03 and abs(a - math.radians(225)) < half - 0.03 / r):
                continue
            z = float(zfun(p.x, p.y)) + 0.004
            mb.lathe([(0.0115, 0), (0.0115, 0.001), (0.009, 0.0042), (0.0055, 0.0052), (0, 0.0053)], 'p', seg=10, M=Matrix.Translation((p.x, p.y, z)))
    return finalize(mb, col, {'p': paint}, smooth=True, recalc=False)


# ============================================================================ tree pit grate + tree
def tree_grate(name="PROP_tree_grate", seed=0, W=1.32, D=1.48, hole=0.27):
    col = _col(name)
    iron = K.m_iron("crn_grate_iron", rust=0.9)
    mb = MB(name + "_grate")
    t, h = 0.012, 0.03
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        mb.bar((a[0], a[1], -h / 2), (b[0], b[1], -h / 2), 0.04, h, 'i')
    mb.bar((x0, 0, -h / 2), (-hole, 0, -h / 2), 0.03, h, 'i')
    mb.bar((hole, 0, -h / 2), (x1, 0, -h / 2), 0.03, h, 'i')
    mb.ring_tube((0, 0, -h / 2), hole, 0.018, 'i', seg=48, rseg=6)
    inner = 0.02

    def inside(x, y):
        return x0 + inner < x < x1 - inner and y0 + inner < y < y1 - inner
    R = hole + 0.06
    while R < math.hypot(W, D) / 2:
        run = []
        steps = int(TAU * R / 0.04)
        for k in range(steps + 1):
            a = TAU * k / steps
            p = (R * math.cos(a), R * math.sin(a))
            if inside(*p) and abs(p[1]) > 0.016:
                run.append(p)
            else:
                if len(run) > 1:
                    for q0, q1 in zip(run[:-1], run[1:]):
                        mb.bar((q0[0], q0[1], -h / 2), (q1[0], q1[1], -h / 2), t, h, 'i')
                run = []
        if len(run) > 1:
            for q0, q1 in zip(run[:-1], run[1:]):
                mb.bar((q0[0], q0[1], -h / 2), (q1[0], q1[1], -h / 2), t, h, 'i')
        R += 0.052
    for k in range(16):
        a = TAU * (k + 0.5) / 16
        dx, dy = math.cos(a), math.sin(a)
        L = min((W / 2 - 0.02) / max(abs(dx), 1e-6), (D / 2 - 0.02) / max(abs(dy), 1e-6))
        mb.bar((dx * hole, dy * hole, -h / 2), (dx * L, dy * L, -h / 2), 0.016, h, 'i')
    finalize(mb, col, {'i': iron})
    return col


def _leaf(mb, rng, c, size, normal, yaw, fold, key, colr, curl=0.0):
    n = Vector(normal).normalized()
    q = n.to_track_quat('Z', 'Y')
    M = Matrix.Translation(Vector(c)) @ q.to_matrix().to_4x4() @ Matrix.Rotation(yaw, 4, 'Z')
    prof = [0.0, 0.34, 0.48, 0.46, 0.34, 0.16, 0.0]
    L = size
    mid = [Vector((0, -L / 2 + L * i / 6, curl * ((i / 6 - 0.5) ** 2) * L)) for i in range(7)]
    for side in (-1, 1):
        pts = [mid[0]]
        for i in range(1, 6):
            w = prof[i] * L * 0.5
            pts.append(mid[i] + Vector((side * w * math.cos(fold), 0, w * math.sin(fold))))
        pts.append(mid[6])
        pts += [mid[i] for i in range(5, 0, -1)]
        if side < 0:
            pts = pts[::-1]
        ids = [mb.add_v(M @ p) for p in pts[:7]]
        back = [mb.add_v(M @ p) for p in pts[7:]]
        poly = ids + back
        mb.face(poly, key, cell=colr)


AUTUMN = [(0.42, 0.40, 0.05), (0.55, 0.42, 0.04), (0.62, 0.36, 0.03), (0.50, 0.18, 0.03), (0.18, 0.26, 0.04), (0.30, 0.34, 0.05), (0.60, 0.48, 0.10)]
DEAD = [(0.36, 0.22, 0.08), (0.28, 0.16, 0.06), (0.45, 0.30, 0.10), (0.22, 0.14, 0.07), (0.50, 0.36, 0.08), (0.40, 0.30, 0.16)]


def street_tree(name="PROP_street_tree", seed=0, height=7.2, leaf_density=1.0):
    """Pruned street tree (lifted crown) with tapered branch tubes and folded leaf geometry."""
    rng = random.Random(seed)
    col = _col(name)
    bark = K.m_bark("crn_bark")
    leafm = K.m_attr("crn_leaf", rough=0.55, transl=0.35)
    mb = MB(name + "_wood")
    lb = MB(name + "_leaves")
    tips = []

    def grow(p, d, L, r, depth):
        n = max(3, int(L / 0.14))
        pts, rad = [Vector(p)], [r]
        cur, dv = Vector(p), Vector(d).normalized()
        for i in range(n):
            g = 0.05 if depth < 2 else -0.04 * depth
            dv = (dv + Vector((rng.gauss(0, 0.13), rng.gauss(0, 0.13), rng.gauss(0, 0.05) + g))).normalized()
            cur = cur + dv * (L / n)
            pts.append(cur.copy())
            rad.append(max(0.003, r * (1 - 0.5 * (i + 1) / n)))
        mb.ttube(pts, rad, 'b', seg=max(5, 12 - 2 * depth), caps=(False, True))
        if depth >= 4 or r < 0.01:
            tips.append((cur, dv, depth))
            return
        if depth >= 2:
            for i in range(2, n, 2):
                tips.append((pts[i], dv, depth + 1))
        nch = rng.randint(2, 3) if depth > 0 else 3
        for k in range(nch):
            t = rng.uniform(0.5, 1.0) if depth > 0 else 1.0
            idx = min(n, max(1, int(t * n)))
            q, rq = pts[idx], rad[idx]
            ax = dv.orthogonal().normalized()
            ax.rotate(Matrix.Rotation(TAU * k / nch + rng.uniform(-0.4, 0.4), 3, dv))
            ang = rng.uniform(0.35, 0.75) if depth > 0 else rng.uniform(0.45, 0.6)
            cd = dv.copy()
            cd.rotate(Matrix.Rotation(ang, 3, ax))
            if depth == 0:
                cd = (cd + Vector((0, 0, 0.6))).normalized()
            grow(q, cd, L * rng.uniform(0.62, 0.8), rq * rng.uniform(0.62, 0.8), depth + 1)

    trunk_h = 2.7
    pts = [Vector((0, 0, -0.02)), Vector((0, 0, 0.12))]
    for k in range(1, 9):
        pts.append(Vector((rng.gauss(0, 0.01) + 0.015 * k / 8, rng.gauss(0, 0.01), 0.12 + (trunk_h - 0.12) * k / 8)))
    rads = [0.19, 0.13] + [0.115 - 0.02 * k / 8 for k in range(1, 9)]
    mb.ttube(pts, rads, 'b', seg=16, caps=(True, False))
    # root flare lumps
    for k in range(5):
        a = TAU * k / 5 + rng.uniform(-0.3, 0.3)
        mb.ttube([(0, 0, 0.12), (0.18 * math.cos(a), 0.18 * math.sin(a), -0.01), (0.3 * math.cos(a), 0.3 * math.sin(a), -0.05)], [0.07, 0.045, 0.02], 'b', seg=8)
    grow(pts[-1], Vector((0, 0, 1)), (height - trunk_h) * 0.55, 0.095, 0)
    for (p, d, depth) in tips:
        nl = int((10 if depth >= 4 else 5) * leaf_density)
        for _ in range(nl):
            off = Vector((rng.gauss(0, 0.16), rng.gauss(0, 0.16), rng.gauss(0, 0.12)))
            c = p + off + d * rng.uniform(0, 0.12)
            nrm = (Vector((rng.gauss(0, 0.6), rng.gauss(0, 0.6), 1.0)) + off * 2).normalized()
            _leaf(lb, rng, c, rng.uniform(0.07, 0.11), nrm, rng.uniform(0, TAU), rng.uniform(0.15, 0.45), 'l', rng.choice(AUTUMN), curl=0.15)
    finalize(mb, col, {'b': bark}, smooth=True, angle=80)
    finalize(lb, col, {'l': leafm}, recalc=False)
    return col


# ============================================================================ small litter
def leaf_litter(col, pts, seed=0, name="crn_leaf_litter"):
    """Fallen leaves at given points [(x, y, z, kind)], lying flat-ish and curled."""
    rng = random.Random(seed)
    mb = MB(name)
    for x, y, z, kind in pts:
        nrm = Vector((rng.gauss(0, 0.25), rng.gauss(0, 0.25), 1.0)).normalized()
        cc = rng.choice(DEAD if rng.random() < 0.7 else AUTUMN)
        _leaf(mb, rng, (x, y, z + 0.004), rng.uniform(0.06, 0.12), nrm, rng.uniform(0, TAU), rng.uniform(0.2, 0.7), 'l', cc, curl=rng.uniform(0.1, 0.6))
    return finalize(mb, col, {'l': K.m_attr("crn_leaf_dead", rough=0.7, transl=0.15)}, recalc=False)


def cigarette(col, pts, seed=0, name="crn_cigarettes"):
    rng = random.Random(seed)
    mb = MB(name)
    for x, y, z in pts:
        a = rng.uniform(0, TAU)
        d = Vector((math.cos(a), math.sin(a), 0))
        r = 0.0038
        p0 = Vector((x, y, z + r * 0.9))
        lf = 0.02
        lp = rng.uniform(0.0, 0.012)
        mb.rod(p0, p0 + d * lf, r, 'f', seg=8)
        if lp > 0.002:
            mb.rod(p0 + d * lf, p0 + d * (lf + lp), r * 0.97, 'p', seg=8)
            mb.rod(p0 + d * (lf + lp), p0 + d * (lf + lp + 0.002), r * 0.9, 'a', seg=8)
    return finalize(mb, col, {'f': K.m_plain("crn_cig_filter", (200, 150, 92), 0.8, noise=0.3, scale=200),
                              'p': K.m_plain("crn_cig_paper", (226, 222, 214), 0.8, noise=0.2),
                              'a': K.m_plain("crn_cig_ash", (60, 58, 56), 0.9, noise=0.3)}, smooth=True)


def cup_flat(name="PROP_cup_flat", seed=0):
    """A stepped-on paper coffee cup lying on the ground (label from cup.png)."""
    rng = random.Random(seed)
    col = _col(name)
    mb = MB(name + "_cup")
    seg, rows = 20, 6
    ids = []
    for j in range(rows + 1):
        t = j / rows
        z = 0.11 * t
        r = 0.03 + 0.012 * t
        row = []
        for i in range(seg + 1):
            a = TAU * i / seg
            x, y = r * math.cos(a), r * math.sin(a)
            # flatten (stepped on): squash y, crumple
            y *= 0.22 + 0.1 * rng.random()
            x *= 1.0 + 0.08 * math.sin(3 * a + t * 4)
            row.append(mb.add_v((x, y + 0.008, z)))
        ids.append(row)
    for j in range(rows):
        for i in range(seg):
            uv = [(i / seg, j / rows), ((i + 1) / seg, j / rows), ((i + 1) / seg, (j + 1) / rows), (i / seg, (j + 1) / rows)]
            mb.face([ids[j][i], ids[j][i + 1], ids[j + 1][i + 1], ids[j + 1][i]], 'c', uv=uv)
    ob = finalize(mb, col, {'c': K.m_image("crn_cup", "cup.png", rough=0.6, dirt=0.6)}, recalc=False, smooth=True)
    # lay it on its side
    me = ob.data
    M = Matrix.Rotation(-PI / 2, 4, 'X') @ Matrix.Rotation(rng.uniform(-0.1, 0.1), 4, 'Y')
    me.transform(M)
    me.transform(Matrix.Translation((0, 0, 0.012)))
    ob.modifiers.new("solid", 'SOLIDIFY').thickness = 0.0015
    return col
