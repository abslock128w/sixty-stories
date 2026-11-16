"""ember_teal: big-budget golden hour pushed to complementary contrast.

Whatever the sun touches is molten amber; whatever it does not falls to deep teal, fed by a
clean, saturated sky. Haze is cool-albedo and strongly forward-scattering, so it glows orange
only along the sun line and reads blue-grey and thin elsewhere.

Sections (each function can be grafted on its own):
  key_lighting(scene)   LIGHT_CTRL keys per shot (sun colour, haze, exposure, sky grade props)
  haze(scene)           haze anisotropy + per-box multipliers
  world(scene)          sky model params, camera/glossy-ray sky grade (horizon->zenith colour,
                        keyed brightness), separate sun-disc boost, teal tint on sky fill,
                        sparser, under-lit cirrus
  materials(scene)      glass fire/teal reflection glow, semi-wet avenue, cooler unlit windows
  hero_fill(scene)      sky-motivated cool fill light linked to the HERO collection only
  compositor(scene)     split-tone CDL, bloom, anamorphic streak, ghost chain, saturation
"""
import bpy

import lighting
import lookkit as K

# ------------------------------------------------------------------ per-shot table
# extra LIGHT_CTRL props this look adds (driven into the world graph):
#   look_skycam   brightness of the sky as seen by the camera (not its lighting)
#   look_zen_r/g/b  camera/glossy sky multiplier at the zenith (horizon multiplier = look_hor_*)
#   look_hor_r/g/b  camera/glossy sky multiplier at the horizon
#   look_disc     extra visible sun disc (x sky_strength), unaffected by look_skycam
CANYON_HAZE = {'haze_r': 0.86, 'haze_g': 0.86, 'haze_b': 0.96}
AERIAL_HAZE = {'haze_r': 0.30, 'haze_g': 0.36, 'haze_b': 0.46}
GOLD = {'look_hor_r': 1.0, 'look_hor_g': 0.88, 'look_hor_b': 0.78,
        'look_zen_r': 0.36, 'look_zen_g': 0.70, 'look_zen_b': 0.98}
DUSK = {'look_hor_r': 1.0, 'look_hor_g': 0.84, 'look_hor_b': 0.62,
        'look_zen_r': 0.28, 'look_zen_g': 0.74, 'look_zen_b': 1.0}


def _k(d, **kw):
    o = dict(d)
    o.update(kw)
    return o


S1 = _k(_k(GOLD, **AERIAL_HAZE), look_skycam=0.55, look_disc=2.0, haze_density=0.00012,
         haze_r=0.24, haze_g=0.33, haze_b=0.52)
S2 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00020)
S3 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00026)
S4 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.55, look_disc=1.0, haze_density=0.00026)
S5 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.95, look_disc=1.0, haze_density=0.00020,
         haze_r=0.58, haze_g=0.78, haze_b=1.0, look_zen_r=0.30, look_zen_g=0.78, look_zen_b=1.05)
