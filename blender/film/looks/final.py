"""final: EMBER AND TEAL, ONE EVENING. The film's final look.

Built on ember_teal (the panel winner): whatever the sun touches is molten amber, whatever it
does not falls to cool teal fed by a clean, graded sky; the haze is cool-albedo and strongly
forward-scattering, so it glows gold only along the sun line. On top of that this version:

  * opens the toe in the SCENE, not the grade: the sky's contribution as a light source is
    scaled per shot (look_fill), so shadows hold texture instead of crushing; exposure lifted
    about half a stop through s1-s5;
  * designs one sky arc for the evening (look_zen/hor/gzmax/cov per shot): gold with a cool
    blue overhead (s1-s4), a lavender-to-peach slot (s5), peach under a violet top with pink
    cloud (s6 apex), cobalt with a wide ember band and pink-violet cloud (end plate);
  * gives the hero a consistent, motivated rig: a gold kicker per shot, parented to the shot
    camera with a fixed sun-side direction (light-linked to the hero only), the winner's cool sky fill a stop lower, and a warm bounce from the sunlit
    canyon floor in the swing and the slot;
  * tames the optics: bloom fed from a clamped source (the sun disc does not carry the veil),
    strength and threshold keyed per shot; tapered anamorphic streak; soft ghosts, none in s6;
  * end-plate aerial perspective keyed on a cleaned depth pass (closing + opening + blur);
  * brighter, warmer window cores and street light at dusk, with the dark navy lower third
    kept for the title.

Sections (each graft-able):
  key_lighting(scene)   LIGHT_CTRL keys per shot
  haze(scene)           anisotropy + per-box multipliers
  world(scene)          sky model, camera/glossy sky grade, sun disc, scaled sky fill, clouds
  materials(scene)      glass fire/teal glow, semi-wet avenue
  hero_rig(scene)       cool fill (per camera), gold sun kicker, warm canyon bounce
  compositor(scene)     bloom/streak/ghost (keyed), shadow teal, CDL, saturation
"""
import math

import bpy

import lighting
import lookkit as K

# ------------------------------------------------------------------ per-shot table
# extra LIGHT_CTRL props this look adds (driven into the world graph):
#   look_skycam      brightness of the sky as seen by the camera (not its lighting)
#   look_zen_r/g/b   camera/glossy sky multiplier at the top of the gradient
#   look_hor_r/g/b   camera/glossy sky multiplier at the horizon
#   look_gzmax       elevation (generated Z) where the gradient reaches the zenith colour
#   look_disc        extra visible sun disc (x sky_strength), unaffected by look_skycam
#   look_fill        multiplier on the sky as a LIGHT (diffuse rays): opens the shadows
#   look_cov         cloud coverage threshold (lower = more cloud)
#   look_warmsky     warm boost of the low sky toward the sun, as a light
#   look_ember       camera-sky ember band: multiplies the low sky toward the sun (dusk)
CANYON_HAZE = {'haze_r': 0.86, 'haze_g': 0.86, 'haze_b': 0.96}
AERIAL_HAZE = {'haze_r': 0.30, 'haze_g': 0.36, 'haze_b': 0.46}
GOLD = {'look_hor_r': 1.0, 'look_hor_g': 0.88, 'look_hor_b': 0.78,
        'look_zen_r': 0.36, 'look_zen_g': 0.70, 'look_zen_b': 0.98,
        'look_gzmax': 0.55, 'look_fill': 1.6, 'look_cov': 0.50, 'look_warmsky': 1.0,
        'look_ember': 0.0}
DUSK = {'look_hor_r': 1.15, 'look_hor_g': 0.66, 'look_hor_b': 0.40,
        'look_zen_r': 0.30, 'look_zen_g': 0.66, 'look_zen_b': 1.05,
        'look_gzmax': 0.32, 'look_fill': 1.3, 'look_cov': 0.46, 'look_warmsky': 0.5,
        'look_ember': 2.2}


def _k(d, **kw):
    o = dict(d)
    o.update(kw)
    return o


# s1: warm-gold air (no green), real gradient up to a cool top, salmon-lit cirrus
S1 = _k(_k(GOLD, **AERIAL_HAZE), look_skycam=0.88, look_disc=2.2, haze_density=0.00012,
         **{'street_emit*': 6.0},
         haze_r=0.27, haze_g=0.25, haze_b=0.29, look_gzmax=0.20, look_fill=1.5, look_cov=0.27,
         look_zen_r=0.26, look_zen_g=0.52, look_zen_b=1.40, cloud_g=0.42, cloud_b=0.38,
         look_warmsky=0.6)
S2 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00018, look_fill=1.5,
         look_warmsky=0.6)
# s3: thinner veil so the low sun grazes the piers warm
S3 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00018,
         haze_r=0.92, haze_g=0.86, haze_b=0.90, look_fill=1.35, look_warmsky=3.6)
# s4: gold sun column (warmer canyon albedo), sky fill trimmed so the volume grain sits lower
S4 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00022,
         haze_r=0.95, haze_g=0.88, haze_b=0.86,
         look_fill=1.8, look_zen_r=0.42, look_zen_g=0.62, look_zen_b=1.0, look_warmsky=1.4)
# s5: the slot sky lighter than the suit: warm lavender overhead warming to peach at the
# bottom (late afternoon, not blue hour), amber pick-up on the slot walls
S5 = _k(_k(GOLD, **CANYON_HAZE), look_skycam=1.15, look_disc=1.0, haze_density=0.00020,
         haze_r=0.70, haze_g=0.74, haze_b=1.0, look_zen_r=1.35, look_zen_g=0.85, look_zen_b=0.62,
         look_hor_r=1.25, look_hor_g=0.78, look_hor_b=0.52, look_gzmax=1.0, look_fill=1.8,
         look_warmsky=1.5)
