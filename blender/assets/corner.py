"""Sixty Stories - HERO ASSET C: street corner (avenue x cross street), 20 m x 20 m patch.

Usage (any bpy session):
    import sys; sys.path.insert(0, "/home/user/sixty/blender/assets")
    import corner
    col = corner.build()                 # collection ASSET_corner (not linked to a scene)
    hyd = corner.hydrant(seed=3)         # any prop on its own -> collection, origin at its base

Frame: origin = intersection of the two curb lines (curb face at the gutter), Z up, metres.
The corner sidewalk occupies x > 0, y > 0 (curb return radius 2 m), 6 m wide on both
streets; the building quadrant x > 6, y > 6 is left empty.  Sidewalk top z = 0, gutter
z = -0.15, crowned roads.  The AVENUE runs along Y (x < 0, one-way toward -Y, 3.4 m lanes
at x = -1.7 / -5.1 / -8.5); the CROSS STREET runs along X (y < 0, one-way toward +X).

Ground pieces are real meshes built in asset space with their objects at the collection
origin (the road / marking shaders read object coordinates against the 20 m road mask
images of corner_tex.py).  Every prop is built by its own function into its own
collection (prop-local frame: base centre at the origin, "front" toward -Y) and is placed
in ASSET_corner as a collection-instance empty, so a city script can re-use the same prop
collections (or call the function again with another seed) for variation.
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corner_tex  # noqa: E402
import corner_kit as K  # noqa: E402
from corner_kit import MB, finalize, srgb  # noqa: E402
import corner_props as P  # noqa: E402
from corner_props import (hydrant, litter_bin, newspaper_box, bollard, pay_station, bike_rack, bicycle,  # noqa: E402,F401
                          electrical_pedestal, control_cabinet, signal_pole, streetlight, sign_post,
                          traffic_cone, manhole, valve_cover, storm_inlet, tree_grate, street_tree,
                          cup_flat, cigarette, leaf_litter)

ROOT = "/home/user/sixty"
EXT = 10.0
RC = 2.0          # curb return radius
CW = 0.18         # curb top width
SW = 6.0          # sidewalk width
GUT = -0.15       # gutter level
SQ = 3.3          # cast-in-place corner pour (ramp) extent
XL = [CW, 1.74, 3.3, 4.65, 6.0, 7.5, 9.0, 10.0]     # slab joint lines (both directions)
TREE_PIT = (0.40, 7.5, 1.74, 9.0)
TRENCH = (8.6, CW, 9.3, SW)
MH = (-5.0, 7.6)
VALVE = (-2.3, -2.6)
INLET = (-0.62, 7.25, -0.02, 8.15)   # grate rect in the gutter
TRUNK = (1.07, 8.25)
SQ2 = math.sqrt(2.0)


# ============================================================================ surfaces
def crown(d):
    s = np.clip(d, 0, 9.0) / 9.0
    return GUT + 0.10 * s * (2 - s)


def road_base(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    A = crown(-x)
    C = crown(-y)
    z = np.where((x < 0) & (y >= 0), A, np.where((y < 0) & (x >= 0), C, np.where((x < 0) & (y < 0), np.maximum(A, C), GUT)))
    return z


class Masks:
    def __init__(self):
        from PIL import Image
        a = np.asarray(Image.open(os.path.join(corner_tex.TEX_DIR, "road_a.png")), np.float32) / 255.0
        b = np.asarray(Image.open(os.path.join(corner_tex.TEX_DIR, "road_b.png")), np.float32) / 255.0
        f = 4
        n = a.shape[0] // f
        self.a = a.reshape(n, f, n, f, 4).mean((1, 3))
        self.b = b.reshape(n, f, n, f, 3).mean((1, 3))
        self.n = n

    def sample(self, arr, x, y, ch):
        n = self.n
        c = np.clip(((np.asarray(x) + EXT) / (2 * EXT) * n).astype(int), 0, n - 1)
        r = np.clip(((EXT - np.asarray(y)) / (2 * EXT) * n).astype(int), 0, n - 1)
        return arr[r, c, ch]


_MASKS = None


def masks():
    global _MASKS
    if _MASKS is None:
        _MASKS = Masks()
    return _MASKS


def vnoise(x, y, seed, scale):
    """Cheap smooth value noise (numpy) for vertex displacement."""
    rng = np.random.default_rng(seed)
    g = rng.random((64, 64))
    u = (np.asarray(x) / scale) % 63
    v = (np.asarray(y) / scale) % 63
    i, j = u.astype(int), v.astype(int)
    fu, fv = u - i, v - j
    fu = fu * fu * (3 - 2 * fu)
    fv = fv * fv * (3 - 2 * fv)
    a = g[i, j] * (1 - fu) + g[i + 1, j] * fu
    b = g[i, j + 1] * (1 - fu) + g[i + 1, j + 1] * fu
    return a * (1 - fv) + b * fv


def road_z(x, y):
    M = masks()
    z = road_base(x, y)
    z = z + (vnoise(x, y, 5, 1.7) - 0.5) * 0.006 + (vnoise(x, y, 6, 0.35) - 0.5) * 0.002
    z = z - 0.004 * M.sample(M.b, x, y, 1)                          # wheel-path ruts
    wet = M.sample(M.a, x, y, 2)
    z = z - 0.012 * np.clip((wet - 0.55) / 0.35, 0, 1) * (np.asarray(x) < 0.2)   # puddle hollows
    pa = M.sample(M.a, x, y, 3)
    z = z - 0.005 * (pa > 0.9) + 0.003 * ((pa > 0.3) & (pa < 0.9))                # trench sag / proud patches
    ix, iy = (INLET[0] + INLET[2]) / 2, (INLET[1] + INLET[3]) / 2
    z = z - 0.02 * np.exp(-(((np.asarray(x) - ix) / 0.45) ** 2 + ((np.asarray(y) - iy) / 0.7) ** 2))
    return z


def is_sidewalk(x, y, inset=0.0):
    """Inside the curb line (sidewalk side), optionally `inset` metres further in."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    r = np.hypot(x - RC, y - RC)
    corner = (x < RC) & (y < RC)
    return np.where(corner, r < RC - inset, (x > inset) & (y > inset))


