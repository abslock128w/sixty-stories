"""Room-module kit + geometry-nodes instancing of rooms behind facade windows.

Each module is a room shell (floor, ceiling, back and side walls, open toward the window)
with furniture, built in a local frame: x across the window bay (-1..1, i.e. 2.0 m wide),
y = depth into the building (0 at the glass .. 4.5 m), z up from the floor (0..3.8 m storey).
Instances are scaled per window to (bay/2, depth/4.5, storey/3.8) and may be mirrored in x.

Per-instance attributes (read in shaders with Attribute node type INSTANCER):
    rr  random 0..1 (wall colour, furniture colour, lamp variation)
    rl  lit rank: room is lit when rl < LIGHT_CTRL.window_frac (same value as its pane's
        'win'.g, so pane and room agree)
    rt  tint: <0.8 warm tungsten, >=0.8 cool fluorescent/LED
All emissive room surfaces scale with LIGHT_CTRL.window_emit.
"""
import math
import random
import bpy

import materials as MAT
from materials import NB, _new, _c4
from cutil import MB

KIT_COLLECTION = "CITY_roomkit"
W, D, H = 1.0, 4.5, 3.78     # half width, depth, ceiling height of a module
# (name, builder) - index order = rtype
MODULES = []
USE_MIX = {
    'residential': [('kitchen', 3), ('kitchen_p', 1), ('living', 3), ('living_p', 1), ('living_b', 2), ('bedroom', 3),
                    ('storage', 0.4)],
    'office': [('office', 5), ('office_p', 2), ('meeting', 1.5), ('corridor', 1), ('storage', 0.5)],
    'hotel': [('hotel', 6), ('hotel_p', 1), ('corridor', 0.7)],
}


# ----------------------------------------------------------------- materials
def _inst(nb, name):
    return nb.n('ShaderNodeAttribute', attribute_type='INSTANCER', attribute_name=name).outputs['Fac']


def _lit(nb):
    """(lit 0/1 * window_emit, tint) sockets."""
    rl = _inst(nb, 'rl')
    # real-room panes: more rooms lit than painted windows (people are home at sunset), still
    # following window_frac; daytime boost so a lit room holds up next to a sunlit facade
    frac = nb.math('MINIMUM', nb.math('MULTIPLY_ADD', nb.ctrl('window_frac'), ROOM_FRAC_MUL, ROOM_FRAC_ADD), 0.95)
    lit = nb.math('LESS_THAN', rl, frac)
    lvl = nb.math('MULTIPLY_ADD', nb.ctrl('sun_strength'), ROOM_DAY_BOOST, nb.ctrl('window_emit'))
    lvl = nb.math('MULTIPLY', lvl, _inst(nb, 'rb'))   # per-instance brightness (shops are brighter)
    return nb.math('MULTIPLY', lit, lvl), _inst(nb, 'rt'), _inst(nb, 'rr')


ROOM_FRAC_MUL = 1.5
ROOM_FRAC_ADD = 0.42
ROOM_DAY_BOOST = 0.07
SHOP_BOOST = 2.4


def _lamp_col(nb, rt):
    return nb.ramp(rt, [(0.0, (1.0, 0.66, 0.40)), (0.5, (1.0, 0.78, 0.56)), (0.8, (0.88, 0.94, 1.0))], interp='CONSTANT')


