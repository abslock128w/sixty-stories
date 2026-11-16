"""Street-level advertising and signage on the hero avenue: billboards (printed + LED), lightboxes,
blade signs, theatre marquees with bulb rows, neon window signs, corner LED wraps.

All brands are invented (see adgen.py). Emission scales with LIGHT_CTRL.street_emit.
"""
import math
import os
import random
import bpy

import materials as MAT
import layout as LY
import adgen
from materials import _new, _c4
from cutil import MB, new_object

ATLAS = None
INFO = []
NEON_WORDS = ["OPEN", "BAR", "PIZZA", "LIVE MUSIC", "COCKTAILS", "24 HRS", "DINER", "NOODLES", "TATTOO", "KARAOKE", "DELI",
              "JAZZ", "HOTEL", "CAFE", "LOUNGE", "RAMEN"]


def _atlas(out_dir):
    global ATLAS, INFO
    if ATLAS is None:
        path = os.path.join(out_dir, "ads_atlas.png")
        INFO = adgen.build_atlas(path)
        ATLAS = bpy.data.images.load(path)
        ATLAS.name = "CITY_ads_atlas"
        ATLAS.pack()
    return ATLAS


def _tex(nb):
    t = nb.n('ShaderNodeTexImage', image=ATLAS, interpolation='Linear', extension='EXTEND')
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    nb.link(uv.outputs['UV'], t.inputs['Vector'])
    return t.outputs['Color']


def m_ad_print(name):
    nb, m = _new(name)
    c = _tex(nb)
    geo = nb.n('ShaderNodeNewGeometry')
    n = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=1.5, i_Detail=3.0)
    fade = nb.n('ShaderNodeMapRange', i_Value=n.outputs['Fac'], **{'i_To Min': 0.8, 'i_To Max': 1.05})
    base = nb.mix(1.0, c, fade.outputs[0], blend='MULTIPLY')
    p = nb.principled(**{'Base Color': base, 'Roughness': 0.42, 'Specular IOR Level': 0.6})
    s = nb.math('MULTIPLY', nb.ctrl('street_emit'), 0.35)   # floodlit at night
    nb.out(MAT.emission_add(nb, p.outputs[0], c, s))
    return m


def m_ad_light(name):
    """Lightbox / LED screen: self-lit in daylight too, brighter at dusk; faint LED pixel grid."""
    nb, m = _new(name)
    c = _tex(nb)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = nb.vmath('MULTIPLY', geo.outputs['Position'], (22.0, 22.0, 22.0))
    w = nb.n('ShaderNodeTexWave', i_Vector=pos, wave_type='BANDS', bands_direction='Z', i_Scale=1.0, i_Distortion=0.0)
    grid = nb.math('MULTIPLY_ADD', w.outputs['Fac'], 0.25, 0.8)
    s = nb.math('MULTIPLY', nb.math('MULTIPLY_ADD', nb.ctrl('street_emit'), 1.6, 0.85), grid)
    p = nb.principled(**{'Base Color': nb.mix(1.0, c, (0.15, 0.15, 0.15, 1), blend='MULTIPLY'), 'Roughness': 0.08,
                         'Specular IOR Level': 0.9})
    nb.out(MAT.emission_add(nb, p.outputs[0], c, s))
    return m


def m_neon(name, col):
    nb, m = _new(name)
    s = nb.math('MULTIPLY_ADD', nb.ctrl('street_emit'), 9.0, 3.0)
    p = nb.principled(**{'Base Color': _c4(col), 'Roughness': 0.2, 'Emission Color': _c4(col), 'Emission Strength': s})
    nb.out(p.outputs[0])
    return m