def pour_z(x, y):
    q = (np.asarray(x) + np.asarray(y)) / SQ2
    w = np.abs(np.asarray(x) - np.asarray(y)) / SQ2
    qb = (2 * RC) / SQ2 - RC + CW     # curb back on the diagonal
    dep = 0.14 * np.clip(1 - (q - qb) / 1.75, 0, 1) - 0.10 * np.maximum(0, w - 0.75)
    return -np.maximum(0, dep)


def walk_z(x, y):
    """Top of the walking surface (pour inside the corner square, 0 elsewhere)."""
    inside = (np.asarray(x) < SQ) & (np.asarray(y) < SQ)
    return np.where(inside, pour_z(x, y), 0.0)


# ============================================================================ heightfield helper
def grid_mesh(name, col, mat, x0, y0, x1, y1, h, zfun, keep=None, project=None, skirt=0.0, attr=None):
    nx = max(2, int(round((x1 - x0) / h)) + 1)
    ny = max(2, int(round((y1 - y0) / h)) + 1)
    xs = np.linspace(x0, x1, nx)
    ys = np.linspace(y0, y1, ny)
    X, Y = np.meshgrid(xs, ys)
    moved = np.zeros_like(X, bool)
    if project is not None:
        X, Y, moved = project(X, Y)
    Z = zfun(X, Y)
    V = np.stack([X.ravel(), Y.ravel(), Z.ravel()], -1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    a = idx[:-1, :-1].ravel()
    b = idx[:-1, 1:].ravel()
    c = idx[1:, 1:].ravel()
    d = idx[1:, :-1].ravel()
    mv = moved.ravel()
    ok = ~(mv[a] & mv[b] & mv[c] & mv[d])
    if keep is not None:
        cx = (X.ravel()[a] + X.ravel()[c]) / 2
        cy = (Y.ravel()[a] + Y.ravel()[c]) / 2
        ok &= keep(cx, cy)
    F = np.stack([a, b, c, d], -1)[ok]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.003)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0005, edges=bm.edges)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if skirt > 0:
        bnd = [e for e in bm.edges if e.is_boundary]
        ret = bmesh.ops.extrude_edge_only(bm, edges=bnd)
        for v in [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]:
            v.co.z -= skirt
    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < -0.5:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    facade_uv(me)
    if attr is not None:
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        at = me.attributes.new(attr[0], 'FLOAT', 'POINT')
        at.data.foreach_set('value', attr[1](co[:, 0], co[:, 1]).astype(np.float32))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def facade_uv(me):
    import facade
    facade._box_uv(me)


