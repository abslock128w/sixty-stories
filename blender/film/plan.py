"""Sixty Stories - FILM plan: hero trajectory, poses, lines and per-shot cameras.

Pure python + numpy (no bpy) so it can be iterated and checked numerically.
Global frame index i == Blender frame number, 0..335.

    plan = build_plan()          # dict with per-frame arrays and event lists
"""
import math

import numpy as np

import physics as ph
from curves import ease, hermite, Shake, gaussian_smooth

FPS = 24
TOTAL = 336
SHOTS = [
    dict(id='s1', title='THE CITY', start=0, count=48, lens_mm=32,
         logline='Golden hour over sixty-storey canyons; the city holds its breath.'),
    dict(id='s2', title='THE PERCH', start=48, count=48, lens_mm=120,
         logline='Two hundred and twenty-eight metres up, Vesper waits on the steel prow.'),
    dict(id='s3', title='THE DROP', start=96, count=48, lens_mm=20,
         logline='He tips forward and lets the tower fall away.'),
    dict(id='s4', title='THE SWING', start=144, count=72, lens_mm=24,
         logline='A line snaps taut above the traffic and the fall becomes flight.'),
    dict(id='s5', title='THREAD THE NEEDLE', start=216, count=48, lens_mm=135,
         logline='Fourteen metres of air between two skybridges. He takes it at a hundred.'),
    dict(id='s6', title='APEX', start=264, count=72, lens_mm=28,
         logline='Weightless against the sun, the whole city below him as the lights come on.'),
]
SHOT_OF = np.zeros(TOTAL, int)
for k, s in enumerate(SHOTS):
    SHOT_OF[s['start']:s['start'] + s['count']] = k

META = ph.load_meta()
BOXES, BOX_NAMES = ph.obstacle_boxes(META)
PERCH = np.array(META['tower']['gargoyle']['top_center'], float)
SLOT = np.array(META['s5_gap']['gap_center'], float)


def shot(i):
    return SHOTS[SHOT_OF[i]]


def frames_of(sid):
    s = [x for x in SHOTS if x['id'] == sid][0]
    return np.arange(s['start'], s['start'] + s['count'])


# =============================================================================== hero
def _sample(fr, P, V, frames):
    """resample integrate() output (sub-frame) at integer frames"""
    out_p, out_v = [], []
    for f in frames:
        k = np.argmin(np.abs(fr - f))
        out_p.append(P[k])
        out_v.append(V[k])
    return np.array(out_p), np.array(out_v)


def _fill(P, V, mode, frs, Ps, Vs, m, a, b):
    lo, hi = min(frs), max(frs)
    for i in range(int(math.ceil(lo - 1e-6)), int(math.floor(hi + 1e-6)) + 1):
        if a <= i <= b:
            k = int(np.argmin(np.abs(frs - i)))
            P[i], V[i] = Ps[k], Vs[k]
            mode[i] = m


