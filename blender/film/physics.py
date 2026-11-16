"""Sixty Stories - FILM: point-mass physics for the hero (pure numpy, no bpy).

The hero's centre of mass (hips) is integrated with gravity, light quadratic air drag and
an inextensible line (rope constraint, inelastic when it snaps taut). Each shot gets a list
of events; the integrator returns per-frame samples (24 fps) plus sub-frame detail.
"""
import json
import math
import os

import numpy as np

FPS = 24.0
G = 9.81
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
META = os.path.join(ROOT, 'blender', 'out', 'city_meta.json')


# --------------------------------------------------------------------- obstacles
def load_meta():
    with open(META) as f:
        return json.load(f)


def obstacle_boxes(meta=None, near=400.0):
    """Axis-aligned boxes (x0,x1,y0,y1,z0,z1) for every building tier near the avenue,
    The Tower, the two skybridges and the perch ornament."""
    meta = meta or load_meta()
    boxes, names = [], []
    for b in meta['buildings']:
        cx, cy = b['footprint_center']
        if abs(cx) > near:
            continue
        top = b['roof_z']
        for t in b['tiers']:
            x0, x1, y0, y1 = t['bbox']
            boxes.append((x0, x1, y0, y1, t['z0'], t['z1']))
            names.append(b['name'])
        # crown / spire above the roof: approximate by the last tier's inner box shrunk
        if b.get('top_z', top) > top + 1:
            x0, x1, y0, y1 = b['tiers'][-1]['bbox']
            sx, sy = (x1 - x0) * 0.3, (y1 - y0) * 0.3
            boxes.append((x0 + sx, x1 - sx, y0 + sy, y1 - sy, top, b['top_z']))
            names.append(b['name'] + '_crown')
    tw = meta['tower']
    for t in tw['tiers']:
        x0, x1, y0, y1 = t['bbox']
        boxes.append((x0, x1, y0, y1, t['z0'], t['z1']))
        names.append('THE_TOWER')
    boxes.append((-50, -20, -310, -290, 240, tw['crown_top_z']))
    names.append('THE_TOWER_crown')
    g = meta['s5_gap']
    y = g['y']
    d = g['bridge_depth_y'] / 2
    lo = g['bridge_low_z']
    hi = g['bridge_high_z']
    boxes.append((-16, 16, y - d - 0.15, y + d + 0.15, g['lowest_point_low_bridge_soffit_z'], lo[1]))
    names.append('BRIDGE_low')
    boxes.append((-16, 16, y - d - 0.15, y + d + 0.15, hi[0] - 0.15, hi[1]))
    names.append('BRIDGE_high')
    # perch ornament: from the wall out to the beak tip, a little below the top
    gg = tw['gargoyle']
    tc = gg['top_center']
    boxes.append((-16.0, gg['beak_tip'][0], tc[1] - 0.5, tc[1] + 0.5, tc[2] - 3.0, tc[2]))
    names.append('PERCH')
    return np.array(boxes, float), names


def box_distance(P, boxes):
    """P (N,3) -> (N,) distance to the nearest box (0 inside), and index of that box."""
    P = np.atleast_2d(P)
    lo = boxes[:, [0, 2, 4]][None]
    hi = boxes[:, [1, 3, 5]][None]
    d = np.maximum(np.maximum(lo - P[:, None, :], P[:, None, :] - hi), 0.0)
    dist = np.sqrt((d ** 2).sum(-1))
    i = dist.argmin(1)
    return dist[np.arange(len(P)), i], i


