"""Sixty Stories - final frame renderer (resumable, progressive, leak-proof).

    $PY blender/film/render_frames.py [--frames a-b] [--stride n] [--limit n] [--shot sN]
                                      [--threads 4] [--chunk 36] [--order progressive|linear]

Writes, per bible section 6:
    blender/out/frames/color/f_%04d.png   2560x1072 (shot_settings.RES) 8-bit sRGB (graded: AgX look + compositor)
    blender/out/frames/depth/f_%04d.png   1280x536 (shot_settings.DEPTH_RES) 8-bit grey, v = round(255/(1+z/25)), sky = 0
Both are written to a temp name and renamed (atomic). A frame whose colour AND depth both
exist is skipped, so the script can be killed and restarted at any time.

Order (progressive): i%8==0 first, then i%4==0, i%2==0, then the rest; inside each pass the
six shots are interleaved so every shot fills in evenly.

Process model: this script is a small supervisor. It spawns a worker (the same script with
--worker) that opens film.blend once (Cycles persistent data keeps the scene in memory
between frames) and renders at most --chunk frames, then exits; the supervisor relaunches
workers until nothing is left. Memory therefore cannot creep over hundreds of frames, and
a crashed worker only costs its current frame.
Per-shot quality settings live in shot_settings.py (one table).
Log: blender/out/frames/render.log (seconds per frame, ETA).
"""
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
OUTD = os.path.join(ROOT, 'blender', 'out')
FRAMES = os.path.join(OUTD, 'frames')
COLOR = os.path.join(FRAMES, 'color')
DEPTH = os.path.join(FRAMES, 'depth')
TMP = os.path.join(FRAMES, '_tmp')
LOG = os.path.join(FRAMES, 'render.log')
FILM = os.path.join(OUTD, 'film.blend')
PY = sys.executable
TOTAL = 336
SHOT_RANGES = [('s1', 0, 48), ('s2', 48, 48), ('s3', 96, 48), ('s4', 144, 72), ('s5', 216, 48), ('s6', 264, 72)]


def shot_of(i):
    for sid, a, n in SHOT_RANGES:
        if a <= i < a + n:
            return sid
    raise ValueError(i)


def _res():
    sys.path.insert(0, HERE)
    import shot_settings as SS
    return SS.RES, SS.DEPTH_RES


def parse(argv):
    o = dict(frames=None, stride=1, limit=0, shot=None, threads=4, chunk=36, order='progressive',
             worker=False, list=None, w=None, h=None)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--worker':
            o['worker'] = True
            i += 1
            continue
        k = a[2:]
        v = argv[i + 1]
        if k in ('stride', 'limit', 'threads', 'chunk', 'w', 'h'):
            v = int(v)
        o[k] = v
        i += 2
    (W, H), _ = _res()
    o['w'] = o['w'] or W
    o['h'] = o['h'] or H
    return o


def cpath(i):
    return os.path.join(COLOR, 'f_%04d.png' % i)


def dpath(i):
    return os.path.join(DEPTH, 'f_%04d.png' % i)


def done(i):
    return os.path.exists(cpath(i)) and os.path.exists(dpath(i))


def frame_order(o):
    if o['frames']:
        a, b = o['frames'].split('-') if '-' in o['frames'] else (o['frames'], o['frames'])
        cand = list(range(int(a), int(b) + 1))
    else:
        cand = list(range(TOTAL))
    if o['shot']:
        cand = [i for i in cand if shot_of(i) in o['shot'].split(',')]
    cand = cand[::o['stride']] if o['stride'] > 1 else cand
    if o['order'] == 'linear':
        return cand
    out = []
    seen = set()
    for m in (8, 4, 2, 1):
        per = {}
        for i in cand:
            if i % m == 0 and i not in seen:
                per.setdefault(shot_of(i), []).append(i)
        # interleave shots: round-robin proportional to shot length
        queues = [per[s] for s, _, _ in SHOT_RANGES if s in per]
        prog = [0.0] * len(queues)
        while any(queues):
            k = min((p / max(1, len(q) + p) if q else 9e9, j) for j, (p, q) in enumerate(zip(prog, queues)))[1]
            if not queues[k]:
                break
            i = queues[k].pop(0)
            prog[k] += 1
            out.append(i)
            seen.add(i)
    return out


def log(msg):
    os.makedirs(FRAMES, exist_ok=True)
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')


