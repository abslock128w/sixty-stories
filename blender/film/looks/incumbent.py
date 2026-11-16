"""incumbent (look2, FILM builder): bold golden-hour blockbuster pass.
Saturated sun, cooler haze albedo (orange where the sun scatters, blue-grey away from it),
strong forward-scattering haze for defined shafts, wet glossy avenue, more city light,
1 stop lower exposure to hold the sky, AgX High Contrast, bloom + anamorphic streak + ghost
chain, ASC-CDL teal/orange grade and +22% saturation."""
import lookkit as K

BASE_OVR = {
    'sun_g': 0.46, 'sun_b': 0.18, 'sun_strength*': 1.3,
    'haze_r': 0.72, 'haze_g': 0.84, 'haze_b': 1.0, 'haze_density*': 0.75,
    'sky_strength*': 1.3,
    'cloud_g': 0.4, 'cloud_b': 0.45, 'cloud_strength*': 1.3,
    'window_emit*': 1.6, 'street_emit*': 2.5, 'car_emit*': 3.0,
}
EV_SHIFT = -0.9
LIGHT = [
    (0, 'aerial', 0.0, -0.2), (47, 'aerial', 0.0, 0.0),
    (48, 'closeup', 0.0, 0.0), (95, 'closeup', 0.0, 0.0),
    (96, 'canyon', 0.0, 0.1), (120, 'canyon', 0.0, 0.3), (143, 'canyon', 0.0, 0.6),
    (144, 'canyon', 0.0, 0.8), (176, 'canyon', 0.0, 1.1), (215, 'canyon', 0.0, 0.8),
    (216, 'canyon', 0.0, -1.2), (248, 'canyon', 0.0, -1.4), (252, 'canyon', 0.0, -1.9),
    (263, 'canyon', 0.0, -2.2),
    (264, 'closeup', 0.15, 0.0), (296, 'closeup', 0.3, 0.0), (318, 'aerial', 0.6, 0.3,
                                                              {'window_emit*': 2.4, 'car_emit*': 4.0}),
    (335, 'dusk_wide', 0.92, 0.25, {'window_emit*': 2.8, 'window_frac*': 1.5, 'street_emit*': 3.5,
                                     'car_emit*': 4.5, 'sky_strength*': 1.6}),
]
HAZE_ANISO = 0.82
# anisotropy keyed per shot (CONSTANT): softer forward glow on the aerials keeps the sky
# around the sun from going white; strong in the canyon for defined shafts
ANISO_KEYS = [(0, 0.7), (48, 0.8), (96, 0.86), (264, 0.8), (300, 0.72)]
SURFACES = {
    'asphalt': dict(rough_mul=0.22, spec=0.9, base_mul=0.6),
    'sidewalk': dict(rough_mul=0.6),
}
GRADE = dict(offset=(-0.004, 0.0, 0.014), power=(1.0, 1.0, 0.95), slope=(1.06, 1.0, 0.94))


def surfaces():
    for name, o in SURFACES.items():
        m, nodes = K.principled(name)
        for n in nodes:
            if 'rough_mul' in o:
                K.scale_input(m, n, 'Roughness', o['rough_mul'])
            if 'spec' in o:
                K.set_input(m, n, 'Specular IOR Level', o['spec'])
            if 'base_mul' in o:
                v = o['base_mul']
                K.tint_base(m, n, (v, v, v))


def key_anisotropy():
    import bpy
    for m in bpy.data.materials:
        if not (m.name.startswith('ATMO_haze') and m.node_tree):
            continue
        for n in m.node_tree.nodes:
            if n.type != 'PRINCIPLED_VOLUME':
                continue
            s = n.inputs['Anisotropy']
            path = s.path_from_id('default_value')
            try:
                m.node_tree.driver_remove(path)
            except Exception:
                pass
            for fc in K.fcurves(m.node_tree):
                if fc.data_path == path:
                    m.node_tree.animation_data.action.fcurves.remove(fc) if hasattr(
                        m.node_tree.animation_data.action, 'fcurves') else None
            for f, v in ANISO_KEYS:
                s.default_value = v
                s.keyframe_insert('default_value', frame=f)
            for fc in K.fcurves(m.node_tree):
                if fc.data_path == path:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'


def apply(scene):
    K.remove_look_objects()
    K.key_light(scene, LIGHT, base_ovr=BASE_OVR, ev_shift=EV_SHIFT)
    K.haze_anisotropy(HAZE_ANISO)
    key_anisotropy()
    surfaces()
    K.view(scene, 'AgX - High Contrast')
    ng, rl, out = K.new_compositor(scene)
    bloom = K.glare(ng, 'BLOOM', Type='Bloom', Quality='High', Threshold=1.0, Smoothness=0.6,
                    Strength=0.35, Size=0.6, Saturation=1.0)
    streak = K.glare(ng, 'STREAK', Type='Streaks', Quality='High', Threshold=4.0, Smoothness=0.4,
                     Strength=0.22, Streaks=2, **{'Streaks Angle': 0.0}, Fade=0.95, Saturation=0.8)
    ghosts = K.glare(ng, 'GHOSTS', Type='Ghosts', Quality='High', Threshold=12.0, Smoothness=0.3,
                     Strength=0.08, Iterations=3, **{'Color Modulation': 0.35}, Saturation=1.0)
    grade = K.cdl(ng, 'GRADE', **GRADE)
    sat = K.color_correction(ng, 'SAT', saturation=1.2, contrast=1.0)
    K.chain(ng, rl.outputs['Image'], [bloom, streak, ghosts, grade, sat], out.inputs[0])
