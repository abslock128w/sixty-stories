"""Building generators: near (real facade geometry), mid (massing + shader windows),
far (merged boxes). All geometry is built in world space."""
import math
import random
import bpy

import materials as MAT
from cutil import MB, hash01
import layout as LY

SLOTS = ['wall', 'trim', 'window', 'spandrel', 'metal', 'roof', 'shop', 'curtain', 'cw_spandrel', 'blank', 'louvre']
S = {k: i for i, k in enumerate(SLOTS)}

BRICK_COLS = [(0.225, 0.090, 0.053), (0.270, 0.120, 0.068), (0.315, 0.188, 0.112), (0.180, 0.075, 0.053),
              (0.360, 0.285, 0.195), (0.413, 0.338, 0.247), (0.150, 0.098, 0.075), (0.285, 0.150, 0.098)]
STONE_COLS = [(0.46, 0.37, 0.25), (0.42, 0.33, 0.22), (0.394, 0.360, 0.306), (0.354, 0.326, 0.286), (0.422, 0.394, 0.340), (0.313, 0.292, 0.265),
              (0.374, 0.320, 0.258), (0.449, 0.422, 0.374)]
GLASS_TINTS = [(0.36, 0.22, 0.11), (0.11, 0.24, 0.19), (0.07, 0.08, 0.09), (0.30, 0.27, 0.20), (0.16, 0.24, 0.28), (0.20, 0.27, 0.27), (0.30, 0.25, 0.18), (0.17, 0.19, 0.22),
               (0.30, 0.33, 0.35), (0.12, 0.20, 0.22), (0.26, 0.28, 0.30)]
PANEL_COLS = [(0.07, 0.07, 0.08), (0.12, 0.11, 0.10), (0.385, 0.378, 0.364), (0.280, 0.280, 0.280), (0.434, 0.420, 0.392), (0.210, 0.217, 0.231), (0.490, 0.476, 0.448)]


# ----------------------------------------------------------------- neighbour index
class LotIndex:
    def __init__(self, specs, cell=60.0):
        self.cell = cell
        self.g = {}
        for s in specs:
            x0, x1, y0, y1 = s['lot']
            for i in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for j in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.g.setdefault((i, j), []).append(s)

    def height_at(self, x, y):
        c = self.g.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), [])
        h = 0.0
        for s in c:
            x0, x1, y0, y1 = s['lot']
            if x0 <= x <= x1 and y0 <= y <= y1:
                h = max(h, s['height'])
        if LY.TOWER['x0'] <= x <= LY.TOWER['x1'] and LY.TOWER['y0'] <= y <= LY.TOWER['y1']:
            h = max(h, 240.0)
        return h


# ----------------------------------------------------------------- style params
def style_params(style, rng, height):
    P = dict(style=style)
    P['sh'] = rng.uniform(3.6, 4.0)
    P['gh'] = rng.uniform(4.8, 6.2)
    P['sills'] = False
    P['lintels'] = False
    P['ribbon'] = False
    P['curtain'] = False
    P['mech_every'] = 0
    P['parapet'] = rng.uniform(1.0, 2.2)
    P['blind_p'] = rng.uniform(0.2, 0.6)
    P['cool_p'] = rng.uniform(0.05, 0.5)
    if style == 'prewar':
        P.update(bay=rng.uniform(1.9, 2.6), pw=0.0, cw=rng.uniform(0.6, 1.2), dp=0.28, ds=0.28,
                 sill=rng.uniform(0.85, 1.0), head=rng.uniform(2.75, 3.0), sills=True, lintels=rng.random() < 0.8,
                 wall=rng.choice(['brick', 'brick', 'brick', 'limestone']), trim='trim', spandrel='wall',
                 cornice=rng.uniform(0.6, 1.2), pairs=rng.random() < 0.3)
        P['pw'] = P['bay'] - rng.uniform(1.05, 1.35)
    elif style == 'deco':
        P.update(bay=rng.uniform(1.5, 1.9), cw=rng.uniform(1.2, 2.2), dp=rng.uniform(0.35, 0.5), ds=rng.uniform(0.08, 0.16),
                 sill=0.95, head=rng.uniform(2.9, 3.1), wall=rng.choice(['limestone', 'limestone', 'brick']), trim='trim',
                 spandrel=rng.choice(['metal_bronze', 'terracotta', 'wall', 'metal_dark']), cornice=0.35, pairs=False)
        P['pw'] = rng.uniform(0.38, 0.55)
    elif style == 'slab':
        P.update(bay=rng.uniform(1.4, 1.6), pw=0.07, cw=0.5, dp=0.12, ds=rng.uniform(0.18, 0.3),
                 sill=rng.uniform(1.0, 1.2), head=P['sh'] - rng.uniform(0.25, 0.5), wall='panel', trim='concrete',
                 spandrel='wall', ribbon=True, cornice=0.0, pairs=False, mech_every=rng.choice([0, 0, 18, 22]))
    elif style in ('glass', 'twin'):
        P.update(bay=1.5, pw=0.07, cw=0.25, dp=rng.uniform(0.12, 0.35), ds=0.0, sill=0.95, head=P['sh'],
                 wall='concrete', trim='metal_alu', spandrel='cw_spandrel', curtain=True, cornice=0.0, pairs=False,
                 mech_every=rng.choice([0, 15, 20, 25]))
        P['gh'] = rng.uniform(7.0, 9.0)
        P['sh'] = rng.uniform(3.9, 4.2)
        P['head'] = P['sh']
    else:
        raise ValueError(style)
    return P


