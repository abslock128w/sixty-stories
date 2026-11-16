"""Ground, roads, sidewalks, curbs, lane paint, crosswalks; island base + water."""
import math
import random
import bpy

import materials as MAT
import layout as LY
from cutil import MB, new_object

# hero avenue lane plan (x positions), traffic northbound (+Y)
PARK_W = (-10.0, -7.6)
LANES = [(-7.6, -4.3), (-4.3, -1.0), (-1.0, 2.3), (2.3, 5.6)]
BIKE = (5.6, 7.6)
PARK_E = (7.6, 10.0)
SIDEWALK_Z = 0.15


def lane_centres():
    return [(a + b) / 2 for a, b in LANES]


def build_ground(cols):
    col = cols['street']
    X0, X1, Y0, Y1 = LY.SHORE
    mb = MB()
    # island slab (asphalt top everywhere: streets are what is not covered by sidewalks/buildings)
    mb.box(X0, X1, Y0, Y1, -4.0, 0.0, 0, skip=('-z',))
    me = mb.build("GROUND_island", [MAT.get('asphalt')])
    new_object("GROUND_island", me, col)
    # seawall faces (concrete) slightly outside
    mb = MB()
    for (x0, x1, y0, y1) in ((X0 - 0.5, X0, Y0, Y1), (X1, X1 + 0.5, Y0, Y1), (X0, X1, Y0 - 0.5, Y0), (X0, X1, Y1, Y1 + 0.5)):
        mb.box(x0, x1, y0, y1, -4.0, 0.6, 0)
    new_object("GROUND_seawall", mb.build("GROUND_seawall", [MAT.get('concrete')]), col)
    # water
    mb = MB()
    R = 40000.0
    mb.quad((-R, -R, -1.4), (R, -R, -1.4), (R, R, -1.4), (-R, R, -1.4), 0)
    new_object("WATER", mb.build("WATER", [MAT.get('water')]), cols['atmo'])


def build_sidewalks(cols):
    """One sidewalk slab per block (block + sidewalk ring), curbs near the hero avenue."""
    col = cols['street']
    mb = MB()
    cb = MB()
    for (x0, x1, y0, y1) in LY.blocks():
        # sidewalk widths: hero avenue 6 m, cross streets 3.5 m, other avenues 4.5 m
        def sw_x(x):
            if abs(abs(x) - LY.HERO_AVE_W / 2) < 0.1:
                return LY.SIDEWALK
            return 4.5
        sx0 = x0 - (sw_x(x0) if x0 > LY.ISLAND[0] + 1 else 0)
        sx1 = x1 + (sw_x(x1) if x1 < LY.ISLAND[1] - 1 else 0)
        sy0 = y0 - (3.5 if y0 > LY.ISLAND[2] + 1 else 0)
        sy1 = y1 + (3.5 if y1 < LY.ISLAND[3] - 1 else 0)
        mb.box(sx0, sx1, sy0, sy1, -0.05, SIDEWALK_Z, 0, skip=('-z',))
        near = min(abs(sx0), abs(sx1)) < 120 and -900 < y0 < 1300
        if near:
            e = 0.012
            w = 0.32
            zt = SIDEWALK_Z + 0.006
            cb.box(sx0 - e, sx0 + w, sy0 - e, sy1 + e, -0.04, zt, 0, skip=('-z',))
            cb.box(sx1 - w, sx1 + e, sy0 - e, sy1 + e, -0.04, zt, 0, skip=('-z',))
            cb.box(sx0 + w, sx1 - w, sy0 - e, sy0 + w, -0.04, zt, 0, skip=('-z',))
            cb.box(sx0 + w, sx1 - w, sy1 - w, sy1 + e, -0.04, zt, 0, skip=('-z',))
    new_object("SIDEWALKS", mb.build("SIDEWALKS", [MAT.get('sidewalk')]), col)
    new_object("CURBS", cb.build("CURBS", [MAT.get('curb')]), col)


def build_markings(cols, rng):
    col = cols['street']
    mb = MB()
    WHITE, YELLOW, GREEN = 0, 1, 2
    z = 0.004
    sy = LY.street_ys()
    y_lo, y_hi = -1000.0, 1340.0
    inter = [(y - LY.ST_W / 2, y + LY.ST_W / 2) for y in sy]

    def in_inter(y, pad=0.0):
        return any(a - pad <= y <= b + pad for a, b in inter)

    def strip(x0, x1, y0, y1, m, zz=z):
        mb.quad((x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz), m, None)

    # segments between intersections
    bounds = [y_lo] + [v for ab in inter for v in ab] + [y_hi]
    segs = [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds) - 1, 2)]
    for (ya, yb) in segs:
        if yb - ya < 5:
            continue
        a, b = ya + 4.5, yb - 4.5   # leave room for crosswalks
        # parking lane lines + bike lane lines (solid)
        for x in (PARK_W[1], BIKE[0], BIKE[1]):
            strip(x - 0.075, x + 0.075, a, b, WHITE)
        # bike lane green
        strip(BIKE[0] + 0.08, BIKE[1] - 0.08, a, b, GREEN, z * 0.5)
        # dashed lane lines
        for x in (-4.3, -1.0, 2.3):
            y = a + 1.0
            while y + 3.0 < b - 7:
                strip(x - 0.06, x + 0.06, y, y + 3.0, WHITE)
                y += 9.0
        # stop line before the northern crosswalk (northbound traffic)
        strip(PARK_W[1], BIKE[1], b - 1.0, b - 0.5, WHITE)
        # crosswalk zebras across the avenue at both ends of the segment
        for (c0, c1) in ((ya + 0.6, ya + 4.1), (yb - 4.1, yb - 0.6)):
            x = -9.6
            while x < 9.6:
                strip(x, x + 0.6, c0, c1, WHITE)
                x += 1.2
    # crosswalks across the cross streets alongside the hero avenue sidewalks
    for y in sy:
        if not (y_lo < y < y_hi):
            continue
        for xs in (-1, 1):
            xa = xs * (LY.HERO_AVE_W / 2 + 0.6)
            xb = xs * (LY.HERO_AVE_W / 2 + 4.1)
            yy = y - LY.ST_ROAD_HALF + 0.2
            while yy < y + LY.ST_ROAD_HALF - 0.6:
                strip(min(xa, xb), max(xa, xb), yy, yy + 0.6, WHITE)
                yy += 1.2
        # cross street centre line (double yellow) near the avenue
        for xs in (-1, 1):
            x0 = xs * (LY.HERO_AVE_W / 2 + 5)
            x1 = xs * 240
            strip(min(x0, x1), max(x0, x1), y - 0.18, y - 0.06, YELLOW)
            strip(min(x0, x1), max(x0, x1), y + 0.06, y + 0.18, YELLOW)
    me = mb.build("MARKINGS", [MAT.get('paint_white'), MAT.get('paint_yellow'), MAT.get('bike_green')])
    new_object("MARKINGS", me, col)
    return segs