# ============================================================================ polygons
def poly_area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def clip_half(poly, q, n):
    out = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da = (a[0] - q[0]) * n[0] + (a[1] - q[1]) * n[1]
        db = (b[0] - q[0]) * n[0] + (b[1] - q[1]) * n[1]
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def inset_poly(poly, d):
    n = len(poly)
    L = []
    for k in range(n):
        p0, p1 = Vector(poly[k]), Vector(poly[(k + 1) % n])
        t = (p1 - p0).normalized()
        L.append((p0 + Vector((-t.y, t.x)) * d, t))
    out = []
    for k in range(n):
        (pa, ta), (pb, tb) = L[k - 1], L[k]
        den = ta.x * tb.y - ta.y * tb.x
        if abs(den) < 1e-9:
            out.append(tuple(pb))
            continue
        s = ((pb.x - pa.x) * tb.y - (pb.y - pa.y) * tb.x) / den
        out.append(tuple(pa + ta * s))
    return out


def rect_sub(r, h):
    x0, y0, x1, y1 = r
    a0, b0, a1, b1 = h
    if a1 <= x0 or a0 >= x1 or b1 <= y0 or b0 >= y1:
        return [r]
    out = []
    if b0 > y0:
        out.append((x0, y0, x1, b0))
    if b1 < y1:
        out.append((x0, b1, x1, y1))
    yy0, yy1 = max(y0, b0), min(y1, b1)
    if a0 > x0:
        out.append((x0, yy0, a0, yy1))
    if a1 < x1:
        out.append((a1, yy0, x1, yy1))
    return [o for o in out if (o[2] - o[0]) > 0.05 and (o[3] - o[1]) > 0.05]


def prism_slab(mb, poly, zf, m, cell, ch=0.006, bot=-0.10):
    """Convex CCW poly -> slab with chamfered top edge; zf(x, y) gives the top height."""
    ins = inset_poly(poly, ch)
    n = len(poly)
    top = [mb.add_v((p[0], p[1], zf(*p))) for p in ins]
    mid = [mb.add_v((p[0], p[1], zf(*p) - ch)) for p in poly]
    low = [mb.add_v((p[0], p[1], bot)) for p in poly]
    mb.face(top, m, cell)
    for k in range(n):
        k2 = (k + 1) % n
        mb.face([mid[k], mid[k2], top[k2], top[k]], m, cell)
        mb.face([low[k], low[k2], mid[k2], mid[k]], m, cell)


# ============================================================================ ground builders
def build_road(col):
    mat = K.m_asphalt("crn_asphalt")
    mh_r, v_r = 0.56, 0.115

    def project(X, Y):
        inside = is_sidewalk(X, Y, 0.0)
        r = np.hypot(X - RC, Y - RC)
        corner = (X < RC) & (Y < RC)
        k = (RC - 0.03) / np.maximum(r, 1e-6)
        Xc = np.where(corner, RC + (X - RC) * k, np.where(X < Y, 0.03, X))
        Yc = np.where(corner, RC + (Y - RC) * k, np.where(X < Y, Y, 0.03))
        return np.where(inside, Xc, X), np.where(inside, Yc, Y), inside

    def keep(cx, cy):
        k = np.hypot(cx - MH[0], cy - MH[1]) > mh_r
        k &= np.hypot(cx - VALVE[0], cy - VALVE[1]) > v_r
        k &= ~((cx > INLET[0] + 0.04) & (cx < 0.2) & (cy > INLET[1] + 0.04) & (cy < INLET[3] - 0.04))
        return k
    return grid_mesh("crn_road", col, mat, -EXT, -EXT, EXT, EXT, 0.05, road_z, keep=keep, project=project)


