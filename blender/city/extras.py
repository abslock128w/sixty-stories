"""Round 6 street dressing + aerial additions. Uses its own RNGs so nothing earlier changes.

Street: subway entrances with green globe lamps, lamp-post banners, bollards, lit kiosks, mailboxes,
planters, building flags, extra pedestrian crowds, vehicle variety (town cars, hatchbacks, pickups,
step vans). Aerial: a park with tree mass and a pond, suspension bridges, industry on far shores.
"""
import math
import random
import bpy

import materials as MAT
import protos as PR
import layout as LY
import street as ST
import signage as SG
from protos import cyl, _finish
from cutil import MB, new_object
from streetlife import inst

PARK = (268.0, 732.0, 905.0, 1335.0)      # x0, x1, y0, y1 (far ring, > 250 m from the hero avenue)


def in_park(x, y, pad=0.0):
    return PARK[0] - pad <= x <= PARK[1] + pad and PARK[2] - pad <= y <= PARK[3] + pad


# ----------------------------------------------------------------- materials
MAT.BUILDERS['globe_green'] = lambda n: MAT.m_emit(n, (0.35, 1.0, 0.45), 'street_emit', 6.0, bsdf_color=(0.1, 0.5, 0.2))
MAT.BUILDERS['paint_green'] = lambda n: MAT.m_simple(n, (0.04, 0.14, 0.08), rough=0.45, noise_amt=0.1)
MAT.BUILDERS['paint_blue'] = lambda n: MAT.m_simple(n, (0.03, 0.07, 0.25), rough=0.4, noise_amt=0.1)
MAT.BUILDERS['grass'] = lambda n: MAT.m_simple(n, (0.06, 0.12, 0.03), rough=0.9, noise_amt=0.35, noise_scale=0.08)
MAT.BUILDERS['path'] = lambda n: MAT.m_simple(n, (0.32, 0.29, 0.25), rough=0.9, noise_amt=0.2)
MAT.BUILDERS['patina'] = lambda n: MAT.m_simple(n, (0.18, 0.36, 0.30), rough=0.55, metal=0.3, noise_amt=0.3, noise_scale=1.5,
                                                grime_k=0.3)
MAT.BUILDERS['cloth_var2'] = lambda n: _cloth2(n)


def _cloth2(name):
    nb, m = MAT._new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    r = nb.math('FRACT', nb.math('MULTIPLY', oi.outputs['Random'], 7.13))
    col = nb.ramp(r, [(0.0, (0.02, 0.02, 0.025)), (0.25, (0.08, 0.10, 0.20)), (0.45, (0.30, 0.26, 0.20)),
                      (0.6, (0.6, 0.58, 0.54)), (0.75, (0.05, 0.05, 0.05)), (0.9, (0.18, 0.20, 0.22))], interp='CONSTANT')
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.85})
    nb.out(p.outputs[0])
    return m


MAT.BUILDERS['cloth_var3'] = lambda n: _cloth3(n)


def _cloth3(name):
    nb, m = MAT._new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    col = nb.ramp(oi.outputs['Random'], [
        (0.0, (0.55, 0.06, 0.05)), (0.1, (0.02, 0.02, 0.025)), (0.22, (0.85, 0.82, 0.76)), (0.32, (0.06, 0.12, 0.35)),
        (0.42, (0.75, 0.55, 0.12)), (0.5, (0.04, 0.04, 0.04)), (0.6, (0.25, 0.35, 0.18)), (0.68, (0.55, 0.20, 0.40)),
        (0.76, (0.40, 0.30, 0.22)), (0.86, (0.10, 0.35, 0.55)), (0.94, (0.9, 0.9, 0.88))], interp='CONSTANT')
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.8, 'Sheen Weight': 0.3})
    nb.out(p.outputs[0])
    return m