# s6 apex: thin air between camera and hero, violet top; cloud coverage held through s6
S6a = _k(_k(GOLD, **CANYON_HAZE), look_skycam=0.5, look_disc=1.6, haze_density=0.00012,
          look_zen_r=0.27, look_zen_g=0.22, look_zen_b=0.66, look_gzmax=0.30, look_cov=0.46,
          cloud_g=0.46, cloud_b=0.46, look_fill=0.55)
S6b = _k(_k(GOLD, **AERIAL_HAZE), look_skycam=0.6, look_disc=1.0, haze_density=0.00013,
          look_zen_r=0.40, look_zen_g=0.50, look_zen_b=0.95, look_gzmax=0.32, look_cov=0.46,
          cloud_g=0.42, cloud_b=0.40, look_fill=1.3, look_ember=0.6)
S6c = _k(_k(DUSK, **AERIAL_HAZE), look_skycam=0.75, look_disc=0.0, haze_density=0.00012,
          haze_r=0.32, haze_g=0.36, haze_b=0.54, cloud_g=0.34, cloud_b=0.38,
          look_hor_r=1.55, look_hor_g=0.74, look_hor_b=0.26, look_gzmax=0.46)

LIGHT = [  # (frame, preset, dusk, exposure offset, overrides)
    (0, 'aerial', 0.0, -0.15, S1), (47, 'aerial', 0.0, -0.05, S1),
    (48, 'closeup', 0.0, 0.0, S2), (95, 'closeup', 0.0, 0.0, S2),
    (96, 'canyon', 0.0, -0.1, S3), (120, 'canyon', 0.0, 0.1, S3), (143, 'canyon', 0.0, 0.25, S3),
    # s4: +0.3 (not +0.5) so the volume grain sits lower; eases to -0.1 into the sun at the end
    (144, 'canyon', 0.0, 0.3, S4), (200, 'canyon', 0.0, 0.3, S4), (215, 'canyon', 0.0, -0.1, S4),
    # s5: an even ramp (0.03, then 0.1 stop per frame as the sun comes up the slot), no pump
    (216, 'canyon', 0.0, -0.4, S5), (244, 'canyon', 0.0, -1.2, S5), (263, 'canyon', 0.0, -3.5, S5),
    (264, 'closeup', 0.15, -0.8, S6a), (296, 'closeup', 0.3, -0.5, S6a),
    # FILM fix: the pull-back crosses dark rooftops (median luma fell to 8 at 312): lift through
    (306, 'aerial', 0.42, 0.6, _k(S6b, look_ember=0.3, **{'window_emit*': 1.3})),
    (312, 'aerial', 0.5, 0.95, _k(S6b, look_ember=0.45, **{'window_emit*': 1.35})),
    (318, 'aerial', 0.6, 0.3, _k(S6b, **{'window_emit*': 1.4, 'street_emit*': 1.2, 'car_emit*': 1.2})),
    (335, 'dusk_wide', 0.95, 0.0, _k(S6c, **{'window_emit*': 1.4, 'street_emit*': 1.0, 'car_emit*': 1.2})),
]
# molten sun: keep the dusk progression, but push it toward amber
BASE_OVR = {'sun_g*': 0.80, 'sun_b*': 0.50, 'sun_strength*': 1.1, 'cloud_g*': 0.85, 'cloud_b*': 0.6}

ANISO = 0.82
# anisotropy (LINEAR, held with a key at each end of a shot): tighter forward glow on the
# opener so the skyline cuts out dark against a hot sun; lower at the apex so less sun-lit
# veil sits between the long lens and the hero; a slow ramp over the pull-back, no step
ANISO_KEYS = [(0, 0.88), (47, 0.88), (48, 0.82), (263, 0.82), (264, 0.70), (296, 0.70), (335, 0.76)]
HAZE_MULT = {'ATMO_haze_mat_low': 1.7, 'ATMO_haze_mat_canyon': 3.8}
# canyon haze multiplier keyed (LINEAR): thins over the last frames of s5 (into the sun) and
# stays thin through s6 so the apex hero is not veiled
CANYON_KEYS = [(0, 3.8), (244, 3.8), (263, 1.2), (264, 1.2), (335, 1.2)]
# low-box multiplier keyed the same way (thin into the sun at the end of s5 and at the apex,
# back to the full ground haze over the pull-back)
LOW_KEYS = [(0, 1.7), (244, 1.7), (263, 1.0), (296, 1.0), (318, 1.7), (335, 1.7)]

LOOK_PROPS = ('look_skycam', 'look_zen_r', 'look_zen_g', 'look_zen_b', 'look_hor_r', 'look_hor_g',
              'look_hor_b', 'look_disc', 'look_fill', 'look_gzmax', 'look_cov', 'look_warmsky', 'look_ember')


# ------------------------------------------------------------------ lighting keys
def key_lighting(scene):
    ctrl = lighting.get_ctrl()
    for p in LOOK_PROPS:
        if p not in ctrl:
            ctrl[p] = 1.0
    K.key_light(scene, LIGHT, base_ovr=BASE_OVR)


