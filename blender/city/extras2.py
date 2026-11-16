"""Round 7 street detail: cross-street population and signage, parking meters, benches, bike racks,
utility boxes with stickers, security cameras, tactile paving, road arrows, litter and leaves,
graffiti on side walls, drainpipes, building numbers; waterfront piers and boats; skybridge-tower
crowns. Own RNGs throughout (nothing earlier changes)."""
import math
import zlib
import os
import random
import bpy
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import materials as MAT
import protos as PR
import layout as LY
import street as ST
import signage as SG
import extras as EX
from protos import cyl, _finish
from cutil import MB, new_object
from streetlife import inst

GRAFFITI = None
GINFO = []


def build_graffiti_atlas(out_dir):
    """16 invented spray tags / throw-ups on transparent background (2048 atlas, RGBA)."""
    global GRAFFITI
    S, N = 512, 4
    im = Image.new('RGBA', (S * N, S * N), (0, 0, 0, 0))
    r = random.Random(77)
    words = ["ZEKO", "MIRA", "KRASH", "OHNO", "VEXT", "LUMA", "DOZE", "REKT", "FIZZ", "OMEN", "SKAR", "NUBE", "TIKO",
             "JAXX", "PLUM", "WREN"]
    fonts = [SG.adgen.FONTS[k] for k in ('black', 'xbi', 'cond', 'serif2')]
    for i in range(N * N):
        cell = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(cell)
        col = r.choice([(230, 40, 60), (40, 180, 230), (250, 220, 40), (240, 240, 240), (30, 30, 30), (150, 60, 200),
                        (60, 200, 90)])
        out = r.choice([(10, 10, 10), (255, 255, 255), (250, 120, 20)])
        f = ImageFont.truetype(r.choice(fonts), r.randint(120, 190))
        txt = words[i]
        x, y = 30 + r.randint(0, 40), 140 + r.randint(-40, 60)
        for dx in range(-8, 9, 4):
            for dy in range(-8, 9, 4):
                d.text((x + dx, y + dy), txt, font=f, fill=out + (255,))
        d.text((x, y), txt, font=f, fill=col + (255,))
        for k in range(r.randint(0, 4)):   # drips
            xx = r.randint(40, 460)
            d.line([(xx, 300), (xx, 300 + r.randint(20, 120))], fill=col + (230,), width=4)
        cell = cell.rotate(r.uniform(-12, 12), resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
        im.paste(cell, ((i % N) * S, (i // N) * S))
        GINFO.append(((i % N) / N, 1 - (i // N + 1) / N, (i % N + 1) / N, 1 - (i // N) / N))
    path = os.path.join(out_dir, "graffiti_atlas.png")
    im.save(path)
    GRAFFITI = bpy.data.images.load(path)
    GRAFFITI.name = "CITY_graffiti_atlas"
    GRAFFITI.pack()


def m_graffiti(name):
    nb, m = MAT._new(name)
    t = nb.n('ShaderNodeTexImage', image=GRAFFITI, interpolation='Linear')
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    nb.link(uv.outputs['UV'], t.inputs['Vector'])
    p = nb.principled(**{'Base Color': t.outputs['Color'], 'Roughness': 0.6})
    tr = nb.n('ShaderNodeBsdfTransparent')
    mx = nb.n('ShaderNodeMixShader', i_Fac=nb.math('MULTIPLY', t.outputs['Alpha'], 0.92))
    nb.link(tr.outputs[0], mx.inputs[1])
    nb.link(p.outputs[0], mx.inputs[2])
    nb.out(mx.outputs[0])
    return m


MAT.BUILDERS['graffiti'] = m_graffiti
MAT.BUILDERS['tactile'] = lambda n: MAT.m_simple(n, (0.65, 0.48, 0.05), rough=0.6, noise_amt=0.2, noise_scale=40, bump=0.6)
MAT.BUILDERS['paper'] = lambda n: MAT.m_simple(n, (0.7, 0.7, 0.66), rough=0.8, noise_amt=0.2)
MAT.BUILDERS['leaf_dry'] = lambda n: MAT.m_simple(n, (0.28, 0.14, 0.04), rough=0.8, noise_amt=0.4, noise_scale=30)
MAT.BUILDERS['wood_bench'] = lambda n: MAT.m_simple(n, (0.30, 0.18, 0.08), rough=0.6, noise_amt=0.3, noise_scale=6, bump=0.2)


# ----------------------------------------------------------------- props
def p_meter(name):
    mb = MB()
    cyl(mb, 0, 0, 0, 1.05, 0.04, 0.04, n=8, mat=0)
    mb.box(-0.12, 0.12, -0.09, 0.09, 1.05, 1.45, 0)
    mb.box(-0.08, 0.08, -0.095, -0.09, 1.2, 1.32, 1)
    return _finish(mb, name, ['metal_dark', 'sign_white'])


def p_bench(name):
    mb = MB()
    for x in (-0.8, 0.8):
        mb.box(x - 0.04, x + 0.04, -0.25, 0.25, 0, 0.45, 1)
        mb.box(x - 0.04, x + 0.04, 0.2, 0.25, 0.45, 0.85, 1)
    for k in range(4):
        mb.box(-0.95, 0.95, -0.25 + k * 0.12, -0.17 + k * 0.12, 0.43, 0.46, 0)
    for k in range(3):
        mb.box(-0.95, 0.95, 0.24, 0.27, 0.55 + k * 0.1, 0.62 + k * 0.1, 0)
    return _finish(mb, name, ['wood_bench', 'metal_dark'])


def p_bikerack(name):
    mb = MB()
    for x in (-1.2, -0.4, 0.4, 1.2):
        n = 8
        for k in range(n):
            a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
            p0 = (math.cos(a0) * 0.35, 0.55 + math.sin(a0) * 0.3)
            p1 = (math.cos(a1) * 0.35, 0.55 + math.sin(a1) * 0.3)
            mb.box(x - 0.025, x + 0.025, min(p0[0], p1[0]) - 0.025, max(p0[0], p1[0]) + 0.025, min(p0[1], p1[1]),
                   max(p0[1], p1[1]) + 0.03, 0)
        for y in (-0.35, 0.35):
            mb.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 0.56, 0)
    return _finish(mb, name, ['metal_alu'])


def p_utilbox(name, ad):
    """Utility / signal-controller box plastered with stickers and a paste-up."""
    mb = MB()
    mb.box(-0.45, 0.45, -0.3, 0.3, 0, 1.3, 0)
    mb.box(-0.5, 0.5, -0.35, 0.35, 1.3, 1.36, 0)
    u0, v0, u1, v1 = ad['uv']
    mb.quad((-0.35, -0.302, 0.3), (0.35, -0.302, 0.3), (0.35, -0.302, 1.2), (-0.35, -0.302, 1.2), 1,
            uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    r = random.Random(zlib.crc32(name.encode()))
    for k in range(10):
        x, z = r.uniform(-0.4, 0.3), r.uniform(0.1, 1.2)
        s = r.uniform(0.05, 0.12)
        mb.quad((0.452, x, z), (0.452, x + s, z), (0.452, x + s, z + s * r.uniform(0.6, 1.4)), (0.452, x, z + s), 2 + k % 3)
    return _finish(mb, name, ['hvac_paint', 'ad_print', 'paint_white', 'sig_red', 'paint_yellow'])


def p_camera(name):
    mb = MB()
    mb.box(-0.04, 0.04, 0, 0.35, -0.04, 0.04, 0)
    mb.box(-0.08, 0.08, 0.3, 0.6, -0.12, 0.0, 1)
    mb.box(-0.05, 0.05, 0.6, 0.62, -0.09, -0.03, 2)
    return _finish(mb, name, ['metal_dark', 'paint_white', 'car_glass'])


def p_litter(name):
    """A scatter of litter and dry leaves for sidewalks and gutters (~2 x 1.2 m patch)."""
    mb = MB()
    r = random.Random(zlib.crc32(name.encode()))
    for k in range(70):
        x, y = r.uniform(-1.0, 1.0), r.uniform(-0.6, 0.6)
        a = r.uniform(0, 6.28)
        s = r.uniform(0.03, 0.08)
        m = 1 if k < 58 else (0 if k < 66 else 2)
        z = 0.004 + r.uniform(0, 0.01)
        ca, sa = math.cos(a) * s, math.sin(a) * s
        mb.poly([(x - ca, y - sa, z), (x - sa * 0.6, y + ca * 0.6, z + 0.005), (x + ca, y + sa, z), (x + sa * 0.6, y - ca * 0.6, z)], m)
    for k in range(2):   # cups / cans
        x, y = r.uniform(-0.8, 0.8), r.uniform(-0.5, 0.5)
        cyl(mb, x, y, 0.0, 0.11, 0.035, 0.045, n=8, mat=3)
    return _finish(mb, name, ['paper', 'leaf_dry', 'fabric_red', 'sig_red'])


def p_drainpipe(name):
    mb = MB()
    cyl(mb, 0, 0, 0.0, 1.0, 0.06, 0.06, n=8, mat=0)
    for z in (0.2, 0.8):
        mb.box(-0.08, 0.08, -0.08, 0.08, z, z + 0.03, 0)
    return _finish(mb, name, ['metal_dark'])


def p_boat(name, L, kind):
    mb = MB()
    n = 10
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        def w(t):
            return 0.5 * L * 0.32 * (1 - max(0.0, t - 0.7) / 0.3 * 0.95)
        y0, y1 = -L / 2 + L * t0, -L / 2 + L * t1
        for s in (-1, 1):
            q = [(s * w(t0), y0, 1.2), (s * w(t1), y1, 1.2), (s * w(t1) * 0.6, y1, -0.4), (s * w(t0) * 0.6, y0, -0.4)]
            mb.poly(q if s > 0 else q[::-1], 0)
        mb.quad((-w(t0), y0, 1.2), (w(t0), y0, 1.2), (w(t1), y1, 1.2), (-w(t1), y1, 1.2), 1)
    if kind == 'ferry':
        mb.box(-L * 0.12, L * 0.12, -L * 0.35, L * 0.2, 1.2, 4.0, 0)
        mb.box(-L * 0.11, L * 0.11, -L * 0.3, L * 0.15, 2.2, 3.2, 2)
        mb.box(-L * 0.08, L * 0.08, -L * 0.1, L * 0.1, 4.0, 6.0, 3)
    else:
        mb.box(-L * 0.08, L * 0.08, -L * 0.1, L * 0.12, 1.2, 3.0, 0)
        mb.box(-L * 0.075, L * 0.075, 0.05 * L, L * 0.12, 2.0, 2.8, 2)
    return _finish(mb, name, ['paint_white', 'plywood', 'car_glass', 'fabric_red'])


def p_roadplate(name):
    mb = MB()
    mb.box(-1.2, 1.2, -0.8, 0.8, 0.0, 0.025, 0)
    for x in (-1.15, 1.15):
        mb.box(x - 0.03, x + 0.03, -0.75, 0.75, 0.025, 0.03, 1)
    return _finish(mb, name, ['metal_dark', 'paint_black'], bevel=0.01)


def register():
    ads = [a for a in SG.INFO if 0.6 <= a['aspect'] <= 0.8]
    PR.BUILD.update(roadplate=p_roadplate, meter=p_meter, bench=p_bench, bikerack=p_bikerack, camera=p_camera, drainpipe=p_drainpipe,
                    ferry=lambda n: p_boat(n, 38.0, 'ferry'), tug=lambda n: p_boat(n, 22.0, 'tug'))
    for k in range(3):
        PR.BUILD['utilbox_%d' % k] = (lambda a: (lambda n: p_utilbox(n, a)))(ads[k * 3 % len(ads)])
    for k in range(4):
        PR.BUILD['litter_%d' % k] = p_litter


# ----------------------------------------------------------------- placement
def dress(cols, specs):
    r = random.Random(4242)
    col = cols['props']
    n = {}

    def add(proto, loc, rz=0.0, sc=1.0):
        inst(col, proto, loc, rz, sc)
        n[proto] = n.get(proto, 0) + 1
    ys = [y for y in LY.street_ys() if -1000 < y < 1330]
    kerb = LY.ROAD_HALF + 0.45
    # avenue: meters by the parking lanes, benches, racks, utility boxes, litter
    for side in (-1, 1):
        y = -1000.0
        while y < 1330:
            if not any(abs(y - yc) < LY.ST_W / 2 + 4 for yc in ys):
                k = r.random()
                if k < 0.35:
                    add('meter', (side * kerb, y, ST.SIDEWALK_Z), 0 if side < 0 else math.pi)
                elif k < 0.45:
                    add('bench', (side * (LY.ROAD_HALF + 2.2), y, ST.SIDEWALK_Z), math.pi / 2 * (1 if side < 0 else -1))
                elif k < 0.52:
                    add('bikerack', (side * (LY.ROAD_HALF + 1.4), y, ST.SIDEWALK_Z), math.pi / 2)
                elif k < 0.58:
                    add('utilbox_%d' % r.randrange(3), (side * (LY.ROAD_HALF + 0.9), y, ST.SIDEWALK_Z), r.choice((0, math.pi)))
                if r.random() < 0.5:
                    add('litter_%d' % r.randrange(4), (side * r.uniform(LY.ROAD_HALF - 0.6, LY.HERO_AVE_W / 2 - 0.5), y,
                                                       ST.SIDEWALK_Z if r.random() < 0.6 else 0.0), r.uniform(0, 6.28))
            y += r.uniform(5, 12)
    for k in range(30):
        add('roadplate', (r.choice(ST.lane_centres()) + r.uniform(-0.5, 0.5), r.uniform(-900, 1300), 0.0), r.uniform(-0.1, 0.1))
    # tactile strips + road arrows + cameras at intersections
    mb = MB()
    for yc in ys:
        for side in (-1, 1):
            for sy in (-1, 1):
                ye = yc + sy * (LY.ST_W / 2 + 0.3)
                x0 = side * (LY.ROAD_HALF + 0.35)
                x1 = side * (LY.ROAD_HALF + 4.0)
                mb.box(min(x0, x1), max(x0, x1), min(ye, ye + sy * 0.6), max(ye, ye + sy * 0.6), ST.SIDEWALK_Z,
                       ST.SIDEWALK_Z + 0.008, 0)
        yb = yc - LY.ST_W / 2 - 12
        for xl in ST.lane_centres():
            ax = [(xl - 0.15, yb - 4.0), (xl + 0.15, yb - 4.0), (xl + 0.15, yb - 1.2), (xl + 0.45, yb - 1.2), (xl, yb),
                  (xl - 0.45, yb - 1.2), (xl - 0.15, yb - 1.2)]
            mb.poly([(p[0], p[1], 0.006) for p in ax], 1)
    new_object("STREET_tactile_arrows", mb.build("STREET_tactile_arrows", [MAT.get('tactile'), MAT.get('paint_white')]), cols['street'])
    # cross streets: people, parked cars, trees exist; add more traffic, signs, items
    for yc in ys:
        for xs in (-1, 1):
            x = xs * (LY.HERO_AVE_W / 2 + 8)
            while abs(x) < 235:
                if r.random() < 0.7:
                    add(r.choice(EX.PEOPLE), (x + r.uniform(-1, 1), yc + r.choice((-1, 1)) * r.uniform(LY.ST_ROAD_HALF + 0.6, LY.ST_W / 2 - 0.3),
                                              ST.SIDEWALK_Z), r.choice((math.pi / 2, -math.pi / 2)) + r.uniform(-0.3, 0.3))
                if r.random() < 0.25:
                    kind = r.choice(['sedan', 'cab', 'town_car', 'suv', 'hatch', 'van', 'cab', 'step_van'])
                    add(kind, (x, yc + r.choice((-2.7, 2.7)), 0.0), math.pi / 2 * (1 if r.random() < 0.5 else -1))
                if r.random() < 0.08:
                    add('litter_%d' % r.randrange(4), (x, yc + r.choice((-1, 1)) * (LY.ST_ROAD_HALF + 1.5), ST.SIDEWALK_Z), r.uniform(0, 6.28))
                x += xs * r.uniform(3, 9)
    # cross-street faces of near avenue lots: lightboxes, blade signs, graffiti, drainpipes, numbers, cameras
    gm = MB()
    sm = MB()
    for s in specs:
        if s['ring'] != 'near' or not s.get('params'):
            continue
        x0, x1, y0, y1 = s['lot']
        gh = s['params']['gh']
        for (yy, sy) in ((y0, -1), (y1, 1)):
            if not any(abs(abs(yy - c) - LY.ST_W / 2) < 0.6 for c in ys):
                continue
            yf = yy + sy * (s['params']['dp'] + s['params']['ds'] + 0.3)
            x = x0 + 2
            while x < x1 - 4:
                k = r.random()
                if k < 0.45:
                    ad = SG.AdPicker(r).pick(2.0, 4.0, ('ad_logo', 'ad_type', 'ad_product'))
                    h = 0.8
                    w = h * ad['aspect']
                    if x + w > x1 - 1:
                        break
                    u0, v0, u1, v1 = ad['uv']
                    pts = [(x, yf, gh - 1.2), (x + w, yf, gh - 1.2), (x + w, yf, gh - 1.2 + h), (x, yf, gh - 1.2 + h)]
                    uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                    if sy > 0:   # viewer looking -y: right is -x
                        pts = [pts[1], pts[0], pts[3], pts[2]]
                    sm.quad(*pts, mat=1, uv=uv)
                    sm.box(x - 0.05, x + w + 0.05, min(yf, yf - sy * 0.25), max(yf, yf - sy * 0.25), gh - 1.25, gh - 1.1 + h, 0)
                    x += w + r.uniform(1, 3)
                elif k < 0.6:
                    gi = GINFO[r.randrange(len(GINFO))]
                    w = r.uniform(2.0, 3.5)
                    pts = [(x, yf - sy * 0.25, 0.3), (x + w, yf - sy * 0.25, 0.3), (x + w, yf - sy * 0.25, 0.3 + w / 2),
                           (x, yf - sy * 0.25, 0.3 + w / 2)]
                    uv = [(gi[0], gi[1]), (gi[2], gi[1]), (gi[2], gi[3]), (gi[0], gi[3])]
                    if sy > 0:
                        pts = [pts[1], pts[0], pts[3], pts[2]]
                    gm.quad(*pts, mat=0, uv=uv)
                    x += w + 1
                else:
                    x += r.uniform(2, 5)
            if r.random() < 0.6:
                add('drainpipe', (x1 - 0.4, yy + sy * 0.25, 0.0), 0, 1.0)
                inst(col, 'drainpipe', (x1 - 0.4, yy + sy * 0.25, 1.0), 0, 1.0).scale = (1, 1, min(30.0, s.get('roof_z', 20) - 1))
            if r.random() < 0.3:
                add('camera', (x0 + 1.0, yy + sy * 0.2, 3.6), 0.0 if sy < 0 else math.pi)
    new_object("SIGNAGE_cross", sm.build("SIGNAGE_cross", [MAT.get('metal_dark'), MAT.get('ad_light')]), col)
    if gm.F:
        new_object("GRAFFITI", gm.build("GRAFFITI", [MAT.get('graffiti')]), col)
    # building numbers over avenue doors
    font = bpy.data.fonts.load(SG.adgen.FONTS['serif'], check_existing=True)
    num = 0
    for s in specs:
        w = SG.avenue_walls(s)
        if w is None or s['ring'] != 'near' or not s.get('params'):
            continue
        cu = bpy.data.curves.new("num", 'FONT')
        cu.body = str(100 + (int(abs(s['lot'][2]) * 7 + s['id']) % 1800))
        cu.size = 0.32
        cu.extrude = 0.01
        cu.font = font
        cu.align_x = 'CENTER'
        ob = bpy.data.objects.new("BLDG_NUM.%d" % num, cu)
        col.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        me.materials.append(MAT.get('metal_bronze'))
        o = bpy.data.objects.new("BLDG_NUM.%d" % num, me)
        col.objects.link(o)
        y = (w.y0 + w.y1) / 2 + r.uniform(-4, 4)
        o.location = (w.fx + w.sx * (s['params']['dp'] + 0.15), y, 2.75)
        o.rotation_euler = (1.5708, 0, 1.5708 if w.sx > 0 else -1.5708)
        num += 1
    n['building_numbers'] = num
    return n


def waterfront(cols):
    """Piers on piles, an irregular rock-armoured shore segment, boats on the water."""
    r = random.Random(919)
    col = cols['far']
    mb = MB()
    y0 = LY.SHORE[3]
    for k in range(7):
        x = -1200 + k * 380 + r.uniform(-60, 60)
        L, W = r.uniform(90, 180), r.uniform(18, 35)
        mb.box(x - W / 2, x + W / 2, y0, y0 + L, 0.6, 1.4, 0)
        for px in (x - W / 2 + 1, x + W / 2 - 1):
            yy = y0 + 4
            while yy < y0 + L:
                mb.box(px - 0.3, px + 0.3, yy - 0.3, yy + 0.3, -1.6, 0.6, 1)
                yy += 8
        if r.random() < 0.6:   # pier shed
            mb.box(x - W / 2 + 3, x + W / 2 - 3, y0 + L * 0.3, y0 + L * 0.85, 1.4, 1.4 + r.uniform(6, 11), 2)
    # rock armour along part of the east shore (irregular edge)
    for k in range(400):
        y = r.uniform(-1400, 1300)
        x = LY.SHORE[1] + r.uniform(0, 6)
        s = r.uniform(0.8, 2.2)
        mb.box(x - s, x + s, y - s, y + s, -1.6, r.uniform(-0.6, 0.8), 3)
    new_object("WATERFRONT_piers", mb.build("WATERFRONT_piers", [MAT.get('concrete'), MAT.get('plywood'),
                                                                MAT.get('metal_dark'), MAT.get('concrete')]), col)
    n = 0
    for k in range(9):
        kind = r.choice(['ferry', 'tug', 'tug'])
        x = r.uniform(-1300, 1300) if k < 5 else r.choice((-1, 1)) * r.uniform(1600, 2200)
        y = r.uniform(1500, 2200) if k < 5 else r.uniform(-1200, 1200)
        inst(col, kind, (x, y, -1.4), r.uniform(0, 6.28))
        n += 1
    return n


def skybridge_crowns(cols):
    """Distinctive lit lantern crowns on the twin skybridge towers (fins + glowing crown box)."""
    mb = MB()
    for (x0, x1, h) in ((-60.0, -16.0, 198.0), (16.0, 60.0, 186.0)):
        y0, y1 = 352.0, 410.0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, d = (x1 - x0) * 0.7, (y1 - y0) * 0.7
        mb.box(cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, h, h + 9, 1)
        n = 14
        for k in range(n + 1):
            yy = cy - d / 2 + d * k / n
            for xx in (cx - w / 2 - 0.4, cx + w / 2):
                mb.box(xx, xx + 0.4, yy - 0.15, yy + 0.15, h, h + 14 + 4 * math.sin(k / n * math.pi), 0)
        for k in range(int(w / 2.5) + 1):
            xx = cx - w / 2 + k * 2.5
            for yy in (cy - d / 2 - 0.4, cy + d / 2):
                mb.box(xx - 0.15, xx + 0.15, yy, yy + 0.4, h, h + 12 + 6 * math.sin(k * 2.5 / w * math.pi), 0)
        mb.box(cx - 0.5, cx + 0.5, cy - 0.5, cy + 0.5, h + 9, h + 40, 0)
    new_object("SKYBRIDGE_crowns", mb.build("SKYBRIDGE_crowns", [MAT.get('steel_deco'), MAT.get('flood')]), cols['hero'])