def build_puddles(col):
    mat = K.m_water("crn_water")
    M = masks()
    out = []
    for (cx, cy, rx, ry) in ((-0.42, 8.55, 0.75, 0.85), (-0.30, 6.75, 0.45, 0.5)):
        xs = np.linspace(cx - rx, min(cx + rx, -0.005), 40)
        ys = np.linspace(cy - ry, cy + ry, 40)
        X, Y = np.meshgrid(xs, ys)
        wet = M.sample(M.a, X, Y, 2)
        Z = road_z(X, Y)
        sel = wet > 0.85
        if not sel.any():
            continue
        lvl = float(np.percentile(Z[sel], 70)) + 0.002
        mb = MB(f"crn_puddle_{len(out)}")
        mb.quad([(cx - rx, cy - ry, lvl), (min(cx + rx, -0.005), cy - ry, lvl), (min(cx + rx, -0.005), cy + ry, lvl), (cx - rx, cy + ry, lvl)], 'w')
        out.append(finalize(mb, col, {'w': mat}, recalc=False))
    return out


def curb_path(s):
    """Curb line: avenue (x=0, y 10->2), return arc, cross street (y=0, x 2->10).
    Returns point, tangent, outward (road side) normal."""
    if s <= 8.0:
        p, t = Vector((0, 10 - s)), Vector((0, -1))
    elif s <= 8.0 + math.pi:
        a = math.pi + (s - 8.0) / RC
        p = Vector((RC + RC * math.cos(a), RC + RC * math.sin(a)))
        t = Vector((-math.sin(a), math.cos(a)))
    else:
        p, t = Vector((2 + (s - 8.0 - math.pi), 0)), Vector((1, 0))
    return p, t, Vector((t.y, -t.x))


def curb_profile(zt, zg, chip, throat=False):
    c = chip
    P = [(0.014, -0.45), (0.006, zg - 0.06)]
    if throat:
        P += [(0.004, zg + 0.005), (-0.09, zg + 0.005), (-0.09, zg + 0.115), (0.0, zg + 0.115)]
    P += [(0.0, zt - 0.022 - c * 0.7), (-0.003 - c, zt - 0.008 - c), (-0.012 - c * 0.8, zt - 0.006 - c * 0.5),
          (-0.024 - c * 0.3, zt - 0.004), (-0.165, zt), (-0.176, zt - 0.008), (-CW, zt - 0.02), (-CW - 0.004, -0.45)]
    return P


def build_curb(col):
    gran = K.m_granite("crn_granite")
    conc = K.m_granite("crn_curb_concrete", col=(168, 164, 156), concrete=True)
    iron = K.m_iron("crn_iron_hood", rust=0.7)
    L1, L2 = 8.0, 8.0 + math.pi
    xs = lambda x: L2 + (x - 2.0)  # noqa: E731
    ys = lambda y: 10.0 - y        # noqa: E731
    segs = [(ys(10), ys(8.15), gran), (ys(8.15), ys(7.25), iron), (ys(7.25), ys(5.0), gran), (ys(5.0), ys(3.4), gran), (ys(3.4), L1, gran),
            (L1, L1 + math.pi / 3, gran), (L1 + math.pi / 3, L1 + 2 * math.pi / 3, gran), (L1 + 2 * math.pi / 3, L2, gran),
            (L2, xs(3.8), gran), (xs(3.8), xs(5.9), gran), (xs(5.9), xs(8.6), gran), (xs(8.6), xs(9.3), conc), (xs(9.3), xs(10.0), gran)]
    rng = random.Random(17)
    out = []
    for si, (s0, s1, mat) in enumerate(segs):
        mb = MB(f"crn_curb_{si:02d}")
        dz = rng.uniform(-0.004, 0.003)
        do = rng.uniform(-0.004, 0.004)
        tw = rng.uniform(-0.002, 0.002)
        a0 = s0 + (0.0 if si == 0 else 0.003)
        a1 = s1 - (0.0 if si == len(segs) - 1 else 0.003)
        n = max(2, int((a1 - a0) / 0.025) + 1)
        # chips: a few gaussian bites along the arris, more on the old granite
        nb = 0 if mat is iron else rng.randint(1, 4)
        bites = [(rng.uniform(a0, a1), rng.uniform(0.02, 0.07), rng.uniform(0.008, 0.022)) for _ in range(nb)]
        if mat is not iron and rng.random() < 0.7:
            bites.append((a0 + 0.01, 0.03, rng.uniform(0.006, 0.015)))
            bites.append((a1 - 0.01, 0.03, rng.uniform(0.006, 0.015)))
        rings = []
        prof_len = None
        for i in range(n):
            s = a0 + (a1 - a0) * i / (n - 1)
            p, t, nv = curb_path(s)
            back = p - nv * (CW - 0.02)
            zt = float(walk_z(back.x, back.y)) + dz + tw * (i / (n - 1) - 0.5)
            zg = float(road_base(p.x + nv.x * 0.05, p.y + nv.y * 0.05))
            chip = sum(dd * math.exp(-((s - sc) / w) ** 2) for sc, w, dd in bites)
            prof = curb_profile(zt, zg, chip, throat=(mat is iron))
            prof_len = len(prof)
            rings.append([mb.add_v((p.x + nv.x * (o + do), p.y + nv.y * (o + do), z)) for (o, z) in prof])
        k = prof_len
        for a, b in zip(rings[:-1], rings[1:]):
            for j in range(k):
                j2 = (j + 1) % k
                mb.face([a[j], b[j], b[j2], a[j2]], 'm')
        mb.face(rings[0][::-1], 'm')
        mb.face(rings[-1], 'm')
        out.append(finalize(mb, col, {'m': mat}, smooth=True, angle=35))
    # dark throat cavity behind the inlet hood
    mb = MB("crn_inlet_throat")
    mb.box((0.02, 7.28, -0.45), (0.25, 8.12, GUT + 0.12), 'd')
    finalize(mb, col, {'d': K.m_dark("crn_void")})
    return out


