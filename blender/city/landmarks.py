"""s5 feature: twin glass towers flanking the avenue joined by two stacked skybridges."""
import math
import bpy

import materials as MAT
import layout as LY
from cutil import MB, new_object

B = LY.BRIDGE


def build_skybridges(col):
    y0, y1 = B['y'] - B['depth'] / 2, B['y'] + B['depth'] / 2
    x0, x1 = -LY.HERO_AVE_W / 2 + 0.1, LY.HERO_AVE_W / 2 - 0.1
    mb = MB(attrs=('win', 'bcol'))
    STEEL, GLASS, DECK, LIGHT, ALU = 0, 1, 2, 3, 4
    A = {'bcol': (0.2, 0.25, 0.27, 0.5)}
    for (zb, zt) in (B['low'], B['high']):
        # deck slab and roof slab with a shallow arched soffit (segments)
        mb.box(x0, x1, y0, y1, zb, zb + 0.7, DECK, attrs=A)
        mb.box(x0, x1, y0 - 0.15, y1 + 0.15, zt - 0.45, zt, ALU, attrs=A)
        # arched underside: chain of slabs dropping toward the towers (haunches)
        n = 16
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            xa, xb = x0 + (x1 - x0) * t0, x0 + (x1 - x0) * t1
            sag = (lambda t: 1.6 * (2 * t - 1) ** 4) if zb == B['low'][0] else (lambda t: 0.0)
            mb.box(xa, xb, y0 + 0.4, y1 - 0.4, zb - 0.15 - max(sag(t0), sag(t1)), zb, STEEL, attrs=A)
        # glazing both sides, one pane per 2 m
        nb = int((x1 - x0) / 2.0)
        for k in range(nb):
            xa = x0 + (x1 - x0) * k / nb
            xb = x0 + (x1 - x0) * (k + 1) / nb
            for side, yy in ((-1, y0 + 0.25), (1, y1 - 0.25)):
                p = [(xa, yy, zb + 0.7), (xb, yy, zb + 0.7), (xb, yy, zt - 0.45), (xa, yy, zt - 0.45)]
                if side > 0:
                    p = [p[1], p[0], p[3], p[2]]
                mb.poly(p, GLASS, [(0, 0), (1, 0), (1, 1), (0, 1)] if side < 0 else [(1, 0), (0, 0), (0, 1), (1, 1)],
                        {'win': (0.5 + 0.4 * math.sin(k), 0.0, 0.0, 0.35), 'bcol': A['bcol']})
            # external Vierendeel posts
            for yy in (y0 - 0.05, y1 + 0.05):
                mb.box(xa - 0.12, xa + 0.12, yy - 0.12, yy + 0.12, zb - 0.1, zt, STEEL, attrs=A)
        # diagonal bracing on the outer faces (thin slanted boxes as quads)
        for yy, s in ((y0 - 0.2, -1), (y1 + 0.2, 1)):
            for k in range(nb):
                xa = x0 + (x1 - x0) * k / nb
                xb = x0 + (x1 - x0) * (k + 1) / nb
                za, zc = (zb + 0.7, zt - 0.45) if k % 2 == 0 else (zt - 0.45, zb + 0.7)
                w = 0.09
                pts = [(xa, yy, za - w), (xb, yy, zc - w), (xb, yy, zc + w), (xa, yy, za + w)]
                if s > 0:
                    pts = pts[::-1]
                mb.poly(pts, STEEL, None, A)
        # warm light strip on the ceiling inside
        mb.quad((x0, y0 + 1.0, zt - 0.47), (x0, y1 - 1.0, zt - 0.47), (x1, y1 - 1.0, zt - 0.47), (x1, y0 + 1.0, zt - 0.47), LIGHT,
                None, A)
        # floor inside
        mb.box(x0, x1, y0 + 0.25, y1 - 0.25, zb + 0.7, zb + 0.72, ALU, attrs=A)
    me = mb.build("SKYBRIDGES", [MAT.get('steel_deco'), MAT.get('curtain'), MAT.get('concrete'), MAT.get('sign_warm'),
                                 MAT.get('metal_alu')])
    return new_object("SKYBRIDGES", me, col)


def gap_info():
    return dict(
        kind="twin_skybridges",
        description="Two glass skybridges span the avenue between twin towers; the hero threads the 14 m gap between them heading +Y.",
        y=B['y'], bridge_depth_y=B['depth'], x_span=[-LY.HERO_AVE_W / 2, LY.HERO_AVE_W / 2],
        bridge_low_z=list(B['low']), bridge_high_z=list(B['high']),
        gap_z=[B['low'][1], B['high'][0] - 0.15], gap_clear_height=B['high'][0] - 0.15 - B['low'][1], gap_width=LY.HERO_AVE_W,
        gap_center=[0.0, B['y'], (B['low'][1] + B['high'][0]) / 2], through_direction=[0.0, 1.0, 0.0],
        lowest_point_low_bridge_soffit_z=B['low'][0] - 1.75,
    )
