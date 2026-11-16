"""City plan: street grid, blocks, lots and building specs (deterministic)."""
import math
import random

SEED = 6060
AVE_SPACING = 250.0
AVE_X = [AVE_SPACING * k for k in range(-5, 6)]          # -1250 .. 1250
HERO_AVE_W = 32.0
AVE_W = 30.0
ROAD_HALF = 10.0          # hero avenue roadway half width
SIDEWALK = 6.0
ST_W = 18.0
ST_ROAD_HALF = 5.5        # cross street roadway half width (11 m), sidewalks 3.5 m
ST_PITCH = 85.0
ST_Y0 = -257.5            # a cross street centre line
ISLAND = (-1340.0, 1340.0, -1420.0, 1350.0)   # buildable extent (x0, x1, y0, y1)
SHORE = (-1390.0, 1390.0, -1470.0, 1400.0)    # waterline

NEAR_Y = (-450.0, 900.0)
NEAR_DIST = 62.0          # from the avenue wall
MID_DIST = 420.0

TOWER = dict(cx=-46.0, cy=-300.0, x0=-76.0, x1=-16.0, y0=-332.0, y1=-268.0, height=240.0)
TWIN_Y = (352.0, 410.0)   # twin towers + skybridges, block centred y=380
BRIDGE = dict(y=381.0, depth=6.0, low=(60.0, 66.0), high=(80.0, 86.0))


def street_ys():
    ys = []
    j = -20
    while True:
        y = ST_Y0 + ST_PITCH * j
        if y > ISLAND[3] + 60:
            break
        if y > ISLAND[2] - 60:
            ys.append(y)
        j += 1
    return ys


def ave_half(x):
    return HERO_AVE_W / 2 if abs(x) < 1 else AVE_W / 2


def blocks():
    """List of (x0, x1, y0, y1) building blocks (inside sidewalks? no: lot lines)."""
    out = []
    sy = street_ys()
    for i in range(len(AVE_X) - 1):
        xa, xb = AVE_X[i], AVE_X[i + 1]
        x0 = xa + ave_half(xa)
        x1 = xb - ave_half(xb)
        for j in range(len(sy) - 1):
            y0 = sy[j] + ST_W / 2
            y1 = sy[j + 1] - ST_W / 2
            out.append((x0, x1, y0, y1))
    # strips beyond the outer avenues up to the island edge
    for xa, side in ((AVE_X[0], -1), (AVE_X[-1], 1)):
        for j in range(len(sy) - 1):
            y0 = sy[j] + ST_W / 2
            y1 = sy[j + 1] - ST_W / 2
            if side < 0:
                out.append((ISLAND[0], xa - AVE_W / 2, y0, y1))
            else:
                out.append((xa + AVE_W / 2, ISLAND[1], y0, y1))
    res = []
    for (x0, x1, y0, y1) in out:
        x0 = max(x0, ISLAND[0])
        x1 = min(x1, ISLAND[1])
        y0 = max(y0, ISLAND[2])
        y1 = min(y1, ISLAND[3])
        if x1 - x0 > 20 and y1 - y0 > 20:
            res.append((x0, x1, y0, y1))
    return res


def dist_to_hero_ave(x0, x1):
    """Distance from a lot to the hero avenue wall (0 if fronting it)."""
    if x0 >= 0:
        return max(0.0, x0 - HERO_AVE_W / 2)
    if x1 <= 0:
        return max(0.0, -HERO_AVE_W / 2 - x1)
    return 0.0


def _cluster(x, y):
    """Skyline density: midtown cluster around the canyon, downtown cluster south."""
    c = 0.0
    c += 1.0 * math.exp(-(((x - 30) / 520) ** 2 + ((y - 250) / 700) ** 2))
    c += 0.8 * math.exp(-(((x + 150) / 330) ** 2 + ((y + 1150) / 260) ** 2))
    c += 0.45 * math.exp(-(((x - 700) / 300) ** 2 + ((y - 900) / 300) ** 2))
    return c


def _height(rng, x, y, frontage):
    c = _cluster(x, y)
    med = 26 + 70 * c + (22 if frontage else 0)
    h = med * math.exp(rng.gauss(0, 0.42))
    if rng.random() < 0.05 + 0.18 * c:
        h = rng.uniform(150, 290) * (0.6 + 0.4 * c)
    return max(14.0, min(h, 300.0))


def _style_for(rng, h, near):
    if h < 40:
        return rng.choice(['prewar', 'prewar', 'prewar', 'slab'])
    if h < 95:
        return rng.choices(['prewar', 'deco', 'slab', 'glass'], [0.45, 0.25, 0.2, 0.1])[0]
    if h < 160:
        return rng.choices(['deco', 'slab', 'glass', 'prewar'], [0.35, 0.25, 0.3, 0.1])[0]
    return rng.choices(['deco', 'glass', 'slab'], [0.4, 0.45, 0.15])[0]


def _split(rng, a, b, wmin, wmax):
    """Split interval a..b into pieces of width in [wmin, wmax]."""
    cuts = [a]
    x = a
    while b - x > wmax:
        w = rng.uniform(wmin, wmax)
        if b - (x + w) < wmin:
            w = (b - x) / 2
        x += w
        cuts.append(x)
    cuts.append(b)
    return list(zip(cuts[:-1], cuts[1:]))