def build_slabs(col):
    mat = K.m_concrete("crn_slab")
    rng = random.Random(23)
    holes = [TREE_PIT, TRENCH]
    rects = []
    for i in range(len(XL) - 1):
        for j in range(len(XL) - 1):
            r = (XL[i], XL[j], XL[i + 1], XL[j + 1])
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            if (cx > SW and cy > SW) or (cx < SQ and cy < SQ):
                continue
            rs = [r]
            for h in holes:
                rs = [q for rr in rs for q in rect_sub(rr, h)]
            rects += rs
    mb = MB("crn_slabs")
    cracked = set(rng.sample(range(len(rects)), 5))
    g = 0.004
    tp = TREE_PIT
    for k, r in enumerate(rects):
        x0, y0, x1, y1 = r[0] + g, r[1] + g, r[2] - g, r[3] - g
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        tint = (rng.random(), rng.random(), 0.0)
        dz = rng.gauss(0, 0.0018)
        gx, gy = rng.gauss(0, 0.0025), rng.gauss(0, 0.0025)
        # root heave next to the tree pit: lift the edge that faces the trunk
        near = (x0 < tp[2] + 0.4 and x1 > tp[0] - 0.4 and y0 < tp[3] + 0.4 and y1 > tp[1] - 0.4)
        if near:
            vx, vy = TRUNK[0] - cx, TRUNK[1] - cy
            ln = math.hypot(vx, vy)
            gx += 0.022 * vx / ln
            gy += 0.022 * vy / ln
            dz += 0.012
        pieces = [(poly, dz, gx, gy)]
        if k in cracked or (near and rng.random() < 0.6):
            q = (cx + rng.uniform(-0.25, 0.25) * (x1 - x0), cy + rng.uniform(-0.25, 0.25) * (y1 - y0))
            a = rng.uniform(0, math.pi)
            nn = (math.cos(a), math.sin(a))
            gap = 0.0018
            p1 = clip_half(poly, (q[0] + nn[0] * gap, q[1] + nn[1] * gap), nn)
            p2 = clip_half(poly, (q[0] - nn[0] * gap, q[1] - nn[1] * gap), (-nn[0], -nn[1]))
            pieces = [(p1, dz + rng.uniform(-0.004, 0.006), gx + rng.gauss(0, 0.006), gy + rng.gauss(0, 0.006)),
                      (p2, dz + rng.uniform(-0.004, 0.006), gx + rng.gauss(0, 0.006), gy + rng.gauss(0, 0.006))]
        for pp, dzz, gxx, gyy in pieces:
            if len(pp) < 3 or abs(poly_area(pp)) < 0.01:
                continue
            if poly_area(pp) < 0:
                pp = pp[::-1]
            zf = (lambda X, Y, dzz=dzz, gxx=gxx, gyy=gyy: dzz + gxx * (X - cx) + gyy * (Y - cy))
            prism_slab(mb, pp, zf, 'm', tint)
    ob = finalize(mb, col, {'m': mat}, recalc=False)
    # bedding under the joints
    mb = MB("crn_bed")
    mb.quad([(0.1, 0.1, -0.03), (EXT, 0.1, -0.03), (EXT, SW, -0.03), (0.1, SW, -0.03)], 'm')
    mb.quad([(0.1, SW, -0.03), (SW, SW, -0.03), (SW, EXT, -0.03), (0.1, EXT, -0.03)], 'm')
    finalize(mb, col, {'m': K.m_soil("crn_bedding")}, recalc=False)
    return ob


