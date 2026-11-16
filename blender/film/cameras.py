"""Sixty Stories - FILM: the six camera moves (pure numpy).

Every shot is a list of keys evaluated with C1 Hermite splines; positions can be world
space or relative to the hero (offset added to his hips path, so the camera inherits his
physics but not his jitter), the aim is a subject (hero chest or a world point) placed at a
chosen normalised screen position, plus roll, lens, aperture and procedural operator shake.

design_cameras(hero) -> dict sid -> dict(frames, loc (N,3), rot (N,3,3) camera basis
                         columns (right, up, back), lens (N), fstop (N), focus (N))
"""
import math

import numpy as np

from curves import hermite, ease, Shake, gaussian_smooth, look_basis
import plan as PL

SENSOR_W = 36.0
SENSOR_H = 36.0 * 804 / 1920


def _rot_axis(M, axis, ang):
    axis = axis / np.linalg.norm(axis)
    c, s = math.cos(ang), math.sin(ang)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    R = np.eye(3) + s * K + (1 - c) * K @ K
    return R @ M


def frame_subject(eye, subj, sx, sy, lens, roll_deg):
    """Camera basis that puts world point subj at normalised screen (sx, sy) in
    [-0.5, 0.5] (x right, y up) for the given lens, with roll (deg, + = clockwise horizon)."""
    M = look_basis(eye, subj, 0.0)
    ax = math.atan(sx * SENSOR_W / lens)
    ay = math.atan(sy * SENSOR_H / lens)
    right, up = M[:, 0], M[:, 1]
    # turning the camera right moves the subject left on screen
    M = _rot_axis(M, up, ax)
    M = _rot_axis(M, M[:, 0], -ay)
    if roll_deg:
        M = _rot_axis(M, M[:, 2], math.radians(roll_deg))
    return M


def project(M, eye, p, lens):
    """world point -> normalised screen (sx, sy, depth)."""
    d = np.asarray(p, float) - eye
    x, y, z = d @ M[:, 0], d @ M[:, 1], -(d @ M[:, 2])
    if z <= 0.01:
        return None
    return (x / z * lens / SENSOR_W, y / z * lens / SENSOR_H, z)


def _k(keys, f):
    return hermite(keys, f)


def hero_chest(hero, f, dz=0.35):
    P = hero['P']
    f = np.clip(f, 0, PL.TOTAL - 1)
    i0 = int(math.floor(f))
    i1 = min(i0 + 1, PL.TOTAL - 1)
    t = f - i0
    p = P[i0] * (1 - t) + P[i1] * t
    return p + np.array([0, 0, dz])


def _shot_hero(hero, frames, lead=0.0, dz=0.35, clamp=None):
    lo, hi = clamp if clamp else (frames[0], frames[-1])
    return np.array([hero_chest(hero, min(max(f + lead, lo), hi), dz) for f in frames])


def _finish(frames, loc, subj, scr, roll, lens, fstop, shake_amp, seed, focus_pts=None):
    sh = Shake(seed)
    N = len(frames)
    rot = np.zeros((N, 3, 3))
    focus = np.zeros(N)
    loc2 = loc.copy()
    for k, f in enumerate(frames):
        n = sh(float(f))
        amp_p, amp_r = shake_amp[k]
        M = frame_subject(loc[k], subj[k], scr[k, 0], scr[k, 1], lens[k], roll[k])
        # operator / aircraft micro shake: rotation (deg) + position (m)
        M = _rot_axis(M, M[:, 1], math.radians(amp_r * n[0]))
        M = _rot_axis(M, M[:, 0], math.radians(amp_r * 0.8 * n[1]))
        M = _rot_axis(M, M[:, 2], math.radians(amp_r * 0.5 * n[2]))
        loc2[k] = loc[k] + amp_p * np.array([n[3], n[4], n[5]])
        rot[k] = M
        fp = subj[k] if focus_pts is None else focus_pts[k]
        focus[k] = max(0.3, float(-(fp - loc2[k]) @ M[:, 2]))
    return dict(frames=np.array(frames), loc=loc2, rot=rot, lens=np.asarray(lens, float),
                fstop=np.asarray(fstop, float), focus=focus, subj=subj)


def _yawpitch_basis(eye, aim_dir_keys, frames, roll):
    pass