def design_hero():
    P = np.zeros((TOTAL, 3))
    V = np.zeros((TOTAL, 3))
    mode = [''] * TOTAL          # 'perch' | 'free' | 'line'
    line = [None] * TOTAL        # (side, anchor) while attached / firing
    webs = []                    # dict(side, anchor, on, taut, off, fire_from)
    hips0 = PERCH + np.array([0.12, 0.0, 0.40])   # crouch hips (approx; build uses real)

    # ---- s1 + s2: on the perch (rig origin pinned on the perch top, see build)
    for i in range(0, 96):
        P[i] = hips0
        mode[i] = 'perch'

    # ---- s3: push off and dive (scripted, cheated acceleration toward ~215 km/h)
    f3 = frames_of('s3')
    vz_keys = [(95, 0.0), (97, 2.6), (103, 0.0), (110, -12.0), (118, -38.0), (126, -54.0),
               (134, -60.0), (143, -62.0)]
    p = hips0.copy() + np.array([0.15, 0, 0.0])
    for i in f3:
        vz = hermite(vz_keys, i)[0, 0]
        vx = 1.2 + 6.0 * math.exp(-(i - 96) / 9.0)
        vy = 0.9 * ease((i - 100) / 30.0)
        v = np.array([vx, vy, vz])
        if i > f3[0]:
            p = p + v / FPS
        P[i] = p
        V[i] = v
        mode[i] = 'free'

    # ---- s4: east line, pendulum bottoming ~28 m above the street
    A4 = ph.wall_point(BOXES, 'E', -200.0, 92.0)
    fb, pb, vb = 180.0, np.array([-6.0, A4[1], 28.0]), np.array([0, 35.0, 0])
    L4 = float(np.linalg.norm(pb - A4))
    f_taut4, f_fire4, f_rel4 = 151.0, 146.0, 207.0
    fr, Pp, Vp = ph.integrate(pb, vb, fb, f_taut4, A4, L4, sub=20)
    p_t, v_t = Pp[-1], Vp[-1]
    n = (p_t - A4) / L4
    v_pre = v_t + 26.0 * n          # outward radial speed lost when the line snaps taut
    fr0, P0, V0 = ph.integrate(p_t, v_pre, f_taut4, 144, sub=20)
    fr1, P1, V1 = ph.integrate(pb, vb, fb, f_rel4, A4, L4, sub=20)
    fr2, P2, V2 = ph.integrate(P1[-1], V1[-1], f_rel4, 215, sub=20)
    for frs, Ps, Vs, m in ((fr0, P0, V0, 'free'), (fr, Pp, Vp, 'line'), (fr1, P1, V1, 'line'),
                           (fr2, P2, V2, 'free')):
        _fill(P, V, mode, frs, Ps, Vs, m, 144, 215)
    for i in range(int(f_fire4), int(f_rel4)):
        line[i] = ('R', A4)
        mode[i] = 'line'
    webs.append(dict(side='R', anchor=A4, on=int(f_fire4), taut=int(f_taut4), off=int(f_rel4), name='web_s4'))

    # ---- s5: west line low and fast, release, flip through the skybridge slot
    fs5 = 245.0
    ps = np.array([-1.0, SLOT[1], SLOT[2] + 0.2])
    vs = np.array([-1.5, 28.0, 2.5])
    f_rel5, f_taut5, f_fire5 = 235.0, 221.0, 217.0
    frb, Pb, Vb = ph.integrate(ps, vs, fs5, f_rel5, sub=20)
    pr, vr = Pb[-1], Vb[-1]
    A5, L5 = _anchor_perp(pr, vr, 'W', 105.0)
    frs5, Ps5, Vs5 = ph.integrate(pr, vr, f_rel5, f_taut5, A5, L5, sub=20)
    pt5, vt5 = Ps5[-1], Vs5[-1]
    n5 = (pt5 - A5) / L5
    fr50, P50, V50 = ph.integrate(pt5, vt5 + 6.0 * n5, f_taut5, 216, sub=20)
    fra, Pa, Va = ph.integrate(ps, vs, fs5, 263, sub=20)
    for frs, Ps, Vs, m in ((fr50, P50, V50, 'free'), (frs5, Ps5, Vs5, 'line'), (frb, Pb, Vb, 'free'),
                           (fra, Pa, Va, 'free')):
        _fill(P, V, mode, frs, Ps, Vs, m, 216, 263)
    for i in range(int(f_fire5), int(f_rel5)):
        line[i] = ('L', A5)
        mode[i] = 'line'
    webs.append(dict(side='L', anchor=A5, on=int(f_fire5), taut=int(f_taut5), off=int(f_rel5), name='web_s5'))
    # fires again at the end of s5 (line still flying when we cut)
    A5b = ph.wall_point(BOXES, 'E', 452.0, 118.0)
    webs.append(dict(side='R', anchor=A5b, on=257, taut=999, off=264, name='web_s5b', fly_frames=9))

    # ---- s6: last rising swing (east), release near the top, apex hang, free fall
    fq = 284.0
    f_rel6 = 279.0
    pr6 = np.array([-2.5, 520.0, 136.0])
    vr6 = np.array([0.5, 6.0, 5.0])
    frq, Pq, Vq = ph.integrate(pr6, vr6, f_rel6, 335, sub=20)
    fq = float(frq[np.argmax(Pq[:, 2])])
    q, vq = Pq[np.argmax(Pq[:, 2])], Vq[np.argmax(Pq[:, 2])]
    A6, L6 = _anchor_perp(pr6, vr6, 'E', 172.0)
    fr6, P6, V6 = ph.integrate(pr6, vr6, f_rel6, 264, A6, L6, sub=20)
    for frs, Ps, Vs, m in ((fr6, P6, V6, 'line'), (frq, Pq, Vq, 'free')):
        _fill(P, V, mode, frs, Ps, Vs, m, 264, 335)
    for i in range(264, int(f_rel6)):
        line[i] = ('R', A6)
        mode[i] = 'line'
    webs.append(dict(side='R', anchor=A6, on=264, taut=264, off=int(f_rel6), name='web_s6'))

    return dict(P=P, V=V, mode=mode, line=line, webs=webs,
                anchors=dict(s4=A4, s5=A5, s5b=A5b, s6=A6), L=dict(s4=L4, s5=L5, s6=L6),
                key=dict(s4_bottom=fb, s4_taut=f_taut4, s4_fire=f_fire4, s4_rel=f_rel4,
                         s5_slot=fs5, s5_rel=f_rel5, s5_taut=f_taut5, s5_fire=f_fire5,
                         s6_rel=f_rel6, s6_apex=fq))


