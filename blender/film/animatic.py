"""Animatic / look-dev stills from film.blend.

    $PY animatic.py --shots s1,s4 --step 4 [--w 640] [--samples 12] [--threads 2] [--blur 0]
    $PY animatic.py --frames 100,120 --w 1920 --samples 0 --final 1 --tag final

--final 1 uses the per-shot final settings from shot_settings (samples, blur, subsurf) and
writes final_sN_fXXXX.png; otherwise animatic frames go to preview/film/anim/ and a contact
sheet per shot is assembled as preview/film/animatic_sN.png.
"""
import os
import sys
import time
import resource

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'blender', 'common'))
import bpy  # noqa
import plan as PL  # noqa
import shot_settings as SS  # noqa

OUT = os.path.join(ROOT, 'blender', 'out', 'preview', 'film')
ANIM = os.path.join(OUT, 'anim')


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    o = dict(shots='', frames='', step='4', w='640', samples='12', threads='2', blur='0', final='0',
             tag='', vol='1', sheet='1')
    i = 0
    while i < len(a):
        o[a[i][2:]] = a[i + 1]
        i += 2
    return o


def sheet(sid, files, cols=4):
    from PIL import Image, ImageDraw
    ims = [(f, Image.open(p)) for f, p in files]
    if not ims:
        return
    w, h = ims[0][1].size
    rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (cols * w + (cols + 1) * 4, rows * h + (rows + 1) * 4), (20, 20, 20))
    d = ImageDraw.Draw(S)
    for k, (f, im) in enumerate(ims):
        x = 4 + (k % cols) * (w + 4)
        y = 4 + (k // cols) * (h + 4)
        S.paste(im, (x, y))
        d.text((x + 6, y + 4), '%d' % f, fill=(255, 255, 0))
    S.save(os.path.join(OUT, 'animatic_%s.png' % sid))


def main():
    o = args()
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', 'out', 'film.blend'))
    scene = bpy.context.scene
    r = scene.render
    r.compositor_device = 'CPU'
    r.threads_mode = 'FIXED'
    r.threads = int(o['threads'])
    final = o['final'] == '1'
    W = int(o['w'])
    r.resolution_x = W
    r.resolution_y = int(round(W * 804 / 1920))
    r.use_motion_blur = final or o['blur'] == '1'
    frames = []
    if o['frames']:
        for part in o['frames'].split(','):
            if '-' in part:
                a, b = part.split('-')
                frames += list(range(int(a), int(b) + 1, int(o['step'])))
            else:
                frames.append(int(part))
    for sid in [s for s in o['shots'].split(',') if s]:
        fr = PL.frames_of(sid)
        sel = list(fr[::int(o['step'])])
        if fr[-1] not in sel:
            sel.append(int(fr[-1]))
        frames += [int(x) for x in sel]
    os.makedirs(ANIM, exist_ok=True)
    body = bpy.data.objects.get('HERO_body')
    if not final:
        scene.cycles.samples = int(o['samples'])
        scene.cycles.adaptive_threshold = 0.1
        scene.cycles.max_bounces = 4
        if o['vol'] == '0':
            for ob in bpy.data.objects:
                if ob.name.startswith('ATMO_haze'):
                    ob.hide_render = True
    try:
        scene.compositing_node_group.nodes['DEPTH_OUT'].mute = True
    except Exception:
        pass
    done = {}
    for f in frames:
        sid = PL.shot(f)['id']
        st = SS.SHOT[sid]
        if final:
            scene.cycles.samples = int(o['samples']) if int(o['samples']) > 0 else st['samples']
            scene.cycles.adaptive_threshold = st['threshold']
        scene.frame_set(f)
        rig = bpy.data.objects.get('HERO_RIG')
        for ch in (rig.children if rig else []):
            for m in ch.modifiers:
                if m.type == 'SUBSURF':
                    m.render_levels = st['subsurf'] if final else 1
        if final:
            for k, v in SS.CYCLES.items():
                setattr(scene.cycles, k, v)
        fn = os.path.join(OUT if final else ANIM, ('final_%s_f%04d%s.png' if final else '%s_f%04d%s.png') % (sid, f, o['tag']))
        r.filepath = fn
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        msg = '[anim] %s f%d %dx%d spp=%d thr=%s blur=%s %.1fs peakRSS=%.2fGB' % (
            sid, f, r.resolution_x, r.resolution_y, scene.cycles.samples, o['threads'], r.use_motion_blur, dt, rss)
        print(msg, flush=True)
        with open(os.path.join(OUT, 'render_log.txt'), 'a') as fh:
            fh.write(msg + '\n')
        done.setdefault(sid, []).append((f, fn))
    if not final and o['sheet'] == '1':
        for sid, files in done.items():
            sheet(sid, files)


if __name__ == '__main__':
    main()
