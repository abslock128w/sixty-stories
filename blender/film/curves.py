"""Small curve / easing / noise helpers for camera work (pure numpy)."""
import math

import numpy as np


def ease(t, kind='smooth'):
    t = np.clip(t, 0.0, 1.0)
    if kind == 'linear':
        return t
    if kind == 'smooth':      # quintic smootherstep: zero vel + acc at both ends
        return t * t * t * (t * (6 * t - 15) + 10)
    if kind == 'in':          # starts slow
        return t * t * t
    if kind == 'out':         # ends slow
        return 1 - (1 - t) ** 3
    if kind == 'in2':
        return t * t
    if kind == 'out2':
        return 1 - (1 - t) ** 2
    raise ValueError(kind)


def hermite(keys, f):
    """Catmull-Rom style spline through keys [(frame, value(array-like)), ...] evaluated at
    frame(s) f. Tangents are finite differences w.r.t. frame (non-uniform), so motion is
    C1 through every key. Ends use zero tangent if the key is marked by a tuple of 3 with
    'hold' (ease in/out at that key)."""
    fs = np.array([k[0] for k in keys], float)
    vs = np.array([np.atleast_1d(np.asarray(k[1], float)) for k in keys])
    hold = [len(k) > 2 and k[2] == 'hold' for k in keys]
    n = len(fs)
    m = np.zeros_like(vs)
    for i in range(n):
        if hold[i]:
            continue
        if i == 0:
            m[i] = (vs[1] - vs[0]) / (fs[1] - fs[0])
        elif i == n - 1:
            m[i] = (vs[-1] - vs[-2]) / (fs[-1] - fs[-2])
        else:
            m[i] = ((vs[i + 1] - vs[i]) / (fs[i + 1] - fs[i]) * (fs[i] - fs[i - 1]) +
                    (vs[i] - vs[i - 1]) / (fs[i] - fs[i - 1]) * (fs[i + 1] - fs[i])) / (fs[i + 1] - fs[i - 1])
    f = np.atleast_1d(np.asarray(f, float))
    out = np.zeros((len(f), vs.shape[1]))
    for j, x in enumerate(f):
        if x <= fs[0]:
            out[j] = vs[0] + m[0] * (x - fs[0]) * 0
            continue
        if x >= fs[-1]:
            out[j] = vs[-1]
            continue
        i = np.searchsorted(fs, x) - 1
        h = fs[i + 1] - fs[i]
        t = (x - fs[i]) / h
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        out[j] = h00 * vs[i] + h10 * h * m[i] + h01 * vs[i + 1] + h11 * h * m[i + 1]
    return out


class Shake:
    """Deterministic smooth noise: sum of incommensurate sines per channel."""

    def __init__(self, seed, channels=6, octaves=4):
        rng = np.random.default_rng(seed)
        self.freq = rng.uniform(0.6, 1.4, (channels, octaves)) * (1.7 ** np.arange(octaves))[None] * 0.35
        self.phase = rng.uniform(0, 2 * math.pi, (channels, octaves))
        self.amp = (0.55 ** np.arange(octaves))[None].repeat(channels, 0)

    def __call__(self, f):
        """f in frames -> (channels,) in roughly [-1, 1]"""
        t = f / 24.0
        return (self.amp * np.sin(2 * math.pi * self.freq * t + self.phase)).sum(1) / 1.6


def gaussian_smooth(arr, sigma, axis=0):
    """Edge-preserving-ish smoothing of a per-frame array (reflect padding)."""
    if sigma <= 0:
        return arr
    r = int(math.ceil(sigma * 3))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = np.moveaxis(np.asarray(arr, float), axis, 0)
    pad = np.concatenate([2 * a[:1] - a[r:0:-1], a, 2 * a[-1:] - a[-2:-r - 2:-1]], 0)
    out = np.zeros_like(a)
    for i, w in enumerate(k):
        out += w * pad[i:i + len(a)]
    return np.moveaxis(out, 0, axis)


def look_basis(eye, target, roll_deg=0.0, up=(0, 0, 1)):
    """camera basis (right, up, back) as 3x3 columns for Blender camera (-Z forward, +Y up)."""
    eye = np.asarray(eye, float)
    fwd = np.asarray(target, float) - eye
    fwd /= np.linalg.norm(fwd)
    upv = np.asarray(up, float)
    right = np.cross(fwd, upv)
    if np.linalg.norm(right) < 1e-6:
        right = np.cross(fwd, np.array([0, 1.0, 0]))
    right /= np.linalg.norm(right)
    cup = np.cross(right, fwd)
    r = math.radians(roll_deg)
    right2 = right * math.cos(r) + cup * math.sin(r)
    cup2 = cup * math.cos(r) - right * math.sin(r)
    return np.stack([right2, cup2, -fwd], 1)