def segment_clearance(a, b, boxes, n=60, skip_end=0.0):
    """min distance from the segment a->b (sampled) to boxes; skip_end metres at b ignored."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    L = np.linalg.norm(b - a)
    tmax = 1.0 - (skip_end / L if L > 0 else 0)
    t = np.linspace(0, max(tmax, 0), n)[:, None]
    d, i = box_distance(a + (b - a) * t, boxes)
    k = d.argmin()
    return d[k], i[k], float(t[k, 0])


# --------------------------------------------------------------------- integrator
def simulate(p0, v0, t0, t1, events, drag=0.0016, gscale=1.0, sub=200, gfun=None):
    """Integrate from global frame t0 to t1 (frames, floats).
    events: list of dicts sorted by frame:
      {'f': frame, 'type': 'attach', 'anchor': xyz, 'L': length or None (=current), 'reel': m/s}
      {'f': frame, 'type': 'release'}
      {'f': frame, 'type': 'kick', 'dv': xyz}       (instant impulse, e.g. push-off)
    Returns dict of arrays sampled at integer frames t0..t1 (inclusive) and sub-frames.
    """
    dt = 1.0 / (FPS * sub)
    p = np.array(p0, float)
    v = np.array(v0, float)
    ev = sorted(events, key=lambda e: e['f'])
    k = 0
    rope = None  # (anchor, L, reel)
    frames = []
    P, V, A, R, T = [], [], [], [], []
    nsteps = int(round((t1 - t0) * sub))
    for s in range(nsteps + 1):
        f = t0 + s / sub
        while k < len(ev) and ev[k]['f'] <= f + 1e-9:
            e = ev[k]
            if e['type'] == 'attach':
                anc = np.array(e['anchor'], float)
                L = e.get('L') or float(np.linalg.norm(p - anc))
                rope = [anc, L, e.get('reel', 0.0)]
            elif e['type'] == 'release':
                rope = None
            elif e['type'] == 'kick':
                v = v + np.array(e['dv'], float)
            k += 1
        if s % sub == 0:
            frames.append(f)
            P.append(p.copy())
            V.append(v.copy())
            A.append(None if rope is None else rope[0].copy())
            R.append(None if rope is None else rope[1])
        if s == nsteps:
            break
        gs = gscale if gfun is None else gfun(f)
        acc = np.array([0, 0, -G * gs]) - drag * np.linalg.norm(v) * v
        v = v + acc * dt
        p = p + v * dt
        if rope is not None:
            anc, L, reel = rope
            if reel:
                rope[1] = L = max(L - reel * dt, 2.0)
            d = p - anc
            r = np.linalg.norm(d)
            if r > L:
                n = d / r
                p = anc + n * L
                vr = v.dot(n)
                if vr > 0:
                    v = v - vr * n
    return dict(f=np.array(frames), P=np.array(P), V=np.array(V), anchor=A, L=R)


def speed_kmh(V):
    return np.linalg.norm(V, axis=-1) * 3.6


def wall_point(boxes, side, y, z):
    """Face point on the avenue street wall at (y, z): side 'E' (x>0) or 'W' (x<0).
    Returns xyz or None when there is no building there."""
    b = boxes
    m = (b[:, 2] <= y) & (b[:, 3] >= y) & (b[:, 4] <= z) & (b[:, 5] >= z)
    if side == 'E':
        m &= b[:, 0] >= 15.0
        m &= b[:, 0] < 40.0
        if not m.any():
            return None
        return np.array([b[m, 0].min(), y, z])
    m &= b[:, 1] <= -15.0
    m &= b[:, 1] > -40.0
    if not m.any():
        return None
    return np.array([b[m, 1].max(), y, z])


# --------------------------------------------------------------------- piecewise design
def integrate(p, v, f0, f1, anchor=None, L=None, drag=0.0016, gscale=1.0, sub=100):
    """Integrate from frame f0 to f1 (f1 < f0 runs time backwards, exactly reversing the
    forward equations). With an anchor the hero rides a sphere of radius L (taut line).
    Returns (frames, P, V) sampled at every 1/sub frame including both ends."""
    n = max(1, int(round(abs(f1 - f0) * sub)))
    h = (f1 - f0) / n / FPS  # signed seconds per step
    p = np.array(p, float)
    v = np.array(v, float)
    A = None if anchor is None else np.array(anchor, float)
    if A is not None and L is None:
        L = float(np.linalg.norm(p - A))
    Fs, Ps, Vs = [f0], [p.copy()], [v.copy()]

    def acc(p, v):
        a = np.array([0, 0, -G * gscale]) - drag * np.linalg.norm(v) * v
        if A is not None:
            d = p - A
            r = np.linalg.norm(d)
            nn = d / r
            # tension keeps |d| = L: centripetal + cancel outward accel
            a = a - nn * (a.dot(nn) + v.dot(v) / r)
        return a

    for s in range(n):
        # RK4
        k1v = acc(p, v); k1p = v
        k2v = acc(p + k1p * h / 2, v + k1v * h / 2); k2p = v + k1v * h / 2
        k3v = acc(p + k2p * h / 2, v + k2v * h / 2); k3p = v + k2v * h / 2
        k4v = acc(p + k3p * h, v + k3v * h); k4p = v + k3v * h
        p = p + h / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
        v = v + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        if A is not None:
            d = p - A
            nn = d / np.linalg.norm(d)
            p = A + nn * L
            v = v - nn * v.dot(nn)
        Fs.append(f0 + (s + 1) * (f1 - f0) / n)
        Ps.append(p.copy())
        Vs.append(v.copy())
    return np.array(Fs), np.array(Ps), np.array(Vs)
