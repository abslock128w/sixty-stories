"""after_rain: AFTER THE RAIN.

A storm has just cleared. A heavy slate-blue cloud deck covers the sky and is broken open
along the horizon where the low sun blasts through a clear slot, lighting the deck from
underneath in crimson, orange and gold. Rain-washed air (thin, cool, strongly
forward-scattering haze, so far towers stay crisp and the glow lives on the sun line and in
the avenue). Every horizontal surface is wet: mirror puddles, damp sheen, drying patches.
Ambient is cool and low, the sun is hot; the end plate turns the deck indigo/purple with a
last red seam at the horizon over a wet, blazing city.

Parts (graft-able independently):
  build_world()        new world LOOK_world_rain: multiple-scattering sky + storm deck with a
                       ragged clear slot around the sun and an under-lit base. Every
                       time-varying value reads LIGHT_CTRL custom props ar_* (keyed in LIGHT).
  wet_city()           shared shader group LOOK_wetmask (horizontal faces x puddle noise x
                       drying patches) feeding a water clear-coat + base darkening into the
                       Principled nodes of the city's surface materials.
  tune_haze()          per-box density multipliers, anisotropy, steam.
  build_comp()         bloom + anamorphic streak + cool-shadow/warm-highlight grade.
"""
import math

import bpy

import lighting
import lookkit as K

# ------------------------------------------------------------------ storm deck controls
# custom LIGHT_CTRL props read by the world (defaults; keyed per shot below)
AR_DEFAULTS = dict(
    ar_glow=1.0,          # under-glow amount (0..1.2); dusk lowers it -> only a red seam
    ar_hot=9.0,           # under-glow brightness multiplier
    ar_deck_r=0.045, ar_deck_g=0.066, ar_deck_b=0.120,   # unlit deck base (slate blue)
    ar_edge_lo=0.035,     # deck lower edge (sin elev) away from the sun
    ar_edge_hi=0.140,     # deck lower edge at the sun azimuth (sun sits just below it)
    ar_reach=0.28,        # how far up the deck the under-glow reaches (sin elev)
)

DUSK_DECK = dict(ar_glow=0.32, ar_hot=6.0, ar_deck_r=0.034, ar_deck_g=0.024, ar_deck_b=0.075,
                 ar_edge_lo=0.045, ar_edge_hi=0.070, ar_reach=0.16)


def _mix(a, b, t):
    out = {}
    for k in a:
        out[k] = a[k] + (b[k] - a[k]) * t
    return out


def deck(t=0.0):
    return _mix(AR_DEFAULTS, DUSK_DECK, t)


# common overrides for every key: cooler, rain-washed haze albedo, hotter sun
BASE = {'haze_r': 0.62, 'haze_g': 0.66, 'haze_b': 0.74, 'sun_strength*': 1.2, 'sun_g*': 0.93, 'sun_b*': 0.85}


def ov(d=None, deck_t=0.0, **kw):
    o = dict(deck(deck_t))
    if d:
        o.update(d)
    o.update(kw)
    return o


AER = dict(haze_density=0.00012, haze_r=0.26, haze_g=0.28, haze_b=0.34)
CLOSE = dict(haze_density=0.00014, haze_r=0.20, haze_g=0.24, haze_b=0.33)
CANY = dict(haze_density=0.00016, haze_r=0.27, haze_g=0.30, haze_b=0.38)