def m_bulbs(name):
    """Marquee fascia: rows of warm bulbs (UV u in bulb units, v 0..1)."""
    nb, m = _new(name)
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    sp = nb.n('ShaderNodeSeparateXYZ', i_Vector=uv.outputs['UV'])
    fu = nb.math('SUBTRACT', nb.math('FRACT', sp.outputs['X']), 0.5)
    rows = nb.math('SUBTRACT', nb.math('FRACT', nb.math('MULTIPLY', sp.outputs['Y'], 2.0)), 0.5)
    d = nb.math('ADD', nb.math('MULTIPLY', fu, fu), nb.math('MULTIPLY', rows, rows))
    dot = nb.math('LESS_THAN', d, 0.09)
    s = nb.math('MULTIPLY', dot, nb.math('MULTIPLY_ADD', nb.ctrl('street_emit'), 10.0, 4.0))
    base = nb.mix(dot, (0.35, 0.27, 0.12, 1), (1.0, 0.9, 0.7, 1))
    p = nb.principled(**{'Base Color': base, 'Roughness': 0.3, 'Metallic': nb.math('SUBTRACT', 1.0, dot)})
    nb.out(MAT.emission_add(nb, p.outputs[0], (1.0, 0.78, 0.45, 1), s))
    return m


MAT.BUILDERS['ad_print'] = m_ad_print
MAT.BUILDERS['ad_light'] = m_ad_light
MAT.BUILDERS['neon_pink'] = lambda n: m_neon(n, (1.0, 0.12, 0.55))
MAT.BUILDERS['neon_cyan'] = lambda n: m_neon(n, (0.1, 0.85, 1.0))
MAT.BUILDERS['neon_green'] = lambda n: m_neon(n, (0.25, 1.0, 0.35))
MAT.BUILDERS['neon_amber'] = lambda n: m_neon(n, (1.0, 0.55, 0.08))
MAT.BUILDERS['marquee_bulbs'] = m_bulbs
PRINT, LIGHT, FRAME, BULB, NP, NC, NG, NA = range(8)
NEONS = [NP, NC, NG, NA]


class Wall:
    """An avenue-facing wall: x plane at fx, outward sign sx (+1: faces +X), spanning y0..y1."""

    def __init__(self, fx, sx, y0, y1):
        self.fx, self.sx, self.y0, self.y1 = fx, sx, y0, y1

    def p(self, y, out, z):
        return (self.fx + self.sx * out, y, z)

    def right(self):
        return self.sx   # +1: viewer's right is +y


def ad_quad(mb, wall, ya, yb, za, zb, out, mat, ad):
    u0, v0, u1, v1 = ad['uv']
    if wall.sx > 0:
        pts = [wall.p(ya, out, za), wall.p(yb, out, za), wall.p(yb, out, zb), wall.p(ya, out, zb)]
    else:
        pts = [wall.p(yb, out, za), wall.p(ya, out, za), wall.p(ya, out, zb), wall.p(yb, out, zb)]
    mb.quad(*pts, mat=mat, uv=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])


def frame_box(mb, wall, ya, yb, za, zb, o0, o1, m=FRAME):
    x0, x1 = sorted((wall.fx + wall.sx * o0, wall.fx + wall.sx * o1))
    mb.box(x0, x1, ya, yb, za, zb, m)


class AdPicker:
    def __init__(self, rng):
        self.rng = rng
        self.used = {}

    def pick(self, lo, hi, kinds=None):
        c = [a for a in INFO if lo <= a['aspect'] <= hi and (kinds is None or a['kind'] in kinds)]
        c.sort(key=lambda a: (self.used.get(a['i'], 0), self.rng.random()))
        a = c[0]
        self.used[a['i']] = self.used.get(a['i'], 0) + 1
        return a


def billboard(mb, wall, yc, z0, height, ad, out, lit, rng):
    w = height * ad['aspect']
    ya, yb = yc - w / 2, yc + w / 2
    frame_box(mb, wall, ya - 0.15, yb + 0.15, z0 - 0.15, z0 + height + 0.15, out - 0.35, out - 0.02)
    ad_quad(mb, wall, ya, yb, z0, z0 + height, out, LIGHT if lit else PRINT, ad)
    if not lit:   # catwalk + lamp arms
        frame_box(mb, wall, ya, yb, z0 - 0.35, z0 - 0.25, out - 0.3, out + 0.6)
        k = int(w / 3) + 1
        for i in range(k):
            y = ya + (i + 0.5) * w / k
            frame_box(mb, wall, y - 0.04, y + 0.04, z0 + height + 0.15, z0 + height + 0.2, out, out + 0.9)
            frame_box(mb, wall, y - 0.15, y + 0.15, z0 + height + 0.05, z0 + height + 0.2, out + 0.8, out + 1.0)
    return ya, yb