# ----------------------------------------------------------------- props
def p_subway(name):
    """Subway entrance: railings around a stair well (dark), two green globe lamps on posts."""
    mb = MB()
    L, W = 5.2, 1.9
    mb.quad((-W / 2, -L / 2, 0.01), (W / 2, -L / 2, 0.01), (W / 2, L / 2, 0.01), (-W / 2, L / 2, 0.01), 2)
    for (x0, x1, y0, y1) in ((-W / 2 - 0.05, -W / 2, -L / 2, L / 2), (W / 2, W / 2 + 0.05, -L / 2, L / 2),
                             (-W / 2, W / 2, L / 2, L / 2 + 0.05)):
        mb.box(x0, x1, y0, y1, 0.0, 0.25, 0)
        mb.box(x0, x1, y0, y1, 0.95, 1.05, 0)
        n = int(max(x1 - x0, y1 - y0) / 0.13)
        for k in range(n):
            t = (k + 0.5) / n
            if x1 - x0 > y1 - y0:
                x = x0 + (x1 - x0) * t
                mb.box(x - 0.012, x + 0.012, y0, y1, 0.25, 0.95, 0)
            else:
                y = y0 + (y1 - y0) * t
                mb.box(x0, x1, y - 0.012, y + 0.012, 0.25, 0.95, 0)
    for x in (-W / 2, W / 2):
        cyl(mb, x, -L / 2, 0, 1.9, 0.05, 0.04, n=8, mat=0)
        cyl(mb, x, -L / 2, 1.9, 2.25, 0.17, 0.17, n=12, mat=1)
        cyl(mb, x, -L / 2, 2.25, 2.3, 0.17, 0.02, n=12, mat=1)
    # sign band on the railing front
    mb.box(-W / 2, W / 2, L / 2 + 0.05, L / 2 + 0.08, 1.05, 1.35, 0)
    return _finish(mb, name, ['paint_green', 'globe_green', 'room_dark'])


def p_bollard(name):
    mb = MB()
    cyl(mb, 0, 0, 0, 0.9, 0.13, 0.12, n=10, mat=0)
    cyl(mb, 0, 0, 0.9, 0.98, 0.12, 0.05, n=10, mat=0)
    return _finish(mb, name, ['metal_dark'])


def p_mailbox(name):
    mb = MB()
    mb.box(-0.27, 0.27, -0.25, 0.25, 0.35, 1.1, 0)
    cyl(mb, 0.0, 1.1, -0.27, 0.27, 0.25, n=10, mat=0, axis='x')
    for x in (-0.22, 0.22):
        mb.box(x - 0.03, x + 0.03, -0.2, 0.2, 0, 0.35, 1)
    return _finish(mb, name, ['paint_blue', 'metal_dark'], bevel=0.02)


def p_planter(name):
    mb = MB()
    mb.box(-0.6, 0.6, -0.6, 0.6, 0, 0.7, 0)
    rng = random.Random(5)
    for k in range(60):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0, 0.5)
        x, y, z = math.cos(a) * r, math.sin(a) * r, rng.uniform(0.75, 1.3)
        s = rng.uniform(0.12, 0.2)
        mb.poly([(x - s, y, z), (x, y - s, z + s * 0.6), (x + s, y, z), (x, y + s, z + s * 0.4)], 1)
    return _finish(mb, name, ['concrete', 'leaves'])