S6a = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.5, look_disc=1.0, haze_density=0.00016)
S6b = _k(_k(GOLD, **AERIAL_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00013)
S6c = _k(_k(DUSK, **AERIAL_HAZE), look_skycam=0.75, look_disc=0.0, haze_density=0.00012,
         haze_r=0.22, haze_g=0.30, haze_b=0.44, cloud_g=0.40, cloud_b=0.16)

LIGHT = [  # (frame, preset, dusk, exposure offset, overrides)
    (0, 'aerial', 0.0, -0.55, S1), (47, 'aerial', 0.0, -0.45, S1),
    (48, 'closeup', 0.0, 0.0, S2), (95, 'closeup', 0.0, 0.0, S2),
    (96, 'canyon', 0.0, -0.6, S3), (120, 'canyon', 0.0, -0.4, S3), (143, 'canyon', 0.0, -0.2, S3),
    (144, 'canyon', 0.0, 0.0, S4), (215, 'canyon', 0.0, 0.0, S4),
    (216, 'canyon', 0.0, -1.5, S5), (248, 'canyon', 0.0, -1.7, S5), (252, 'canyon', 0.0, -2.1, S5),
    (263, 'canyon', 0.0, -2.4, S5),
    (264, 'closeup', 0.15, 0.0, S6a), (296, 'closeup', 0.3, 0.0, S6a), (318, 'aerial', 0.6, 0.3, S6b),
    (335, 'dusk_wide', 0.95, 0.0, S6c),
]
# molten sun: keep the dusk progression, but push it toward amber
BASE_OVR = {'sun_g*': 0.80, 'sun_b*': 0.50, 'sun_strength*': 1.1, 'cloud_g*': 0.85, 'cloud_b*': 0.6}

ANISO = 0.82
HAZE_MULT = {'ATMO_haze_mat_low': 1.7, 'ATMO_haze_mat_canyon': 3.8}

LOOK_PROPS = ('look_skycam', 'look_zen_r', 'look_zen_g', 'look_zen_b', 'look_hor_r', 'look_hor_g',
              'look_hor_b', 'look_disc')


# ------------------------------------------------------------------ lighting keys
def key_lighting(scene):
    ctrl = lighting.get_ctrl()
    for p in LOOK_PROPS:
        if p not in ctrl:
            ctrl[p] = 1.0
    K.key_light(scene, LIGHT, base_ovr=BASE_OVR)


def haze(scene):
    K.haze_anisotropy(ANISO)
    for name, mult in HAZE_MULT.items():
        m = bpy.data.materials.get(name)
        if m and m.node_tree and m.node_tree.nodes.get('LowMul'):
            m.node_tree.nodes['LowMul'].inputs[1].default_value = mult


# ------------------------------------------------------------------ world
def _n(nt, name, typ, loc, **props):
    n = nt.nodes.get(name)
    if n is None:
        n = nt.nodes.new(typ)
        n.name = name
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _rename_by(nt, newname, typ, pred):
    n = nt.nodes.get(newname)
    if n is not None:
        return n
    for c in nt.nodes:
        if c.bl_idname == typ and not c.name.startswith('LOOK_') and pred(c):
            c.name = newname
            return c
    return None


def _ctrl_color(nt, name, props, loc):
    c = _n(nt, name, 'ShaderNodeCombineColor', loc)
    for i, p in enumerate(props):
        lighting.drive_node_input(nt, c, i, p)
    return c


def _ctrl_value(nt, name, prop, loc):
    v = _n(nt, name, 'ShaderNodeValue', loc)
    lighting.drive(nt, f'nodes["{v.name}"].outputs[0].default_value', prop)
    return v


def world(scene):
    w = bpy.data.worlds.get('CITY_world')
    nt = w.node_tree
    L = nt.links
    # cleaner air: less aerosol (sky holds blue and the horizon saturates), more ozone (deeper zenith)
    for nm in ('SkyDisc', 'SkyNoDisc'):
        s = nt.nodes[nm]
        s.aerosol_density = 1.0
        s.air_density = 1.15
        s.ozone_density = 2.2
        s.sun_intensity = 0.6
    # sparser, under-lit cirrus
    cov = _rename_by(nt, 'LOOK_cloud_cov', 'ShaderNodeMapRange',
                     lambda n: abs(n.inputs['From Min'].default_value - 0.44) < 1e-4)
    big = _rename_by(nt, 'LOOK_cloud_big', 'ShaderNodeMapRange',
                     lambda n: abs(n.inputs['From Min'].default_value - 0.36) < 1e-4)
    dark = _rename_by(nt, 'LOOK_cloud_dark', 'ShaderNodeRGB',
                      lambda n: abs(n.outputs[0].default_value[0] - 0.20) < 1e-4)
    if cov:
        cov.inputs['From Min'].default_value = 0.50
        cov.inputs['From Max'].default_value = 0.70
    if big:
        big.inputs['From Min'].default_value = 0.42
        big.inputs['From Max'].default_value = 0.58
    if dark:
        dark.outputs[0].default_value = (0.07, 0.10, 0.16, 1.0)
    nt.nodes['CloudOpacity'].inputs[1].default_value = 0.85

    over = nt.nodes['CloudOver']
    bg = [n for n in nt.nodes if n.type == 'BACKGROUND'][0]
    sky_d, sky_n = nt.nodes['SkyDisc'], nt.nodes['SkyNoDisc']
    sstr = nt.nodes['CTRL_sky_strength']
    X = 1700
    tc = _n(nt, 'LOOK_tc', 'ShaderNodeTexCoord', (X, -900))
    sep = _n(nt, 'LOOK_sep', 'ShaderNodeSeparateXYZ', (X + 200, -900))
    L.new(tc.outputs['Generated'], sep.inputs[0])
    gz = _n(nt, 'LOOK_gz', 'ShaderNodeMapRange', (X + 400, -900), interpolation_type='SMOOTHSTEP')
    gz.inputs['From Min'].default_value = 0.0
    gz.inputs['From Max'].default_value = 0.55
    L.new(sep.outputs['Z'], gz.inputs['Value'])
    hor = _ctrl_color(nt, 'LOOK_hor', ('look_hor_r', 'look_hor_g', 'look_hor_b'), (X + 400, -700))
    zen = _ctrl_color(nt, 'LOOK_zen', ('look_zen_r', 'look_zen_g', 'look_zen_b'), (X + 400, -1100))
    grade = _n(nt, 'LOOK_grade', 'ShaderNodeMix', (X + 600, -800), data_type='RGBA', blend_type='MIX')
    L.new(gz.outputs[0], grade.inputs['Factor'])
    L.new(hor.outputs[0], grade.inputs[6])
    L.new(zen.outputs[0], grade.inputs[7])
    graded = _n(nt, 'LOOK_graded', 'ShaderNodeVectorMath', (X + 800, -600), operation='MULTIPLY')
    L.new(over.outputs['Result'], graded.inputs[0])
    L.new(grade.outputs['Result'], graded.inputs[1])
    skycam = _ctrl_value(nt, 'LOOK_skycam_v', 'look_skycam', (X + 800, -1000))
    cam = _n(nt, 'LOOK_cam', 'ShaderNodeVectorMath', (X + 1000, -600), operation='SCALE')
    L.new(graded.outputs[0], cam.inputs[0])
    L.new(skycam.outputs[0], cam.inputs['Scale'])
    # visible sun disc, added back unaffected by the sky dimming
    dsub = _n(nt, 'LOOK_disc_sub', 'ShaderNodeVectorMath', (X + 600, -1400), operation='SUBTRACT')
    L.new(sky_d.outputs['Color'], dsub.inputs[0])
    L.new(sky_n.outputs['Color'], dsub.inputs[1])
    dmax = _n(nt, 'LOOK_disc_max', 'ShaderNodeVectorMath', (X + 800, -1400), operation='MAXIMUM')
    dmax.inputs[1].default_value = (0.0, 0.0, 0.0)
    L.new(dsub.outputs[0], dmax.inputs[0])
    discv = _ctrl_value(nt, 'LOOK_disc_v', 'look_disc', (X + 800, -1600))
    dk = _n(nt, 'LOOK_disc_k', 'ShaderNodeMath', (X + 1000, -1600), operation='MULTIPLY')
    L.new(discv.outputs[0], dk.inputs[0])
    L.new(sstr.outputs[0], dk.inputs[1])
    dsc = _n(nt, 'LOOK_disc_scale', 'ShaderNodeVectorMath', (X + 1000, -1400), operation='SCALE')
    L.new(dmax.outputs[0], dsc.inputs[0])
    L.new(dk.outputs[0], dsc.inputs['Scale'])
    camd = _n(nt, 'LOOK_cam_disc', 'ShaderNodeVectorMath', (X + 1200, -600), operation='ADD')
    L.new(cam.outputs[0], camd.inputs[0])
    L.new(dsc.outputs[0], camd.inputs[1])
    # sky as a light: tinted toward teal so every shadow is fed a cool fill
    fill = _n(nt, 'LOOK_fill_tint', 'ShaderNodeVectorMath', (X + 800, -300), operation='MULTIPLY')
    L.new(over.outputs['Result'], fill.inputs[0])
    fill.inputs[1].default_value = (0.86, 1.0, 1.12)
    lp = _n(nt, 'LOOK_lp', 'ShaderNodeLightPath', (X + 800, 200))
    mg = _n(nt, 'LOOK_mix_glossy', 'ShaderNodeMix', (X + 1200, -300), data_type='RGBA')
    L.new(lp.outputs['Is Glossy Ray'], mg.inputs['Factor'])
    L.new(fill.outputs[0], mg.inputs[6])
    L.new(graded.outputs[0], mg.inputs[7])
    mc = _n(nt, 'LOOK_mix_cam', 'ShaderNodeMix', (X + 1400, -300), data_type='RGBA')
    L.new(lp.outputs['Is Camera Ray'], mc.inputs['Factor'])
    L.new(mg.outputs['Result'], mc.inputs[6])
    L.new(camd.outputs[0], mc.inputs[7])
    L.new(mc.outputs['Result'], bg.inputs['Color'])
    bg.location = (X + 1600, 0)
    [n for n in nt.nodes if n.type == 'OUTPUT_WORLD'][0].location = (X + 1800, 0)


# ------------------------------------------------------------------ materials
def _env_mix(mat):
    """The window's grazing-angle environment glow: Mix with A cool / B warm colours."""
    nt = mat.node_tree
    n = nt.nodes.get('LOOK_env_mix')
    if n is not None:
        return n
    for c in nt.nodes:
        if c.bl_idname != 'ShaderNodeMix' or c.data_type != 'RGBA':
            continue
        a = c.inputs[6].default_value
        if abs(a[0] - 0.30) < 1e-3 and abs(a[2] - 0.46) < 1e-3:
            c.name = 'LOOK_env_mix'
            return c
    return None


def materials(scene):
    for nm in ('window', 'curtain'):
        m = bpy.data.materials.get(nm)
        if not m or not m.node_tree:
            continue
        mx = _env_mix(m)
        if mx is not None:
            mx.inputs[6].default_value = (0.10, 0.30, 0.44, 1.0)   # teal sky away from the sun
            mx.inputs[7].default_value = (1.0, 0.46, 0.12, 1.0)    # fire toward the sun
    # semi-wet avenue: mirrors the sun glare, tail lights and sky
    m, nodes = K.principled('asphalt')
    if m and nodes:
        K.scale_input(m, nodes[0], 'Roughness', 0.45)
        K.set_input(m, nodes[0], 'Specular IOR Level', 0.75)
        K.tint_base(m, nodes[0], (0.8, 0.8, 0.8))


# ------------------------------------------------------------------ hero fill
# Sky-motivated cool fill on the camera-facing (shadow) side of the backlit hero: one sun lamp
# per shot camera, parented to it (no falloff, so the level does not depend on lens distance),
# tilted to come from above, light-linked to the HERO collection only and switched on only
# while its camera is live. Irradiance per shot (W/m^2):
FILL = {'s1': 0.0, 's2': 1.2, 's3': 1.5, 's4': 3.0, 's5': 5.0, 's6': 2.2}
FILL_COLOR = (0.48, 0.72, 1.0)
FILL_TILT = -0.45   # radians about the camera X axis (negative = from above)


def hero_fill(scene):
    import math
    hero = bpy.data.collections.get('HERO')
    if hero is None:
        return
    for sid, (a, b) in K.SHOTS.items():
        cam = None
        for m in scene.timeline_markers:
            if m.frame == a and m.camera is not None:
                cam = m.camera
        if cam is None:
            continue
        name = 'LOOK_fill_' + sid
        ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'SUN')
        ld.color = FILL_COLOR
        ld.angle = math.radians(20.0)
        if ld.animation_data:
            ld.animation_data_clear()
        ob = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(ob)
        ob.parent = cam
        ob.location = (0, 0, 0)
        ob.rotation_euler = (FILL_TILT, 0.0, 0.0)
        ob.visible_camera = False
        ob.visible_glossy = False
        try:
            ob.light_linking.receiver_collection = hero
            # only the hero shadows his own fill (the camera often looks up from below the
            # street line, where city geometry would block a camera-direction light)
            ob.light_linking.blocker_collection = hero
        except Exception as e:
            K.log('light linking failed', e)
        K.log('fill', name, cam.name, ob.light_linking.receiver_collection)
        e = FILL[sid]
        keys = {0: 0.0, 335: 0.0}
        keys.update({a - 1: 0.0, b + 1: 0.0})
        keys.update({a: e, b: e})
        for f, v in sorted(keys.items()):
            if 0 <= f <= 335:
                ld.energy = v
                ld.keyframe_insert('energy', frame=f)
        K.set_interp(ld, 'CONSTANT')