# ===================================================================== supervisor
def sweep_tmp():
    """Remove leftovers of killed runs: blender/out/frames/_tmp/* and depth|color/*.tmp.png."""
    import shutil
    n = 0
    if os.path.isdir(TMP):
        for x in os.listdir(TMP):
            p = os.path.join(TMP, x)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            n += 1
    for d in (DEPTH, COLOR):
        if os.path.isdir(d):
            for x in os.listdir(d):
                if x.endswith('.tmp.png'):
                    os.remove(os.path.join(d, x))
                    n += 1
    return n


def cur_marker(pid):
    return os.path.join(TMP, 'worker_%d.cur' % pid)


def supervise(o):
    os.makedirs(TMP, exist_ok=True)
    log('supervisor: swept %d stale temp files' % sweep_tmp())
    todo = [i for i in frame_order(o) if not done(i)]
    if o['limit']:
        todo = todo[:o['limit']]
    log('supervisor: %d frames to render (order=%s, threads=%d, chunk=%d)' % (len(todo), o['order'], o['threads'], o['chunk']))
    times = []
    fails = {}
    abandoned = []
    t_start = time.time()
    while True:
        todo = [i for i in todo if not done(i) and i not in abandoned]
        if not todo:
            break
        batch = todo[:o['chunk']]
        cmd = [PY, os.path.abspath(__file__), '--worker', '--list', ','.join(map(str, batch)),
               '--threads', str(o['threads']), '--w', str(o['w']), '--h', str(o['h'])]
        t0 = time.time()
        p = subprocess.Popen(cmd)
        rc = p.wait()
        n_ok = sum(1 for i in batch if done(i))
        if n_ok:
            times.append(((time.time() - t0) / n_ok, n_ok))
        # charge a failure only to the frame the worker was on when it died
        mk = cur_marker(p.pid)
        cur = None
        if os.path.exists(mk):
            try:
                cur = int(open(mk).read().strip())
            except ValueError:
                cur = None
            os.remove(mk)
        if rc != 0:
            log('WORKER DIED (exit %d) after %d/%d frames, on frame %s; untouched frames requeued'
                % (rc, n_ok, len(batch), cur))
            if cur is not None and not done(cur):
                fails[cur] = fails.get(cur, 0) + 1
                if fails[cur] >= 3:
                    abandoned.append(cur)
                    log('!!!!! ABANDONING frame %d after 3 failed attempts !!!!!' % cur)
        else:
            # clean exit but a frame missing (e.g. outputs not found): charge it
            for i in batch:
                if not done(i):
                    fails[i] = fails.get(i, 0) + 1
                    if fails[i] >= 3 and i not in abandoned:
                        abandoned.append(i)
                        log('!!!!! ABANDONING frame %d after 3 failed attempts !!!!!' % i)
        left = sum(1 for i in todo if not done(i) and i not in abandoned)
        if times:
            spf = sum(t * n for t, n in times) / sum(n for _, n in times)
            log('progress: %d done this run, %d left, %.1f s/frame (incl. load), ETA %.2f h' % (
                sum(n for _, n in times), left, spf, left * spf / 3600))
    log('supervisor finished in %.2f h; abandoned frames: %s' % ((time.time() - t_start) / 3600, abandoned or 'none'))
    if abandoned:
        log('!!!!! %d FRAME(S) ABANDONED: %s; rerun the same command to retry them !!!!!' % (len(abandoned), abandoned))
        sys.exit(2)