def _anchor_perp(p, v, side, az):
    """Anchor on the `side` street wall at height az such that the line is perpendicular
    to the velocity at p (so the release is tangent to the circle)."""
    vh = v / np.linalg.norm(v)
    up = np.array([0, 0, 1.0])
    up = up - vh * up.dot(vh)
    up /= np.linalg.norm(up)
    lat = np.cross(vh, up)
    sols = []
    for a in np.linspace(-1.5, 1.5, 6001):
        u = math.cos(a) * up + math.sin(a) * lat
        if u[2] <= 0.05:
            continue
        L = (az - p[2]) / u[2]
        A = p + L * u
        w = ph.wall_point(BOXES, side, A[1], A[2])
        if w is not None and abs(A[0] - w[0]) < 0.08:
            sols.append((abs(a), A, L, w))
    if not sols:
        raise RuntimeError('no anchor for %s at z %.1f' % (side, az))
    sols.sort(key=lambda s: s[0])
    _, A, L, w = sols[0]
    return w.copy(), float(np.linalg.norm(w - p))


# ---------------------------------------------------------------------- pose schedule
# (frame, pose, weight, interp) - named poses from hero_api.POSES ('_L' variants mirrored)
POSE_KEYS = [
    (0, 'perch_crouch', 1.0), (40, 'perch_crouch', 1.0), (62, 'perch_crouch', 1.0),
    (68, 'perch_look_up', 0.55), (74, 'perch_look_up', 1.0), (86, 'perch_look_up', 1.0),
    (95, 'leap', 0.22),
    # s3
    (96, 'leap', 0.55), (100, 'leap', 1.0), (106, 'leap', 1.0), (112, 'dive', 0.6), (118, 'dive', 1.0),
    (132, 'dive', 1.0), (138, 'dive_reach', 0.7), (143, 'dive_reach', 1.0),
    # s4
    (144, 'dive_reach', 1.0), (146, 'shoot_R', 1.0), (150, 'shoot_R', 1.0), (154, 'swing_R', 0.7),
    (158, 'swing_R', 1.0), (170, 'swing_R', 1.0), (180, 'swing_tuck', 1.0), (196, 'swing_tuck', 1.0),
    (203, 'swing_R', 1.0), (207, 'release_arch', 0.6), (211, 'release_arch', 1.0), (215, 'release_arch', 1.0),
    # s5
    (216, 'release_arch', 1.0), (218, 'shoot_L', 1.0), (221, 'shoot_L', 1.0), (224, 'swing_L', 1.0),
    (230, 'swing_tuck_L', 1.0), (234, 'swing_tuck_L', 1.0), (238, 'flip_tuck', 1.0), (252, 'flip_tuck', 1.0),
    (256, 'freefall_spread', 0.7), (259, 'shoot_R', 1.0), (263, 'shoot_R', 1.0),
    # s6
    (264, 'swing_R', 1.0), (272, 'swing_R', 1.0), (276, 'release_arch', 0.8), (280, 'release_arch', 1.0),
    (285, 'apex_classic', 1.0), (298, 'apex_classic', 1.0), (308, 'freefall_spread', 1.0),
    (335, 'freefall_spread', 1.0),
]
# head look offsets (frame, yaw, pitch): yaw + = toward his left
HEAD_KEYS = [(62, 0, 0), (76, 50, -4), (86, 60, -6), (94, 35, 4)]


