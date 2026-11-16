"""Per-shot render settings (looks live in blender/film/looks/<name>.py).

samples / threshold: Cycles samples and adaptive noise threshold for the final render
subsurf:  HERO_body Subdivision render level
"""

# the look module applied by build_film.py as its last step: blender/film/looks/<LOOK>.py
LOOK = 'incumbent'

# look-neutral lighting keys in the plate (frame, lighting preset, dusk); looks re-key all
NEUTRAL_LIGHT = [(0, 'aerial', 0.0), (47, 'aerial', 0.0), (48, 'closeup', 0.0), (95, 'closeup', 0.0),
                 (96, 'canyon', 0.0), (215, 'canyon', 0.0), (216, 'canyon', 0.0), (263, 'canyon', 0.0),
                 (264, 'closeup', 0.15), (296, 'closeup', 0.3), (318, 'aerial', 0.6),
                 (335, 'dusk_wide', 0.9)]

# Cycles settings applied to every shot (light-path trimming measured in bench.py: ~2x faster
# than the city defaults with no visible loss in these shots)
CYCLES = dict(diffuse_bounces=1, glossy_bounces=2, transmission_bounces=2, volume_bounces=0,
              max_bounces=4, transparent_max_bounces=8)

# per-shot final render quality
SHOT = {
    's1': dict(samples=16, threshold=0.04, subsurf=1, volume_step=4.0),
    's2': dict(samples=20, threshold=0.03, subsurf=2, volume_step=4.0),
    's3': dict(samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's4': dict(samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's5': dict(samples=20, threshold=0.025, subsurf=1, volume_step=4.0),
    's6': dict(samples=16, threshold=0.04, subsurf=1, volume_step=4.0),
}
