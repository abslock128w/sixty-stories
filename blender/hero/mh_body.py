"""Load the MakeHuman (CC0) base mesh, apply macro + detail targets, return a lean
athletic male body as numpy arrays in Blender space (metres, Z up, facing -Y).

Pure data parsing: nothing from the MakeHuman code base is executed.
"""
import os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'mh_data')
HEIGHT_M = 1.78


def _parse_obj(path):
    V, VT, faces, fuv, fgroup = [], [], [], [], []
    group = None
    with open(path) as f:
        for line in f:
            if line.startswith('v '):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('g '):
                group = line.split()[1]
            elif line.startswith('f '):
                vs, ts = [], []
                for tok in line.split()[1:]:
                    p = tok.split('/')
                    vs.append(int(p[0]) - 1)
                    ts.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                faces.append(vs); fuv.append(ts); fgroup.append(group)
    return np.array(V, float), np.array(VT, float), faces, fuv, fgroup


def _load_target(rel):
    path = os.path.join(DATA, 'targets', rel)
    idx, d = [], []
    with open(path) as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            p = line.split()
            idx.append(int(p[0])); d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, int), np.array(d, float).reshape(-1, 3)


def _three(v):
    """MakeHuman style 3-way split of a 0..1 slider into (min, avg, max) weights."""
    if v < 0.5:
        return (1 - 2 * v, 2 * v, 0.0)
    return (0.0, 2 - 2 * v, 2 * v - 1)


# Body design: lean gymnast / climber
MACRO = dict(muscle=0.85, weight=0.36, height=0.62, proportions=1.0,
             race=dict(caucasian=0.45, african=0.30, asian=0.25))

DETAIL = {
    'torso/torso-vshape-incr.target': 0.35,
    'torso/torso-muscle-pectoral-incr.target': 0.55,
    'torso/torso-muscle-dorsi-incr.target': 0.55,
    'torso/torso-scale-depth-decr.target': 0.10,
    'stomach/stomach-pregnant-decr.target': 0.6,
    'measure/measure-waist-circ-decr.target': 0.55,
    'measure/measure-neck-circ-incr.target': 0.1,
    'measure/measure-shoulder-dist-incr.target': 0.55,
    'measure/measure-neck-height-decr.target': 0.35,
    'measure/measure-frontchest-dist-incr.target': 0.25,
    'measure/measure-calf-circ-incr.target': 0.15,
    'hip/hip-scale-horiz-decr.target': 0.15,
    'buttocks/buttocks-volume-incr.target': 0.15,
}
for s in 'lr':
    DETAIL.update({
        f'armslegs/{s}-upperarm-shoulder-muscle-incr.target': 0.45,
        f'armslegs/{s}-upperarm-muscle-incr.target': 0.5,
        f'armslegs/{s}-lowerarm-muscle-incr.target': 0.7,
        f'armslegs/{s}-upperleg-muscle-incr.target': 0.65,
        f'armslegs/{s}-lowerleg-muscle-incr.target': 0.65,
        f'armslegs/{s}-upperarm-fat-decr.target': 0.5,
        f'armslegs/{s}-lowerarm-fat-decr.target': 0.4,
        f'armslegs/{s}-upperleg-fat-decr.target': 0.15,
        f'armslegs/{s}-lowerleg-fat-decr.target': 0.5,
    })


def build(macro=MACRO, detail=DETAIL):
    V, VT, faces, fuv, fgroup = _parse_obj(os.path.join(DATA, '3dobjs', 'base.obj'))
    X = V.copy()
    mus = dict(zip(('minmuscle', 'averagemuscle', 'maxmuscle'), _three(macro['muscle'])))
    wei = dict(zip(('minweight', 'averageweight', 'maxweight'), _three(macro['weight'])))
    h = macro['height']; hmax = max(0.0, 2 * h - 1); hmin = max(0.0, 1 - 2 * h)
    pr = max(0.0, 2 * macro['proportions'] - 1)
    for m, wm in mus.items():
        for w, ww in wei.items():
            k = wm * ww
            if k <= 0:
                continue
            i, d = _load_target(f'macrodetails/universal-male-young-{m}-{w}.target'); X[i] += k * d
            if hmax > 0:
                i, d = _load_target(f'macrodetails/height/male-young-{m}-{w}-maxheight.target'); X[i] += k * hmax * d
            if hmin > 0:
                i, d = _load_target(f'macrodetails/height/male-young-{m}-{w}-minheight.target'); X[i] += k * hmin * d
            if pr > 0:
                i, d = _load_target(f'macrodetails/proportions/male-young-{m}-{w}-idealproportions.target'); X[i] += k * pr * d
    for race, k in macro['race'].items():
        i, d = _load_target(f'macrodetails/{race}-male-young.target'); X[i] += k * d
    for rel, k in detail.items():
        i, d = _load_target(rel); X[i] += k * d

    # MakeHuman space: Y up, +Z front, decimetres -> Blender: Z up, -Y front, metres
    B = np.stack([X[:, 0], -X[:, 2], X[:, 1]], 1)

    # joints from the skeleton file (mean of helper vertices)
    sk = json.load(open(os.path.join(DATA, 'rigs', 'default.mhskel')))
    joints = {k: B[np.array(v)].mean(0) for k, v in sk['joints'].items()}

    body_faces = [k for k, g in enumerate(fgroup) if g == 'body']
    used = sorted({v for k in body_faces for v in faces[k]})
    remap = -np.ones(len(B), int); remap[used] = np.arange(len(used))
    P = B[used]
    zmin = P[:, 2].min(); zmax = P[:, 2].max()
    s = HEIGHT_M / (zmax - zmin)
    off = np.array([0.0, 0.0, -zmin])
    # centre between the feet in x/y
    ank = 0.5 * (joints['foot.L____head'] + joints['foot.R____head'])
    off[1] = -(ank[1] - 0.04 / s)   # origin ~4 cm in front of the ankles (mid-foot)
    P = (P + off) * s
    joints = {k: (v + off) * s for k, v in joints.items()}
    F = [[int(remap[v]) for v in faces[k]] for k in body_faces]
    FUV = [[VT[t] for t in fuv[k]] for k in body_faces]

    wts = json.load(open(os.path.join(DATA, 'rigs', 'default_weights.mhw')))['weights']
    weights = {}
    for bone, lst in wts.items():
        a = np.array(lst, float)
        if len(a) == 0:
            continue
        vi = remap[a[:, 0].astype(int)]
        ok = vi >= 0
        if ok.any():
            weights[bone] = (vi[ok], a[ok, 1])
    return dict(verts=P, faces=F, face_uvs=FUV, joints=joints, bones=sk['bones'],
                weights=weights, orig_index=np.array(used), scale=s)


if __name__ == '__main__':
    import time
    t = time.time()
    d = build()
    P = d['verts']
    print('verts', len(P), 'faces', len(d['faces']), 'time', round(time.time() - t, 2))
    print('bbox', P.min(0).round(3), P.max(0).round(3))
    for j in ('head____head', 'neck01____head', 'spine05____head', 'upperarm01.L____head', 'foot.L____head', 'wrist.L____head'):
        print(j, d['joints'][j].round(3))