def mats_for(P):
    wall = P['wall']
    m = {
        'wall': MAT.get(wall),
        'trim': MAT.get(P['trim']),
        'window': MAT.get('window'),
        'spandrel': MAT.get(P['spandrel']) if P['spandrel'] != 'wall' else MAT.get(wall),
        'metal': MAT.get('metal_dark'),
        'roof': MAT.get('roof'),
        'shop': MAT.get('shop'),
        'curtain': MAT.get('curtain'),
        'cw_spandrel': MAT.get('cw_spandrel'),
        'blank': MAT.get('brick') if wall != 'panel' else MAT.get('concrete'),
        'louvre': MAT.get('louvre'),
    }
    return [m[k] for k in SLOTS]


def bcol_for(P, rng):
    if P['curtain']:
        c = rng.choice(GLASS_TINTS)
    elif P['wall'] == 'brick':
        c = rng.choice(BRICK_COLS)
    elif P['wall'] == 'panel':
        c = rng.choice(PANEL_COLS)
    else:
        c = rng.choice(STONE_COLS)
    j = rng.uniform(0.9, 1.1)
    return (c[0] * j, c[1] * j, c[2] * j, rng.random())


# ----------------------------------------------------------------- facade
class Face:
    def __init__(self, p0, p1):
        self.p0 = p0
        self.p1 = p1
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        self.L = math.hypot(dx, dy)
        self.d = (dx / self.L, dy / self.L)
        self.n = (self.d[1], -self.d[0])  # outward for CCW polygons

    def pt(self, s, o, z):
        return (self.p0[0] + self.d[0] * s + self.n[0] * o, self.p0[1] + self.d[1] * s + self.n[1] * o, z)

    def box(self, mb, s0, s1, o0, o1, z0, z1, mat, attrs=None, back=False, caps=True):
        if s1 - s0 < 1e-3 or o1 - o0 < 1e-4 or z1 - z0 < 1e-3:
            return
        sc = (s0 + s1) / 2
        oc = (o0 + o1) / 2
        c = (self.p0[0] + self.d[0] * sc + self.n[0] * oc, self.p0[1] + self.d[1] * sc + self.n[1] * oc)
        skip = set()
        if not back:
            skip.add('+w')  # inward face (n_box = -outward)
        if not caps:
            skip |= {'+l', '-l'}
        mb.obox(c, self.d, (s1 - s0) / 2, (o1 - o0) / 2, z0, z1, mat, skip=skip, attrs=attrs)

    def quad(self, mb, s0, s1, o, z0, z1, mat, attrs=None, uv=True):
        mb.quad(self.pt(s0, o, z0), self.pt(s1, o, z0), self.pt(s1, o, z1), self.pt(s0, o, z1), mat,
                [(0, 0), (1, 0), (1, 1), (0, 1)] if uv else None, attrs)


def floor_levels(z0, z1, zbase, P, storefront):
    """Window rows [(fz, sill_z, head_z)] between z0 and z1 for floors starting at zbase."""
    rows = []
    fz = zbase + (P['gh'] if storefront else 0.0)
    if storefront:
        fz = max(fz, z0 + P['gh'])
    # align floors to the building's floor grid
    if fz < z0:
        k = math.ceil((z0 - fz) / P['sh'])
        fz += k * P['sh']
    while fz + P['head'] <= z1 - 0.3:
        rows.append((fz, fz + P['sill'], fz + P['head'] - (0.0 if not P['curtain'] else 0.0)))
        fz += P['sh']
    return rows


