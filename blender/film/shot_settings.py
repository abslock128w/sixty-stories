"""Per-shot render settings (looks live in blender/film/looks/<name>.py).

samples / threshold: Cycles samples and adaptive noise threshold for the final render
subsurf:  HERO_body Subdivision render level
"""

# master frame size (2.39:1) and the depth map delivered beside it (half size)
RES = (2560, 1072)
DEPTH_RES = (1280, 536)


def shutter(i):
    """Motion-blur shutter (fraction of a frame, opening AT the frame) per global frame:
    short on the wides so window grids stay crisp, moderate in the hero shots so blur reads
    as speed while the hero / tracked subject stays sharp."""
    if i < 48:
        return 0.1           # s1 aerial
    if 304 <= i:
        return 0.1           # s6 pull-back and end plate
    return 0.25


# the look module applied by build_film.py as its last step: blender/film/looks/<LOOK>.py
LOOK = 'final'

# look-neutral lighting keys in the plate (frame, lighting preset, dusk); looks re-key all
NEUTRAL_LIGHT = [(0, 'aerial', 0.0), (47, 'aerial', 0.0), (48, 'closeup', 0.0), (95, 'closeup', 0.0),
                 (96, 'canyon', 0.0), (215, 'canyon', 0.0), (216, 'canyon', 0.0), (263, 'canyon', 0.0),
                 (264, 'closeup', 0.15), (296, 'closeup', 0.3), (318, 'aerial', 0.6),
                 (335, 'dusk_wide', 0.9)]

# Cycles light paths: full depth (100% crops showed fuller bounce in the canyon and glass;
# time is not a constraint for the master)
CYCLES = dict(max_bounces=8, diffuse_bounces=3, glossy_bounces=4, transmission_bounces=6,
              volume_bounces=1, transparent_max_bounces=12)

# per-shot final render quality
SHOT = {
    's1': dict(samples=128, threshold=0.01, subsurf=1, volume_step=4.0),
    's2': dict(samples=160, threshold=0.008, subsurf=2, volume_step=4.0),
    's3': dict(samples=128, threshold=0.01, subsurf=1, volume_step=4.0),
    's4': dict(samples=128, threshold=0.01, subsurf=1, volume_step=4.0),
    's5': dict(samples=128, threshold=0.01, subsurf=1, volume_step=4.0),
    's6': dict(samples=128, threshold=0.01, subsurf=1, volume_step=4.0),
}