# ===================================================================== worker
def worker(o):
    import bpy
    import numpy as np
    import shot_settings as SS
    frames = [int(x) for x in o['list'].split(',') if x]
    os.makedirs(COLOR, exist_ok=True)
    os.makedirs(DEPTH, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=FILM)
    scene = bpy.context.scene
    r = scene.render
    if o['threads'] and int(o['threads']) > 0:
        r.threads_mode = 'FIXED'
        r.threads = o['threads']
    else:
        r.threads_mode = 'AUTO'
    if os.environ.get('SIXTY_GPU'):   # local machines: render on the GPU (Metal/OptiX/CUDA)
        try:
            cp = bpy.context.preferences.addons['cycles'].preferences
            for dt in (os.environ['SIXTY_GPU'].upper(), 'METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
                try:
                    cp.compute_device_type = dt
                except Exception:
                    continue
                cp.get_devices()
                if any(d.type == dt for d in cp.devices):
                    for d in cp.devices:
                        d.use = True
                    scene.cycles.device = 'GPU'
                    print('[render_frames] GPU rendering with', dt, [d.name for d in cp.devices], flush=True)
                    break
        except Exception as e:
            print('[render_frames] GPU setup failed, using CPU:', e, flush=True)
    r.use_persistent_data = True
    r.compositor_device = 'CPU'
    r.resolution_x, r.resolution_y, r.resolution_percentage = o['w'], o['h'], 100
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_depth = '8'
    r.image_settings.color_mode = 'RGB'
    ng = scene.compositing_node_group
    fo = ng.nodes.get('DEPTH_OUT')
    if fo is None:   # a look built its own compositor without the delivery node: add it
        sys.path.insert(0, os.path.join(HERE, 'looks'))
        import lookkit
        rl = [n for n in ng.nodes if n.type == 'R_LAYERS'][0]
        fo = lookkit.add_depth_out(ng, rl)
    rig = bpy.data.objects.get('HERO_RIG')
    subs = [m for o in rig.children for m in o.modifiers if m.type == 'SUBSURF'] if rig else []
    for k, v in SS.CYCLES.items():
        setattr(scene.cycles, k, v)
    log('worker pid %d: loaded film.blend in %.1fs, %d frames' % (os.getpid(), time.time() - t0, len(frames)))
    for i in frames:
        if done(i):
            continue
        with open(cur_marker(os.getpid()), 'w') as fh:
            fh.write(str(i))
        sid = shot_of(i)
        st = SS.SHOT[sid]
        c = scene.cycles
        c.samples = st['samples']
        c.adaptive_threshold = st['threshold']
        c.volume_step_rate = st.get('volume_step', 4.0)
        for k, v in st.get('cycles', {}).items():
            setattr(c, k, v)
        for m in subs:
            m.render_levels = st['subsurf']
        r.use_motion_blur = True
        r.motion_blur_position = 'START'
        r.motion_blur_shutter = SS.shutter(i)
        scene.frame_set(i)
        tag = 'p%d_%d' % (os.getpid(), i)
        ddir = os.path.join(TMP, tag)
        os.makedirs(ddir, exist_ok=True)
        fo.directory = ddir + os.sep
        fo.file_name = 'd'
        tmp_c = os.path.join(TMP, tag + '.png')
        r.filepath = tmp_c
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        # ---- depth
        exr = [os.path.join(ddir, f) for f in os.listdir(ddir) if f.endswith('.exr')]
        if not exr or not os.path.exists(tmp_c):
            log('frame %d: missing outputs (%s)' % (i, os.listdir(ddir)))
            continue
        img = bpy.data.images.load(exr[0])
        w, h = img.size
        px = np.empty(w * h * img.channels, np.float32)
        img.pixels.foreach_get(px)
        z = px.reshape(h, w, img.channels)[::-1, :, 0]
        bpy.data.images.remove(img)
        write_depth(z, dpath(i), np)
        os.replace(tmp_c, cpath(i))
        for f in os.listdir(ddir):
            os.remove(os.path.join(ddir, f))
        os.rmdir(ddir)
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        log('frame %3d %s rendered in %6.1f s (%d spp max, %d thr, %dx%d) peakRSS %.2f GB' % (
            i, sid, dt, st['samples'], o['threads'], o['w'], o['h'], rss))


def despeckle_depth(v, np, tol=10.0):
    """Cycles' Z pass holds one sample per pixel, so with volumes, DOF and motion blur a
    few pixels report a ray that escaped (sky / far) inside a near surface: salt-and-pepper
    in the depth image. Replace pixels that differ from their 3x3 median by more than tol
    (twice, to catch 2-pixel clusters); real edges survive because the median keeps them."""
    v = v.astype(np.float32)
    for _ in range(3):
        p = np.pad(v, 1, mode='edge')
        h, w = v.shape
        stack = np.stack([p[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)], 0)
        med = np.median(stack, axis=0)
        bad = np.abs(v - med) > tol
        v = np.where(bad, med, v)
    return v


def write_depth(z, path, np):
    """z: (H, W) camera depth in metres (sky = huge). 2x2 min filter -> DEPTH_RES."""
    from PIL import Image
    h, w = z.shape
    z = z[:h // 2 * 2, :w // 2 * 2]
    zz = z.reshape(h // 2, 2, w // 2, 2).min(axis=(1, 3))
    sky = ~np.isfinite(zz) | (zz > 1e6)
    zc = np.where(sky, 1.0, np.maximum(zz, 0.0))
    v = np.rint(255.0 / (1.0 + zc / 25.0))
    v[sky] = 0
    v = despeckle_depth(v, np)
    im = Image.fromarray(v.astype(np.uint8), 'L')
    _, (DW, DH) = _res()
    if im.size != (DW, DH):
        im = im.resize((DW, DH), Image.NEAREST)
    tmp = path + '.tmp.png'
    im.save(tmp)
    os.replace(tmp, path)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    o = parse(argv)
    if o['worker']:
        worker(o)
    else:
        supervise(o)