def build_facade(mb, face, z0, z1, P, rng, bcol, storefront, ext_end, fl_rand, zfloor0=0.0):
    L = face.L
    if L < 2.0:
        face.quad(mb, 0, L, 0, z0, z1, S['wall'], {'bcol': bcol}, uv=False)
        return
    A = {'bcol': bcol}
    dp, ds, cw, pw = P['dp'], P['ds'], P['cw'], P['pw']
    curtain = P['curtain']
    n = max(1, int(round((L - 2 * cw) / P['bay'])))
    b = (L - 2 * cw) / n
    if b < pw + 0.6:
        n = max(1, int((L - 2 * cw) / (pw + 0.9)))
        b = (L - 2 * cw) / n
    ext = dp if ext_end else 0.0
    wall = S['trim'] if curtain else S['wall']
    # corner piers / mullions
    face.box(mb, 0, cw, 0, dp, z0, z1, wall, A)
    face.box(mb, L - cw, L + ext, 0, dp, z0, z1, wall, A)
    # interior piers
    me_ = P.get('major_every', 0)
    for k in range(1, n):
        s = cw + k * b
        if me_ and k % me_ == 0:
            face.box(mb, s - pw / 2 - 0.2, s + pw / 2 + 0.2, 0, dp + 0.22, z0, z1, wall, A)
        else:
            face.box(mb, s - pw / 2, s + pw / 2, 0, dp, z0, z1, wall if not P['ribbon'] else S['trim'], A)
    rows = floor_levels(z0, z1, zfloor0, P, storefront)
    # storefront zone
    ztop_store = z0
    if storefront:
        ztop_store = z0 + P['gh']
        for k in range(n):
            s0 = cw + k * b + (pw / 2 if k > 0 else 0)
            s1 = cw + (k + 1) * b - (pw / 2 if k < n - 1 else 0)
            if curtain:
                face.quad(mb, s0, s1, 0, z0 + 0.1, ztop_store - 0.6,
                          S['shop'], {'bcol': bcol, 'win': (rng.random() * 0.4, 0.0, 0.0, rng.random())})
                face.box(mb, s0, s1, 0, 0.12, ztop_store - 0.6, ztop_store, S['trim'], A, caps=False)
            else:
                face.box(mb, s0, s1, 0, 0.1, z0, z0 + 0.5, S['trim'], A, caps=False)
                face.quad(mb, s0, s1, 0, z0 + 0.5, ztop_store - 1.0,
                          S['shop'], {'bcol': bcol, 'win': (rng.random(), 0.0, 0.0, rng.random())})
                face.box(mb, s0, s1, 0, max(ds, 0.12) + 0.04, ztop_store - 1.0, ztop_store - 0.2, S['metal'], A, caps=False)
                face.box(mb, s0, s1, 0, max(ds, 0.1), ztop_store - 0.2, ztop_store, S['trim'], A, caps=False)
    # window rows + spandrels between
    edges = [ztop_store] + [z for r in rows for z in (r[1], r[2])] + [z1]
    # spandrel bands: (edges[0], sill0), (head0, sill1), ..., (head_last, z1)
    bands = [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2)]
    for (za, zb) in bands:
        if zb - za < 0.01:
            continue
        if P['ribbon']:
            face.box(mb, 0, L + (ds if ext_end else 0.0), 0, ds, za, zb, S['spandrel'], A, caps=True)
            continue
        for k in range(n):
            s0 = cw + k * b + (pw / 2 if k > 0 else 0)
            s1 = cw + (k + 1) * b - (pw / 2 if k < n - 1 else 0)
            if curtain or ds <= 0.001:
                face.quad(mb, s0, s1, 0.0, za, zb, S['cw_spandrel'] if curtain else S['spandrel'], A, uv=False)
            else:
                face.box(mb, s0, s1, 0, ds, za, zb, S['spandrel'], A, caps=False)
    # windows
    blind_p = P['blind_p']
    for fi, (fz, sz, hz) in enumerate(rows):
        flr = fl_rand(fz)
        mech = P['mech_every'] and (int(round(fz / P['sh'])) % P['mech_every'] in (0, 1)) and fz > 30
        for k in range(n):
            s0 = cw + k * b + (pw / 2 if k > 0 else 0)
            s1 = cw + (k + 1) * b - (pw / 2 if k < n - 1 else 0)
            if mech:
                face.quad(mb, s0, s1, 0.0, sz, hz, S['louvre'], A, uv=False)
                continue
            r = rng.random()
            lrank = 0.75 * hash01(flr, k // 5) + 0.25 * rng.random()
            blind = rng.uniform(0.08, 0.9) if rng.random() < blind_p else 0.0
            tint = rng.random() * (1 - P['cool_p']) if rng.random() > P['cool_p'] else 0.8 + rng.random() * 0.2
            wa = {'bcol': bcol, 'win': (r, lrank, blind, tint)}
            if P.get('pairs') and (s1 - s0) > 1.6:
                mid = (s0 + s1) / 2
                face.quad(mb, s0, mid - 0.12, 0.0, sz, hz, S['curtain'] if curtain else S['window'], wa)
                face.quad(mb, mid + 0.12, s1, 0.0, sz, hz, S['curtain'] if curtain else S['window'],
                          {'bcol': bcol, 'win': (rng.random(), lrank, blind, tint)})
                face.box(mb, mid - 0.12, mid + 0.12, 0, ds, sz, hz, S['wall'], A, caps=False)
            else:
                face.quad(mb, s0, s1, 0.0, sz, hz, S['curtain'] if curtain else S['window'], wa)
            if P.get('frames_z') is not None and sz >= P['frames_z']:
                fw, fd = 0.07, 0.09
                M = S['metal']
                face.box(mb, s0, s0 + fw, 0, fd, sz, hz, M, A)
                face.box(mb, s1 - fw, s1, 0, fd, sz, hz, M, A)
                face.box(mb, s0 + fw, s1 - fw, 0, fd, sz, sz + fw, M, A)
                face.box(mb, s0 + fw, s1 - fw, 0, fd, hz - fw, hz, M, A)
                face.box(mb, (s0 + s1) / 2 - 0.035, (s0 + s1) / 2 + 0.035, 0, fd * 0.8, sz + fw, hz - fw, M, A)
                tz = sz + (hz - sz) * 0.72
                face.box(mb, s0 + fw, s1 - fw, 0, fd * 0.8, tz - 0.03, tz + 0.03, M, A)
            if P['sills']:
                face.box(mb, s0 - 0.07, s1 + 0.07, 0, ds + 0.08, sz - 0.07, sz + 0.03, S['trim'], A)
            if P['lintels']:
                face.box(mb, s0 - 0.14, s1 + 0.14, 0, ds + 0.04, hz - 0.02, hz + 0.24, S['trim'], A)
        if curtain and fi % 1 == 0:
            # horizontal transom fins at slab level
            face.box(mb, cw, L - cw, 0, dp * 0.6, fz - 0.06, fz + 0.06, S['trim'], A, caps=False)


def offset_poly(poly, d):
    """Offset a convex CCW polygon outward by d."""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = dy / L, -dx / L
        lines.append(((a[0] + nx * d, a[1] + ny * d), (dx / L, dy / L)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + d1[0] * t, p1[1] + d1[1] * t))
    return out


def rect(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def chamfer_rect(x0, x1, y0, y1, c):
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


# ----------------------------------------------------------------- tiers
def make_tiers(spec, P, rng):
    """List of tiers: dict(poly, z0, z1, inset) and crown info."""
    x0, x1, y0, y1 = spec['lot']
    H = spec['height']
    st = P['style']
    w, d = x1 - x0, y1 - y0
    tiers = []
    crown = None
    if st == 'prewar':
        tiers.append(dict(poly=rect(x0, x1, y0, y1), z0=0.0, z1=H, inset=False))
        crown = 'cornice'
    elif st == 'slab':
        if rng.random() < 0.5 and H > 60:
            pod = rng.uniform(12, 22)
            tiers.append(dict(poly=rect(x0, x1, y0, y1), z0=0.0, z1=pod, inset=False))
            ins = [rng.uniform(2, 6) for _ in range(4)]
            px0, px1 = x0 + ins[0], x1 - ins[1]
            py0, py1 = y0 + ins[2], y1 - ins[3]
            if px1 - px0 > 12 and py1 - py0 > 12:
                tiers.append(dict(poly=rect(px0, px1, py0, py1), z0=pod, z1=H, inset=True))
            else:
                tiers[0]['z1'] = H
        else:
            tiers.append(dict(poly=rect(x0, x1, y0, y1), z0=0.0, z1=H, inset=False))
        crown = 'penthouse'
    elif st == 'deco':
        nset = 2 if H < 110 else (3 if H < 200 else 4)
        zs = [0.0]
        frac = [0.42, 0.68, 0.84, 0.93][:nset]
        frac[-1] = 1.0 if nset == 1 else frac[-1]
        for f in frac[:-1]:
            zs.append(H * (f + rng.uniform(-0.04, 0.04)))
        zs.append(H)
        cx0, cx1, cy0, cy1 = x0, x1, y0, y1
        for i in range(len(zs) - 1):
            tiers.append(dict(poly=rect(cx0, cx1, cy0, cy1), z0=zs[i], z1=zs[i + 1], inset=i > 0))
            ix = min(rng.uniform(2.5, 5.0), (cx1 - cx0 - 14) / 2)
            iy = min(rng.uniform(2.5, 5.0), (cy1 - cy0 - 14) / 2)
            if ix < 1.5 or iy < 1.5:
                ix = iy = 0
            cx0, cx1, cy0, cy1 = cx0 + ix, cx1 - ix, cy0 + iy, cy1 - iy
        crown = 'deco'
    elif st in ('glass', 'twin'):
        plaza = 0.0 if st == 'twin' else rng.choice([0.0, 0.0, 3.0, 5.0])
        px0, px1, py0, py1 = x0 + plaza, x1 - plaza, y0 + plaza, y1 - plaza
        if px1 - px0 < 16 or py1 - py0 < 16:
            px0, px1, py0, py1 = x0, x1, y0, y1
        cham = rng.random() < 0.45 and min(px1 - px0, py1 - py0) > 24
        c = rng.uniform(3, 7) if cham else 0.0
        if st == 'twin':
            c = 0.0
        mk = (lambda a, b, cc, dd: chamfer_rect(a, b, cc, dd, c)) if cham else rect
        if H > 160 and rng.random() < 0.6 and st != 'twin':
            z1 = H * rng.uniform(0.6, 0.75)
            tiers.append(dict(poly=mk(px0, px1, py0, py1), z0=0.0, z1=z1, inset=plaza > 0))
            s = rng.uniform(3, 6)
            tiers.append(dict(poly=mk(px0 + s, px1 - s, py0 + s, py1 - s), z0=z1, z1=H, inset=True))
        else:
            tiers.append(dict(poly=mk(px0, px1, py0, py1), z0=0.0, z1=H, inset=plaza > 0))
        crown = 'glass'
    return tiers, crown


# ----------------------------------------------------------------- near building
def build_near(spec, lidx, protos_out, P=None, tiers=None, crown=None, bcol=None, mb=None, mats=None):
    rng = random.Random(spec['seed'])
    if P is None:
        P = style_params('glass' if spec['style'] == 'twin' else spec['style'], rng, spec['height'])
        if spec['style'] == 'twin':
            P['style'] = 'twin'
            P['mech_every'] = 0
            P['dp'] = 0.3
    if tiers is None:
        tiers, crown = make_tiers(spec, P, rng)
    if bcol is None:
        bcol = bcol_for(P, rng)
    if spec['style'] == 'twin':
        bcol = (0.20, 0.25, 0.27, 0.5)
    mb = mb or MB(attrs=('win', 'bcol'))
    flr_seed = rng.random()
    fl_rand = lambda fz: hash01(spec['seed'], int(fz * 10))
    x0, x1, y0, y1 = spec['lot']
    block = spec.get('block')
    for ti, t in enumerate(tiers):
        poly = [p for i, p in enumerate(t['poly']) if math.hypot(p[0] - t['poly'][i - 1][0], p[1] - t['poly'][i - 1][1]) > 0.05]
        t['poly'] = poly
        npoly = len(poly)
        faces = [Face(poly[i], poly[(i + 1) % npoly]) for i in range(npoly)]
        kinds = []
        for f in faces:
            # is the face on the lot line toward a street, a party wall, or exposed (inset)?
            mx = (f.p0[0] + f.p1[0]) / 2 + f.n[0] * 1.5
            my = (f.p0[1] + f.p1[1]) / 2 + f.n[1] * 1.5
            nh = max(lidx.height_at(mx, my), lidx.height_at(f.pt(f.L * 0.2, 1.5, 0)[0], f.pt(f.L * 0.2, 1.5, 0)[1]),
                     lidx.height_at(f.pt(f.L * 0.8, 1.5, 0)[0], f.pt(f.L * 0.8, 1.5, 0)[1]))
            kinds.append(nh)
        for i, f in enumerate(faces):
            nh = kinds[i]
            nxt = kinds[(i + 1) % npoly]
            zb = t['z0']
            if nh > t['z0'] + 0.5:
                # party wall up to the neighbour's height
                zb = min(t['z1'], nh)
                f.quad(mb, 0, f.L, 0, t['z0'], zb, S['blank'], {'bcol': bcol}, uv=False)
            if zb < t['z1'] - 2.0:
                storefront = (t['z0'] == 0.0 and zb == 0.0)
                build_facade(mb, f, zb, t['z1'], P, rng, bcol, storefront, ext_end=(nxt <= zb + 0.5 and nxt < t['z1']),
                             fl_rand=fl_rand)
            elif zb < t['z1']:
                f.quad(mb, 0, f.L, 0, zb, t['z1'], S['blank'], {'bcol': bcol}, uv=False)
        # roof of tier + parapet coping / cornice
        is_top = ti == len(tiers) - 1
        A = {'bcol': bcol}
        if P['cornice'] > 0 and (is_top or P['style'] == 'deco'):
            cp = offset_poly(poly, P['dp'] + (P['cornice'] if is_top else 0.25))
            hh = 0.9 if is_top else 0.45
            mb.prism(cp, t['z1'] - hh, t['z1'], S['trim'], top=False, bottom=True, attrs=A)
            mb.prism(cp, t['z1'], t['z1'] + 0.01, S['trim'], top=False, attrs=A)
            mb.poly([(p[0], p[1], t['z1'] + 0.01) for p in cp], S['roof'], None, A)
        else:
            cp = offset_poly(poly, P['dp'] + 0.02)
            mb.prism(cp, t['z1'] - 0.5, t['z1'], S['trim'] if not P['curtain'] else S['metal'], top=False,
                     bottom=True, attrs=A)
            mb.poly([(p[0], p[1], t['z1']) for p in cp], S['roof'], None, A)
    top = tiers[-1]
    roof_z = top['z1']
    extra_top = build_crown(mb, crown, top, P, rng, bcol, spec, protos_out) if crown else 0.0
    me = mb.build(f"B{spec['id']}_{spec['style']}", mats or mats_for(P))
    spec['roof_z'] = roof_z
    spec['top_z'] = roof_z + extra_top
    spec['tiers'] = [dict(poly=[tuple(map(float, p)) for p in t['poly']], z0=t['z0'], z1=t['z1']) for t in tiers]
    spec['params'] = dict(storey=P['sh'], bay=P['bay'], gh=P['gh'], dp=P['dp'], ds=P['ds'], curtain=P['curtain'])
    return me


def poly_bounds(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


def build_crown(mb, crown, top, P, rng, bcol, spec, protos_out):
    x0, x1, y0, y1 = poly_bounds(top['poly'])
    z = top['z1']
    A = {'bcol': bcol}
    w, d = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    extra = 0.0
    if crown == 'cornice':
        # bulkhead + water tower(s)
        bw, bd = min(6, w * 0.3), min(5, d * 0.3)
        bx = rng.uniform(x0 + 2, x1 - 2 - bw)
        by = rng.uniform(y0 + 2, y1 - 2 - bd)
        mb.box(bx, bx + bw, by, by + bd, z + 0.01, z + 3.2, S['blank'], attrs=A, skip=('-z',))
        nw = 1 if w * d < 900 else 2
        for _ in range(nw):
            protos_out.append(('water_tower', (rng.uniform(x0 + 4, x1 - 4), rng.uniform(y0 + 4, y1 - 4), z),
                               rng.uniform(0, 6.28), rng.uniform(0.85, 1.15)))
        extra = 12.0
        for _ in range(rng.randint(0, 3)):
            protos_out.append(('hvac', (rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2), z),
                               rng.choice([0, 1.5708]), 1.0))
    elif crown == 'penthouse':
        pw_, pd = w * rng.uniform(0.35, 0.6), d * rng.uniform(0.35, 0.6)
        mb.box(cx - pw_ / 2, cx + pw_ / 2, cy - pd / 2, cy + pd / 2, z, z + rng.uniform(4, 7), S['louvre'], attrs=A,
               skip=('-z',))
        for _ in range(rng.randint(2, 6)):
            protos_out.append(('hvac', (rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2), z),
                               rng.choice([0, 1.5708]), 1.0))
        if rng.random() < 0.3:
            protos_out.append(('antenna', (cx + rng.uniform(-3, 3), cy + rng.uniform(-3, 3), z), 0.0,
                               rng.uniform(0.6, 1.4)))
        extra = 7.0
    elif crown == 'deco':
        # stepped crown: 2-4 shrinking blocks then a finial or pyramid
        steps = rng.randint(2, 4)
        cz = z
        sx, sy = w, d
        for i in range(steps):
            sx *= rng.uniform(0.62, 0.8)
            sy *= rng.uniform(0.62, 0.8)
            hh = rng.uniform(3.5, 7.0)
            mb.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz, cz + hh, S['wall'], attrs=A, skip=('-z',))
            # fins on each step: vertical ribs
            nf = max(2, int(sx / 2.2))
            for k in range(nf):
                fx = cx - sx / 2 + (k + 0.5) * sx / nf
                mb.box(fx - 0.18, fx + 0.18, cy - sy / 2 - 0.35, cy - sy / 2, cz, cz + hh + 0.6, S['trim'], attrs=A,
                       skip=('-z', '+y'))
                mb.box(fx - 0.18, fx + 0.18, cy + sy / 2, cy + sy / 2 + 0.35, cz, cz + hh + 0.6, S['trim'], attrs=A,
                       skip=('-z', '-y'))
            cz += hh
        if rng.random() < 0.55:
            sh = rng.uniform(12, 30) * (1.6 if spec.get('supertall') else 1.0)
            r0 = min(sx, sy) * 0.22
            n = 8
            pts0 = [(cx + r0 * math.cos(2 * math.pi * k / n + math.pi / 8), cy + r0 * math.sin(2 * math.pi * k / n + math.pi / 8)) for k in range(n)]
            for k in range(n):
                a, b = pts0[k], pts0[(k + 1) % n]
                mb.poly([(a[0], a[1], cz), (b[0], b[1], cz), (cx, cy, cz + sh)], S['spandrel'] if P['spandrel'] in ('metal_bronze', 'metal_dark') else S['trim'], None, A)
            extra = cz - z + sh
        else:
            # pyramid roof
            ph = min(sx, sy) * rng.uniform(0.3, 0.6)
            c4 = [(cx - sx / 2, cy - sy / 2), (cx + sx / 2, cy - sy / 2), (cx + sx / 2, cy + sy / 2), (cx - sx / 2, cy + sy / 2)]
            for k in range(4):
                a, b = c4[k], c4[(k + 1) % 4]
                mb.poly([(a[0], a[1], cz), (b[0], b[1], cz), (cx, cy, cz + ph)], S['spandrel'], None, A)
            extra = cz - z + ph
    elif crown == 'glass':
        kind = rng.choice(['screen', 'slant', 'mast', 'flat'])
        if spec.get('supertall'):
            kind = 'slant'
        if kind == 'screen':
            # curtain wall extends above the roof as an open screen (both faces)
            hh = rng.uniform(5, 10)
            poly = top['poly']
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                mb.quad((a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], z + hh), (a[0], a[1], z + hh), S['cw_spandrel'], None, A)
                mb.quad((b[0], b[1], z), (a[0], a[1], z), (a[0], a[1], z + hh), (b[0], b[1], z + hh), S['metal'], None, A)
            extra = hh
        elif kind == 'slant':
            hh = min(w, d) * rng.uniform(0.35, 0.7)
            # wedge: one side rises
            P0 = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
            if rng.random() < 0.5:
                T = [(x0, y0, z), (x1, y0, z), (x1, y1, z + hh), (x0, y1, z + hh)]
                mb.quad(*T, mat=S['curtain'], uv=None, attrs={'bcol': bcol, 'win': (0.5, 0.95, 0, 0.3)})
                mb.quad((x0, y1, z), (x0, y1, z + hh), (x1, y1, z + hh), (x1, y1, z), mat=S['cw_spandrel'], attrs=A)
                mb.poly([(x1, y0, z), (x1, y1, z), (x1, y1, z + hh)], S['cw_spandrel'], None, A)
                mb.poly([(x0, y0, z), (x0, y1, z + hh), (x0, y1, z)], S['cw_spandrel'], None, A)
            else:
                T = [(x0, y0, z + hh), (x0, y0, z), (x0, y1, z), (x0, y1, z + hh)]
                mb.quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), mat=S['roof'], attrs=A)
                mb.quad((x1, y0, z), (x1, y1, z), (x0, y1, z + hh), (x0, y0, z + hh), mat=S['curtain'],
                        attrs={'bcol': bcol, 'win': (0.5, 0.95, 0, 0.3)})
                mb.quad((x0, y0, z), (x0, y1, z), (x0, y1, z + hh), (x0, y0, z + hh), mat=S['cw_spandrel'], attrs=A)
                mb.poly([(x0, y0, z), (x0, y0, z + hh), (x1, y0, z)], S['cw_spandrel'], None, A)
                mb.poly([(x0, y1, z), (x1, y1, z), (x0, y1, z + hh)], S['cw_spandrel'], None, A)
            extra = hh
            if spec.get('supertall'):
                protos_out.append(('antenna', (cx, cy, z + hh * 0.5), 0.0, 3.0))
                extra = hh + 30
        else:
            pw_, pd = w * 0.45, d * 0.45
            mb.box(cx - pw_ / 2, cx + pw_ / 2, cy - pd / 2, cy + pd / 2, z, z + 6, S['louvre'], attrs=A, skip=('-z',))
            extra = 6
            if kind == 'mast':
                protos_out.append(('antenna', (cx, cy, z + 6), 0.0, rng.uniform(1.2, 2.5)))
                extra = 30
    return extra