def build_pour(col):
    mat = K.m_concrete("crn_pour", col=(170, 166, 158), use_cell=False, gum=1.3)
    b = RC - CW

    def project(X, Y):
        r = np.hypot(X - RC, Y - RC)
        out = (X < RC) & (Y < RC) & (r > b)
        k = b / np.maximum(r, 1e-6)
        return np.where(out, RC + (X - RC) * k, X), np.where(out, RC + (Y - RC) * k, Y), out
    e = SQ - 0.004
    return grid_mesh("crn_corner_pour", col, mat, CW, CW, e, e, 0.035, pour_z, project=project, skirt=0.08)


def build_trench_patch(col):
    mat = K.m_asphalt("crn_patch_asphalt", masks=False, patch=1.0, base=(44, 44, 44))
    x0, y0, x1, y1 = TRENCH

    def zf(X, Y):
        return -0.007 + (vnoise(X, Y, 9, 0.4) - 0.5) * 0.008 + (vnoise(X, Y, 10, 0.08) - 0.5) * 0.002
    return grid_mesh("crn_trench_patch", col, mat, x0 + 0.004, y0 + 0.002, x1 - 0.004, y1, 0.04, zf, skirt=0.06)


def build_markings(col):
    mat = K.m_thermo("crn_thermo")
    mb = MB("crn_markings")

    def rect(x0, y0, x1, y1, step=0.12):
        nx = max(1, int(math.ceil((x1 - x0) / step)))
        ny = max(1, int(math.ceil((y1 - y0) / step)))
        xs = np.linspace(x0, x1, nx + 1)
        ys = np.linspace(y0, y1, ny + 1)
        Xg, Yg = np.meshgrid(xs, ys)
        Z = road_z(Xg, Yg) + 0.003
        ids = [[mb.add_v((float(Xg[j, i]), float(Yg[j, i]), float(Z[j, i]))) for i in range(nx + 1)] for j in range(ny + 1)]
        for j in range(ny):
            for i in range(nx):
                mb.face([ids[j][i], ids[j][i + 1], ids[j + 1][i + 1], ids[j + 1][i]], 'm')
        # side walls
        ring = [ids[0][i] for i in range(nx + 1)] + [ids[j][nx] for j in range(1, ny + 1)] + \
               [ids[ny][i] for i in range(nx - 1, -1, -1)] + [ids[j][0] for j in range(ny - 1, 0, -1)]
        low = [mb.add_v((mb.v[v][0], mb.v[v][1], mb.v[v][2] - 0.006)) for v in ring]
        n = len(ring)
        for k in range(n):
            k2 = (k + 1) % n
            mb.face([ring[k], low[k], low[k2], ring[k2]], 'm')

    # ladder crosswalk across the avenue (y 0.5..3.7) and across the cross street (x 0.5..3.7)
    for a0, a1 in ((0.5, 0.7), (3.5, 3.7)):
        rect(-EXT, a0, -0.3, a1)
        rect(a0, -EXT, a1, -0.3)
    for c in np.arange(-0.9, -EXT, -1.2):
        rect(c - 0.3, 0.75, c + 0.3, 3.45)
        rect(0.75, c - 0.3, 3.45, c + 0.3)
    rect(-EXT, 4.9, -0.32, 5.5)             # stop bar
    rect(-3.5, 5.5, -3.3, EXT)              # solid lane line before the stop bar
    rect(5.6, -3.5, 8.58, -3.3)             # cross-street dash, cut by the trench patch
    # left-turn arrow in the curb lane (traffic heading -Y, turning toward +X)
    rect(-1.86, 7.05, -1.66, 9.7)
    rect(-1.86, 6.92, -1.22, 7.12)
    tip, base0, base1 = (-0.72, 7.02), (-1.22, 6.58), (-1.22, 7.46)
    nseg = 6
    for i in range(nseg):
        t0, t1 = i / nseg, (i + 1) / nseg
        pa = [(base0[0] + (tip[0] - base0[0]) * t, base0[1] + (tip[1] - base0[1]) * t) for t in (t0, t1)]
        pb = [(base1[0] + (tip[0] - base1[0]) * t, base1[1] + (tip[1] - base1[1]) * t) for t in (t0, t1)]
        pts = [pa[0], pa[1], pb[1], pb[0]]
        ids = [mb.add_v((x, y, float(road_z(x, y)) + 0.003)) for x, y in pts]
        mb.face(ids, 'm')
    return finalize(mb, col, {'m': mat}, recalc=False)


