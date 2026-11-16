"""Placement of street furniture, trees, traffic, parked cars, pedestrians, awnings,
sidewalk sheds and steam along the hero avenue (and sparser elsewhere)."""
import math
import random
import bpy

import materials as MAT
import protos as PR
import layout as LY
import street as ST
from cutil import MB, new_object

_count = {}


def inst(col, proto, loc, rotz=0.0, scale=1.0, name=None):
    me = PR.get(proto)
    _count[proto] = _count.get(proto, 0) + 1
    ob = bpy.data.objects.new(name or f"{proto}.{_count[proto]:04d}", me)
    ob.location = loc
    ob.rotation_euler = (0, 0, rotz)
    if scale != 1.0:
        ob.scale = (scale, scale, scale)
    col.objects.link(ob)
    if proto in SHADOWED and loc[2] < 1.0:
        sx, sy = SHADOWED[proto]
        sh = bpy.data.objects.new(f"cshadow.{proto}.{_count[proto]:04d}", PR.get('shadow_blob'))
        sh.location = (loc[0], loc[1], loc[2] + 0.006)
        sh.rotation_euler = (0, 0, rotz)
        sh.scale = (sx * scale, sy * scale, 1.0)
        col.objects.link(sh)
    return ob


# props that get a soft contact-shadow decal (footprint in metres)
SHADOWED = {'hydrant': (0.7, 0.7), 'trash': (0.9, 0.9), 'newsbox': (0.8, 0.7), 'mailbox': (0.9, 0.8), 'bench': (2.3, 0.9),
            'utilbox_0': (1.3, 1.0), 'utilbox_1': (1.3, 1.0), 'utilbox_2': (1.3, 1.0), 'planter': (1.6, 1.6),
            'bus_shelter': (4.8, 2.0), 'kiosk_0': (3.6, 2.6), 'kiosk_1': (3.6, 2.6), 'kiosk_2': (3.6, 2.6),
            'kiosk_3': (3.6, 2.6), 'bollard': (0.45, 0.45), 'meter': (0.4, 0.4), 'trashbags': (1.8, 1.2),
            'cafe': (2.0, 2.0), 'lamp': (0.7, 0.7), 'tree_a': (2.5, 2.5), 'tree_b': (2.2, 2.2), 'tree_c': (2.8, 2.8),
            'pp_walk_a': (0.6, 0.45), 'pp_walk_b': (0.6, 0.45), 'pp_walk_c': (0.6, 0.45), 'pp_stand': (0.55, 0.4),
            'pp_stand_b': (0.55, 0.4), 'pp_phone': (0.55, 0.4), 'ped_a': (0.6, 0.45), 'ped_b': (0.6, 0.45)}


def counts():
    return dict(_count)


def _inter():
    return [(y - LY.ST_W / 2, y + LY.ST_W / 2) for y in LY.street_ys()]


def _near_inter(y, pad):
    return any(a - pad <= y <= b + pad for a, b in _inter())