def haze(scene):
    K.haze_anisotropy(ANISO)
    for m in bpy.data.materials:
        if not (m.name.startswith('ATMO_haze') and m.node_tree):
            continue
        nt = m.node_tree
        for n in nt.nodes:
            if n.type != 'PRINCIPLED_VOLUME':
                continue
            sock = n.inputs['Anisotropy']
            path = sock.path_from_id('default_value')
            for fc in K.fcurves(nt):
                if fc.data_path == path:
                    K._remove_fcurve(nt, fc)
            for f, v in ANISO_KEYS:
                sock.default_value = v
                nt.keyframe_insert(path, frame=f)
            for fc in K.fcurves(nt):
                if fc.data_path == path:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
    for name, mult in HAZE_MULT.items():
        m = bpy.data.materials.get(name)
        if m and m.node_tree and m.node_tree.nodes.get('LowMul'):
            nt = m.node_tree
            sock = nt.nodes['LowMul'].inputs[1]
            path = sock.path_from_id('default_value')
            for fc in K.fcurves(nt):
                if fc.data_path == path:
                    K._remove_fcurve(nt, fc)
            sock.default_value = mult
            keys = {'ATMO_haze_mat_canyon': CANYON_KEYS, 'ATMO_haze_mat_low': LOW_KEYS}.get(name)
            if keys:
                for f, v in keys:
                    sock.default_value = v
                    nt.keyframe_insert(path, frame=f)
                for fc in K.fcurves(nt):
                    if fc.data_path == path:
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'LINEAR'


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
    # cleaner air: less aerosol (sky holds blue and the horizon saturates), more ozone
    for nm in ('SkyDisc', 'SkyNoDisc'):
        s = nt.nodes[nm]
        s.aerosol_density = 1.0
        s.air_density = 1.15
        s.ozone_density = 2.2
        s.sun_intensity = 0.6
    # cirrus: coverage keyed per shot, under-lit dark side, fades a little lower to the horizon
    cov = _rename_by(nt, 'LOOK_cloud_cov', 'ShaderNodeMapRange',
                     lambda n: abs(n.inputs['From Min'].default_value - 0.44) < 1e-4)
    big = _rename_by(nt, 'LOOK_cloud_big', 'ShaderNodeMapRange',
                     lambda n: abs(n.inputs['From Min'].default_value - 0.36) < 1e-4)
    hz = _rename_by(nt, 'LOOK_cloud_hz', 'ShaderNodeMapRange',
                    lambda n: abs(n.inputs['From Min'].default_value - 0.02) < 1e-4
                    and abs(n.inputs['From Max'].default_value - 0.16) < 1e-4)
    dark = _rename_by(nt, 'LOOK_cloud_dark', 'ShaderNodeRGB',
                      lambda n: abs(n.outputs[0].default_value[0] - 0.20) < 1e-4)
    if cov:
        cov.inputs['From Max'].default_value = 0.70
        lighting.drive_node_input(nt, cov, 'From Min', 'look_cov')
    if big:
        big.inputs['From Min'].default_value = 0.40
        big.inputs['From Max'].default_value = 0.58
    if hz:
        hz.inputs['From Min'].default_value = 0.02
        hz.inputs['From Max'].default_value = 0.11
    if dark:
        dark.outputs[0].default_value = (0.09, 0.10, 0.16, 1.0)
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
    lighting.drive_node_input(nt, gz, 'From Max', 'look_gzmax')
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
    # ember band (end plate): the camera sky near the horizon toward the sun is multiplied up
    # and pushed orange, so the afterglow reads as a wide hot band rather than a thin seam
    edot = _n(nt, 'LOOK_e_dot', 'ShaderNodeVectorMath', (X + 200, -1800), operation='DOT_PRODUCT')
    L.new(tc.outputs['Generated'], edot.inputs[0])
    L.new(nt.nodes['SunVec'].outputs[0], edot.inputs[1])
    elobe = _n(nt, 'LOOK_e_lobe', 'ShaderNodeMapRange', (X + 400, -1800), interpolation_type='SMOOTHSTEP')
    elobe.inputs['From Min'].default_value = -0.2
    elobe.inputs['From Max'].default_value = 1.0
    L.new(edot.outputs['Value'], elobe.inputs['Value'])
    eband = _n(nt, 'LOOK_e_band', 'ShaderNodeMapRange', (X + 400, -2000), interpolation_type='SMOOTHSTEP')
    eband.inputs['From Min'].default_value = 0.16
    eband.inputs['From Max'].default_value = 0.0
    L.new(sep.outputs['Z'], eband.inputs['Value'])
    em1 = _n(nt, 'LOOK_e_m1', 'ShaderNodeMath', (X + 600, -1900), operation='MULTIPLY')
    L.new(elobe.outputs[0], em1.inputs[0])
    L.new(eband.outputs[0], em1.inputs[1])
    ev = _ctrl_value(nt, 'LOOK_ember_v', 'look_ember', (X + 600, -2100))
    em2 = _n(nt, 'LOOK_e_m2', 'ShaderNodeMath', (X + 800, -1900), operation='MULTIPLY')
    L.new(em1.outputs[0], em2.inputs[0])
    L.new(ev.outputs[0], em2.inputs[1])
    ecol = _n(nt, 'LOOK_e_col', 'ShaderNodeVectorMath', (X + 1000, -1900), operation='SCALE')
    ecol.inputs[0].default_value = (1.0, 0.48, 0.12)
    L.new(em2.outputs[0], ecol.inputs['Scale'])
    eone = _n(nt, 'LOOK_e_one', 'ShaderNodeVectorMath', (X + 1100, -1900), operation='ADD')
    eone.inputs[0].default_value = (1.0, 1.0, 1.0)
    L.new(ecol.outputs[0], eone.inputs[1])
    emul = _n(nt, 'LOOK_e_mul', 'ShaderNodeVectorMath', (X + 1150, -700), operation='MULTIPLY')
    L.new(cam.outputs[0], emul.inputs[0])
    L.new(eone.outputs[0], emul.inputs[1])
    camd = _n(nt, 'LOOK_cam_disc', 'ShaderNodeVectorMath', (X + 1200, -600), operation='ADD')
    L.new(emul.outputs[0], camd.inputs[0])
    L.new(dsc.outputs[0], camd.inputs[1])
    # sky as a light: tinted toward teal and scaled per shot (look_fill) so shadows hold detail
    # ... plus a warm boost from the low sky on the sun side (the orange horizon is a light
    # source at golden hour: it warms whatever faces the sun line, shade stays cool)
    sunvec = nt.nodes['SunVec']
    wdot = _n(nt, 'LOOK_w_dot', 'ShaderNodeVectorMath', (X + 200, 200), operation='DOT_PRODUCT')
    L.new(tc.outputs['Generated'], wdot.inputs[0])
    L.new(sunvec.outputs[0], wdot.inputs[1])
    # half-lambert lobe: full toward the sun, a quarter at 90 degrees, none at the anti-sun
    wpos = _n(nt, 'LOOK_w_pos', 'ShaderNodeMath', (X + 400, 200), operation='MULTIPLY_ADD')
    L.new(wdot.outputs['Value'], wpos.inputs[0])
    wpos.inputs[1].default_value = 0.5
    wpos.inputs[2].default_value = 0.5
    wpow = _n(nt, 'LOOK_w_pow', 'ShaderNodeMath', (X + 600, 200), operation='POWER')
    wpow.inputs[1].default_value = 2.0
    L.new(wpos.outputs[0], wpow.inputs[0])
    whz = _n(nt, 'LOOK_w_hz', 'ShaderNodeMapRange', (X + 400, 0), interpolation_type='SMOOTHSTEP')
    whz.inputs['From Min'].default_value = 0.35
    whz.inputs['From Max'].default_value = 0.0
    L.new(sep.outputs['Z'], whz.inputs['Value'])
    wm = _n(nt, 'LOOK_w_m', 'ShaderNodeMath', (X + 800, 200), operation='MULTIPLY')
    L.new(wpow.outputs[0], wm.inputs[0])
    L.new(whz.outputs[0], wm.inputs[1])
    wv = _ctrl_value(nt, 'LOOK_warmsky_v', 'look_warmsky', (X + 800, 350))
    wm2 = _n(nt, 'LOOK_w_m2', 'ShaderNodeMath', (X + 1000, 200), operation='MULTIPLY')
    L.new(wm.outputs[0], wm2.inputs[0])
    L.new(wv.outputs[0], wm2.inputs[1])
    wcol = _n(nt, 'LOOK_w_col', 'ShaderNodeVectorMath', (X + 1000, 0), operation='SCALE')
    wcol.inputs[0].default_value = (1.2, 0.62, 0.28)
    L.new(wm2.outputs[0], wcol.inputs['Scale'])
    wsum = _n(nt, 'LOOK_w_sum', 'ShaderNodeVectorMath', (X + 1100, -100), operation='ADD')
    wsum.inputs[0].default_value = (0.86, 1.0, 1.12)
    L.new(wcol.outputs[0], wsum.inputs[1])
    fill = _n(nt, 'LOOK_fill_tint', 'ShaderNodeVectorMath', (X + 800, -300), operation='MULTIPLY')
    L.new(over.outputs['Result'], fill.inputs[0])
    L.new(wsum.outputs[0], fill.inputs[1])
    fillv = _ctrl_value(nt, 'LOOK_fill_v', 'look_fill', (X + 800, -450))
    fills = _n(nt, 'LOOK_fill_scale', 'ShaderNodeVectorMath', (X + 1000, -300), operation='SCALE')
    L.new(fill.outputs[0], fills.inputs[0])
    L.new(fillv.outputs[0], fills.inputs['Scale'])
    lp = _n(nt, 'LOOK_lp', 'ShaderNodeLightPath', (X + 800, 200))
    mg = _n(nt, 'LOOK_mix_glossy', 'ShaderNodeMix', (X + 1200, -300), data_type='RGBA')
    L.new(lp.outputs['Is Glossy Ray'], mg.inputs['Factor'])
    L.new(fills.outputs[0], mg.inputs[6])
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


