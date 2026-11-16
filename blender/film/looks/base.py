"""base: the approved v1 look (the Vesper v1 render): shipped city presets per shot with
per-shot exposure offsets, AgX Medium High Contrast, gentle bloom + faint horizontal streak.
No grade, no material overrides, no extra lights."""
import lookkit as K

LIGHT = [
    (0, 'aerial', 0.0, 0.0), (47, 'aerial', 0.0, 0.1),
    (48, 'closeup', 0.0, 0.0), (95, 'closeup', 0.0, 0.0),
    (96, 'canyon', 0.0, -0.7), (120, 'canyon', 0.0, -0.5), (143, 'canyon', 0.0, -0.3),
    (144, 'canyon', 0.0, 0.0), (215, 'canyon', 0.0, 0.0),
    (216, 'canyon', 0.0, -1.6), (248, 'canyon', 0.0, -1.8), (252, 'canyon', 0.0, -2.2),
    (263, 'canyon', 0.0, -2.5),
    (264, 'closeup', 0.15, 0.0), (296, 'closeup', 0.3, 0.0), (318, 'aerial', 0.6, 0.3),
    (335, 'dusk_wide', 0.9, 0.0),
]


def apply(scene):
    K.remove_look_objects()
    K.key_light(scene, LIGHT)
    K.haze_anisotropy(0.65)
    K.view(scene, 'AgX - Medium High Contrast')
    ng, rl, out = K.new_compositor(scene)
    bloom = K.glare(ng, 'BLOOM', Type='Bloom', Quality='High', Threshold=1.2, Smoothness=0.6,
                    Strength=0.22, Size=0.55, Saturation=1.0)
    streak = K.glare(ng, 'STREAK', Type='Streaks', Quality='High', Threshold=6.0, Smoothness=0.4,
                     Strength=0.10, Streaks=2, **{'Streaks Angle': 0.0}, Fade=0.93, Saturation=0.8)
    K.chain(ng, rl.outputs['Image'], [bloom, streak], out.inputs[0])