def place_street_furniture(cols, lots, rng):
    col = cols['props']
    Y0, Y1 = -1000.0, 1340.0
    kerb = LY.ROAD_HALF + 0.6
    # street lamps: both sides, staggered, every ~30 m
    for side in (-1, 1):
        y = Y0 + (0 if side < 0 else 15)
        while y < Y1:
            if not _near_inter(y, 3.0):
                inst(col, 'lamp', (side * kerb, y, ST.SIDEWALK_Z), rotz=(math.pi if side > 0 else 0.0))
            y += 30.0
    # signals at every avenue intersection: NE corner pole (arm toward -X over lanes)
    sigs = []
    for i, yc in enumerate(LY.street_ys()):
        if not (Y0 < yc < Y1):
            continue
        red = (hash((i * 7919) % 13) % 3) != 0
        ys = yc - LY.ST_W / 2 - 1.0
        inst(col, 'signal_red' if red else 'signal_green', (kerb - 0.1, ys, ST.SIDEWALK_Z))
        # second pole on the far (north) side facing south-bound pedestrians: same model, mirrored
        inst(col, 'signal_red' if red else 'signal_green', (-kerb + 0.1, yc + LY.ST_W / 2 + 1.0, ST.SIDEWALK_Z), rotz=math.pi)
        sigs.append((yc, red))
    # trees, hydrants, trash, newsboxes on the hero avenue sidewalks
    for side in (-1, 1):
        y = Y0 + rng.uniform(0, 8)
        while y < Y1:
            if not _near_inter(y, 6.0):
                r = rng.random()
                x = side * (LY.ROAD_HALF + 1.6)
                if r < 0.35:
                    inst(col, rng.choice(['tree_a', 'tree_b', 'tree_c']), (x, y, ST.SIDEWALK_Z), rng.uniform(0, 6.28),
                         rng.uniform(0.85, 1.15))
                elif r < 0.45:
                    inst(col, 'hydrant', (side * (LY.ROAD_HALF + 0.75), y, ST.SIDEWALK_Z), rng.uniform(0, 6.28))
                elif r < 0.55:
                    inst(col, 'trash', (side * (LY.ROAD_HALF + 0.8), y, ST.SIDEWALK_Z))
                elif r < 0.6:
                    inst(col, 'newsbox', (side * (LY.ROAD_HALF + 0.9), y, ST.SIDEWALK_Z), rotz=side * math.pi / 2)
            y += rng.uniform(7, 14)
    # trees along cross streets near the avenue
    for yc in LY.street_ys():
        if not (Y0 < yc < Y1):
            continue
        for side in (-1, 1):
            for xs in (-1, 1):
                x = xs * (LY.HERO_AVE_W / 2 + 12)
                while abs(x) < 230:
                    if rng.random() < 0.45:
                        inst(col, rng.choice(['tree_a', 'tree_b']), (x, yc + side * (LY.ST_ROAD_HALF + 1.2), ST.SIDEWALK_Z),
                             rng.uniform(0, 6.28), rng.uniform(0.8, 1.1))
                    x += xs * rng.uniform(8, 14)
    # bus shelters
    for y in (-520.0, -105.0, 270.0, 640.0, 1010.0):
        inst(col, 'bus_shelter', (LY.ROAD_HALF + 2.0, y, ST.SIDEWALK_Z), rotz=math.pi / 2)
    # manholes on the roadway
    for _ in range(140):
        y = rng.uniform(Y0, Y1)
        x = rng.choice(ST.lane_centres()) + rng.uniform(-0.8, 0.8)
        inst(col, 'manhole', (x, y, 0.0), rng.uniform(0, 6.28))
    return sigs


def place_steam(cols, rng):
    col = cols['props']
    out = []
    for (x, y) in ((-2.6, -205.0), (4.2, 118.0), (-5.9, 455.0), (0.7, 790.0)):
        inst(col, 'vent', (x, y, 0.0))
        # steam plume: overlapping homogeneous puffs (procedural-noise volumes cost ~8 s of sync each)
        import bmesh
        bm = bmesh.new()
        z = 3.4
        r = 0.45
        drift = 0.0
        for k in range(9):
            g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
            sx = rng.uniform(0.85, 1.2)
            for v in g['verts']:
                v.co.x = v.co.x * sx + drift + rng.uniform(-0.15, 0.15) * r
                v.co.y = v.co.y * sx + rng.uniform(-0.15, 0.15) * r
                v.co.z = v.co.z * rng.uniform(0.7, 1.0) + z
            z += r * 0.9
            r *= 1.28
            drift += rng.uniform(0.1, 0.5) * r
        me = bpy.data.meshes.new(f"STEAM.{len(out):02d}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(MAT.get('steam'))
        ob = new_object(f"STEAM.{len(out):02d}", me, cols['atmo'], loc=(x, y, 0.0))
        ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))
        out.append(ob)
    return out