# ----------------------------------------------------------------- mid / far (shader windows)
def far_attrs(spec, rng):
    st = spec['style']
    if st in ('glass', 'twin'):
        c = rng.choice(GLASS_TINTS)
        style = 1.0
        bay = 1.5
    elif st == 'slab':
        c = rng.choice(PANEL_COLS)
        style = 0.6
        bay = 1.5
    elif st == 'deco':
        c = rng.choice(STONE_COLS)
        style = 0.25
        bay = rng.uniform(1.6, 2.0)
    else:
        c = rng.choice(BRICK_COLS + STONE_COLS[:2])
        style = 0.0
        bay = rng.uniform(1.9, 2.6)
    j = rng.uniform(0.85, 1.12)
    bcol = (c[0] * j, c[1] * j, c[2] * j, rng.random())
    bprm = (style, bay, rng.uniform(3.6, 4.0), 0.0)
    return bcol, bprm


def build_massing(mb, spec, protos_out, detail):
    """Mid/far building: tiers as prisms with shader windows (far material slot 0, roof slot 1)."""
    rng = random.Random(spec['seed'])
    st = spec['style'] if spec['style'] != 'twin' else 'glass'
    P = style_params(st, rng, spec['height'])
    tiers, crown = make_tiers(spec, P, rng)
    bcol, bprm = far_attrs(spec, rng)
    A = {'bcol': bcol, 'bprm': bprm}
    R = {'bcol': (0.11, 0.105, 0.1, bcol[3]), 'bprm': (0, 1, 1, 0)}
    A = dict(A)
    for t in tiers:
        mb.prism(t['poly'], t['z0'], t['z1'], 1, top=True, attrs=A, side_mat=0)
        # roof face uses slot 1 (roof); prism top got mat 1 via 'mat'
        if detail and st in ('prewar', 'deco'):
            cp = offset_poly(t['poly'], 0.5)
            mb.prism(cp, t['z1'] - 0.7, t['z1'] + 0.3, 2, top=True, bottom=True, attrs=A)
    top = tiers[-1]
    x0, x1, y0, y1 = poly_bounds(top['poly'])
    z = top['z1']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    extra = 0
    if crown == 'deco':
        sx, sy, cz = w, d, z
        for i in range(rng.randint(1, 3)):
            sx *= rng.uniform(0.6, 0.8)
            sy *= rng.uniform(0.6, 0.8)
            hh = rng.uniform(4, 8)
            mb.prism(rect(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2), cz, cz + hh, 2, attrs=A)
            cz += hh
        if rng.random() < 0.5:
            sh = rng.uniform(10, 25) * (1.8 if spec.get('supertall') else 1)
            r0 = min(sx, sy) * 0.25
            for k in range(4):
                a = (cx + r0 * math.cos(k * math.pi / 2 + math.pi / 4), cy + r0 * math.sin(k * math.pi / 2 + math.pi / 4))
                b = (cx + r0 * math.cos((k + 1) * math.pi / 2 + math.pi / 4), cy + r0 * math.sin((k + 1) * math.pi / 2 + math.pi / 4))
                mb.poly([(a[0], a[1], cz), (b[0], b[1], cz), (cx, cy, cz + sh)], 2, None, A)
            cz += sh
        extra = cz - z
    elif crown in ('penthouse', 'glass'):
        if rng.random() < 0.7:
            pw_, pd = w * rng.uniform(0.3, 0.55), d * rng.uniform(0.3, 0.55)
            hh = rng.uniform(4, 7)
            mb.prism(rect(cx - pw_ / 2, cx + pw_ / 2, cy - pd / 2, cy + pd / 2), z, z + hh, 1, attrs=R, side_mat=1)
            extra = hh
        if detail and rng.random() < 0.15:
            protos_out.append(('antenna', (cx, cy, z), 0.0, rng.uniform(0.8, 2.0)))
    elif crown == 'cornice' and detail:
        if rng.random() < 0.6:
            protos_out.append(('water_tower', (rng.uniform(x0 + 3, x1 - 3), rng.uniform(y0 + 3, y1 - 3), z),
                               rng.uniform(0, 6.28), rng.uniform(0.85, 1.15)))
        bw, bd = min(5, w * 0.3), min(4, d * 0.3)
        mb.prism(rect(cx - bw / 2, cx + bw / 2, cy - bd / 2, cy + bd / 2), z, z + 3, 1, attrs=R, side_mat=1)
    if detail and rng.random() < 0.5:
        for _ in range(rng.randint(1, 3)):
            protos_out.append(('hvac', (rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2), z),
                               rng.choice([0, 1.5708]), 1.0))
    spec['roof_z'] = z
    spec['top_z'] = z + extra
    spec['tiers'] = [dict(poly=[tuple(map(float, p)) for p in t['poly']], z0=t['z0'], z1=t['z1']) for t in tiers]


def far_mats():
    return [MAT.get('far'), MAT.get('roof'), MAT.get('trim')]