def build_tree_pit(col):
    soil = K.m_soil("crn_soil")
    x0, y0, x1, y1 = TREE_PIT

    def zf(X, Y):
        r = np.hypot(X - TRUNK[0], Y - TRUNK[1])
        return -0.075 + (vnoise(X, Y, 12, 0.12) - 0.5) * 0.02 + 0.05 * np.exp(-(r / 0.22) ** 2)
    grid_mesh("crn_pit_soil", col, soil, x0 + 0.004, y0 + 0.004, x1 - 0.004, y1 - 0.004, 0.03, zf)
    # steel edge angle around the pit
    mb = MB("crn_pit_edge")
    t = 0.006
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        mb.bar((a[0], a[1], -0.012), (b[0], b[1], -0.012), 0.012, 0.024, 'm')
    finalize(mb, col, {'m': K.m_iron("crn_iron", rust=0.8)})


# ============================================================================ props placement
PLACE = [
    # (function, kwargs, location, rot_deg)
    ('signal_pole', dict(seed=1), (4.9, 0.55, 0.0), 0),
    ('streetlight', dict(seed=2), (0.55, 4.9, 0.0), -90),
    ('hydrant', dict(seed=3), (5.75, 0.50, -0.004), 0),
    ('litter_bin', dict(seed=4), (6.55, 0.62, -0.003), 0),
    ('bollard', dict(seed=5), (7.25, 0.42, -0.004), 0),
    ('bollard', dict(seed=6), (8.65, 0.42, -0.004), 0),
    ('control_cabinet', dict(seed=7), (7.95, 1.30, 0.0), 180),
    ('newspaper_box', dict(seed=8), (9.45, 0.72, -0.003), 180),
    ('pay_station', dict(seed=9), (0.50, 5.85, -0.003), 90),
    ('bike_rack', dict(seed=10), (0.85, 7.0, -0.004), 90),
    ('bicycle', dict(seed=11), (1.18, 7.02, 0.0), 90),
    ('electrical_pedestal', dict(seed=12), (1.35, 4.35, -0.003), 90),
    ('sign_post', dict(seed=13), (0.40, 9.75, -0.004), -90),
    ('traffic_cone', dict(seed=14), (9.75, -0.55, None), 23),
    ('tree_grate', dict(seed=15), ((TREE_PIT[0] + TREE_PIT[2]) / 2, (TREE_PIT[1] + TREE_PIT[3]) / 2, -0.004), 0),
    ('street_tree', dict(seed=16), (TRUNK[0], TRUNK[1], -0.06), 0),
    ('manhole', dict(seed=17), (MH[0], MH[1], None), 12),
    ('valve_cover', dict(seed=18), (VALVE[0], VALVE[1], None), 40),
    ('storm_inlet', dict(seed=19), ((INLET[0] + INLET[2]) / 2, (INLET[1] + INLET[3]) / 2, GUT - 0.02), 0),
    ('cup_flat', dict(seed=20), (-0.22, 6.05, None), 70),
    ('cup_flat', dict(seed=21), (2.9, 2.35, 0.0), -20),
]