# ============================================================================== shots
def cam_s1(hero):
    fr = PL.frames_of('s1')
    loc = _k([(0, (34.0, -488.0, 338.0)), (20, (28.0, -432.0, 300.0)),
              (47, (9.0, -352.0, 246.0), 'hold')], fr)
    # aim drifts from up-canyon (into the sun) down onto the crown / perch
    aim = _k([(0, (-4.0, 520.0, 150.0)), (14, (-8.0, 150.0, 120.0)), (32, (-14.0, -170.0, 200.0)),
              (47, (-10.0, -270.0, 226.0), 'hold')], fr)
    # aim interpolation in angle space: convert to unit directions and re-normalise
    dirs = aim - loc
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    subj = loc + dirs * 100.0
    lens = _k([(0, 22.0), (47, 30.0, 'hold')], fr)[:, 0]
    roll = _k([(0, -1.5), (30, 2.0), (47, 1.0)], fr)[:, 0]
    scr = np.zeros((len(fr), 2))
    fstop = np.full(len(fr), 8.0)
    shake = [(0.05, 0.05)] * len(fr)
    focus_pts = None
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 11, focus_pts)


def cam_s2(hero):
    fr = PL.frames_of('s2')
    loc = _k([(48, (-14.05, -296.2, 233.4)), (70, (-13.3, -297.4, 231.3)),
              (95, (-12.2, -299.4, 229.5), 'hold')], fr)
    # subject: chest early, helmet late
    head = PL.PERCH + np.array([0.25, 0.0, 0.74])
    chest = PL.PERCH + np.array([0.15, 0.0, 0.48])
    w = ease((fr - 56) / 34.0)[:, None]
    subj = chest * (1 - w) + head * w
    scr = _k([(48, (0.06, -0.04)), (70, (0.14, 0.0)), (95, (0.19, 0.04), 'hold')], fr)
    lens = _k([(48, 85.0, 'hold'), (95, 135.0, 'hold')], fr)[:, 0]
    roll = _k([(48, 3.0), (95, -1.5)], fr)[:, 0]
    fstop = _k([(48, 2.8), (95, 2.0)], fr)[:, 0]
    shake = [(0.004, 0.05)] * len(fr)
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 22)


def cam_s3(hero):
    fr = PL.frames_of('s3')
    P = hero['P']
    off = _k([(96, (0.05, -1.7, 1.5)), (104, (0.8, -2.4, 1.6)), (112, (2.4, -2.6, 2.6)),
              (122, (3.6, -2.0, 3.6)), (132, (4.1, -1.4, 4.1)), (143, (4.3, -1.1, 4.4))], fr)
    loc = P[fr] + off
    loc[:, 2] = np.minimum(loc[:, 2], 229.95)
    loc = gaussian_smooth(loc, 1.5)
    subj = _shot_hero(hero, fr, lead=0.3, dz=0.1)
    # framing: him low-centre early (over the shoulder), centre later
    scr = _k([(96, (0.08, -0.18)), (108, (0.02, -0.12)), (120, (0.0, -0.02)), (143, (0.0, 0.02))], fr)
    lens = _k([(96, 24.0), (112, 20.0), (143, 18.0)], fr)[:, 0]
    roll = _k([(96, 0.0), (112, 4.0), (128, 9.0), (143, 14.0)], fr)[:, 0]
    fstop = np.full(len(fr), 4.0)
    sp = np.linalg.norm(hero['V'][fr], axis=1)
    shake = [(0.003 + 0.0004 * s, 0.05 + 0.006 * s) for s in sp]
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 33)


def cam_s4(hero):
    fr = PL.frames_of('s4')
    P = hero['P']
    off = _k([(144, (1.2, -4.2, 1.4)), (152, (0.6, -4.8, 0.2)), (164, (-0.6, -5.2, -2.2)),
              (176, (0.2, -3.8, -3.8)), (186, (3.4, -1.6, -2.6)), (196, (4.2, 0.4, -1.0)),
              (204, (3.2, -2.6, -1.4)), (215, (1.6, -8.5, -2.2), 'hold')], fr)
    off = gaussian_smooth(off, 1.2)
    loc = P[fr] + off
    subj = _shot_hero(hero, fr, lead=0.6, dz=0.3)
    scr = _k([(144, (0.0, -0.12)), (152, (-0.04, -0.06)), (170, (0.0, 0.0)), (184, (0.0, 0.08)),
              (196, (-0.05, 0.05)), (206, (0.0, 0.05)), (215, (0.08, 0.12))], fr)
    lens = _k([(144, 24.0), (176, 20.0), (196, 22.0), (215, 26.0)], fr)[:, 0]
    roll = _k([(144, -4.0), (160, -8.0), (176, 12.0), (190, 20.0), (204, 6.0), (215, -3.0)], fr)[:, 0]
    fstop = np.full(len(fr), 2.8)
    sp = np.linalg.norm(hero['V'][fr], axis=1)
    shake = [(0.003 + 0.0003 * s, 0.04 + 0.004 * s) for s in sp]
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 44)