def m_room_surface(name, palette, rough=0.8, glow=0.5, mult_rr=1.0):
    """Room surfaces are EMISSION ONLY (no BSDF): a camera ray that enters a window ends on the
    first room surface, with no further bounces. Brightness = lit-room lamp glow + daylight
    near the window, shaded by a fixed fake key (ceiling lights / window light) so furniture
    keeps its form. This keeps interiors nearly free to render."""
    nb, m = _new(name)
    em, rt, rr = _lit(nb)
    rrm = nb.math('FRACT', nb.math('MULTIPLY', rr, mult_rr))
    col = nb.ramp(rrm, palette, interp='CONSTANT')
    lc = _lamp_col(nb, rt)
    tc = nb.n('ShaderNodeTexCoord')
    lo = nb.n('ShaderNodeSeparateXYZ', i_Vector=tc.outputs['Object'])
    ly, lz = lo.outputs['Y'], lo.outputs['Z']
    # local-space normal of the module surface
    nl = nb.n('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='WORLD', convert_to='OBJECT')
    geo = nb.n('ShaderNodeNewGeometry')
    nb.link(geo.outputs['Normal'], nl.inputs['Vector'])
    ns = nb.n('ShaderNodeSeparateXYZ', i_Vector=nl.outputs[0])
    # lamp key from above + slight fill; contact darkening near the floor
    # fake key: tops lit by ceiling lamps, faces toward the window lit by daylight, faces away
    # darker -> furniture separates from walls
    key = nb.math('ADD', nb.math('MULTIPLY', nb.math('MAXIMUM', ns.outputs['Z'], 0.0), 0.55),
                  nb.math('MULTIPLY_ADD', nb.math('MAXIMUM', nb.math('MULTIPLY', ns.outputs['Y'], -1.0), 0.0), 0.45, 0.32))
    key = nb.math('MULTIPLY', key, nb.math('MINIMUM', nb.math('MULTIPLY_ADD', lz, 0.6, 0.55), 1.0))
    pool = nb.math('EXPONENT', nb.math('MULTIPLY', nb.math('POWER', nb.math('SUBTRACT', ly, 1.9), 2.0), -0.22))
    lamp = nb.math('MULTIPLY', nb.math('MULTIPLY', em, glow * 1.0), nb.math('MULTIPLY', key, pool))
    # daylight from the window (local -y), fading with depth
    wkey = nb.math('MULTIPLY_ADD', nb.math('MAXIMUM', nb.math('MULTIPLY', ns.outputs['Y'], -1.0), 0.0), 0.6, 0.45)
    fall = nb.math('EXPONENT', nb.math('MULTIPLY', ly, -0.55))
    day = nb.math('MULTIPLY', nb.math('MULTIPLY', fall, nb.ctrl('sun_strength')), 0.03 * DAYK)
    day = nb.math('MULTIPLY', day, wkey)
    # sun patch on the floor / lower walls of rooms whose window faces the sun
    out_w = nb.n('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
    out_w.inputs['Vector'].default_value = (0.0, -1.0, 0.0)
    sv = nb.n('ShaderNodeCombineXYZ', i_X=nb.ctrl('sun_x'), i_Y=nb.ctrl('sun_y'), i_Z=0.0)
    facing = nb.math('MAXIMUM', nb.vmath('DOT_PRODUCT', nb.vmath('NORMALIZE', out_w.outputs[0]), sv.outputs[0]), 0.0)
    lx = lo.outputs['X']
    patch = nb.math('MULTIPLY', nb.math('LESS_THAN', ly, 2.6), nb.math('LESS_THAN', nb.math('ABSOLUTE', lx), 0.7))
    patch = nb.math('MULTIPLY', patch, nb.math('LESS_THAN', lz, 1.1))
    patch = nb.math('MULTIPLY', patch, nb.math('MULTIPLY', facing, nb.ctrl('sun_strength')))
    c3 = nb.vmath('SCALE', nb.mix(1.0, col, (1.0, 0.62, 0.32, 1), blend='MULTIPLY'), scale=nb.math('MULTIPLY', patch, 0.16))
    c1 = nb.vmath('SCALE', nb.mix(1.0, col, lc, blend='MULTIPLY'), scale=lamp)
    c1 = nb.vmath('ADD', c1, c3)
    c2 = nb.vmath('SCALE', nb.mix(1.0, col, (0.85, 0.85, 0.85, 1), blend='MULTIPLY'), scale=day)
    e = nb.n('ShaderNodeEmission', i_Strength=1.0)
    nb.link(nb.vmath('ADD', c1, c2), e.inputs['Color'])
    nb.out(e.outputs[0])
    return m


DAYK = 0.55


def m_room_emit(name, kind):
    nb, m = _new(name)
    em, rt, rr = _lit(nb)
    if kind == 'lamp':
        col = _lamp_col(nb, rt)
        s = nb.math('MULTIPLY', em, 16.0)
        p = nb.principled(**{'Base Color': (0.9, 0.88, 0.8, 1), 'Roughness': 0.4})
    else:   # screens: on in most lit rooms; dim in dark ones (TVs / monitors left on)
        col = nb.ramp(rr, [(0.0, (0.35, 0.55, 1.0)), (0.5, (0.75, 0.85, 1.0)), (0.8, (1.0, 0.7, 0.45))], interp='CONSTANT')
        on = nb.math('GREATER_THAN', nb.math('FRACT', nb.math('MULTIPLY', rr, 7.3)), 0.2)
        s = nb.math('MULTIPLY', on, nb.math('ADD', nb.math('MULTIPLY', em, 2.0), nb.math('MULTIPLY', nb.ctrl('window_emit'), 0.6)))
        p = nb.principled(**{'Base Color': (0.01, 0.01, 0.012, 1), 'Roughness': 0.05, 'Specular IOR Level': 0.8})
    nb.out(MAT.emission_add(nb, p.outputs[0], col, s))
    return m


def _reg():
    B = MAT.BUILDERS
    B['room_wall'] = lambda n: m_room_surface(n, [
        (0.0, (0.70, 0.66, 0.58)), (0.14, (0.72, 0.50, 0.28)), (0.26, (0.30, 0.50, 0.56)), (0.38, (0.78, 0.76, 0.72)),
        (0.50, (0.62, 0.30, 0.22)), (0.62, (0.45, 0.55, 0.36)), (0.74, (0.68, 0.58, 0.42)), (0.86, (0.26, 0.32, 0.48))], glow=1.1)
    B['room_floor'] = lambda n: m_room_surface(n, [
        (0.0, (0.36, 0.22, 0.11)), (0.3, (0.52, 0.36, 0.20)), (0.55, (0.28, 0.27, 0.28)), (0.75, (0.62, 0.52, 0.40)),
        (0.9, (0.22, 0.13, 0.07))], rough=0.45, glow=0.8, mult_rr=3.1)
    B['room_ceiling'] = lambda n: m_room_surface(n, [(0.0, (0.70, 0.69, 0.66)), (0.7, (0.62, 0.62, 0.60))], glow=0.9)
    B['room_wood'] = lambda n: m_room_surface(n, [
        (0.0, (0.88, 0.87, 0.84)), (0.3, (0.55, 0.38, 0.22)), (0.5, (0.90, 0.89, 0.86)), (0.75, (0.30, 0.18, 0.10)),
        (0.88, (0.20, 0.30, 0.36))], rough=0.5, glow=0.9, mult_rr=5.7)
    B['room_fabric'] = lambda n: m_room_surface(n, [
        (0.0, (0.72, 0.16, 0.10)), (0.17, (0.14, 0.34, 0.62)), (0.34, (0.82, 0.60, 0.16)), (0.5, (0.18, 0.45, 0.30)),
        (0.67, (0.62, 0.56, 0.48)), (0.84, (0.55, 0.22, 0.45))], rough=0.95, glow=0.9, mult_rr=2.3)
    B['room_metal'] = lambda n: m_room_surface(n, [(0.0, (0.86, 0.87, 0.88)), (0.6, (0.62, 0.63, 0.65))], glow=1.0,
                                                 mult_rr=1.7)
    B['room_dark'] = lambda n: m_room_surface(n, [(0.0, (0.05, 0.05, 0.055))], glow=0.6)
    B['room_plant'] = lambda n: m_room_surface(n, [(0.0, (0.10, 0.30, 0.07)), (0.5, (0.16, 0.38, 0.10))], glow=1.0, mult_rr=3.3)
    B['room_lamp'] = lambda n: m_room_emit(n, 'lamp')
    B['room_screen'] = lambda n: m_room_emit(n, 'screen')
    B['room_book'] = lambda n: m_room_surface(n, [
        (0.0, (0.40, 0.08, 0.06)), (0.2, (0.10, 0.18, 0.35)), (0.4, (0.60, 0.55, 0.40)), (0.6, (0.12, 0.25, 0.14)),
        (0.8, (0.85, 0.80, 0.70))], glow=1.0, mult_rr=13.0)


_reg()
SLOTS = ['room_wall', 'room_floor', 'room_ceiling', 'room_wood', 'room_fabric', 'room_metal', 'room_dark', 'room_plant',
         'room_lamp', 'room_screen', 'room_book', 'cloth_var', 'skin']
WALL, FLOOR, CEIL, WOOD, FAB, METAL, DARK, PLANT, LAMP, SCREEN, BOOK, CLOTH, SKIN = range(len(SLOTS))


# ----------------------------------------------------------------- furniture helpers
def shell(mb, depth=D, h=H):
    mb.quad((-W, 0, 0), (W, 0, 0), (W, depth, 0), (-W, depth, 0), FLOOR, None)
    mb.quad((-W, depth, h), (W, depth, h), (W, 0, h), (-W, 0, h), CEIL, None)
    mb.quad((-W, depth, 0), (W, depth, 0), (W, depth, h), (-W, depth, h), WALL, None)
    mb.quad((-W, 0, 0), (-W, depth, 0), (-W, depth, h), (-W, 0, h), WALL, None)
    mb.quad((W, depth, 0), (W, 0, 0), (W, 0, h), (W, depth, h), WALL, None)
    # skirting
    mb.box(-W, W, depth - 0.02, depth, 0, 0.1, WOOD, skip=('-z', '+z', '+y'))


def B(mb, x0, x1, y0, y1, z0, z1, m):
    mb.box(x0, x1, y0, y1, z0, z1, m, skip=('-z',))


def table(mb, x0, x1, y0, y1, h=0.75, m=WOOD):
    B(mb, x0, x1, y0, y1, h - 0.04, h, m)
    for (x, y) in ((x0 + 0.05, y0 + 0.05), (x1 - 0.05, y0 + 0.05), (x0 + 0.05, y1 - 0.05), (x1 - 0.05, y1 - 0.05)):
        B(mb, x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, h - 0.04, m)


def chair(mb, x, y, face=1, m=WOOD):
    B(mb, x - 0.22, x + 0.22, y - 0.22, y + 0.22, 0.42, 0.46, m)
    by = y - face * 0.2
    B(mb, x - 0.22, x + 0.22, by - 0.025, by + 0.025, 0.46, 0.9, m)
    for (dx, dy) in ((-0.19, -0.19), (0.19, -0.19), (-0.19, 0.19), (0.19, 0.19)):
        B(mb, x + dx - 0.02, x + dx + 0.02, y + dy - 0.02, y + dy + 0.02, 0, 0.42, m)


def pendant(mb, x, y, z=2.55, h=H):
    B(mb, x - 0.006, x + 0.006, y - 0.006, y + 0.006, z + 0.25, h, METAL)
    mb.box(x - 0.22, x + 0.22, y - 0.22, y + 0.22, z, z + 0.25, DARK, skip=('-z',))
    mb.quad((x - 0.2, y + 0.2, z + 0.01), (x + 0.2, y + 0.2, z + 0.01), (x + 0.2, y - 0.2, z + 0.01), (x - 0.2, y - 0.2, z + 0.01), LAMP, None)


def ceiling_panel(mb, x, y, w=0.6, d=1.2, h=H):
    mb.quad((x - w / 2, y + d / 2, h - 0.01), (x + w / 2, y + d / 2, h - 0.01), (x + w / 2, y - d / 2, h - 0.01),
            (x - w / 2, y - d / 2, h - 0.01), LAMP, None)


def floor_lamp(mb, x, y):
    B(mb, x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0, 0.03, METAL)
    B(mb, x - 0.015, x + 0.015, y - 0.015, y + 0.015, 0.03, 1.45, METAL)
    mb.box(x - 0.2, x + 0.2, y - 0.2, y + 0.2, 1.45, 1.75, LAMP)


def plant(mb, x, y, s=1.0, rng=None):
    rng = rng or random.Random(int(x * 100 + y * 10))
    B(mb, x - 0.17 * s, x + 0.17 * s, y - 0.17 * s, y + 0.17 * s, 0, 0.4 * s, WALL)
    for k in range(9):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.05, 0.3) * s
        z = rng.uniform(0.5, 1.3) * s
        px, py = x + math.cos(a) * r, y + math.sin(a) * r
        L = 0.22 * s
        mb.poly([(px - L * math.cos(a + 1.2), py - L * math.sin(a + 1.2), z), (px + L * math.cos(a), py + L * math.sin(a), z + 0.12),
                 (px + L * math.cos(a + 1.2), py + L * math.sin(a + 1.2), z)], PLANT)
        mb.poly([(px, py, z - 0.3), (px + 0.02, py, z - 0.3), (px + L * math.cos(a), py + L * math.sin(a), z + 0.12)], PLANT)


def drapes(mb, rng, h=H):
    for side in (-1, 1):
        x0 = side * W
        w = rng.uniform(0.25, 0.45)
        n = 6
        pts = []
        for k in range(n + 1):
            x = x0 - side * w * k / n
            y = 0.14 + (0.05 if k % 2 else 0.0)
            pts.append((x, y))
        for a, b in zip(pts[:-1], pts[1:]):
            q = [(a[0], a[1], 0.05), (b[0], b[1], 0.05), (b[0], b[1], h - 0.15), (a[0], a[1], h - 0.15)]
            mb.poly(q if side < 0 else q[::-1], FAB)
            mb.poly(q[::-1] if side < 0 else q, FAB)
    B(mb, -W, W, 0.1, 0.13, h - 0.17, h - 0.12, METAL)


def person(mb, x, y, rot=0.0, sit=False):
    c, s = math.cos(rot), math.sin(rot)

    def bx(x0, x1, y0, y1, z0, z1, m):
        # rotated box about (x, y)
        P = []
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for z in (z0, z1):
            for (px, py) in pts:
                P.append((x + px * c - py * s, y + px * s + py * c, z))
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
        for f in faces:
            mb.poly([P[i] for i in f], m)
    zl = 0.46 if sit else 0.0
    if not sit:
        bx(-0.14, -0.03, -0.07, 0.07, 0, 0.86, CLOTH)
        bx(0.03, 0.14, -0.07, 0.07, 0, 0.86, CLOTH)
    else:
        bx(-0.14, 0.14, -0.05, 0.4, 0.42, 0.55, CLOTH)
        bx(-0.14, 0.14, 0.35, 0.47, 0.0, 0.5, CLOTH)
    zb = 0.86 if not sit else 0.5
    bx(-0.2, 0.2, -0.11, 0.11, zb, zb + 0.6, CLOTH)
    bx(-0.27, -0.2, -0.06, 0.06, zb + 0.05, zb + 0.58, CLOTH)
    bx(0.2, 0.27, -0.06, 0.06, zb + 0.05, zb + 0.58, CLOTH)
    bx(-0.08, 0.08, -0.09, 0.09, zb + 0.62, zb + 0.86, SKIN)


# ----------------------------------------------------------------- modules
def r_kitchen(mb, rng, p=False):
    shell(mb)
    # base cabinets with dark handles, worktop, colourful tiled backsplash, upper cabinets
    B(mb, -W, 0.2, D - 0.62, D, 0, 0.88, WOOD)
    B(mb, -W, 0.2, D - 0.64, D, 0.88, 0.92, DARK)                  # worktop (dark stone)
    B(mb, -W, 0.2, D - 0.02, D, 0.92, 1.48, FAB)                   # backsplash tiles
    B(mb, -W, 0.2, D - 0.36, D - 0.02, 1.5, 2.25, WOOD)             # upper cabinets
    for x in (-0.75, -0.35, 0.05):
        B(mb, x - 0.12, x + 0.12, D - 0.375, D - 0.36, 1.55, 1.58, DARK)
        B(mb, x - 0.12, x + 0.12, D - 0.635, D - 0.62, 0.78, 0.8, DARK)
    for x in (-0.85, -0.65, -0.45):                                # jars on the worktop
        B(mb, x - 0.05, x + 0.05, D - 0.3, D - 0.2, 0.92, 1.12, BOOK)
    B(mb, 0.25, W - 0.02, D - 0.72, D, 0, 1.95, METAL)              # tall bright fridge
    B(mb, 0.27, 0.31, D - 0.735, D - 0.72, 0.9, 1.6, DARK)          # fridge handle
    B(mb, 0.25, W - 0.02, D - 0.73, D - 0.72, 1.24, 1.26, DARK)     # freezer split
    B(mb, -0.62, -0.25, D - 0.6, D - 0.3, 0.92, 0.95, METAL)        # sink
    table(mb, -0.55, 0.45, 1.3, 2.1)
    chair(mb, -0.3, 1.0, 1)
    chair(mb, 0.2, 2.4, -1)
    pendant(mb, -0.05, 1.7, z=2.15)
    B(mb, -0.35, -0.2, 1.6, 1.75, 0.75, 0.98, PLANT)                # vase with stems
    B(mb, 0.05, 0.3, 1.5, 1.75, 0.75, 0.8, BOOK)                    # fruit bowl
    if p:
        person(mb, -0.3, D - 1.0, rot=math.pi)


def r_living(mb, rng, p=False, b=False):
    shell(mb)
    if not b:
        # back wall: media unit, big glowing TV, two framed prints above / beside it
        B(mb, -0.8, 0.8, D - 0.45, D, 0, 0.5, WOOD)
        B(mb, -0.62, 0.62, D - 0.08, D, 0.95, 1.72, DARK)
        mb.quad((-0.58, D - 0.081, 0.99), (0.58, D - 0.081, 0.99), (0.58, D - 0.081, 1.68), (-0.58, D - 0.081, 1.68), SCREEN, None)
        for (x0, x1, z0, z1) in ((-0.95, -0.7, 1.2, 1.9), (0.7, 0.95, 1.0, 1.6), (-0.4, 0.4, 2.0, 2.5)):
            B(mb, x0, x1, D - 0.04, D, z0, z1, DARK)
            mb.quad((x0 + 0.04, D - 0.041, z0 + 0.04), (x1 - 0.04, D - 0.041, z0 + 0.04), (x1 - 0.04, D - 0.041, z1 - 0.04),
                    (x0 + 0.04, D - 0.041, z1 - 0.04), BOOK, None)
        # sofa near the window, its back to us, colourful cushions
        B(mb, -0.85, 0.65, 1.3, 2.15, 0, 0.42, FAB)
        B(mb, -0.85, 0.65, 1.3, 1.55, 0.42, 0.9, FAB)
        B(mb, -0.95, -0.85, 1.3, 2.15, 0, 0.62, FAB)
        B(mb, 0.65, 0.75, 1.3, 2.15, 0, 0.62, FAB)
        for x in (-0.6, 0.3):
            B(mb, x, x + 0.32, 1.6, 1.72, 0.42, 0.8, BOOK)
        table(mb, -0.45, 0.35, 2.6, 3.2, h=0.42)
        B(mb, W - 0.03, W, 0.8, 2.6, 0, 2.3, WOOD)
        for z in (0.0, 0.45, 0.9, 1.35, 1.8, 2.25):
            B(mb, W - 0.35, W, 0.8, 2.6, z, z + 0.03, WOOD)
        for yy in (0.8, 2.57):
            B(mb, W - 0.35, W, yy, yy + 0.03, 0, 2.3, WOOD)
        for z in (0.45, 0.9, 1.35, 1.8, 2.25):
            y = 0.85
            while y < 2.5:
                w = rng.uniform(0.03, 0.08)
                B(mb, W - 0.33, W - 0.36 + 0.28, y, y + w, z - 0.4, z - 0.4 + rng.uniform(0.22, 0.32), BOOK)
                y += w + 0.005
        floor_lamp(mb, -0.75, 0.75)
        plant(mb, 0.72, 0.45, 1.15, rng)
        mb.quad((-0.8, 1.9, 0.005), (0.6, 1.9, 0.005), (0.6, 3.5, 0.005), (-0.8, 3.5, 0.005), FAB, None)
        if p:
            person(mb, -0.1, 1.85, rot=0.0, sit=True)
    else:
        # dining + armchair layout, bookcase wall at the back
        B(mb, -W, W, D - 0.03, D, 0, 2.3, WOOD)
        for z in (0.0, 0.45, 0.9, 1.35, 1.8, 2.25):
            B(mb, -W, W, D - 0.35, D, z, z + 0.03, WOOD)
        for z in (0.45, 0.9, 1.35, 1.8, 2.25):
            y = -W + 0.04
            while y < W - 0.1:
                w = rng.uniform(0.03, 0.08)
                B(mb, y, y + w, D - 0.33, D - 0.08, z - 0.4, z - 0.4 + rng.uniform(0.22, 0.32), BOOK)
                y += w + 0.004
        table(mb, -0.6, 0.6, 1.5, 2.4)
        chair(mb, -0.3, 1.25, 1)
        chair(mb, 0.3, 2.65, -1)
        B(mb, 0.35, 0.95, 0.6, 1.2, 0, 0.45, FAB)
        B(mb, 0.35, 0.95, 1.1, 1.2, 0.45, 0.9, FAB)
        pendant(mb, 0.0, 1.95, z=2.4)
        plant(mb, -0.75, 0.45, 1.2, rng)


def r_bedroom(mb, rng):
    shell(mb)
    B(mb, -0.75, 0.75, D - 2.1, D - 0.05, 0, 0.5, WOOD)
    B(mb, -0.73, 0.73, D - 2.08, D - 0.1, 0.5, 0.62, FAB)
    B(mb, -0.75, 0.75, D - 0.08, D, 0, 1.1, WOOD)
    B(mb, -0.6, -0.1, D - 0.55, D - 0.15, 0.62, 0.74, WALL)
    B(mb, 0.1, 0.6, D - 0.55, D - 0.15, 0.62, 0.74, WALL)
    B(mb, -W, -0.8, D - 0.5, D - 0.05, 0, 0.55, WOOD)
    mb.box(-0.97, -0.83, D - 0.35, D - 0.21, 0.55, 0.8, LAMP)
    B(mb, W - 0.6, W, 0.6, 1.8, 0, 2.1, WOOD)
    drapes(mb, rng)


def r_office(mb, rng, p=False):
    shell(mb)
    for (y0, face) in ((1.0, 1), (2.6, -1)):
        table(mb, -0.95, 0.95, y0, y0 + 0.8, h=0.74, m=WALL)
        for x in (-0.48, 0.48):
            my = y0 + (0.6 if face > 0 else 0.2)
            B(mb, x - 0.03, x + 0.03, my - 0.03, my + 0.03, 0.74, 0.95, DARK)
            B(mb, x - 0.3, x + 0.3, my - 0.02, my + 0.02, 0.95, 1.3, DARK)
            yy = my - 0.021 * face
            q = [(x - 0.28, yy, 0.97), (x + 0.28, yy, 0.97), (x + 0.28, yy, 1.28), (x - 0.28, yy, 1.28)]
            mb.poly(q if face > 0 else q[::-1], SCREEN)
            chair(mb, x, y0 - 0.35 if face > 0 else y0 + 1.15, face, m=DARK)
    B(mb, -0.95, 0.95, 1.8, 1.84, 0.74, 1.2, FAB)       # screen partition
    B(mb, -W, W, D - 0.5, D, 0, 1.3, METAL)             # filing cabinets
    ceiling_panel(mb, 0, 1.3)
    ceiling_panel(mb, 0, 3.2)
    plant(mb, 0.75, D - 0.8, 1.1, rng)
    if p:
        person(mb, 0.4, 3.9, rot=0.3)


def r_meeting(mb, rng):
    shell(mb)
    table(mb, -0.55, 0.55, 0.9, 3.9, h=0.74, m=WOOD)
    for y in (1.3, 2.1, 2.9, 3.6):
        chair(mb, -0.75, y, 1, m=DARK)
        chair(mb, 0.75, y, 1, m=DARK)
    B(mb, -0.8, 0.8, D - 0.06, D, 0.9, 1.8, DARK)
    mb.quad((-0.76, D - 0.061, 0.94), (0.76, D - 0.061, 0.94), (0.76, D - 0.061, 1.76), (-0.76, D - 0.061, 1.76), SCREEN, None)
    ceiling_panel(mb, 0, 2.4, w=0.8, d=2.6)


def r_hotel(mb, rng, p=False):
    shell(mb)
    B(mb, -0.85, 0.65, D - 2.1, D - 0.05, 0, 0.55, WALL)
    B(mb, -0.84, 0.64, D - 2.08, D - 0.1, 0.55, 0.66, CEIL)
    B(mb, -0.85, 0.65, D - 0.08, D, 0, 1.3, FAB)
    B(mb, 0.68, W, D - 0.5, D - 0.05, 0, 0.55, WOOD)
    mb.box(0.78, 0.92, D - 0.35, D - 0.21, 0.55, 0.85, LAMP)
    table(mb, -W + 0.05, -W + 0.6, 0.8, 1.8, h=0.75)
    mb.box(-W + 0.15, -W + 0.3, 1.5, 1.65, 0.75, 1.1, LAMP)
    B(mb, 0.35, 0.95, 0.5, 1.1, 0, 0.42, FAB)
    B(mb, 0.35, 0.95, 1.0, 1.1, 0.42, 0.85, FAB)
    drapes(mb, rng)
    if p:
        person(mb, -0.2, 1.4, rot=0.5)


def r_corridor(mb, rng):
    shell(mb)
    for y in (0.9, 2.4, 3.9):
        ceiling_panel(mb, 0, y, w=0.35, d=0.35)
    B(mb, -0.45, 0.45, D - 0.04, D, 0, 2.1, WOOD)       # door 2.1 m
    B(mb, 0.3, 0.36, D - 0.08, D - 0.04, 1.0, 1.06, METAL)
    plant(mb, 0.8, 0.5, 0.9, rng)


def r_storage(mb, rng):
    shell(mb)
    for x0 in (-W, W - 0.5):
        B(mb, x0, x0 + 0.5, 0.6, D - 0.2, 0, 2.2, METAL)
        for z in (0.0, 0.75, 1.5):
            y = 0.65
            while y < D - 0.5:
                w = rng.uniform(0.3, 0.6)
                B(mb, x0 + 0.03, x0 + 0.47, y, y + w, z + 0.02, z + rng.uniform(0.3, 0.6), WOOD)
                y += w + rng.uniform(0.05, 0.3)
    ceiling_panel(mb, 0, 2.2, w=0.2, d=1.2)


def r_shop(mb, rng):
    """Shopfront interior (scaled to the storefront zone height): shelves, counter, lights."""
    shell(mb, depth=D, h=H)
    for x0 in (-W, W - 0.45):
        B(mb, x0, x0 + 0.45, 0.8, D - 0.3, 0, 2.2, WOOD)
        for z in (0.5, 1.0, 1.5, 2.0):
            y = 0.85
            while y < D - 0.4:
                w = rng.uniform(0.08, 0.2)
                B(mb, x0 + 0.05, x0 + 0.4, y, y + w, z - 0.45, z - 0.45 + rng.uniform(0.12, 0.3), BOOK)
                y += w + 0.01
    B(mb, -0.4, 0.4, D - 1.4, D - 0.8, 0, 1.0, WOOD)
    B(mb, -0.42, 0.42, D - 1.42, D - 0.78, 1.0, 1.04, WALL)
    for y in (0.8, 2.0, 3.2):
        ceiling_panel(mb, 0, y, w=0.25, d=0.8)
    person(mb, 0.0, D - 0.5, rot=math.pi)


def r_ac(mb, rng):
    """Window air-conditioner hanging out of the lower sash (outside the glass, y < 0)."""
    B(mb, -0.33, 0.33, -0.42, 0.18, 1.0, 1.42, METAL)
    mb.quad((-0.3, -0.421, 1.05), (0.3, -0.421, 1.05), (0.3, -0.421, 1.37), (-0.3, -0.421, 1.37), DARK, None)
    B(mb, -0.36, 0.36, -0.15, -0.05, 0.96, 1.0, METAL)


def r_fire_escape(mb, rng):
    """One storey of a painted-steel fire escape outside the window (y < 0): grated landing,
    railings with balusters, and the stair down to the landing below."""
    M = DARK
    B(mb, -1.25, 1.25, -1.15, -0.03, -0.05, 0.0, M)
    B(mb, -1.25, 1.25, -1.17, -1.13, 0.93, 0.97, M)
    B(mb, -1.25, 1.25, -1.17, -1.13, 0.45, 0.48, M)
    for x in (-1.25, 1.21):
        B(mb, x, x + 0.04, -1.15, -0.03, 0.93, 0.97, M)
    x = -1.25
    while x <= 1.26:
        B(mb, x - 0.012, x + 0.012, -1.16, -1.14, 0.0, 0.93, M)
        x += 0.14
    for y in (-0.9, -0.6, -0.3):
        for x in (-1.25, 1.23):
            B(mb, x, x + 0.02, y - 0.01, y + 0.01, 0.0, 0.93, M)
    for x in (-1.1, 1.1):
        mb.poly([(x - 0.02, -0.03, -0.05), (x - 0.02, -1.0, -0.05), (x - 0.02, -0.03, -0.75)], M)
        mb.poly([(x + 0.02, -0.03, -0.75), (x + 0.02, -1.0, -0.05), (x + 0.02, -0.03, -0.05)], M)
    z0, z1 = -0.05, -3.85
    xa, xb = 0.95, -0.85
    for yy in (-1.08, -0.55):
        q = [(xa, yy, z0), (xa, yy, z0 + 0.12), (xb, yy, z1 + 0.12), (xb, yy, z1)]
        mb.poly(q, M)
        mb.poly(q[::-1], M)
    n = 13
    for k in range(n):
        t = (k + 0.5) / n
        xs = xa + (xb - xa) * t
        zs = z0 + (z1 - z0) * t
        B(mb, xs - 0.07, xs + 0.07, -1.08, -0.55, zs, zs + 0.02, M)
    for yy in (-1.1, -0.53):
        q = [(xa, yy, z0 + 0.9), (xa, yy, z0 + 0.94), (xb, yy, z1 + 0.94), (xb, yy, z1 + 0.9)]
        mb.poly(q, M)
        mb.poly(q[::-1], M)


def _shop_shell(mb, wall_d=D):
    shell(mb, depth=wall_d, h=H)
    # fit-out: dark floor tiles, timber / painted panelling on the walls, a dark ceiling band
    mb.quad((-W, 0.02, 0.004), (W, 0.02, 0.004), (W, wall_d, 0.004), (-W, wall_d, 0.004), DARK, None)
    for x0, x1 in ((-W, -W + 0.03), (W - 0.03, W)):
        B(mb, x0, x1, 0.3, wall_d, 0.0, 2.6, FAB)
    B(mb, -W, W, wall_d - 0.03, wall_d, 0.0, 2.6, WOOD)
    B(mb, -W, W, 0.0, wall_d, H - 0.6, H - 0.55, DARK)
    for y in (0.7, 1.9, 3.1):
        for x in (-0.55, 0.55):
            mb.box(x - 0.08, x + 0.08, y - 0.08, y + 0.08, H - 0.03, H - 0.01, LAMP)   # downlights


def r_cafe(mb, rng):
    _shop_shell(mb)
    B(mb, -W, 0.2, D - 1.6, D - 1.0, 0, 1.05, WOOD)                 # counter
    B(mb, -W, 0.25, D - 1.65, D - 0.95, 1.05, 1.1, DARK)
    B(mb, -0.7, -0.35, D - 1.45, D - 1.15, 1.1, 1.5, METAL)          # espresso machine
    B(mb, -W, W, D - 0.05, D, 1.6, 2.4, DARK)                       # menu board
    mb.quad((-0.9, D - 0.051, 1.65), (0.9, D - 0.051, 1.65), (0.9, D - 0.051, 2.35), (-0.9, D - 0.051, 2.35), BOOK, None)
    B(mb, -W, W, D - 0.4, D, 0.9, 1.4, BOOK)                        # back shelf with cups / bags
    for y in (0.6, 1.6):                                             # window bar + stools
        B(mb, -0.95, 0.95, y, y + 0.35, 1.0, 1.05, WOOD)
        for x in (-0.6, 0.0, 0.6):
            chair(mb, x, y - 0.3, 1, m=DARK)
    for x in (-0.4, 0.4):
        pendant(mb, x, D - 1.3, z=2.2)
    person(mb, -0.3, D - 0.7, rot=math.pi)
    person(mb, 0.4, 0.3, rot=0.2)


def r_grocery(mb, rng):
    _shop_shell(mb)
    for x0 in (-W, W - 0.6):                                         # glowing fridges
        B(mb, x0, x0 + 0.6, 1.4, D - 0.1, 0, 2.1, METAL)
        q = (x0 + 0.6 + 0.001) if x0 < 0 else (x0 - 0.001)
        pts = [(q, 1.45, 0.1), (q, D - 0.15, 0.1), (q, D - 0.15, 2.0), (q, 1.45, 2.0)]
        mb.poly(pts if x0 < 0 else pts[::-1], SCREEN)
    for y in (0.4, 1.0):                                             # produce crates at the window
        for i in range(5):
            x = -0.9 + i * 0.38
            B(mb, x, x + 0.34, y, y + 0.45, 0.45, 0.62, WOOD)
            B(mb, x + 0.03, x + 0.31, y + 0.03, y + 0.42, 0.62, 0.72, rng.choice((BOOK, PLANT, FAB)))
        B(mb, -0.95, 0.95, y, y + 0.45, 0, 0.45, WOOD)
    B(mb, -0.3, 0.3, 2.0, D - 0.5, 0, 1.5, WOOD)                    # centre gondola
    for z in (0.4, 0.8, 1.2):
        B(mb, -0.33, 0.33, 2.0, D - 0.5, z, z + 0.25, BOOK)
    person(mb, 0.6, 2.4, rot=math.pi / 2)


def r_clothing(mb, rng):
    _shop_shell(mb)
    for x in (-0.55, 0.55):                                          # mannequins in the window
        person(mb, x, 0.5, rot=0.0)
    for y in (1.6, 2.6, 3.6):                                        # rails with garments
        B(mb, -0.8, 0.8, y - 0.01, y + 0.01, 1.55, 1.58, METAL)
        x = -0.78
        while x < 0.78:
            w = rng.uniform(0.04, 0.09)
            B(mb, x, x + w, y - 0.2, y + 0.2, 0.75, 1.55, FAB)
            x += w + 0.015
    B(mb, -W, W, D - 0.3, D, 0, 2.4, WALL)
    B(mb, -0.6, 0.6, D - 0.05, D, 0.4, 2.2, METAL)                  # mirror
    B(mb, -0.5, 0.5, 1.0, 1.3, 0, 0.9, WOOD)                        # display table
    B(mb, -0.45, 0.45, 1.05, 1.25, 0.9, 1.0, FAB)


def r_pharmacy(mb, rng):
    _shop_shell(mb)
    for x0 in (-W, W - 0.4):
        B(mb, x0, x0 + 0.4, 0.8, D - 0.2, 0, 2.0, CEIL)
        for z in (0.3, 0.65, 1.0, 1.35, 1.7):
            y = 0.85
            while y < D - 0.3:
                w = rng.uniform(0.05, 0.14)
                B(mb, x0 + 0.03, x0 + 0.37, y, y + w, z, z + rng.uniform(0.1, 0.25), BOOK)
                y += w + 0.01
    B(mb, -0.7, 0.7, D - 1.0, D - 0.5, 0, 1.0, CEIL)                 # counter
    B(mb, -W, W, D - 0.05, D, 2.2, 2.6, SCREEN)                     # backlit sign
    ceiling_panel(mb, 0, 1.2, w=0.8, d=0.4)
    ceiling_panel(mb, 0, 2.8, w=0.8, d=0.4)
    person(mb, 0.0, D - 0.3, rot=math.pi)


def r_restaurant(mb, rng):
    _shop_shell(mb)
    for (x, y) in ((-0.5, 0.8), (0.5, 0.8), (-0.5, 2.3), (0.5, 2.3)):
        table(mb, x - 0.35, x + 0.35, y - 0.35, y + 0.35, h=0.75)
        B(mb, x - 0.37, x + 0.37, y - 0.37, y + 0.37, 0.75, 0.76, CEIL)   # tablecloth
        chair(mb, x, y - 0.55, 1)
        chair(mb, x, y + 0.55, -1)
        pendant(mb, x, y, z=2.0)
    person(mb, -0.5, 1.35, rot=math.pi, sit=True)
    person(mb, 0.5, 2.85, rot=math.pi, sit=True)
    B(mb, -W, W, D - 0.5, D, 0, 1.1, WOOD)                           # bar
    B(mb, -W, W, D - 0.25, D, 1.4, 2.4, BOOK)                        # bottle wall


DEFS = [
    ('kitchen', lambda mb, r: r_kitchen(mb, r)),
    ('kitchen_p', lambda mb, r: r_kitchen(mb, r, p=True)),
    ('living', lambda mb, r: r_living(mb, r)),
    ('living_p', lambda mb, r: r_living(mb, r, p=True)),
    ('living_b', lambda mb, r: r_living(mb, r, b=True)),
    ('bedroom', r_bedroom),
    ('office', lambda mb, r: r_office(mb, r)),
    ('office_p', lambda mb, r: r_office(mb, r, p=True)),
    ('meeting', r_meeting),
    ('hotel', lambda mb, r: r_hotel(mb, r)),
    ('hotel_p', lambda mb, r: r_hotel(mb, r, p=True)),
    ('corridor', r_corridor),
    ('storage', r_storage),
    ('shop', r_shop),
    ('ac', r_ac),
    ('fire_escape', r_fire_escape),
    ('shop_cafe', r_cafe),
    ('shop_grocery', r_grocery),
    ('shop_clothing', r_clothing),
    ('shop_pharmacy', r_pharmacy),
    ('shop_restaurant', r_restaurant),
]
INDEX = {n: i for i, (n, f) in enumerate(DEFS)}


def build_kit(parent_col):
    kit = bpy.data.collections.get(KIT_COLLECTION)
    if kit is None:
        kit = bpy.data.collections.new(KIT_COLLECTION)
        parent_col.children.link(kit)
    mats = [MAT.get(m) for m in SLOTS]
    for i, (name, fn) in enumerate(DEFS):
        mb = MB()
        fn(mb, random.Random(100 + i))
        me = mb.build(f"ROOM_{i:02d}_{name}", mats)
        ob = bpy.data.objects.new(f"R{i:02d}_{name}", me)
        kit.objects.link(ob)
    return kit


_ng = None


def node_group(kit):
    global _ng
    if _ng is not None:
        return _ng
    ng = bpy.data.node_groups.new("CITY_rooms_instancer", 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = kit
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    ci.transform_space = 'ORIGINAL'
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True

    def attr(name, t):
        a = N.new('GeometryNodeInputNamedAttribute')
        a.data_type = t
        a.inputs['Name'].default_value = name
        return a.outputs['Attribute']
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(attr('rot', 'FLOAT_VECTOR'), e2r.inputs[0])
    L.new(gi.outputs[0], iop.inputs['Points'])
    L.new(ci.outputs[0], iop.inputs['Instance'])
    L.new(attr('rtype', 'INT'), iop.inputs['Instance Index'])
    L.new(e2r.outputs[0], iop.inputs['Rotation'])
    L.new(attr('scl', 'FLOAT_VECTOR'), iop.inputs['Scale'])
    L.new(iop.outputs[0], go.inputs[0])
    _ng = ng
    return ng


class RoomPoints:
    """Collects room placements for one building."""

    def __init__(self):
        self.P = []

    def add(self, loc, n_out, width, depth, storey, rtype, rr, rl, rt, mirror=False):
        nx, ny = n_out
        th = math.atan2(nx, -ny)          # local +y -> inward (-n)
        sx = width / 2.0 * (-1 if mirror else 1)
        name = rtype if isinstance(rtype, str) else DEFS[rtype][0]
        rb = SHOP_BOOST if name.startswith('shop') else 1.0
        self.P.append((loc, (0.0, 0.0, th), (sx, depth / D, storey / 3.8), INDEX[rtype] if isinstance(rtype, str) else rtype,
                       rr, rl, rt, rb))

    def build(self, name, col, kit):
        if not self.P:
            return None
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(self.P))
        import numpy as np
        me.vertices.foreach_set("co", np.array([p[0] for p in self.P], dtype=np.float32).ravel())
        for an, t, idx in (('rot', 'FLOAT_VECTOR', 1), ('scl', 'FLOAT_VECTOR', 2)):
            a = me.attributes.new(an, t, 'POINT')
            a.data.foreach_set("vector", np.array([p[idx] for p in self.P], dtype=np.float32).ravel())
        a = me.attributes.new('rtype', 'INT', 'POINT')
        a.data.foreach_set("value", np.array([p[3] for p in self.P], dtype=np.int32))
        for an, idx in (('rr', 4), ('rl', 5), ('rt', 6), ('rb', 7)):
            a = me.attributes.new(an, 'FLOAT', 'POINT')
            a.data.foreach_set("value", np.array([p[idx] for p in self.P], dtype=np.float32))
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        # camera rays only (they reach rooms through the see-through panes): diffuse / glossy /
        # shadow rays never test the 70k+ room instances, which keeps sampling cost ~flat
        ob.visible_diffuse = False
        ob.visible_glossy = False
        ob.visible_shadow = False
        ob.visible_volume_scatter = False
        mod = ob.modifiers.new("rooms", 'NODES')
        mod.node_group = node_group(kit)
        return ob


def pick(rng, use):
    mix = USE_MIX[use]
    tot = sum(w for _, w in mix)
    r = rng.random() * tot
    for n, w in mix:
        r -= w
        if r <= 0:
            return n
    return mix[-1][0]