# ------------------------------------------------------------------ body orientation
def body_intent(hero):
    """Per frame desired body orientation: ('line', side, anchor, travel) or
    ('free', front, up) world vectors, or ('perch',)."""
    P, V = hero['P'], hero['V']
    out = []
    for i in range(TOTAL):
        m = hero['mode'][i]
        v = V[i]
        sp = np.linalg.norm(v) + 1e-9
        if m == 'perch':
            out.append(('perch',))
        elif m == 'line' and hero['line'][i] is not None:
            side, A = hero['line'][i]
            trav = v / sp if sp > 1 else np.array([0, 1.0, 0])
            out.append(('line', side, A, trav))
        else:
            out.append(('free',) + free_orientation(i, P, V))
    return out


def free_orientation(i, P, V):
    v = V[i]
    vh = v / (np.linalg.norm(v) + 1e-9)
    if 96 <= i <= 143:
        # dive: body axis (up) leads the velocity: head toward the street, front (chest)
        # toward the east / avenue, rotating from upright as he tips over
        t = ease((i - 96) / 20.0, 'smooth')
        up = (1 - t) * np.array([0.25, 0, 1.0]) + t * np.array([0.1, 0.75, -0.65])
        front = (1 - t) * np.array([1.0, 0, -0.2]) + t * np.array([0.35, 0.0, -1.0])
        return _ortho(front, up)
    if 144 <= i <= 150:
        return _ortho(np.array([0.2, 0.3, -1.0]), np.array([0.1, 0.8, -0.45]))
    if 207 <= i <= 215:   # release arch: chest to the sky, travelling into the sun
        t = ease((i - 207) / 8.0)
        up = (1 - t) * np.array([0, 0.6, 1.0]) + t * np.array([0, 0.9, 0.7])
        return _ortho(np.array([0, 0.3, 1.0]) * (1 - t) + np.array([0, 0.2, 1.0]) * t, up)
    if 216 <= i <= 220:
        return _ortho(np.array([0, 1.0, 0.3]), np.array([0, 0.4, 1.0]))
    if 235 <= i <= 256:   # front flip about the travel-lateral axis through the slot
        a = 2 * math.pi * ease((i - 236.5) / 17.0, 'smooth')
        up0 = np.array([0, 0.25, 1.0])
        fr0 = np.array([0, 1.0, -0.25])
        ax = np.array([1.0, 0, 0])   # rotate about +X: front flip when travelling +Y
        up = _rot(up0, ax, a)
        fr = _rot(fr0, ax, a)
        return _ortho(fr, up)
    if 257 <= i <= 263:
        return _ortho(np.array([0, 1.0, 0.1]), np.array([0, 0.2, 1.0]))
    if 276 <= i:
        # release, half twist to face back toward the city (and the camera), weightless hang
        t = ease((i - 276) / 10.0)
        yaw = math.pi * t
        fr = np.array([math.sin(yaw) * 0.0 + 0.0, math.cos(yaw), 0.15])
        fr = np.array([-math.sin(yaw) * 1.0, math.cos(yaw), 0.15 + 0.1 * t])
        up = np.array([0, 0, 1.0]) + (1 - t) * np.array([0, 0.5, 0])
        return _ortho(fr, up)
    return _ortho(np.array([0, 1.0, 0]), np.array([0, 0, 1.0]))


def _rot(v, ax, a):
    ax = ax / np.linalg.norm(ax)
    return v * math.cos(a) + np.cross(ax, v) * math.sin(a) + ax * ax.dot(v) * (1 - math.cos(a))


def _ortho(front, up):
    up = np.asarray(up, float)
    up = up / np.linalg.norm(up)
    front = np.asarray(front, float)
    front = front - up * front.dot(up)
    front /= np.linalg.norm(front)
    return front, up


# ============================================================================= checks
def report_hero(hero):
    P, V = hero['P'], hero['V']
    d, idx = ph.box_distance(P, BOXES)
    sp = ph.speed_kmh(V)
    lines = []
    for i in range(96, TOTAL):
        tag = ''
        if hero['line'][i] is not None:
            side, A = hero['line'][i]
            c, bi, t = ph.segment_clearance(P[i], A, BOXES, n=80, skip_end=6.0)
            tag = 'line clr %.1f %s' % (c, BOX_NAMES[bi])
        lines.append('%3d %-5s %s %4.0f km/h clr %5.1f %-14s %s' % (
            i, hero['mode'][i], np.round(P[i], 1), sp[i], d[i], BOX_NAMES[idx[i]], tag))
    return '\n'.join(lines)


if __name__ == '__main__':
    h = design_hero()
    print(report_hero(h))
    print(h['anchors'], h['L'])