def blade(mb, wall, y, z0, h, ad, rng, out0):
    """Vertical sign perpendicular to the wall, ads on both faces, neon edge."""
    depth = h * ad['aspect']
    o0, o1 = out0 + 0.3, out0 + 0.3 + depth
    x0, x1 = sorted((wall.fx + wall.sx * o0, wall.fx + wall.sx * o1))
    mb.box(x0, x1, y - 0.12, y + 0.12, z0 - 0.1, z0 + h + 0.1, FRAME)
    u0, v0, u1, v1 = ad['uv']
    for sy in (-1, 1):
        yy = y + sy * 0.125
        xa, xb = (x0, x1) if (sy < 0) == (wall.sx > 0) else (x1, x0)
        # viewer facing the -y face: right = +x
        if sy < 0:
            pts = [(x0, yy, z0), (x1, yy, z0), (x1, yy, z0 + h), (x0, yy, z0 + h)]
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        else:
            pts = [(x1, yy, z0), (x0, yy, z0), (x0, yy, z0 + h), (x1, yy, z0 + h)]
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        mb.quad(*pts, mat=LIGHT, uv=uv)
    nm = rng.choice(NEONS)
    mb.box(x0, x1, y - 0.16, y + 0.16, z0 - 0.16, z0 - 0.1, nm)
    mb.box(x0, x1, y - 0.16, y + 0.16, z0 + h + 0.1, z0 + h + 0.16, nm)


def marquee(mb, wall, ya, yb, z0, ad, rng):
    """Theatre canopy over the sidewalk: soffit, bulb fascia, letterboard on top."""
    depth = 3.4
    o0, o1 = 0.2, depth
    x0, x1 = sorted((wall.fx + wall.sx * o0, wall.fx + wall.sx * o1))
    mb.box(x0, x1, ya, yb, z0, z0 + 0.9, FRAME)
    xf = wall.fx + wall.sx * (o1 + 0.01)
    L = yb - ya
    n = L / 0.32
    pts = [(xf, ya, z0 + 0.05), (xf, yb, z0 + 0.05), (xf, yb, z0 + 0.85), (xf, ya, z0 + 0.85)]
    uv = [(0, 0), (n, 0), (n, 1), (0, 1)]
    if wall.sx < 0:
        pts = [pts[1], pts[0], pts[3], pts[2]]
    mb.quad(*pts, mat=BULB, uv=uv)
    # side bulbs
    for y, s in ((ya - 0.01, -1), (yb + 0.01, 1)):
        q = [(x0, y, z0 + 0.05), (x1, y, z0 + 0.05), (x1, y, z0 + 0.85), (x0, y, z0 + 0.85)]
        mb.quad(*(q if s < 0 else q[::-1]), mat=BULB, uv=[(0, 0), (depth / 0.32, 0), (depth / 0.32, 1), (0, 1)])
    # letterboard rising above the canopy front
    h = min(2.6, L / ad['aspect'])
    wb = h * ad['aspect']
    ym = (ya + yb) / 2
    frame_box(mb, wall, ym - wb / 2 - 0.1, ym + wb / 2 + 0.1, z0 + 0.9, z0 + 1.0 + h + 0.1, o1 - 0.5, o1 - 0.3)
    ad_quad(mb, wall, ym - wb / 2, ym + wb / 2, z0 + 1.0, z0 + 1.0 + h, o1 - 0.29, LIGHT, ad)
    # soffit bulbs (downlights) as a bulb strip under the canopy
    q = [(x0, ya + 0.2, z0 - 0.01), (x1, ya + 0.2, z0 - 0.01), (x1, yb - 0.2, z0 - 0.01), (x0, yb - 0.2, z0 - 0.01)]
    mb.quad(*q[::-1], mat=BULB, uv=[(0, 0), (depth / 0.6, 0), (depth / 0.6, 2), (0, 2)])