def place(parent, coll, loc, rot, name):
    em = bpy.data.objects.new(name, None)
    em.instance_type = 'COLLECTION'
    em.instance_collection = coll
    x, y, z = loc
    if z is None:
        z = float(road_z(x, y)) if not is_sidewalk(x, y, 0.0) else float(walk_z(x, y))
        # tilt to the road surface
        e = 0.2
        dzx = float(road_z(x + e, y) - road_z(x - e, y)) / (2 * e)
        dzy = float(road_z(x, y + e) - road_z(x, y - e)) / (2 * e)
        em.rotation_euler = (math.atan(dzy), -math.atan(dzx), math.radians(rot))
    else:
        em.rotation_euler = (0, 0, math.radians(rot))
    em.location = (x, y, z)
    em.empty_display_size = 0.3
    parent.objects.link(em)
    return em


def scatter_small(col, lib):
    """Leaves in the gutters / pit, cigarette ends, extra cups: one mesh per kind, placed on the ground."""
    rng = random.Random(91)
    pts = []
    # gutter bands
    for _ in range(420):
        if rng.random() < 0.6:
            y = rng.uniform(2.2, 9.95)
            x = -abs(rng.gauss(0, 0.12)) - 0.01
        else:
            x = rng.uniform(2.2, 9.95)
            y = -abs(rng.gauss(0, 0.12)) - 0.01
        pts.append((x, y, float(road_z(x, y)) + 0.002, 'road'))
    for _ in range(140):
        x = rng.uniform(TREE_PIT[0] + 0.05, TREE_PIT[2] - 0.05)
        y = rng.uniform(TREE_PIT[1] + 0.05, TREE_PIT[3] - 0.05)
        pts.append((x, y, -0.03, 'pit'))
    for _ in range(90):
        x, y = rng.uniform(0.3, 5.8), rng.uniform(0.3, 9.9)
        if rng.random() < 0.5:
            x, y = y, x
        if not is_sidewalk(x, y, 0.2) or (x > SW and y > SW):
            continue
        pts.append((x, y, float(walk_z(x, y)) + 0.001, 'walk'))
    leaf_litter(col, pts, seed=5)
    # cigarette ends: near the bin, the signal pole, the corner and the curb
    cig = []
    for cxy, n, rad in (((6.55, 0.62), 9, 0.6), ((4.9, 0.55), 7, 0.5), ((1.2, 1.2), 6, 0.7), ((0.4, 5.5), 4, 0.5)):
        for _ in range(n):
            x, y = cxy[0] + rng.gauss(0, rad), cxy[1] + rng.gauss(0, rad)
            z = float(walk_z(x, y)) if is_sidewalk(x, y, 0.0) else float(road_z(x, y))
            cig.append((x, y, z))
    for _ in range(8):
        y = rng.uniform(3, 9.8)
        cig.append((-rng.uniform(0.02, 0.12), y, float(road_z(-0.05, y))))
    cigarette(col, cig, seed=7)


def build(variant=None):
    v = dict(name="ASSET_corner", seed=0)
    v.update(variant or {})
    corner_tex.make_all()
    K.reset()
    col = bpy.data.collections.new(v['name'])
    g = bpy.data.collections.new(v['name'] + "_ground")
    col.children.link(g)
    build_road(g)
    build_puddles(g)
    build_curb(g)
    build_slabs(g)
    build_pour(g)
    build_trench_patch(g)
    build_markings(g)
    build_tree_pit(g)
    P.ramp_tactile(g, pour_z)
    pr = bpy.data.collections.new(v['name'] + "_props")
    col.children.link(pr)
    lib = {}
    for i, (fn, kw, loc, rot) in enumerate(PLACE):
        key = (fn, tuple(sorted(kw.items())))
        if key not in lib:
            lib[key] = getattr(P, fn)(name=f"PROP_{fn}_{kw.get('seed', 0)}", **kw)
        place(pr, lib[key], loc, rot, f"inst_{fn}_{i:02d}")
    sm = bpy.data.collections.new(v['name'] + "_litter")
    col.children.link(sm)
    scatter_small(sm, lib)
    return col


if __name__ == "__main__":
    import time
    t = time.time()
    c = build()
    print("built", c.name, "%.1fs" % (time.time() - t))