def place_traffic(cols, sigs, rng):
    """Northbound traffic in four lanes; queues behind red lights; parked cars both sides."""
    col = cols['vehicles']
    sig_by_y = sorted(sigs)
    moving = ['sedan'] * 5 + ['suv'] * 3 + ['cab'] * 6 + ['cab_suv'] * 2 + ['van'] * 2 + ['truck'] + ['bus']
    lengths = dict(sedan=4.75, suv=4.95, cab=4.85, cab_suv=4.75, van=6.0, truck=8.0, bus=12.2)
    lanes = ST.lane_centres()
    Y0, Y1 = -1000.0, 1330.0
    placed = []
    for li, x in enumerate(lanes):
        # walk north from Y0
        y = Y0 + rng.uniform(0, 30)
        while y < Y1:
            # next stop line ahead
            ahead = [(yc, red) for (yc, red) in sig_by_y if yc - LY.ST_W / 2 - 4.6 > y]
            kind = rng.choice(moving)
            if li == 3 and rng.random() < 0.3:
                kind = 'bus'
            L = lengths[kind]
            if ahead and ahead[0][1]:
                stop = ahead[0][0] - LY.ST_W / 2 - 5.2
                # queue: fill from the stop line backward
                q = stop
                n = rng.randint(2, 6)
                for k in range(n):
                    kq = rng.choice(moving)
                    Lq = lengths[kq]
                    yq = q - Lq / 2
                    if yq < y:
                        break
                    placed.append((kq, x + rng.uniform(-0.25, 0.25), yq, True))
                    q = yq - Lq / 2 - rng.uniform(1.4, 2.6)
                y = stop + LY.ST_W + 14 + rng.uniform(0, 20)
                continue
            if not _near_inter(y, -2):
                placed.append((kind, x + rng.uniform(-0.3, 0.3), y, False))
            y += L + rng.uniform(18, 70)
    # parked cars, both curbs (gaps at intersections, hydrants and bus stops)
    parked = []
    for xs, xc in ((-1, (ST.PARK_W[0] + ST.PARK_W[1]) / 2), (1, (ST.PARK_E[0] + ST.PARK_E[1]) / 2)):
        y = Y0
        while y < Y1:
            kind = rng.choice(['sedan', 'sedan', 'suv', 'suv', 'van', 'sedan', 'cab'])
            L = lengths[kind]
            if not _near_inter(y, 9) and rng.random() < 0.82:
                parked.append((kind, xc + rng.uniform(-0.1, 0.1), y + L / 2, False))
            y += L + rng.uniform(0.8, 2.5)
    for (kind, x, y, stopped) in placed + parked:
        inst(col, kind, (x, y, 0.0), rotz=rng.uniform(-0.01, 0.01))
    # a few cars on cross streets near the avenue
    for yc in LY.street_ys():
        if not (Y0 < yc < Y1):
            continue
        for xs in (-1, 1):
            x = xs * (LY.HERO_AVE_W / 2 + 12 + rng.uniform(0, 20))
            while abs(x) < 240:
                if rng.random() < 0.35:
                    kind = rng.choice(['sedan', 'cab', 'suv', 'van'])
                    inst(col, kind, (x, yc + rng.choice([-2.6, 2.6]), 0.0), rotz=math.pi / 2 * (1 if (hash(int(yc)) % 2) else -1))
                x += xs * rng.uniform(8, 30)
    return dict(moving=len(placed), parked=len(parked))


def place_pedestrians(cols, rng):
    col = cols['props']
    n = 0
    for side in (-1, 1):
        y = -1000.0
        while y < 1340:
            if rng.random() < 0.6:
                x = side * rng.uniform(LY.ROAD_HALF + 1.0, LY.HERO_AVE_W / 2 - 0.6)
                inst(col, rng.choice(['ped_a', 'ped_b']), (x, y, ST.SIDEWALK_Z), rotz=rng.choice([0, math.pi]) + rng.uniform(-0.3, 0.3))
                n += 1
            y += rng.uniform(2, 14)
    return n


def build_awnings_and_sheds(cols, lots, rng):
    """Awnings over storefronts and green sidewalk sheds along some hero-avenue frontages."""
    col = cols['props']
    aw = MB()
    sh = MB()
    FAB = 4
    for s in lots:
        if s['ring'] != 'near' or s['kind'] != 'ave':
            continue
        x0, x1, y0, y1 = s['lot']
        if x1 <= 0:
            wx, side = x1, 1      # west side, faces +X
        elif x0 >= 0:
            wx, side = x0, -1
        else:
            continue
        if abs(abs(wx) - LY.HERO_AVE_W / 2) > 0.5:
            continue
        r = rng.random()
        if r < 0.18 and s['style'] in ('prewar', 'deco', 'slab'):
            # sidewalk shed: posts + deck + plywood fascia
            ya, yb = y0 + 0.5, y1 - 0.5
            xo = wx + side * 4.4
            zt = 3.6
            y = ya
            while y <= yb:
                for xx in (wx + side * 0.6, xo):
                    sh.box(xx - 0.08, xx + 0.08, y - 0.08, y + 0.08, 0.15, zt, 0)
                y += 2.4
            sh.box(min(wx, xo), max(wx, xo) + 0.0, ya, yb, zt, zt + 0.25, 1)
            sh.box(min(xo, xo + side * 0.05), max(xo, xo + side * 0.05), ya, yb, zt - 0.6, zt + 1.15, 0)
        elif r < 0.65:
            # awnings: per 4-8 m bay along the frontage
            y = y0 + rng.uniform(0.5, 3)
            m = rng.randrange(4)
            while y < y1 - 4:
                w = rng.uniform(3.5, 7.0)
                if rng.random() < 0.7:
                    z0, z1 = 2.9, 3.5
                    d = rng.uniform(1.2, 1.8)
                    xa = wx + side * 0.45
                    xb = wx + side * (0.45 + d)
                    aw.quad((xb, y, z0), (xb, y + w, z0), (xa, y + w, z1), (xa, y, z1), m) if side > 0 else \
                        aw.quad((xa, y, z1), (xa, y + w, z1), (xb, y + w, z0), (xb, y, z0), m)
                    # valance
                    aw.box(min(xb, xb + side * 0.02), max(xb, xb + side * 0.02), y, y + w, z0 - 0.3, z0, m)
                y += w + rng.uniform(0.5, 4)
    if aw.F:
        new_object("AWNINGS", aw.build("AWNINGS", [MAT.get('fabric_green'), MAT.get('fabric_red'), MAT.get('fabric_navy'),
                                                    MAT.get('fabric_cream')]), col)
    if sh.F:
        new_object("SHEDS", sh.build("SHEDS", [MAT.get('shed_green'), MAT.get('plywood')]), col)