LIGHT = [
    (0, 'aerial', 0.0, -0.5, ov(AER)), (47, 'aerial', 0.0, -0.4, ov(AER)),
    (48, 'closeup', 0.0, -0.35, ov(CLOSE)), (95, 'closeup', 0.0, -0.35, ov(CLOSE)),
    (96, 'canyon', 0.0, 0.0, ov(CANY)), (120, 'canyon', 0.0, 0.2, ov(CANY)),
    (143, 'canyon', 0.0, 0.4, ov(CANY)),
    (144, 'canyon', 0.0, 0.6, ov(CANY)), (215, 'canyon', 0.0, 0.6, ov(CANY)),
    (216, 'canyon', 0.0, -0.6, ov(CANY)), (248, 'canyon', 0.0, -0.8, ov(CANY)),
    (252, 'canyon', 0.0, -1.4, ov(CANY)), (263, 'canyon', 0.0, -1.8, ov(CANY)),
    (264, 'closeup', 0.15, 0.0, ov(CLOSE, 0.1)), (296, 'closeup', 0.3, 0.2, ov(CLOSE, 0.3)),
    (318, 'aerial', 0.6, 0.4, ov(AER, 0.65, street_emit=3.0, car_emit=3.0)),
    (335, 'dusk_wide', 0.9, 0.3, ov(dict(haze_density=0.00012, haze_r=0.30, haze_g=0.30, haze_b=0.46, sky_strength=0.24),
                                     1.0, street_emit=5.0, car_emit=4.5, window_emit=0.85, window_frac=0.34)),
]


# ------------------------------------------------------------------ world
WORLD = 'LOOK_world_rain'


def _ensure_ar_props():
    ctrl = lighting.get_ctrl()
    for k, v in AR_DEFAULTS.items():
        if k not in ctrl:
            ctrl[k] = float(v)
    for p in ('sun_x', 'sun_y', 'sun_z'):
        if p not in ctrl:
            ctrl[p] = 0.0