# ------------------------------------------------------------------ compositor
GRADE = dict(
    view='AgX - Punchy',
    hl_sat=1.2, mid_sat=1.05, sh_sat=1.0,       # Colour Correction per-range saturation
    offset=(-0.0012, -0.0006, 0.0), power=(1.03, 1.0, 0.98), slope=(1.05, 1.0, 0.94),
    bloom=0.28, streak=0.14, ghost=0.08, clamp=100.0,
    teal=(0.70, 0.98, 1.25), teal_knee=0.20,    # shadow tint colour and luminance knee
)
# shadow-teal amount per shot (keyed on the compositor; ramps inside s6)
TEAL_KEYS = [(0, 0.85), (47, 0.85), (48, 0.55), (95, 0.55), (96, 0.45), (143, 0.45), (144, 0.50),
             (215, 0.50), (216, 0.35), (263, 0.35), (264, 0.50), (318, 0.40), (335, 0.30)]


def _cc_range(n, rng, **kw):
    """Set Colour Correction inputs of one range ('Master','Highlights','Midtones','Shadows')."""
    order = ['Master', 'Highlights', 'Midtones', 'Shadows']
    names = ['Saturation', 'Contrast', 'Gamma', 'Gain', 'Offset']
    socks = [s for s in n.inputs if s.name in names]
    k = order.index(rng)
    for j, nm in enumerate(names):
        if nm in kw:
            socks[k * 5 + j].default_value = kw[nm]