def neon_text(col, wall, y, z, text, mat, size=0.45):
    cu = bpy.data.curves.new("neon", 'FONT')
    cu.body = text
    cu.size = size
    cu.bevel_depth = 0.012
    cu.bevel_resolution = 1
    cu.align_x = 'CENTER'
    cu.font = bpy.data.fonts.load(adgen.FONTS['bold'], check_existing=True)
    tmp = bpy.data.objects.new("tmp", cu)
    col.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.materials.append(mat)
    ob = bpy.data.objects.new("NEON." + text, me)
    col.objects.link(ob)
    ob.location = (wall.fx + wall.sx * 0.35, y, z)
    ob.rotation_euler = (1.5708, 0, 1.5708 if wall.sx > 0 else -1.5708)
    return ob


def avenue_walls(spec):
    """Avenue-facing wall of a near building's lowest tier."""
    x0, x1, y0, y1 = spec['lot']
    if x1 <= 0 and abs(x1 + LY.HERO_AVE_W / 2) < 0.6:
        return Wall(x1, 1, y0, y1)
    if x0 >= 0 and abs(x0 - LY.HERO_AVE_W / 2) < 0.6:
        return Wall(x0, -1, y0, y1)
    return None


def build(cols, specs, out_dir, seed=4321):
    _atlas(out_dir)
    rng = random.Random(seed)
    picker = AdPicker(rng)
    mats = [MAT.get(k) for k in ('ad_print', 'ad_light', 'metal_dark', 'marquee_bulbs', 'neon_pink', 'neon_cyan',
                                  'neon_green', 'neon_amber')]
    mb = MB()
    col = cols['props']
    stats = dict(billboards=0, led=0, blades=0, marquees=0, lightboxes=0, neon=0, wraps=0)
    cross = LY.street_ys()
    for s in specs:
        if s['ring'] != 'near' or s['kind'] != 'ave' or not s.get('params'):
            continue
        wall = avenue_walls(s)
        if wall is None:
            continue
        P = s['params']
        H = s.get('roof_z', s['height'])
        gh = P['gh']
        out = P['dp'] + P['ds'] + 0.25
        ya, yb = wall.y0 + 1.0, wall.y1 - 1.0
        span = yb - ya
        r = random.Random(s['seed'] * 7 + 11)
        curtain = P.get('curtain')
        # 1. big billboard(s) on the lower 10 storeys
        zc = gh + 1.5
        if r.random() < 0.7 and span > 8:
            lit = r.random() < (0.55 if curtain else 0.35)
            ad = picker.pick(0.9, 4.0) if r.random() < 0.65 else picker.pick(0.5, 0.8)
            hmax = min(10.0, H - zc - 3)
            h = min(hmax, r.uniform(4.5, 9.5), (span * 0.75) / ad['aspect'])
            if h > 3:
                yc = r.uniform(ya + h * ad['aspect'] / 2, yb - h * ad['aspect'] / 2) if span > h * ad['aspect'] else (ya + yb) / 2
                billboard(mb, wall, yc, zc, h, ad, out, lit, r)
                stats['led' if lit else 'billboards'] += 1
                zc += h + 1.5
                # stacked second board
                if r.random() < 0.4 and zc + 6 < min(42, H - 3):
                    ad2 = picker.pick(1.0, 4.0)
                    h2 = min(r.uniform(5, 10), (span * 0.9) / ad2['aspect'], min(42, H - 3) - zc)
                    if h2 > 3:
                        billboard(mb, wall, (ya + yb) / 2 + r.uniform(-2, 2), zc, h2, ad2, out, r.random() < 0.5, r)
                        stats['billboards'] += 1
        # 2. blade sign at one end
        if r.random() < 0.45 and H > gh + 8:
            ad = picker.pick(0.3, 0.55)
            h = r.uniform(5, 9)
            y = (wall.y0 + 1.5) if r.random() < 0.5 else (wall.y1 - 1.5)
            blade(mb, wall, y, gh + 1.0, h, ad, r, out)
            stats['blades'] += 1
        # 3. marquee for some masonry buildings, else lightboxes over the shopfronts
        if not curtain and r.random() < 0.18 and span > 9:
            w = min(span - 1, r.uniform(9, 15))
            yc = r.uniform(ya + w / 2, yb - w / 2)
            marquee(mb, wall, yc - w / 2, yc + w / 2, gh - 1.7, picker.pick(2.0, 4.0, ('ad_show', 'ad_logo', 'ad_movie')), r)
            stats['marquees'] += 1
        else:
            y = ya
            while y < yb - 3:
                if r.random() < 0.55:
                    ad = picker.pick(2.0, 4.0, ('ad_logo', 'ad_type', 'ad_product'))
                    h = r.uniform(0.7, 1.0)
                    w = h * ad['aspect']
                    if y + w > yb:
                        break
                    frame_box(mb, wall, y - 0.05, y + w + 0.05, gh - 1.25, gh - 1.25 + h + 0.1, out - 0.2, out + 0.05)
                    ad_quad(mb, wall, y, y + w, gh - 1.2, gh - 1.2 + h, out + 0.06, LIGHT, ad)
                    stats['lightboxes'] += 1
                    y += w + r.uniform(1.0, 4.0)
                else:
                    y += r.uniform(2, 5)
        # 3b. small paste-up posters on the base piers (street-level layer)
        if not curtain and r.random() < 0.6:
            y = ya + r.uniform(0, 2)
            for k in range(r.randint(2, 6)):
                ad = picker.pick(0.6, 0.8)
                ph = r.uniform(1.1, 1.6)
                pw_ = ph * ad['aspect']
                if y + pw_ > yb:
                    break
                ad_quad(mb, wall, y, y + pw_, 0.6, 0.6 + ph, P['dp'] + 0.13, PRINT, ad)
                y += pw_ + r.uniform(0.02, 0.1) if r.random() < 0.7 else pw_ + r.uniform(2, 6)
        # 4. neon words in shop windows
        for k in range(r.randint(0, 2)):
            neon_text(col, wall, r.uniform(ya + 1, yb - 1), r.uniform(1.9, 2.8), r.choice(NEON_WORDS),
                      mats[rng.choice(NEONS)], size=r.uniform(0.35, 0.55))
            stats['neon'] += 1
        # 5. corner LED wrap where the lot meets a cross street
        for (yy, sgn) in ((wall.y0, -1), (wall.y1, 1)):
            if any(abs(abs(yy - c) - LY.ST_W / 2) < 0.6 for c in cross) and r.random() < 0.3 and H > 30:
                ad = picker.pick(1.3, 2.0)
                h = r.uniform(5, 8)
                w = h * ad['aspect']
                z0 = gh + 2.0
                ye = yy - sgn * 0.0
                ya2, yb2 = (ye - w, ye) if sgn > 0 else (ye, ye + w)
                frame_box(mb, wall, ya2, yb2, z0 - 0.2, z0 + h + 0.2, out - 0.3, out)
                ad_quad(mb, wall, ya2, yb2, z0, z0 + h, out + 0.01, LIGHT, ad)
                # side face on the cross street
                ad2 = picker.pick(1.3, 2.0)
                d = min(8.0, h * ad2['aspect'])
                yf = ye + sgn * (out + 0.01)
                xa, xb = wall.fx + wall.sx * out, wall.fx - wall.sx * (d - out)
                u0, v0, u1, v1 = ad2['uv']
                pts = [(xa, yf, z0), (xb, yf, z0), (xb, yf, z0 + h), (xa, yf, z0 + h)]
                face_right_is_neg_x = (sgn > 0)
                uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                if (xb < xa) != face_right_is_neg_x:
                    uvs = [(u1, v0), (u0, v0), (u0, v1), (u1, v1)]
                if sgn < 0:
                    pts = [pts[1], pts[0], pts[3], pts[2]]
                    uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
                mb.quad(*pts, mat=LIGHT, uv=uvs)
                stats['wraps'] += 1
    me = mb.build("SIGNAGE", mats)
    new_object("SIGNAGE", me, col)
    return stats