def build_world(scene):
    old = bpy.data.worlds.get(WORLD)
    if old is not None:
        bpy.data.worlds.remove(old)
    w = bpy.data.worlds.new(WORLD)
    try:
        w.use_nodes = True
    except Exception:
        pass
    scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    xs = [0]

    def node(t, **kw):
        n = N.new(t)
        xs[0] += 1
        n.location = ((xs[0] % 12) * 200 - 1200, -(xs[0] // 12) * 250)
        for k, v in kw.items():
            if k.startswith('i_'):
                n.inputs[k[2:].replace('_', ' ')].default_value = v
            else:
                setattr(n, k, v)
        return n

    def math(op, a, b=None, clamp=False):
        m = node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                L.new(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def mrange(v, a, b, c=0.0, d=1.0):
        m = node('ShaderNodeMapRange', clamp=True)
        m.interpolation_type = 'SMOOTHSTEP'
        L.new(v, m.inputs['Value'])
        m.inputs['From Min'].default_value = a
        m.inputs['From Max'].default_value = b
        m.inputs['To Min'].default_value = c
        m.inputs['To Max'].default_value = d
        return m.outputs[0]

    def cv(prop):
        return lighting.ctrl_value_node(nt, prop).outputs[0]

    out = node('ShaderNodeOutputWorld')
    # --- sky (as the shipped world: disc for camera rays, no disc for lighting)
    sky_d = node('ShaderNodeTexSky', sky_type='MULTIPLE_SCATTERING', name='SkyDisc')
    sky_n = node('ShaderNodeTexSky', sky_type='MULTIPLE_SCATTERING', name='SkyNoDisc')
    sky_d.sun_disc = True
    sky_n.sun_disc = False
    for s in (sky_d, sky_n):
        s.altitude = 30.0
        s.air_density = 1.0
        s.aerosol_density = 1.2      # rain-washed: fewer aerosols
        s.ozone_density = 1.0
        s.sun_size = math_radians(0.55)
        s.sun_intensity = 0.6
        lighting.drive(nt, f'nodes["{s.name}"].sun_elevation', 'sun_elev')
        lighting.drive(nt, f'nodes["{s.name}"].sun_rotation', 'sun_azim')
    lp = node('ShaderNodeLightPath')
    mix_sky = node('ShaderNodeMix', data_type='RGBA', name='MixSky')
    L.new(lp.outputs['Is Camera Ray'], mix_sky.inputs['Factor'])
    L.new(sky_n.outputs['Color'], mix_sky.inputs['A'])
    L.new(sky_d.outputs['Color'], mix_sky.inputs['B'])
    skys = node('ShaderNodeVectorMath', operation='SCALE')
    L.new(mix_sky.outputs['Result'], skys.inputs[0])
    L.new(cv('sky_strength'), skys.inputs['Scale'])
    # the clear slot under the deck burns gold-orange rather than white
    sep0 = node('ShaderNodeSeparateXYZ')
    L.new(node('ShaderNodeTexCoord').outputs['Generated'], sep0.inputs[0])
    hf = mrange(sep0.outputs['Z'], 0.22, 0.0)
    tint = node('ShaderNodeMix', data_type='RGBA', name='SlotTint')
    L.new(hf, tint.inputs['Factor'])
    tint.inputs['A'].default_value = (1.0, 1.0, 1.0, 1)
    tint.inputs['B'].default_value = (1.0, 0.62, 0.32, 1)
    skyt = node('ShaderNodeVectorMath', operation='MULTIPLY')
    L.new(skys.outputs[0], skyt.inputs[0])
    L.new(tint.outputs['Result'], skyt.inputs[1])
    skys = skyt

    # --- geometry of the deck
    tc = node('ShaderNodeTexCoord')
    D = tc.outputs['Generated']
    sep = node('ShaderNodeSeparateXYZ')
    L.new(D, sep.inputs[0])
    dz = sep.outputs['Z']
    zc = math('MAXIMUM', dz, 0.03)
    comb = node('ShaderNodeCombineXYZ')
    L.new(sep.outputs['X'], comb.inputs['X'])
    L.new(sep.outputs['Y'], comb.inputs['Y'])
    proj = node('ShaderNodeVectorMath', operation='DIVIDE')
    L.new(comb.outputs[0], proj.inputs[0])
    L.new(zc, proj.inputs[1])
    pw = node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    L.new(proj.outputs[0], pw.inputs[0])
    pw.inputs[1].default_value = (0.5, 1.5, 1.0)
    pw.inputs[2].default_value = (13.7, 5.1, 2.3)
    P = pw.outputs[0]
    # coverage: almost total, a few torn gaps
    ncov = node('ShaderNodeTexNoise', i_Scale=0.9, i_Detail=4.0, i_Roughness=0.55)
    L.new(P, ncov.inputs['Vector'])
    cov = mrange(ncov.outputs['Fac'], 0.30, 0.43)
    # billows (rolling stratocumulus underside)
    nb = node('ShaderNodeTexNoise', i_Scale=3.0, i_Detail=7.0, i_Roughness=0.62, i_Distortion=0.4)
    L.new(P, nb.inputs['Vector'])
    bill = mrange(nb.outputs['Fac'], 0.30, 0.72)
    # large cloud masses: modulate the billow relief so the deck is not a uniform wallpaper
    nm = node('ShaderNodeTexNoise', i_Scale=0.22, i_Detail=2.0, i_Roughness=0.5)
    L.new(P, nm.inputs['Vector'])
    bill = math('MULTIPLY', bill, mrange(nm.outputs['Fac'], 0.35, 0.65, 0.35, 1.25))
    # sun alignment
    sunvec = node('ShaderNodeCombineXYZ', name='SunVec')
    for i, p in enumerate(('sun_x', 'sun_y', 'sun_z')):
        lighting.drive_node_input(nt, sunvec, i, p)
    dot = node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    L.new(D, dot.inputs[0])
    L.new(sunvec.outputs[0], dot.inputs[1])
    fwd = math('MAXIMUM', dot.outputs['Value'], 0.0)
    fwd10 = math('POWER', fwd, 10.0)
    fwd3 = math('POWER', fwd, 3.0)
    fwd40 = math('POWER', fwd, 40.0)
    # ragged lower edge of the deck, high over the sun (the slot), low elsewhere
    en = node('ShaderNodeTexNoise', i_Scale=4.0, i_Detail=5.0, i_Roughness=0.6)
    L.new(P, en.inputs['Vector'])
    elo, ehi = cv('ar_edge_lo'), cv('ar_edge_hi')
    edge = math('ADD', elo, math('MULTIPLY', math('SUBTRACT', ehi, elo), fwd10))
    edge = math('ADD', edge, math('MULTIPLY', math('SUBTRACT', en.outputs['Fac'], 0.5), 0.06))
    above = math('SUBTRACT', dz, edge)
    dmask = mrange(above, 0.0, 0.03)
    alpha = math('MULTIPLY', math('MULTIPLY', dmask, cov), 0.985)
    # thin stratus scraps inside the slot (a band just above the horizon), lit hot
    sn = node('ShaderNodeTexNoise', i_Scale=0.9, i_Detail=4.0, i_Roughness=0.5)
    st = node('ShaderNodeVectorMath', operation='MULTIPLY')
    L.new(P, st.inputs[0])
    st.inputs[1].default_value = (0.25, 4.0, 1.0)
    L.new(st.outputs[0], sn.inputs['Vector'])
    sband = math('MULTIPLY', mrange(dz, 0.025, 0.05), mrange(dz, 0.10, 0.075))
    sband = math('MULTIPLY', sband, mrange(sn.outputs['Fac'], 0.55, 0.7))
    salpha = math('MULTIPLY', sband, 0.55)
    # under-glow: strongest at the deck edge, toward the sun, fading up the deck
    reach = cv('ar_reach')
    reach = math('MULTIPLY', reach, math('ADD', 0.25, math('MULTIPLY', fwd3, 0.75)))
    up = math('DIVIDE', math('MAXIMUM', above, 0.0), reach)
    under = math('SUBTRACT', 1.0, math('MINIMUM', up, 1.0))
    under = math('POWER', under, 1.6)
    dirg = math('ADD', 0.08, math('MULTIPLY', math('POWER', fwd, 4.0), 0.92))
    g = math('MULTIPLY', under, dirg)
    g = math('MULTIPLY', g, math('ADD', 0.15, math('MULTIPLY', math('MULTIPLY', bill, bill), 1.7)))
    # thin cloud at gap edges / ragged edge transmits the sun (silver-gold lining)
    rim = math('MULTIPLY', math('MULTIPLY', cov, math('SUBTRACT', 1.0, cov)), 4.0)
    rim = math('MULTIPLY', rim, math('POWER', fwd, 6.0))
    g = math('ADD', g, math('MULTIPLY', rim, 0.9))
    g = math('MULTIPLY', g, cv('ar_glow'))
    gcl = math('MINIMUM', g, 1.0)
    ramp = node('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (0.0, 0.0, 0.0, 1)
    els[1].position = 1.0
    els[1].color = (1.0, 0.72, 0.38, 1)
    for pos, col in ((0.10, (0.30, 0.025, 0.035, 1)), (0.28, (0.75, 0.08, 0.04, 1)),
                     (0.50, (1.0, 0.26, 0.06, 1)), (0.75, (1.0, 0.50, 0.16, 1))):
        e = els.new(pos)
        e.color = col
    L.new(gcl, ramp.inputs[0])
    gl = node('ShaderNodeVectorMath', operation='SCALE')
    L.new(ramp.outputs['Color'], gl.inputs[0])
    L.new(math('MULTIPLY', math('ADD', g, math('MULTIPLY', g, g)), cv('ar_hot')), gl.inputs['Scale'])
    # unlit deck: slate, darker in thick cores, a touch lighter in the billow tops
    dcol = node('ShaderNodeCombineColor')
    for i, p in enumerate(('ar_deck_r', 'ar_deck_g', 'ar_deck_b')):
        lighting.drive_node_input(nt, dcol, i, p)
    dsc = node('ShaderNodeVectorMath', operation='SCALE')
    L.new(dcol.outputs[0], dsc.inputs[0])
    L.new(math('ADD', 0.22, math('MULTIPLY', math('POWER', bill, 1.5), 1.6)), dsc.inputs['Scale'])
    ccol = node('ShaderNodeVectorMath', operation='ADD')
    L.new(dsc.outputs[0], ccol.inputs[0])
    L.new(gl.outputs[0], ccol.inputs[1])
    # stratus scraps colour: hot near the sun
    scol = node('ShaderNodeVectorMath', operation='SCALE')
    L.new(ramp.outputs['Color'], scol.inputs[0])
    sg = math('MULTIPLY', math('ADD', 0.25, math('MULTIPLY', fwd10, 3.0)), cv('ar_hot'))
    L.new(math('MULTIPLY', sg, cv('ar_glow')), scol.inputs['Scale'])
    # composite: sky -> stratus scraps -> deck
    m1 = node('ShaderNodeMix', data_type='RGBA', name='StratusOver')
    L.new(salpha, m1.inputs['Factor'])
    L.new(skys.outputs[0], m1.inputs['A'])
    L.new(scol.outputs[0], m1.inputs['B'])
    m2 = node('ShaderNodeMix', data_type='RGBA', name='DeckOver')
    L.new(alpha, m2.inputs['Factor'])
    L.new(m1.outputs['Result'], m2.inputs['A'])
    L.new(ccol.outputs[0], m2.inputs['B'])
    bg = node('ShaderNodeBackground')
    L.new(m2.outputs['Result'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    L.new(bg.outputs[0], out.inputs['Surface'])
    return w


def math_radians(d):
    return math.radians(d)


# ------------------------------------------------------------------ wet city
WET_GROUP = 'LOOK_wetmask'
# material -> (coat strength, base darkening)
WET = {
    'asphalt': (1.0, 0.55), 'sidewalk': (0.9, 0.45), 'curb': (0.8, 0.4),
    'paint_white': (0.9, 0.35), 'paint_yellow': (0.9, 0.35), 'bike_green': (0.9, 0.4),
    'roof': (1.0, 0.5), 'concrete': (0.8, 0.4), 'limestone': (0.7, 0.35),
    'tower_stone': (0.75, 0.35), 'trim': (0.7, 0.3), 'terracotta': (0.7, 0.3),
    'brick': (0.7, 0.35), 'panel': (0.6, 0.25), 'wall_bcol': (0.7, 0.35), 'far': (0.8, 0.35),
    'gargoyle': (0.85, 0.35), 'steel_prow': (0.6, 0.0), 'metal_dark': (0.5, 0.0),
    'metal_bronze': (0.5, 0.0), 'cw_spandrel': (0.5, 0.0), 'tower_spandrel': (0.6, 0.0),
    'plywood': (0.7, 0.4), 'shed_green': (0.8, 0.3), 'louvre': (0.5, 0.0),
}


def _wet_group():
    g = bpy.data.node_groups.get(WET_GROUP)
    if g is None:
        g = bpy.data.node_groups.new(WET_GROUP, 'ShaderNodeTree')
    g.nodes.clear()
    g.interface.clear()
    for nm in ('Coat', 'CoatRough', 'Dark'):
        g.interface.new_socket(nm, in_out='OUTPUT', socket_type='NodeSocketFloat')
    N, L = g.nodes, g.links
    out = N.new('NodeGroupOutput')

    def math(op, a, b=None):
        m = N.new('ShaderNodeMath')
        m.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                L.new(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def mrange(v, a, b, c=0.0, d=1.0):
        m = N.new('ShaderNodeMapRange')
        m.clamp = True
        L.new(v, m.inputs['Value'])
        m.inputs['From Min'].default_value = a
        m.inputs['From Max'].default_value = b
        m.inputs['To Min'].default_value = c
        m.inputs['To Max'].default_value = d
        return m.outputs[0]

    geo = N.new('ShaderNodeNewGeometry')
    nsep = N.new('ShaderNodeSeparateXYZ')
    L.new(geo.outputs['Normal'], nsep.inputs[0])
    horiz = mrange(nsep.outputs['Z'], 0.80, 0.97)
    n1 = N.new('ShaderNodeTexNoise')
    n1.inputs['Scale'].default_value = 0.16
    n1.inputs['Detail'].default_value = 3.0
    n1.inputs['Roughness'].default_value = 0.55
    L.new(geo.outputs['Position'], n1.inputs['Vector'])
    puddle = mrange(n1.outputs['Fac'], 0.47, 0.53)
    n2 = N.new('ShaderNodeTexNoise')
    n2.inputs['Scale'].default_value = 0.03
    n2.inputs['Detail'].default_value = 1.0
    L.new(geo.outputs['Position'], n2.inputs['Vector'])
    dry = mrange(n2.outputs['Fac'], 0.55, 0.66)
    wetp = math('MULTIPLY', puddle, math('SUBTRACT', 1.0, dry))          # mirror water
    coat = math('MULTIPLY', horiz, math('ADD', 0.4, math('MULTIPLY', wetp, 0.6)))
    coat = math('MULTIPLY', coat, math('SUBTRACT', 1.0, math('MULTIPLY', dry, 0.55)))
    crough = math('ADD', 0.012, math('MULTIPLY', math('SUBTRACT', 1.0, wetp), 0.20))
    dark = math('MULTIPLY', horiz, math('SUBTRACT', 1.0, math('MULTIPLY', dry, 0.6)))
    L.new(coat, out.inputs['Coat'])
    L.new(crough, out.inputs['CoatRough'])
    L.new(dark, out.inputs['Dark'])
    return g


def _wet_material(mat, strength, darken, grp):
    nt = mat.node_tree
    for p in [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED']:
        gname = 'LOOK_wet_' + p.name
        gn = nt.nodes.get(gname)
        if gn is None:
            cw = p.inputs['Coat Weight']
            if cw.is_linked:
                continue    # already a coated material (glass, car paint)
            gn = nt.nodes.new('ShaderNodeGroup')
            gn.name = gname
            gn.node_tree = grp
            gn.location = (p.location[0] - 400, p.location[1] - 500)
            k = nt.nodes.new('ShaderNodeMath')
            k.name = 'LOOK_wetk_' + p.name
            k.operation = 'MULTIPLY'
            nt.links.new(gn.outputs['Coat'], k.inputs[0])
            nt.links.new(k.outputs[0], cw)
            nt.links.new(gn.outputs['CoatRough'], p.inputs['Coat Roughness'])
            # darken the wet base
            s = p.inputs['Base Color']
            mix = nt.nodes.new('ShaderNodeMix')
            mix.name = 'LOOK_wetdark_' + p.name
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            if s.is_linked:
                nt.links.new(s.links[0].from_socket, mix.inputs['A'])
            else:
                mix.inputs['A'].default_value = s.default_value
            dk = nt.nodes.new('ShaderNodeMath')
            dk.name = 'LOOK_wetdk_' + p.name
            dk.operation = 'MULTIPLY'
            nt.links.new(gn.outputs['Dark'], dk.inputs[0])
            nt.links.new(dk.outputs[0], mix.inputs['Factor'])
            mix.inputs['B'].default_value = (0.5, 0.5, 0.5, 1)
            nt.links.new(mix.outputs['Result'], s)
        nt.nodes['LOOK_wetk_' + p.name].inputs[1].default_value = strength
        nt.nodes['LOOK_wetdk_' + p.name].inputs[1].default_value = darken
        p.inputs['Coat IOR'].default_value = 1.33
        try:
            p.inputs['Coat Tint'].default_value = (1, 1, 1, 1)
        except Exception:
            pass


def wet_city():
    grp = _wet_group()
    done, missing = [], []
    for name, (s, d) in WET.items():
        m = bpy.data.materials.get(name)
        if m is None or not m.node_tree:
            missing.append(name)
            continue
        _wet_material(m, s, d, grp)
        done.append(name)
    K.log('wet:', len(done), 'materials; missing', missing)


# ------------------------------------------------------------------ haze, steam
CANYON_ALB = (2.3, 2.2, 2.0)
def tune_haze():
    K.haze_anisotropy(0.90)
    mults = {'ATMO_haze_mat_low': 1.4, 'ATMO_haze_mat_canyon': 4.5}
    for name, v in mults.items():
        m = bpy.data.materials.get(name)
        if m and m.node_tree and m.node_tree.nodes.get('LowMul'):
            m.node_tree.nodes['LowMul'].inputs[1].default_value = v
    # the avenue corridor scatters brighter (wet, steamy street air): albedo x CANYON_ALB
    m = bpy.data.materials.get('ATMO_haze_mat_canyon')
    if m and m.node_tree:
        nt = m.node_tree
        vol = [n for n in nt.nodes if n.type == 'PRINCIPLED_VOLUME'][0]
        hc = nt.nodes.get('HazeColor')
        mul = nt.nodes.get('LOOK_alb')
        if mul is None:
            mul = nt.nodes.new('ShaderNodeMix')
            mul.name = 'LOOK_alb'
            mul.data_type = 'RGBA'
            mul.blend_type = 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            nt.links.new(hc.outputs[0], mul.inputs['A'])
            nt.links.new(mul.outputs['Result'], vol.inputs['Color'])
        mul.inputs['B'].default_value = CANYON_ALB + (1.0,)
    st = bpy.data.materials.get('steam')
    if st and st.node_tree:
        for n in st.node_tree.nodes:
            if n.type == 'PRINCIPLED_VOLUME':
                n.inputs['Density'].default_value = 0.8
                n.inputs['Color'].default_value = (0.92, 0.95, 1.0, 1)
                n.inputs['Anisotropy'].default_value = 0.6


# ------------------------------------------------------------------ hero bounce
# warm light thrown up off the wet avenue onto the hero's underside (light-linked to HERO)
BOUNCE = [(0, 0.0), (47, 0.0), (48, 40.0), (95, 40.0), (96, 60.0), (143, 60.0), (144, 120.0), (215, 120.0),
          (216, 250.0), (263, 250.0), (264, 0.0), (335, 0.0)]


def hero_bounce(scene):
    rig = bpy.data.objects.get('HERO_RIG')
    hero = bpy.data.collections.get('HERO')
    if rig is None or hero is None:
        K.log('no hero rig/collection: bounce skipped')
        return
    ld = bpy.data.lights.get('LOOK_hero_bounce')
    if ld is not None:
        bpy.data.lights.remove(ld)
    ld = bpy.data.lights.new('LOOK_hero_bounce', 'AREA')
    ld.shape = 'DISK'
    ld.size = 5.0
    ld.color = (1.0, 0.58, 0.30)
    ob = bpy.data.objects.new('LOOK_hero_bounce', ld)
    scene.collection.objects.link(ob)
    ob.rotation_euler = (math.pi, 0.0, 0.0)          # facing up
    c = ob.constraints.new('COPY_LOCATION')
    c.target = rig
    if rig.type == 'ARMATURE' and 'spine03' in rig.data.bones:
        c.subtarget = 'spine03'
    c.use_offset = True
    ob.location = (0.0, 0.0, -3.5)
    ob.visible_camera = False
    ob.visible_glossy = False
    try:
        ob.light_linking.receiver_collection = hero
    except Exception as e:
        K.log('light linking failed', e)
    for f, e in BOUNCE:
        ld.energy = e
        ld.keyframe_insert('energy', frame=f)
    K.set_interp(ld, 'CONSTANT')


# ------------------------------------------------------------------ compositor
def build_comp(scene):
    ng, rl, out = K.new_compositor(scene)
    bloom = K.glare(ng, 'BLOOM', Type='Bloom', Quality='High', Threshold=1.4, Smoothness=0.5,
                    Strength=0.20, Size=0.6, Saturation=1.0)
    streak = K.glare(ng, 'STREAK', Type='Streaks', Quality='High', Threshold=4.0, Smoothness=0.5,
                     Strength=0.12, Streaks=2, **{'Streaks Angle': 0.0}, Fade=0.94, Saturation=0.6)
    # cool the low end, keep the hot end warm (scene-linear CDL before AgX)
    grade = K.cdl(ng, 'GRADE', offset=(-0.003, -0.001, 0.004), power=(1.10, 1.03, 0.95),
                  slope=(1.0, 0.98, 1.04))
    cc = K.color_correction(ng, 'SAT', saturation=1.15)
    K.chain(ng, rl.outputs['Image'], [bloom, streak, grade, cc], out.inputs[0])


# ------------------------------------------------------------------ apply
def apply(scene):
    K.remove_look_objects()
    _ensure_ar_props()
    build_world(scene)
    K.key_light(scene, LIGHT, base_ovr=BASE)
    tune_haze()
    wet_city()
    hero_bounce(scene)
    K.view(scene, 'AgX - High Contrast')
    build_comp(scene)
    lighting.touch(scene)
    names = sorted(m.name for m in bpy.data.materials if not m.name.startswith(('HERO_', 'LOOK_')))
    K.log('materials:', ' '.join(names))