def _overlap(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def make_lots():
    """Returns list of building specs (dicts)."""
    rng = random.Random(SEED)
    specs = []
    reserved = [
        (TOWER['x0'], TOWER['x1'], TOWER['y0'], TOWER['y1']),
    ]
    for bi, (bx0, bx1, by0, by1) in enumerate(blocks()):
        brng = random.Random(SEED * 1000 + bi)
        lots = []
        # avenue frontage lots on west / east ends of the block
        dw = brng.uniform(28, 58)
        de = brng.uniform(28, 58)
        if abs(bx1 + HERO_AVE_W / 2) < 0.1 and by0 <= TOWER['cy'] <= by1:
            de = TOWER['x1'] - TOWER['x0']
        if by0 <= (TWIN_Y[0] + TWIN_Y[1]) / 2 <= by1:
            if abs(bx1 + HERO_AVE_W / 2) < 0.1:
                de = 44.0
            if abs(bx0 - HERO_AVE_W / 2) < 0.1:
                dw = 44.0
        if bx1 - bx0 < dw + de + 20:
            dw = de = (bx1 - bx0) / 2
            mids = []
        else:
            mids = [(bx0 + dw, bx1 - de)]
        for (xa, xb, fr) in ((bx0, bx0 + dw, 'w'), (bx1 - de, bx1, 'e')):
            near_hero = dist_to_hero_ave(xa, xb) < 1
            wmin, wmax = (18, 46) if near_hero else (20, 67)
            for (ya, yb) in _split(brng, by0, by1, wmin, wmax):
                lots.append((xa, xb, ya, yb, 'ave'))
        for (ma, mb) in mids:
            ymid = (by0 + by1) / 2 + brng.uniform(-6, 6)
            for (ya, yb) in ((by0, ymid), (ymid, by1)):
                for (xa, xb) in _split(brng, ma, mb, 14, 42):
                    lots.append((xa, xb, ya, yb, 'mid'))
        for (xa, xb, ya, yb, kind) in lots:
            lot = (xa, xb, ya, yb)
            if any(_overlap(lot, r) for r in reserved):
                continue
            specs.append(dict(lot=lot, kind=kind, block=(bx0, bx1, by0, by1)))
    # assign rings, heights, styles
    out = []
    for i, s in enumerate(specs):
        x0, x1, y0, y1 = s['lot']
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r = random.Random(SEED * 7 + i * 13)
        d = dist_to_hero_ave(x0, x1)
        near = d < NEAR_DIST and NEAR_Y[0] <= cy <= NEAR_Y[1]
        mid = (not near) and (d < MID_DIST and -900 <= cy <= 1300 or d < 160)
        ring = 'near' if near else ('mid' if mid else 'far')
        h = _height(r, cx, cy, s['kind'] == 'ave')
        # keep The Tower dominant in its neighbourhood
        dt = math.hypot(cx - TOWER['cx'], cy - TOWER['cy'])
        if dt < 260:
            h = min(h, 70 + dt * 0.35)
        # leave the avenue end open for the sun: north of y=900 the avenue frontage stays lowish
        s.update(id=i, ring=ring, height=h, style=_style_for(r, h, near), seed=r.randrange(1 << 30))
        out.append(s)
    _curate(out)
    return out


def _curate(specs):
    """Hand-tuned overrides: twin towers + skybridges, supertalls, canyon rhythm."""
    rng = random.Random(SEED + 99)
    for s in specs:
        x0, x1, y0, y1 = s['lot']
        cy = (y0 + y1) / 2
        # twin towers flanking the avenue at the skybridge block
        if s['ring'] == 'near' and s['kind'] == 'ave' and dist_to_hero_ave(x0, x1) < 1 and TWIN_Y[0] - 8 <= cy <= TWIN_Y[1] + 8:
            pass
    # rebuild the twin block lots explicitly: remove avenue-frontage lots overlapping it
    twin = []
    for side in (-1, 1):
        if side < 0:
            lot = (-HERO_AVE_W / 2 - 44, -HERO_AVE_W / 2, TWIN_Y[0], TWIN_Y[1])
        else:
            lot = (HERO_AVE_W / 2, HERO_AVE_W / 2 + 44, TWIN_Y[0], TWIN_Y[1])
        twin.append(lot)
    keep = []
    for s in specs:
        if any(_overlap(s['lot'], t) for t in twin):
            continue
        keep.append(s)
    specs[:] = keep
    for k, lot in enumerate(twin):
        specs.append(dict(lot=lot, kind='ave', block=None, id=10000 + k, ring='near',
                          height=198.0 if k == 0 else 186.0, style='twin', seed=777 + k, twin_side=(-1, 1)[k]))
    # fill twin block remainder (between twin lots and block edges in y) is handled by blocks already
    # supertalls
    def set_tall(px, py, h, style):
        best = None
        for s in specs:
            x0, x1, y0, y1 = s['lot']
            if x0 <= px <= x1 and y0 <= py <= y1:
                best = s
        if best:
            best['height'] = h
            best['style'] = style
            best['supertall'] = True
    set_tall(150, 560, 415.0, 'glass')
    set_tall(-330, 980, 352.0, 'deco')
    set_tall(420, -60, 280.0, 'glass')
    set_tall(-560, 300, 262.0, 'deco')
    set_tall(80, -1120, 300.0, 'glass')
    set_tall(-180, -1180, 255.0, 'deco')
    # canyon rhythm on the avenue frontage: avoid two adjacent towers of near equal height
    front = sorted([s for s in specs if s['ring'] == 'near' and s['kind'] == 'ave' and s['style'] != 'twin'],
                   key=lambda s: (s['lot'][0] > 0, s['lot'][2]))
    prev = None
    for s in front:
        if prev is not None and (prev['lot'][0] > 0) == (s['lot'][0] > 0):
            if abs(prev['height'] - s['height']) < 12:
                s['height'] = s['height'] + (25 if rng.random() < 0.5 else -18)
                s['height'] = max(28.0, s['height'])
                s['style'] = _style_for(random.Random(s['seed']), s['height'], True)
        prev = s