def cam_s5(hero):
    fr = PL.frames_of('s5')
    sun = np.array(PL.META['sun']['direction_to_sun'])
    slot = PL.SLOT
    # head-on from up the avenue (sun behind camera): the bridges stack, he comes at us
    loc = _k([(216, (-2.6, 334.0, 47.0)), (245, (-2.2, 350.0, 44.5)), (253, (-2.1, 351.5, 50.0)),
              (263, (-2.0, 352.0, 65.0), 'hold')], fr)
    subj = _shot_hero(hero, fr, lead=0.4, dz=0.2)
    scr = _k([(216, (0.0, -0.02)), (232, (0.0, 0.0)), (245, (0.0, 0.0)), (263, (0.0, 0.04))], fr)
    lens = _k([(216, 40.0), (236, 72.0), (246, 95.0), (252, 125.0), (263, 135.0, 'hold')], fr)[:, 0]
    roll = _k([(216, -2.0), (245, 0.0), (263, 1.5)], fr)[:, 0]
    fstop = _k([(216, 2.8), (263, 2.8)], fr)[:, 0]
    shake = [(0.004, 0.012)] * len(fr)
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 55)


def cam_s6(hero):
    fr = PL.frames_of('s6')
    P = hero['P']
    apex = P[int(hero['key']['s6_apex'])]
    # spiral: polar offsets around the hero (theta from +X, CCW seen from above)
    keys = [(264, (0.0, -9.0, -2.6)), (282, (0.4, -8.5, -1.4)), (294, (0.3, -10.0, 1.8)),
            (304, (0.2, -13.5, 5.0))]
    keys += [(312, (0.5, -38.0, 22.0)), (319, (1.0, -190.0, 110.0)), (326, (-0.5, -400.0, 195.0)),
             (335, (-0.8, -470.0, 218.0), 'hold')]
    off = _k(keys, fr)
    loc = P[fr] + off
    subj = _shot_hero(hero, fr, lead=0.0, dz=0.4)
    subj_h = subj
    wa = ease((fr - 304) / 22.0)
    scr = _k([(264, (0.0, 0.12)), (290, (0.0, 0.05)), (304, (0.03, -0.06)), (318, (0.0, -0.25)),
              (335, (0.0, -0.32), 'hold')], fr)
    lens = _k([(264, 26.0), (290, 24.0), (306, 21.0), (318, 19.0), (335, 18.0, 'hold')], fr)[:, 0]
    roll = _k([(264, 0.0), (290, -6.0), (304, 10.0), (316, 3.0), (335, 0.0, 'hold')], fr)[:, 0]
    fstop = _k([(264, 2.8), (300, 4.0), (318, 8.0), (335, 8.0)], fr)[:, 0]
    shake = [(0.004 * (1 - wi), 0.05 * (1 - 0.7 * wi)) for wi in wa]
    focus_pts = subj_h
    return _finish(fr, loc, subj, scr, roll, lens, fstop, shake, 66, focus_pts)


def design_cameras(hero):
    return dict(s1=cam_s1(hero), s2=cam_s2(hero), s3=cam_s3(hero), s4=cam_s4(hero),
                s5=cam_s5(hero), s6=cam_s6(hero))


def camera_report(hero, cams):
    import physics as ph
    out = []
    for sid, c in cams.items():
        d, idx = ph.box_distance(c['loc'], PL.BOXES)
        sp = np.r_[0, np.linalg.norm(np.diff(c['loc'], axis=0), axis=1) * 24 * 3.6]
        acc = np.r_[0, 0, np.linalg.norm(np.diff(c['loc'], 2, axis=0), axis=1) * 24 * 24]
        for k, f in enumerate(c['frames']):
            pr = project(c['rot'][k], c['loc'][k], hero_chest(hero, f), c['lens'][k])
            out.append('%s %3d cam %s %5.0f km/h acc %6.1f clr %5.1f %-12s lens %5.1f f/%.1f foc %6.1f hero %s' % (
                sid, f, np.round(c['loc'][k], 1), sp[k], acc[k], d[k], PL.BOX_NAMES[idx[k]],
                c['lens'][k], c['fstop'][k], c['focus'][k],
                None if pr is None else (round(pr[0], 2), round(pr[1], 2), round(pr[2], 1))))
    return '\n'.join(out)


if __name__ == '__main__':
    h = PL.design_hero()
    print(camera_report(h, design_cameras(h)))