# ------------------------------------------------------------------ hero rig
# 1) cool sky fill on the camera-facing side: one sun lamp per shot camera, parented to it,
#    tilted to come from above, light-linked to HERO, live only while its camera is.
FILL = {'s1': 0.0, 's2': 0.9, 's3': 1.2, 's4': 0.5, 's5': 2.2, 's6': 0.15}
FILL_COLOR = (0.48, 0.72, 1.0)
FILL_TILT = -0.45   # radians about the camera X axis (negative = from above)
# 2) gold sun kicker, one per shot, parented to the shot camera like the fills, so its
#    direction is FIXED in camera space for the whole shot (no orbiting, no steps). Its side is
#    the screen direction from the hero to the sun at the shot's reference frame (or the sun's
#    camera-space side when it is behind the lens), cheated to RIM_PHI off the lens axis
#    (three-quarter back). Light-linked to HERO and shadowed by him only. Irradiance in W/m^2.
RIM = {'s1': 0.0, 's2': 20.0, 's3': 14.0, 's4': 20.0, 's5': 25.0, 's6': 20.0}
RIM_REF = {'s2': 90, 's3': 130, 's4': 180, 's5': 244, 's6': 276}
RIM_PHI = math.radians(115.0)
RIM_S6_FADE = [(296, 20.0), (318, 4.0), (335, 0.0)]   # LINEAR fade on the pull-back
RIM_COLOR = (1.0, 0.56, 0.22)
# 3) warm bounce thrown up off the sunlit avenue onto the hero's underside (area light,
#    follows the chest, light-linked to HERO)
BOUNCE = [(0, 0.0), (143, 0.0), (144, 90.0), (215, 90.0), (216, 220.0), (263, 220.0), (264, 0.0),
          (335, 0.0)]