SHOP_NAMES = ["KESTREL DELI", "ORLOV & SONS", "BLUE HERON CAFE", "MARLOWE PHARMACY", "NINTH LANTERN", "HALCYON SAVINGS",
              "VESPER NAILS", "ODELL HARDWARE", "PIKE ST PIZZA", "LUMEN OPTICS", "CASSIA BAKERY", "GRAND IRVING HOTEL",
              "TALBOT SHOES", "MERIDIAN BOOKS", "SABLE & CO", "PARAGON CLEANERS", "OSPREY BAR", "FENWAY FLOWERS",
              "ATLAS LUGGAGE", "COPPERLINE", "LITTLE ODESSA", "MARGO'S", "THE RIVETER", "NORTHSTAR CHEMISTS"]


def build_shop_signs(cols, lots, rng):
    """Fictional storefront names on the sign bands of hero-avenue buildings."""
    import bmesh
    col = cols['props']
    mats = [MAT.get('sign_warm'), MAT.get('sign_white'), MAT.get('sign_red'), MAT.get('sign_blue')]
    n = 0
    for s in lots:
        if s['ring'] != 'near' or s['kind'] != 'ave' or not s.get('params') or s['params'].get('curtain'):
            continue
        x0, x1, y0, y1 = s['lot']
        if x1 <= 0 and abs(x1 + LY.HERO_AVE_W / 2) < 0.5:
            side = 1
            wx = x1
        elif x0 >= 0 and abs(x0 - LY.HERO_AVE_W / 2) < 0.5:
            side = -1
            wx = x0
        else:
            continue
        gh = s['params']['gh']
        ya = y0 + 2.0
        while ya < y1 - 8:
            if rng.random() < 0.65:
                name = rng.choice(SHOP_NAMES)
                cu = bpy.data.curves.new("sign", 'FONT')
                cu.body = name
                cu.size = 0.55
                cu.extrude = 0.02
                cu.align_x = 'CENTER'
                tmp = bpy.data.objects.new("tmp", cu)
                col.objects.link(tmp)
                dg = bpy.context.evaluated_depsgraph_get()
                me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
                bpy.data.objects.remove(tmp)
                bpy.data.curves.remove(cu)
                w = max(v.co.x for v in me.vertices) - min(v.co.x for v in me.vertices) if len(me.vertices) else 1
                if w > 7.5:
                    bpy.data.meshes.remove(me)
                    ya += 4
                    continue
                me.materials.append(rng.choice(mats))
                ob = bpy.data.objects.new(f"SIGN.{n:03d}", me)
                col.objects.link(ob)
                xo = wx + side * (max(s['params']['ds'], 0.12) + 0.08)
                ob.location = (xo, ya + w / 2 + 0.3, gh - 0.85)
                # text faces +Y by default lying in XY: stand it up and face the avenue
                ob.rotation_euler = (1.5708, 0, 1.5708 if side > 0 else -1.5708)
                if side < 0:
                    ob.location = (xo, ya + w / 2 + 0.3, gh - 0.85)
                n += 1
                ya += w + rng.uniform(3, 8)
            else:
                ya += rng.uniform(4, 9)
    return n
