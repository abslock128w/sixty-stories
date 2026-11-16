"""Horizon treatment: far shores across the rivers with low-rise silhouettes and a few
distant towers, all shader-windowed and merged into a handful of meshes."""
import math
import random

import materials as MAT
import buildings as BD
from cutil import MB, new_object

REGIONS = [
    # (x0, x1, y0, y1, density, tall_prob)
    (-5200, 5200, 2350, 5200, 0.55, 0.02),     # north shore
    (-5200, -2350, -4200, 2350, 0.5, 0.015),   # west shore
    (2350, 5200, -4200, 2350, 0.5, 0.03),      # east shore
    (-5200, 5200, -5200, -2900, 0.4, 0.01),    # south
    (-9000, 9000, 5200, 11000, 0.12, 0.004),   # far north hinterland (dissolves into haze)
]


def build_horizon(cols, seed=91):
    rng = random.Random(seed)
    col = cols['far']
    land = MB()
    for ri, (x0, x1, y0, y1, dens, tall) in enumerate(REGIONS):
        land.box(x0, x1, y0, y1, -3.0, 0.4, 0, skip=('-z',))
        mb = MB(attrs=('bcol', 'bprm'))
        bx = x0
        while bx < x1:
            bw = rng.uniform(70, 140)
            by = y0
            while by < y1:
                bd = rng.uniform(60, 110)
                # distance from the island fades density a bit
                for _ in range(rng.randint(1, 4)):
                    if rng.random() > dens:
                        continue
                    w = rng.uniform(15, min(60, bw - 10))
                    d = rng.uniform(15, min(50, bd - 10))
                    px = rng.uniform(bx + 5, bx + bw - 5 - w)
                    py = rng.uniform(by + 5, by + bd - 5 - d)
                    h = rng.uniform(6, 30) * math.exp(rng.gauss(0, 0.35))
                    if rng.random() < tall * 2.5:
                        h = rng.uniform(50, 190)
                    spec = dict(style=rng.choice(['prewar', 'prewar', 'slab', 'glass' if h > 50 else 'slab']),
                                seed=rng.randrange(1 << 30))
                    bcol, bprm = BD.far_attrs(spec, random.Random(spec['seed']))
                    A = {'bcol': bcol, 'bprm': bprm}
                    mb.prism(BD.rect(px, px + w, py, py + d), 0.3, 0.4 + h, 1, top=True, attrs=A, side_mat=0)
                    if h > 35:   # setback tiers / crowns so far towers have silhouettes
                        zc, ww, dd = 0.4 + h, w, d
                        for t in range(rng.randint(1, 3)):
                            ww *= rng.uniform(0.55, 0.8)
                            dd *= rng.uniform(0.55, 0.8)
                            th = h * rng.uniform(0.08, 0.25)
                            cx, cy = px + w / 2, py + d / 2
                            mb.prism(BD.rect(cx - ww / 2, cx + ww / 2, cy - dd / 2, cy + dd / 2), zc, zc + th, 1, top=True,
                                     attrs=A, side_mat=0)
                            zc += th
                        if rng.random() < 0.3:
                            cx, cy = px + w / 2, py + d / 2
                            mb.prism(BD.rect(cx - 0.6, cx + 0.6, cy - 0.6, cy + 0.6), zc, zc + h * 0.3, 1, top=True, attrs=A, side_mat=1)
                by += bd
            bx += bw
        new_object(f"HORIZON_{ri}", mb.build(f"HORIZON_{ri}", BD.far_mats()), col)
    # land continues to the horizon on the sun side so the water never meets the sky in a hard band
    land.box(-30000, 30000, 11000, 30000, -3.0, 0.4, 0, skip=('-z',))
    new_object("HORIZON_land", land.build("HORIZON_land", [MAT.get('roof')]), col)