BOUNCE_COLOR = (1.0, 0.58, 0.30)


def _key_energy(ld, keys):
    if ld.animation_data:
        ld.animation_data_clear()
    for f, e in keys:
        ld.energy = e
        ld.keyframe_insert('energy', frame=f)
    K.set_interp(ld, 'CONSTANT')


def _link_hero(ob, hero, block=True):
    try:
        ob.light_linking.receiver_collection = hero
        if block:
            ob.light_linking.blocker_collection = hero
    except Exception as e:
        K.log('light linking failed', e)


def hero_rig(scene):
    hero = bpy.data.collections.get('HERO')
    rig = bpy.data.objects.get('HERO_RIG')
    if hero is None:
        return
    # cool fill per camera
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
        ob = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(ob)
        ob.parent = cam
        ob.location = (0, 0, 0)
        ob.rotation_euler = (FILL_TILT, 0.0, 0.0)
        ob.visible_camera = False
        ob.visible_glossy = False
        _link_hero(ob, hero)
        e = FILL[sid]
        keys = {0: 0.0, 335: 0.0}
        keys.update({a - 1: 0.0, b + 1: 0.0})
        keys.update({a: e, b: e})
        _key_energy(ld, [(f, v) for f, v in sorted(keys.items()) if 0 <= f <= 335])
    # gold sun kicker per shot (camera-parented, fixed direction per shot)
    import mathutils
    sunob = bpy.data.objects.get('SUN')
    f0 = scene.frame_current
    for sid, (a, b) in K.SHOTS.items():
        if RIM.get(sid, 0.0) <= 0.0:
            continue
        cam = None
        for m in scene.timeline_markers:
            if m.frame == a and m.camera is not None:
                cam = m.camera
        if cam is None:
            continue
        fr = RIM_REF.get(sid, (a + b) // 2)
        scene.frame_set(fr)
        M = cam.matrix_world.to_3x3().normalized()
        cpos = cam.matrix_world.translation
        sw = (sunob.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))) if sunob else \
            mathutils.Vector(lighting.sun_vector(0.0))
        sc = M.transposed() @ sw.normalized()
        hp = None
        if rig is not None and rig.type == 'ARMATURE' and 'spine03' in rig.pose.bones:
            hp = rig.matrix_world @ rig.pose.bones['spine03'].head
        hs = mathutils.Vector((0.0, 0.0))
        if hp is not None:
            hc = M.transposed() @ (hp - cpos)
            if hc.z < -1e-3:
                hs = mathutils.Vector((hc.x / -hc.z, hc.y / -hc.z))
        if sc.z < -0.05:   # sun in front of the lens: screen direction hero -> sun
            ss = mathutils.Vector((sc.x / -sc.z, sc.y / -sc.z))
            d = ss - hs
        else:              # sun behind or beside the lens: its camera-space side
            d = mathutils.Vector((sc.x, sc.y))
        if d.length < 1e-4:
            d = mathutils.Vector((1.0, 0.0))
        d.normalize()
        src = mathutils.Vector((d.x * math.sin(RIM_PHI), d.y * math.sin(RIM_PHI), math.cos(RIM_PHI)))
        K.log('kicker %s ref f%d sun_cam (%.2f %.2f %.2f) hero_scr (%.2f %.2f) side %.0f deg' % (
            sid, fr, sc.x, sc.y, sc.z, hs.x, hs.y, math.degrees(math.atan2(d.y, d.x))))
        name = 'LOOK_rim_' + sid
        ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'SUN')
        ld.color = RIM_COLOR
        ld.angle = math.radians(2.0)
        ob = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(ob)
        ob.parent = cam
        ob.location = (0, 0, 0)
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = src.to_track_quat('Z', 'Y')
        ob.visible_camera = False
        ob.visible_glossy = False
        _link_hero(ob, hero)
        e = RIM[sid]
        keys = {0: 0.0, 335: 0.0}
        keys.update({a - 1: 0.0, b + 1: 0.0})
        keys.update({a: e, b: e})
        if sid == 's6':
            keys.update(dict(RIM_S6_FADE))
        _key_energy(ld, [(f, v) for f, v in sorted(keys.items()) if 0 <= f <= 335])
        if sid == 's6':
            for fc in K.fcurves(ld):
                for kp in fc.keyframe_points:
                    if int(round(kp.co[0])) >= 296:
                        kp.interpolation = 'LINEAR'
                # the key at 296 must ramp into 318
    scene.frame_set(f0)
    # warm canyon bounce
    if rig is not None:
        ld = bpy.data.lights.get('LOOK_hero_bounce') or bpy.data.lights.new('LOOK_hero_bounce', 'AREA')
        ld.shape = 'DISK'
        ld.size = 5.0
        ld.color = BOUNCE_COLOR
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
        _link_hero(ob, hero, block=False)
        _key_energy(ld, BOUNCE)


