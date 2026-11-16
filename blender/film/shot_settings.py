"""Per-shot look + render settings: the one table both build_film.py and render_frames.py read.

exposure: stops added on top of lighting.dusk_values()['exposure'] (keyed on LIGHT_CTRL)
mul:      multipliers on LIGHT_CTRL values (e.g. haze_density) keyed for the shot
samples / threshold: Cycles samples and adaptive noise threshold for the final render
subsurf:  HERO_body Subdivision render level
"""

LOOK = 'AgX - High Contrast'

COMP = dict(bloom_threshold=1.0, bloom_strength=0.35, bloom_size=0.6,
            streak_threshold=4.0, streak_strength=0.22, streak_fade=0.95,
            ghost_threshold=12.0, ghost_strength=0.08)

# scene-linear ASC-CDL grade before AgX: cool the shadows, warm the highs, deepen blacks
GRADE = dict(offset=(-0.006, -0.002, 0.004), power=(1.02, 1.04, 1.0), slope=(1.06, 1.0, 0.94))

# look2 base LIGHT_CTRL overrides applied at every lighting key ('name*' multiplies)
BASE_OVR = {
    'sun_g': 0.46, 'sun_b': 0.18, 'sun_strength*': 1.3,
    'haze_r': 0.72, 'haze_g': 0.84, 'haze_b': 1.0, 'haze_density*': 0.75,
    'sky_strength*': 1.3,
    'cloud_g': 0.4, 'cloud_b': 0.45, 'cloud_strength*': 1.3,
    'window_emit*': 1.6, 'street_emit*': 2.5, 'car_emit*': 3.0,
}
EV_SHIFT = -0.9          # global exposure shift of look2 (protect the sky)
SAT = 1.22               # master saturation in the grade
CONTRAST = 1.06
HAZE_ANISO = 0.82
SURFACE_OVR = {
    'asphalt': dict(rough_mul=0.22, spec=0.9, base_mul=0.6),
    'sidewalk': dict(rough_mul=0.6),
}

# Cycles settings applied to every shot (light-path trimming measured in bench.py: ~2x faster
# than the city defaults with no visible loss in these shots)
CYCLES = dict(diffuse_bounces=1, glossy_bounces=2, transmission_bounces=2, volume_bounces=0,
              max_bounces=4, transparent_max_bounces=8)

# light: list of (frame, lighting.PRESETS name, dusk, exposure offset in stops on top of the preset)
SHOT = {
    's1': dict(light=[(0, 'aerial', 0.0, 0.0), (47, 'aerial', 0.0, 0.1)],
               samples=16, threshold=0.04, subsurf=1, volume_step=4.0),
    's2': dict(light=[(48, 'closeup', 0.0, 0.0), (95, 'closeup', 0.0, 0.0)],
               samples=20, threshold=0.03, subsurf=2, volume_step=4.0),
    's3': dict(light=[(96, 'canyon', 0.0, -0.7), (120, 'canyon', 0.0, -0.5), (143, 'canyon', 0.0, -0.3)],
               samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's4': dict(light=[(144, 'canyon', 0.0, 0.0), (215, 'canyon', 0.0, 0.0)],
               samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's5': dict(light=[(216, 'canyon', 0.0, -1.6), (248, 'canyon', 0.0, -1.8), (252, 'canyon', 0.0, -2.2), (263, 'canyon', 0.0, -2.5)],
               samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's6': dict(light=[(264, 'closeup', 0.15, 0.0), (296, 'closeup', 0.3, 0.0), (318, 'aerial', 0.6, 0.3),
                      (335, 'dusk_wide', 0.9, 0.0)],
               samples=16, threshold=0.04, subsurf=1, volume_step=4.0),
}