def _math(ng, name, op, a=None, b=None, loc=(0, 0)):
    n = ng.nodes.new('ShaderNodeMath')
    n.name = name
    n.operation = op
    n.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            ng.links.new(v, n.inputs[i])
    return n


def _mix(ng, name, blend, fac, a, b, loc=(0, 0)):
    n = ng.nodes.new('ShaderNodeMix')
    n.name = name
    n.data_type = 'RGBA'
    n.blend_type = blend
    n.clamp_result = False
    n.location = loc
    for sock, v in ((n.inputs['Factor'], fac), (n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            ng.links.new(v, sock)
    return n


def compositor(scene, g=None):
    """rl -> bloom -> + clamped-source anamorphic streak + ghost chain -> shadow teal (luma
    masked, keyed per shot) -> CDL warm top -> per-range saturation -> out."""
    g = dict(GRADE, **(g or {}))
    K.view(scene, g['view'])
    ng, rl, out = K.new_compositor(scene)
    L = ng.links
    bloom = K.glare(ng, 'LOOK_bloom', Type='Bloom', Quality='High', Threshold=1.6, Smoothness=0.5,
                    Strength=g['bloom'], Size=0.62, Saturation=1.1)
    L.new(rl.outputs['Image'], bloom.inputs['Image'])
    # the sun disc is ~1e4-6e4 in scene-linear: clamp the source so the streak and ghosts keep
    # the same controlled weight whether the disc is in frame or not
    cl = g['clamp']
    clamp = _mix(ng, 'LOOK_clamp', 'DARKEN', 1.0, rl.outputs['Image'], (cl, cl, cl, 1.0))
    streak = K.glare(ng, 'LOOK_streak', Type='Streaks', Quality='High', Threshold=6.0, Smoothness=0.4,
                     Strength=g['streak'], Streaks=2, **{'Streaks Angle': 0.0}, Fade=0.985,
                     Saturation=1.0, Tint=(0.50, 0.78, 1.0, 1.0))
    ghost = K.glare(ng, 'LOOK_ghost', Type='Ghosts', Quality='High', Threshold=4.0, Smoothness=0.3,
                    Strength=g['ghost'], Iterations=3, **{'Color Modulation': 0.4})
    L.new(clamp.outputs['Result'], streak.inputs['Image'])
    L.new(clamp.outputs['Result'], ghost.inputs['Image'])
    add1 = _mix(ng, 'LOOK_add_streak', 'ADD', 1.0, bloom.outputs['Image'], streak.outputs['Glare'])
    add2 = _mix(ng, 'LOOK_add_ghost', 'ADD', 1.0, add1.outputs['Result'], ghost.outputs['Glare'])
    img = add2.outputs['Result']
    # luminance-masked shadow tint toward teal
    sep = ng.nodes.new('CompositorNodeSeparateColor')
    sep.name = 'LOOK_sep'
    L.new(img, sep.inputs[0])
    r = _math(ng, 'LOOK_lr', 'MULTIPLY', sep.outputs[0], 0.2126)
    gg = _math(ng, 'LOOK_lg', 'MULTIPLY_ADD', sep.outputs[1], 0.7152)
    L.new(r.outputs[0], gg.inputs[2])
    lum = _math(ng, 'LOOK_lum', 'MULTIPLY_ADD', sep.outputs[2], 0.0722)
    L.new(gg.outputs[0], lum.inputs[2])
    t = _math(ng, 'LOOK_lt', 'DIVIDE', lum.outputs[0], g['teal_knee'])
    t2 = _math(ng, 'LOOK_lt2', 'SUBTRACT', 1.0, t.outputs[0])
    t2.use_clamp = True
    t3 = _math(ng, 'LOOK_lt3', 'POWER', t2.outputs[0], 1.5)
    amt = _math(ng, 'LOOK_teal_amt', 'MULTIPLY', t3.outputs[0], 0.4)
    for f, v in TEAL_KEYS:
        amt.inputs[1].default_value = v
        ng.keyframe_insert(f'nodes["{amt.name}"].inputs[1].default_value', frame=f)
    K.set_interp(ng, 'LINEAR')
    tint = _mix(ng, 'LOOK_teal', 'MULTIPLY', amt.outputs[0], img, tuple(g['teal']) + (1.0,))
    split = K.cdl(ng, 'LOOK_cdl', offset=g['offset'], power=g['power'], slope=g['slope'])
    cc = ng.nodes.new('CompositorNodeColorCorrection')
    cc.name = 'LOOK_cc'
    _cc_range(cc, 'Highlights', Saturation=g['hl_sat'])
    _cc_range(cc, 'Midtones', Saturation=g['mid_sat'])
    _cc_range(cc, 'Shadows', Saturation=g['sh_sat'])
    L.new(tint.outputs['Result'], split.inputs['Image'])
    L.new(split.outputs['Image'], cc.inputs['Image'])
    L.new(cc.outputs['Image'], out.inputs[0])
    for i, n in enumerate(ng.nodes):
        if n.name.startswith('LOOK_'):
            n.location = (-600 + 160 * (i % 12), 300 - 220 * (i // 12))


def apply(scene):
    K.remove_look_objects()
    key_lighting(scene)
    haze(scene)
    world(scene)
    materials(scene)
    hero_fill(scene)
    compositor(scene)
    lighting.touch(scene)