# ------------------------------------------------------------------ compositor
GRADE = dict(
    view='AgX - Punchy',
    hl_sat=1.18, mid_sat=1.06, sh_sat=1.0,
    offset=(0.0003, 0.0005, 0.0011), power=(1.03, 1.0, 0.98), slope=(1.05, 1.0, 0.94),
    clamp=100.0, teal=(0.72, 0.98, 1.22), teal_knee=0.20,
)
# shadow-teal amount per shot
TEAL_KEYS = [(0, 0.6), (47, 0.6), (48, 0.5), (95, 0.5), (96, 0.42), (143, 0.42), (144, 0.42),
             (215, 0.42), (216, 0.0), (263, 0.0), (264, 0.40), (318, 0.40), (335, 0.45)]
# optics per shot: (frame, bloom, streak, ghost). Bloom is fed from a CLAMPED source (BLOOM_CLAMP)
# so the sun disc does not carry the veil (it used to collapse when the disc left the frame).
# No ghosts in s6: they mirror the sun through the frame centre, where the apex hero is.
OPTICS = [(0, 0.55, 0.06, 0.03), (47, 0.55, 0.06, 0.03), (48, 0.15, 0.05, 0.03), (95, 0.15, 0.05, 0.03),
          (96, 0.26, 0.05, 0.03), (215, 0.26, 0.05, 0.03), (216, 0.24, 0.05, 0.03), (263, 0.24, 0.05, 0.03),
          (264, 0.24, 0.03, 0.0), (296, 0.24, 0.03, 0.0), (318, 0.22, 0.04, 0.0), (335, 0.24, 0.03, 0.0)]
# bloom threshold (scene-linear): s1 lower (broad sky halo carries the glow), s2 high (only the
# hot core of the sky slot blooms, the hero's head stays clean), low on the end plate so the
# window cores get a small warm halation
BLOOM_THRESH = [(0, 1.1), (47, 1.1), (48, 3.0), (95, 3.0), (96, 1.6), (300, 1.6), (335, 0.55)]
BLOOM_CLAMP = 30.0
# depth-graded aerial perspective, end plate only: near roofs darker and cooler, a haze step
# lifting the far city and fading it toward the local average beyond ~4 km (amount keyed; 0
# elsewhere). The depth pass is cleaned first (morphological opening + blur): it holds one
# sample per pixel and is salt-and-pepper under volumes.
DEPTH_KEYS = [(0, 0.0), (300, 0.0), (318, 0.25), (335, 1.0)]
# warm-highlight amount per shot (luma-masked multiply toward amber)
WARM_KEYS = [(0, 0.15), (47, 0.15), (48, 0.10), (95, 0.10), (96, 0.6), (143, 0.6), (144, 0.5),
             (215, 0.5), (216, 0.35), (263, 0.35), (264, 0.12), (318, 0.10), (335, 0.0)]


def _setin(n, names, val):
    """Set the first matching input socket (5.x) or attribute (older API)."""
    for nm in names:
        s = n.inputs.get(nm)
        if s is not None:
            try:
                s.default_value = val
                return True
            except Exception:
                pass
        if hasattr(n, nm):
            try:
                setattr(n, nm, val)
                return True
            except Exception:
                pass
    return False


def _setmenu(n, names, choices):
    for nm in names:
        s = n.inputs.get(nm)
        tgt = (s, 'default_value') if s is not None else ((n, nm) if hasattr(n, nm) else None)
        if tgt is None:
            continue
        for c in choices:
            try:
                setattr(tgt[0], tgt[1], c)
                return c
            except Exception:
                continue
    return None


def _morph(ng, name, src, size):
    """Dilate (size > 0, max) or erode (size < 0, min) a float, step mode."""
    n = ng.nodes.new('CompositorNodeDilateErode')
    n.name = name
    m = _setmenu(n, ['Type', 'mode'], ['Step', 'STEP', 'Steps'])
    ok = _setin(n, ['Size', 'Distance', 'distance'], int(size))
    if not ok:
        _setin(n, ['Size', 'Distance', 'distance'], float(size))
    ng.links.new(src, n.inputs[0])
    K.log('dilate/erode', name, 'mode', m, 'size ok', ok, [s.name for s in n.inputs])
    return n.outputs[0]


def _blur(ng, name, src, px):
    n = ng.nodes.new('CompositorNodeBlur')
    n.name = name
    _setmenu(n, ['Type', 'filter_type'], ['Gaussian', 'GAUSS', 'Fast Gaussian', 'FAST_GAUSS'])
    ok = _setin(n, ['Size'], (float(px), float(px)))
    if not ok:
        ok = _setin(n, ['Size'], float(px)) or (_setin(n, ['size_x'], int(px)) and _setin(n, ['size_y'], int(px)))
    ng.links.new(src, n.inputs[0])
    K.log('blur', name, 'size ok', ok, [s.name for s in n.inputs])
    return n.outputs[0]


def _cc_range(n, rng, **kw):
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


def _key_socket(ng, node, sock_name, keys, interp='LINEAR'):
    idx = [i for i, s in enumerate(node.inputs) if s.name == sock_name][0]
    path = f'nodes["{node.name}"].inputs[{idx}].default_value'
    for f, v in keys:
        node.inputs[idx].default_value = v
        ng.keyframe_insert(path, frame=f)