def _p_kiosk(name, ads):
    """Lit newsstand: box with poster lightboxes on its long sides, awning roof."""
    mb = MB()
    mb.box(-1.4, 1.4, -0.9, 0.9, 0, 2.5, 0)
    mb.box(-1.6, 1.6, -1.1, 1.1, 2.5, 2.65, 1)
    for side, ad in zip((-1, 1), ads):
        u0, v0, u1, v1 = ad['uv']
        y = side * 0.905
        pts = [(-1.2, y, 0.4), (1.2, y, 0.4), (1.2, y, 2.3), (-1.2, y, 2.3)]
        if side > 0:
            pts = [pts[1], pts[0], pts[3], pts[2]]
        mb.quad(*pts, mat=2, uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    mb.quad((1.405, -0.6, 0.9), (1.405, 0.6, 0.9), (1.405, 0.6, 2.2), (1.405, -0.6, 2.2), 3)
    return _finish(mb, name, ['paint_green', 'metal_dark', 'ad_light', 'shop'])


def p_flag(name):
    """Facade flagpole projecting at 30 deg with a striped flag (fictional)."""
    mb = MB()
    L = 3.2
    a = math.radians(30)
    for k in range(10):
        t0, t1 = k / 10, (k + 1) / 10
        x0, z0 = math.cos(a) * L * t0, math.sin(a) * L * t0
        x1, z1 = math.cos(a) * L * t1, math.sin(a) * L * t1
        mb.box(min(x0, x1), max(x0, x1) + 0.03, -0.025, 0.025, min(z0, z1), max(z0, z1) + 0.03, 0)
    tx, tz = math.cos(a) * L, math.sin(a) * L
    for i in range(4):
        z_a, z_b = tz - 0.3 * i, tz - 0.3 * (i + 1)
        m = 1 + (i % 2)
        for side in (-1, 1):
            q = [(tx, 0.0, z_b), (tx - 1.8, 0.03 * side, z_b - 0.15), (tx - 1.8, 0.03 * side, z_a - 0.15), (tx, 0.0, z_a)]
            mb.poly(q if side > 0 else q[::-1], m)
    return _finish(mb, name, ['metal_alu', 'fabric_red', 'fabric_cream'])


def p_banner(name):
    """Pair of vertical banners on a lamp post (lamp arm toward +X, banners on the pole)."""
    mb = MB()
    for side in (-1, 1):
        mb.box(0, 0.75 * side, -0.02, 0.02, 6.6, 6.64, 0) if False else None
    for (x0, x1, m) in ((0.12, 0.82, 1), (-0.82, -0.12, 2)):
        mb.box(min(x0, x1) - 0.05, max(x0, x1) + 0.05, -0.02, 0.02, 6.55, 6.6, 0)
        mb.box(min(x0, x1), max(x0, x1), -0.01, 0.01, 4.6, 6.55, m)
    return _finish(mb, name, ['metal_dark', 'fabric_navy', 'fabric_red'])


# ----------------------------------------------------------------- people
def _person(name, h, pose):
    """Better-proportioned pedestrian: tapered limbs, shoulders, head; pose stride / stand / phone."""
    mb = MB()
    s = h / 1.75
    SKIN, PANTS, TOP, SHOE, HAIR = 0, 1, 2, 3, 4
    st = {'walk_a': 0.32, 'walk_b': -0.32, 'stand': 0.0, 'phone': 0.05}[pose]

    def limb(x, z_top, z_bot, swing, r0, r1, m, y0=0.0):
        L = z_top - z_bot
        yb = y0 + math.sin(swing) * L
        zb = z_top - math.cos(swing) * L
        n = 8
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            p0 = (x + math.cos(a0) * r0, y0 + math.sin(a0) * r0, z_top)
            p1 = (x + math.cos(a1) * r0, y0 + math.sin(a1) * r0, z_top)
            p2 = (x + math.cos(a1) * r1, yb + math.sin(a1) * r1, zb)
            p3 = (x + math.cos(a0) * r1, yb + math.sin(a0) * r1, zb)
            mb.poly([p3, p2, p1, p0], m, smooth=True)
        return yb, zb
    hip = 0.93 * s
    for side, sw in ((-1, st), (1, -st)):
        yb, zb = limb(side * 0.09 * s, hip, 0.08 * s, sw, 0.075 * s, 0.05 * s, PANTS)
        mb.box(side * 0.09 * s - 0.05 * s, side * 0.09 * s + 0.05 * s, yb - 0.06 * s, yb + 0.16 * s, 0, 0.09 * s, SHOE)
    # torso: tapered 8-gon from hips to shoulders
    for k in range(8):
        a0, a1 = 2 * math.pi * k / 8, 2 * math.pi * (k + 1) / 8
        def P(a, z, rx, ry):
            return (math.cos(a) * rx, math.sin(a) * ry, z)
        mb.poly([P(a0, hip - 0.05 * s, 0.17 * s, 0.11 * s), P(a1, hip - 0.05 * s, 0.17 * s, 0.11 * s),
                 P(a1, 1.45 * s, 0.21 * s, 0.12 * s), P(a0, 1.45 * s, 0.21 * s, 0.12 * s)], TOP, smooth=True)
    mb.poly([(math.cos(2 * math.pi * k / 8) * 0.21 * s, math.sin(2 * math.pi * k / 8) * 0.12 * s, 1.45 * s) for k in range(8)], TOP)
    for side, sw in ((-1, -st * 0.8), (1, st * 0.8)):
        if pose == 'phone' and side > 0:
            limb(side * 0.24 * s, 1.42 * s, 1.18 * s, 0.0, 0.05 * s, 0.045 * s, TOP)
            limb(side * 0.24 * s, 1.18 * s, 1.0 * s, -1.9, 0.045 * s, 0.035 * s, TOP)
            continue
        limb(side * 0.24 * s, 1.42 * s, 0.82 * s, sw, 0.055 * s, 0.04 * s, TOP)
    cyl(mb, 0, 0, 1.45 * s, 1.52 * s, 0.05 * s, 0.05 * s, n=8, mat=SKIN)
    # head (squashed 10-gon spheroid stack)
    rings = [(1.52, 0.06), (1.56, 0.095), (1.63, 0.105), (1.70, 0.095), (1.75, 0.06), (1.77, 0.0)]
    for (z0, r0), (z1, r1) in zip(rings[:-1], rings[1:]):
        cyl(mb, 0, 0.01 * s, z0 * s, z1 * s, r0 * s, r1 * s, n=10, mat=SKIN if z1 < 1.69 else HAIR, cap=False)
    return _finish(mb, name, ['skin', 'cloth_var2', 'cloth_var3', 'rubber', 'cloth_dark'])


for _n, _h, _p in (('pp_walk_a', 1.78, 'walk_a'), ('pp_walk_b', 1.66, 'walk_b'), ('pp_stand', 1.72, 'stand'),
                   ('pp_phone', 1.62, 'phone'), ('pp_walk_c', 1.84, 'walk_b'), ('pp_stand_b', 1.6, 'stand')):
    PR.BUILD[_n] = (lambda h, p: (lambda name: _person(name, h, p)))(_h, _p)
PR.BUILD['ped_a'] = PR.BUILD['pp_walk_a']
PR.BUILD['ped_b'] = PR.BUILD['pp_walk_b']
PEOPLE = ['pp_walk_a', 'pp_walk_b', 'pp_stand', 'pp_phone', 'pp_walk_c', 'pp_stand_b']


# ----------------------------------------------------------------- vehicles
def p_town_car(name):
    return PR._car(name, 5.25, 1.9, 1.48, 0.97, 0.47, paint='paint_black', hood=1.25, trunk=1.0)


def p_hatch(name):
    return PR._car(name, 4.2, 1.78, 1.5, 0.95, 0.5, hood=0.95, trunk=0.25)


def p_pickup(name):
    mb_me = PR._car(name, 5.6, 2.0, 1.85, 1.15, 0.55, hood=1.4, trunk=2.0)
    return mb_me


def p_step_van(name):
    return PR._boxveh(name, 6.6, 2.3, 3.2, 1.3, 'paint_brown')


MAT.BUILDERS['paint_black'] = lambda n: MAT.m_simple(n, (0.012, 0.012, 0.014), rough=0.2, coat=1.0, noise_amt=0.0)
MAT.BUILDERS['paint_brown'] = lambda n: MAT.m_simple(n, (0.20, 0.12, 0.06), rough=0.45, noise_amt=0.05, grime_k=0.2)
PR.BUILD.update(town_car=p_town_car, hatch=p_hatch, pickup=p_pickup, step_van=p_step_van, subway=p_subway,
                bollard=p_bollard, mailbox=p_mailbox, planter=p_planter, flag=p_flag, banner=p_banner)
REMAP = {'sedan': [('sedan', 4), ('town_car', 3), ('hatch', 2)], 'suv': [('suv', 3), ('pickup', 1)],
         'van': [('van', 2), ('step_van', 1)], 'truck': [('truck', 1)]}


def remap_vehicles(col):
    r = random.Random(77)
    n = 0
    for ob in list(col.objects):
        base = ob.data.name[2:] if ob.data.name.startswith('P_') else None
        if base in REMAP:
            ch = REMAP[base]
            tot = sum(w for _, w in ch)
            x = r.random() * tot
            for k, w in ch:
                x -= w
                if x <= 0:
                    break
            if k != base:
                ob.data = PR.get(k)
                n += 1
    return n


# ----------------------------------------------------------------- street dressing
def dress_street(cols, specs):
    r = random.Random(9090)
    col = cols['props']
    kerb = LY.ROAD_HALF + 0.6
    ys = [y for y in LY.street_ys() if -1000 < y < 1330]
    n = dict()

    def add(proto, loc, rz=0.0, sc=1.0):
        inst(col, proto, loc, rz, sc)
        n[proto] = n.get(proto, 0) + 1
    # banners on every other street lamp
    for ob in list(col.objects):
        if ob.data.name == 'P_lamp' and r.random() < 0.6:
            add('banner', tuple(ob.location), ob.rotation_euler[2])
    for i, yc in enumerate(ys):
        for side in (-1, 1):
            xs = side * (LY.ROAD_HALF + 3.6)
            # subway entrances on some corners (stairs run along the avenue)
            if (i + (side > 0)) % 3 == 0:
                add('subway', (xs, yc + side * (LY.ST_W / 2 + 6.0), ST.SIDEWALK_Z), 0.0 if side < 0 else math.pi)
            # corner furniture
            for sy in (-1, 1):
                yb = yc + sy * (LY.ST_W / 2 + 1.2)
                for k in range(3):
                    add('bollard', (side * (LY.ROAD_HALF + 0.55), yb + sy * k * 1.4, ST.SIDEWALK_Z))
                if r.random() < 0.5:
                    add('mailbox', (side * (LY.ROAD_HALF + 1.0), yb + sy * 5.5, ST.SIDEWALK_Z), r.uniform(-0.1, 0.1))
            if r.random() < 0.4:
                add('kiosk_%d' % r.randrange(4), (side * (LY.ROAD_HALF + 2.4), yc + r.choice((-1, 1)) * (LY.ST_W / 2 + 14),
                                                  ST.SIDEWALK_Z), math.pi / 2)
        # crowds waiting at the crosswalks
        for side in (-1, 1):
            for sy in (-1, 1):
                for k in range(r.randint(2, 9)):
                    x = side * r.uniform(LY.ROAD_HALF + 0.7, LY.HERO_AVE_W / 2 - 0.5)
                    y = yc + sy * (LY.ST_W / 2 + r.uniform(0.6, 3.5))
                    add(r.choice(PEOPLE[2:4] + PEOPLE[5:]), (x, y, ST.SIDEWALK_Z), (math.pi / 2 if side < 0 else -math.pi / 2) + r.uniform(-0.6, 0.6))
            # people on the crosswalks across the cross street
            if r.random() < 0.5:
                for k in range(r.randint(1, 5)):
                    x = r.choice((-1, 1)) * r.uniform(LY.HERO_AVE_W / 2 + 0.8, LY.HERO_AVE_W / 2 + 3.8)
                    add(r.choice(PEOPLE[:2] + PEOPLE[4:5]), (x, yc + r.uniform(-4.5, 4.5), 0.0), r.choice((0, math.pi)))
    # dense walking crowds on both avenue sidewalks
    for side in (-1, 1):
        y = -1000.0
        while y < 1330:
            if r.random() < 0.8:
                x = side * r.uniform(LY.ROAD_HALF + 1.0, LY.HERO_AVE_W / 2 - 0.5)
                add(r.choice(PEOPLE), (x, y, ST.SIDEWALK_Z), r.choice((0, math.pi)) + r.uniform(-0.25, 0.25))
            y += r.uniform(0.8, 4.5)
    # planters + flags on near-ring avenue frontages
    for s in specs:
        if s['ring'] != 'near' or s['kind'] != 'ave' or not s.get('params'):
            continue
        w = SG.avenue_walls(s)
        if w is None:
            continue
        if r.random() < 0.35:
            add('planter', (w.fx + w.sx * 1.2, r.uniform(w.y0 + 2, w.y1 - 2), ST.SIDEWALK_Z))
        if r.random() < 0.3 and s.get('roof_z', 0) > 20:
            z = s['params']['gh'] + s['params']['storey'] * r.randint(1, 3)
            for k in range(r.randint(1, 3)):
                add('flag', (w.fx + w.sx * 0.4, w.y0 + 3 + k * 4.0, z), 0.0 if w.sx > 0 else math.pi)
    return n


def build_kiosks():
    r = random.Random(31)
    for k in range(4):
        ads = [SG.AdPicker(r).pick(1.0, 1.5), SG.AdPicker(r).pick(1.0, 1.5)]
        PR.BUILD['kiosk_%d' % k] = (lambda a: (lambda name: _p_kiosk(name, a)))(ads)


# ----------------------------------------------------------------- aerial
def build_park(cols):
    col = cols['far']
    x0, x1, y0, y1 = PARK
    mb = MB()
    mb.box(x0, x1, y0, y1, 0.0, 0.32, 0, skip=('-z',))
    r = random.Random(12)
    # pond
    cx, cy = (x0 + x1) / 2 + 60, y0 + 140
    pts = []
    for k in range(24):
        a = 2 * math.pi * k / 24
        rr = 70 + 18 * math.sin(3 * a) + 10 * math.cos(5 * a)
        pts.append((cx + math.cos(a) * rr * 1.4, cy + math.sin(a) * rr))
    mb.poly([(p[0], p[1], 0.34) for p in pts], 2)
    # meandering paths
    for k in range(5):
        y = y0 + 40 + k * 85
        prev = None
        for i in range(25):
            x = x0 + (x1 - x0) * i / 24
            yy = y + 18 * math.sin(i * 0.7 + k)
            if prev:
                mb.quad((prev[0], prev[1] - 2, 0.33), (x, yy - 2, 0.33), (x, yy + 2, 0.33), (prev[0], prev[1] + 2, 0.33), 1)
            prev = (x, yy)
    new_object("PARK_ground", mb.build("PARK_ground", [MAT.get('grass'), MAT.get('path'), MAT.get('water')]), col)
    n = 0
    for k in range(1400):
        x, y = r.uniform(x0 + 4, x1 - 4), r.uniform(y0 + 4, y1 - 4)
        if ((x - cx) / 1.4) ** 2 + (y - cy) ** 2 < 95 ** 2:
            continue
        inst(col, r.choice(['tree_a', 'tree_b', 'tree_c']), (x, y, 0.32), r.uniform(0, 6.28), r.uniform(1.3, 2.1))
        n += 1
    return n


MAT.BUILDERS['bridge_steel'] = lambda n: MAT.m_simple(n, (0.18, 0.22, 0.26), rough=0.5, metal=0.6, noise_amt=0.15, grime_k=0.3)


def build_bridges(cols):
    col = cols['far']
    mb = MB()
    STEEL, STONE, DECK = 0, 1, 2
    specs = [(1390.0, 2350.0, -767.5), (1390.0, 2350.0, 337.5), (-2350.0, -1390.0, -172.5)]
    for (xa, xb, y) in specs:
        zd = 42.0
        mb.box(xa - 260 if xa > 0 else xa, xb if xa > 0 else xb + 260, y - 12, y + 12, zd - 2.5, zd, DECK)
        # approach ramps down into the streets
        ramp_from = xa - 260 if xa > 0 else xb + 260
        ramp_to = xa if xa > 0 else xb
        L = xb - xa
        t1, t2 = xa + L * 0.2, xa + L * 0.8
        for tx in (t1, t2):
            for sy in (-1, 1):
                mb.box(tx - 4, tx + 4, y + sy * 13 - 3, y + sy * 13 + 3, -2, 135, STONE)
            for zz in (60, 100, 128):
                mb.box(tx - 3, tx + 3, y - 13, y + 13, zz, zz + 5, STONE)
        # main cables (catenaries) + suspenders
        for sy in (-1, 1):
            yy = y + sy * 13
            segs = []
            ends = [(xa - (40 if xa > 0 else 0), zd + 2), (t1, 135), (t2, 135), (xb + (0 if xa > 0 else 40), zd + 2)]
            for (pa, pb, sag) in ((ends[0], ends[1], 10), (ends[1], ends[2], 85), (ends[2], ends[3], 10)):
                n = 30
                for i in range(n):
                    u0, u1 = i / n, (i + 1) / n
                    def P(u):
                        return (pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u - sag * 4 * u * (1 - u))
                    q0, q1 = P(u0), P(u1)
                    mb.box(min(q0[0], q1[0]), max(q0[0], q1[0]) + 0.1, yy - 0.6, yy + 0.6, min(q0[1], q1[1]) - 0.4,
                           max(q0[1], q1[1]) + 0.4, STEEL)
                    if i % 2 == 0 and q0[1] > zd + 1:
                        mb.box(q0[0] - 0.1, q0[0] + 0.1, yy - 0.1, yy + 0.1, zd, q0[1], STEEL)
        # truss sides
        mb.box(xa, xb, y - 12.5, y - 11.5, zd, zd + 4, STEEL)
        mb.box(xa, xb, y + 11.5, y + 12.5, zd, zd + 4, STEEL)
        # ramp inside the city: slopes down to street level
        n = 12
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            if xa > 0:
                xa_, xb_ = ramp_from + (ramp_to - ramp_from) * u0, ramp_from + (ramp_to - ramp_from) * u1
                za, zb_ = zd * u0, zd * u1
            else:
                xa_, xb_ = ramp_to + (ramp_from - ramp_to) * u0, ramp_to + (ramp_from - ramp_to) * u1
                za, zb_ = zd * (1 - u0), zd * (1 - u1)
            mb.box(min(xa_, xb_), max(xa_, xb_), y - 9, y + 9, max(0.2, min(za, zb_) - 1.5), max(za, zb_), DECK)
    new_object("BRIDGES", mb.build("BRIDGES", [MAT.get('bridge_steel'), MAT.get('concrete'), MAT.get('concrete')]), col)


def build_industry(cols):
    """Low industrial fabric on the far shores: tanks, sheds, chimneys (aerial horizon texture)."""
    col = cols['far']
    r = random.Random(55)
    mb = MB()
    for k in range(260):
        side = r.choice(['n', 'e', 'w'])
        if side == 'n':
            x, y = r.uniform(-4000, 4000), r.uniform(2400, 3200)
        elif side == 'e':
            x, y = r.uniform(2400, 3300), r.uniform(-3000, 2300)
        else:
            x, y = r.uniform(-3300, -2400), r.uniform(-3000, 2300)
        t = r.random()
        if t < 0.4:
            cyl(mb, x, y, 0.3, r.uniform(8, 20), r.uniform(8, 18), n=16, mat=0)
        elif t < 0.85:
            w, d = r.uniform(30, 90), r.uniform(20, 60)
            mb.box(x, x + w, y, y + d, 0.3, r.uniform(8, 16), 1)
        else:
            cyl(mb, x, y, 0.3, r.uniform(40, 90), 2.5, 1.6, n=10, mat=2)
    new_object("HORIZON_industry", mb.build("HORIZON_industry", [MAT.get('metal_alu'), MAT.get('concrete'),
                                                                 MAT.get('concrete')]), col)
