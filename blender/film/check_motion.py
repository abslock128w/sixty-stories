"""Numeric continuity check of the plan: hero and camera speed / acceleration / angular
velocity per frame, clearance to buildings, hero screen position. Flags spikes.

    $PY check_motion.py [--all]
"""
import math
import sys

import numpy as np

import physics as ph
import plan as PL
import cameras as CAM


def ang(Ma, Mb):
    R = Ma.T @ Mb
    c = (np.trace(R) - 1) / 2
    return math.degrees(math.acos(max(-1, min(1, c))))


def main():
    full = '--all' in sys.argv
    hero = PL.design_hero()
    cams = CAM.design_cameras(hero)
    P = hero['P']
    flags = []
    for sh in PL.SHOTS:
        sid = sh['id']
        c = cams[sid]
        fr = c['frames']
        L = c['loc']
        v = np.r_[np.nan, np.linalg.norm(np.diff(L, axis=0), axis=1) * 24]
        a = np.r_[np.nan, np.nan, np.linalg.norm(np.diff(L, 2, axis=0), axis=1) * 576]
        w = [np.nan] + [ang(c['rot'][k - 1], c['rot'][k]) for k in range(1, len(fr))]
        dw = np.r_[np.nan, np.diff(w)]
        d, idx = ph.box_distance(L, PL.BOXES)
        hv = np.linalg.norm(hero['V'][fr], axis=1) * 3.6
        ha = np.r_[np.nan, np.nan, np.linalg.norm(np.diff(P[fr], 2, axis=0), axis=1) * 576] if sid not in ('s1', 's2') else np.zeros(len(fr))
        print('== %s  cam speed %4.0f..%4.0f km/h  max acc %6.1f m/s2  max ang %.2f deg/frame  min clr %.1f m (%s)' % (
            sid, np.nanmin(v) * 3.6, np.nanmax(v) * 3.6, np.nanmax(a), np.nanmax(w), d.min(), PL.BOX_NAMES[idx[d.argmin()]]))
        for k, f in enumerate(fr):
            pr = CAM.project(c['rot'][k], L[k], CAM.hero_chest(hero, f), c['lens'][k])
            onscreen = pr is not None and abs(pr[0]) < 0.5 and abs(pr[1]) < 0.5
            size = None
            if pr is not None:
                size = 1.8 / (pr[2] * CAM.SENSOR_H / c['lens'][k])
            bad = []
            if d[k] < 1.5:
                bad.append('CLEARANCE %.2f %s' % (d[k], PL.BOX_NAMES[idx[k]]))
            if k >= 2 and not np.isnan(dw[k]) and abs(dw[k]) > 0.6:
                bad.append('ANG JERK %.2f' % dw[k])
            if sid not in ('s1',) and not onscreen:
                bad.append('HERO OFFSCREEN')
            if sid in ('s3', 's4', 's5', 's6') and size is not None and size < 0.125 and f < 312:
                bad.append('HERO SMALL %.2f' % size)
            if bad:
                flags.append((sid, f, bad))
            if full:
                print('%s %3d v %5.0f a %6.1f w %5.2f clr %5.1f hero %s size %s hv %4.0f ha %6.1f %s' % (
                    sid, f, v[k] * 3.6 if not np.isnan(v[k]) else 0, 0 if np.isnan(a[k]) else a[k],
                    0 if np.isnan(w[k]) else w[k], d[k],
                    None if pr is None else (round(pr[0], 2), round(pr[1], 2)),
                    None if size is None else round(size, 2), hv[k], 0 if np.isnan(ha[k]) else ha[k], ' '.join(bad)))
    print('\nFLAGS:')
    for sid, f, b in flags:
        print(sid, f, '; '.join(b))


if __name__ == '__main__':
    main()