def compositor(scene, g=None):
    """rl -> bloom -> + clamped-source tapered anamorphic streak + ghosts -> shadow teal (luma
    masked, keyed) -> CDL warm top -> per-range saturation -> out."""
    g = dict(GRADE, **(g or {}))
    K.view(scene, g['view'])
    ng, rl, out = K.new_compositor(scene)
    L = ng.links
    bloom = K.glare(ng, 'LOOK_bloom', Type='Bloom', Quality='High', Threshold=1.6, Smoothness=0.5,
                    Strength=0.28, Size=0.66, Saturation=1.1)
    bc = BLOOM_CLAMP
    bclamp = _mix(ng, 'LOOK_bloom_clamp', 'DARKEN', 1.0, rl.outputs['Image'], (bc, bc, bc, 1.0))
    L.new(bclamp.outputs['Result'], bloom.inputs['Image'])
    cl = g['clamp']
    clamp = _mix(ng, 'LOOK_clamp', 'DARKEN', 1.0, rl.outputs['Image'], (cl, cl, cl, 1.0))
    # low Fade: each pass attenuates, so the streak tapers to nothing instead of ending in a bar
    streak = K.glare(ng, 'LOOK_streak', Type='Streaks', Quality='High', Threshold=8.0, Smoothness=0.5,
                     Strength=0.06, Streaks=2, **{'Streaks Angle': 0.0}, Fade=0.90, Iterations=5,
                     Saturation=0.9, Tint=(0.62, 0.80, 1.0, 1.0))
    ghost = K.glare(ng, 'LOOK_ghost', Type='Ghosts', Quality='High', Threshold=6.0, Smoothness=0.5,
                    Strength=0.05, Iterations=3, **{'Color Modulation': 0.5})
    L.new(clamp.outputs['Result'], streak.inputs['Image'])
    L.new(clamp.outputs['Result'], ghost.inputs['Image'])
    _key_socket(ng, bloom, 'Strength', [(f, b) for f, b, s, h in OPTICS])
    _key_socket(ng, streak, 'Strength', [(f, s) for f, b, s, h in OPTICS])
    _key_socket(ng, ghost, 'Strength', [(f, h) for f, b, s, h in OPTICS])
    _key_socket(ng, bloom, 'Threshold', BLOOM_THRESH)
    add0 = _mix(ng, 'LOOK_add_bloom', 'ADD', 1.0, rl.outputs['Image'], bloom.outputs['Glare'])
    add1 = _mix(ng, 'LOOK_add_streak', 'ADD', 1.0, add0.outputs['Result'], streak.outputs['Glare'])
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
    # depth steps (end plate): near = darker/cooler, far city (not sky) = lifted toward haze
    # clean depth: cap the sky, opening (erode then dilate) removes the one-sample salt of
    # escaped rays inside near surfaces, then a small blur so the keys cannot switch per pixel
    dcap = _math(ng, 'LOOK_d_cap', 'MINIMUM', rl.outputs['Depth'], 60000.0)
    d = dcap.outputs[0]
    try:
        # closing (removes near 'pepper' in the sky), then opening (removes far 'salt')
        d = _morph(ng, 'LOOK_d_close_d', d, 2)
        d = _morph(ng, 'LOOK_d_close_e', d, -2)
        d = _morph(ng, 'LOOK_d_open_e', d, -2)
        d = _morph(ng, 'LOOK_d_open_d', d, 2)
        d = _blur(ng, 'LOOK_d_blur', d, 3)
    except Exception as e:
        K.log('depth clean failed, using capped raw depth', e)
        d = dcap.outputs[0]
    near = ng.nodes.new('ShaderNodeMapRange')
    near.name = 'LOOK_d_near'
    near.clamp = True
    L.new(d, near.inputs['Value'])
    near.inputs['From Min'].default_value = 250.0
    near.inputs['From Max'].default_value = 900.0
    near.inputs['To Min'].default_value = 1.0
    near.inputs['To Max'].default_value = 0.0
    far = ng.nodes.new('ShaderNodeMapRange')
    far.name = 'LOOK_d_far'
    far.clamp = True
    L.new(d, far.inputs['Value'])
    far.inputs['From Min'].default_value = 1500.0
    far.inputs['From Max'].default_value = 7000.0
    notsky = _math(ng, 'LOOK_d_notsky', 'LESS_THAN', d, 50000.0)
    farm = _math(ng, 'LOOK_d_farm', 'MULTIPLY', far.outputs[0], notsky.outputs[0])
    damt = _math(ng, 'LOOK_d_amt', 'MULTIPLY', 1.0, 1.0)
    for f, v in DEPTH_KEYS:
        damt.inputs[0].default_value = v
        ng.keyframe_insert(f'nodes["{damt.name}"].inputs[0].default_value', frame=f)
    nk = _math(ng, 'LOOK_d_nk', 'MULTIPLY', near.outputs[0], damt.outputs[0])
    nk2 = _math(ng, 'LOOK_d_nk2', 'MULTIPLY', nk.outputs[0], 0.5)
    fk = _math(ng, 'LOOK_d_fk', 'MULTIPLY', farm.outputs[0], damt.outputs[0])
    fk2 = _math(ng, 'LOOK_d_fk2', 'MULTIPLY', fk.outputs[0], 0.10)
    dnear = _mix(ng, 'LOOK_d_neardark', 'MULTIPLY', nk2.outputs[0], tint.outputs['Result'],
                 (0.55, 0.66, 0.95, 1.0))
    # far field (beyond ~4 km): fade toward the local average so single-pixel lights dissolve
    # into the dusk band instead of reading as a dot matrix
    ff = ng.nodes.new('ShaderNodeMapRange')
    ff.name = 'LOOK_d_ff'
    ff.clamp = True
    L.new(d, ff.inputs['Value'])
    ff.inputs['From Min'].default_value = 4000.0
    ff.inputs['From Max'].default_value = 10000.0
    ff.inputs['To Min'].default_value = 0.0
    ff.inputs['To Max'].default_value = 0.7
    ffm = _math(ng, 'LOOK_d_ffm', 'MULTIPLY', ff.outputs[0], notsky.outputs[0])
    ffk = _math(ng, 'LOOK_d_ffk', 'MULTIPLY', ffm.outputs[0], damt.outputs[0])
    try:
        avg = _blur(ng, 'LOOK_d_avg', dnear.outputs['Result'], 9)
        dfade = _mix(ng, 'LOOK_d_fade', 'MIX', ffk.outputs[0], dnear.outputs['Result'], avg)
        dsrc = dfade.outputs['Result']
    except Exception as e:
        K.log('far fade failed', e)
        dsrc = dnear.outputs['Result']
    dfar = _mix(ng, 'LOOK_d_farhaze', 'ADD', fk2.outputs[0], dsrc, (0.95, 0.56, 0.48, 1.0))
    # warm highlights (sun-lit stone), keyed per shot: strongest on the dive so the low sun
    # reads on the piers against the cool shadow glass
    hm = ng.nodes.new('ShaderNodeMapRange')
    hm.name = 'LOOK_hl_mask'
    hm.clamp = True
    L.new(lum.outputs[0], hm.inputs['Value'])
    # (scene-linear, before the view exposure: the canyon shots sit ~1.5 stops up in the view)
    hm.inputs['From Min'].default_value = 0.012
    hm.inputs['From Max'].default_value = 0.10
    hamt = _math(ng, 'LOOK_hl_amt', 'MULTIPLY', hm.outputs[0], 0.0)
    for f, v in WARM_KEYS:
        hamt.inputs[1].default_value = v
        ng.keyframe_insert(f'nodes["{hamt.name}"].inputs[1].default_value', frame=f)
    dwarm = _mix(ng, 'LOOK_hl_warm', 'MULTIPLY', hamt.outputs[0], dfar.outputs['Result'],
                 (1.34, 0.95, 0.62, 1.0))
    split = K.cdl(ng, 'LOOK_cdl', offset=g['offset'], power=g['power'], slope=g['slope'])
    cc = ng.nodes.new('CompositorNodeColorCorrection')
    cc.name = 'LOOK_cc'
    _cc_range(cc, 'Highlights', Saturation=g['hl_sat'])
    _cc_range(cc, 'Midtones', Saturation=g['mid_sat'])
    _cc_range(cc, 'Shadows', Saturation=g['sh_sat'])
    L.new(dwarm.outputs['Result'], split.inputs['Image'])
    L.new(split.outputs['Image'], cc.inputs['Image'])
    L.new(cc.outputs['Image'], out.inputs[0])
    K.set_interp(ng, 'LINEAR')
    for i, n in enumerate(ng.nodes):
        if n.name.startswith('LOOK_'):
            n.location = (-600 + 160 * (i % 12), 300 - 220 * (i // 12))


# ------------------------------------------------------------------ FILM fixes (owner: FILM)
# sun bloom from the UNCLAMPED image, very high threshold so only the disc glows (apex reads
# as a sun again without veiling the hero); keyed per shot
SUNGLOW = [(0, 0.0), (263, 0.0), (264, 0.22), (300, 0.22), (318, 0.0), (335, 0.0)]
# the sun lamp's specular glint on the water reads as a second sun on the pull-back
GLOSSY_SUN_OFF_FROM = 300
# haze boxes end at +-15 km: that edge drew a visible line at the horizon on the opener
HAZE_XY_SCALE = 1.0   # tested 4x and 40x: both drew a hard bright horizon band, so left at the shipped size


def film_fixes(scene):
    for name in ('ATMO_haze_box', 'ATMO_haze_low_box'):
        ob = bpy.data.objects.get(name)
        if ob:
            ob.scale = (HAZE_XY_SCALE, HAZE_XY_SCALE, 1.0)
    sun = bpy.data.objects.get('SUN')
    if sun is not None:
        try:
            for fc in K.fcurves(sun):
                if fc.data_path == 'visible_glossy':
                    K._remove_fcurve(sun, fc)
            for f, v in ((0, True), (GLOSSY_SUN_OFF_FROM - 1, True), (GLOSSY_SUN_OFF_FROM, False)):
                sun.visible_glossy = v
                sun.keyframe_insert('visible_glossy', frame=f)
            for fc in K.fcurves(sun):
                if fc.data_path == 'visible_glossy':
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
        except Exception as e:  # noqa
            K.log('visible_glossy not keyable:', e)


def sun_glow(scene):
    ng = scene.compositing_node_group
    out = [n for n in ng.nodes if n.type == 'GROUP_OUTPUT'][0]
    rl = [n for n in ng.nodes if n.type == 'R_LAYERS'][0]
    src = out.inputs[0].links[0].from_socket
    glow = K.glare(ng, 'LOOK_sunglow', Type='Bloom', Quality='High', Threshold=40.0, Smoothness=0.5,
                   Strength=0.0, Size=0.85, Saturation=1.0)
    ng.links.new(rl.outputs['Image'], glow.inputs['Image'])
    _key_socket(ng, glow, 'Strength', SUNGLOW)
    add = _mix(ng, 'LOOK_add_sunglow', 'ADD', 1.0, src, glow.outputs['Glare'])
    ng.links.new(add.outputs['Result'], out.inputs[0])
    K.set_interp(ng, 'LINEAR')


def apply(scene):
    K.remove_look_objects()
    film_fixes(scene)
    key_lighting(scene)
    haze(scene)
    world(scene)
    materials(scene)
    hero_rig(scene)
    compositor(scene)
    sun_glow(scene)
    lighting.touch(scene)
