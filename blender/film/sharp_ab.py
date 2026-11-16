"""Sharpness A/B: render a 100% crop region of one frame of film.blend with setting variants.

    $PY sharp_ab.py FRAME x0,x1,y0,y1(px, top-left origin, of 1920x804) OUTDIR variant[,variant...]
variant = name:key=val;key=val   keys: blur (shutter, 0=off), dof (0/1), spp, thr, denoise (0/1),
          filter (px), glare (0/1 compositor glare nodes), prefilter (NONE/FAST/ACCURATE), fstop
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa
import shot_settings as SS  # noqa
import plan as PL  # noqa


def main():
    f = int(sys.argv[1])
    x0, x1, y0, y1 = [int(v) for v in sys.argv[2].split(',')]
    out = sys.argv[3]
    os.makedirs(out, exist_ok=True)
    variants = sys.argv[4].split(',')
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '..', 'out', 'film.blend'))
    sc = bpy.context.scene
    r = sc.render
    r.compositor_device = 'CPU'
    r.threads_mode = 'FIXED'
    r.threads = 4
    r.resolution_x, r.resolution_y = 1920, 804
    r.use_border = True
    r.use_crop_to_border = True
    r.border_min_x, r.border_max_x = x0 / 1920, x1 / 1920
    r.border_min_y, r.border_max_y = 1 - y1 / 804, 1 - y0 / 804
    ng = sc.compositing_node_group
    if ng.nodes.get('DEPTH_OUT'):
        ng.nodes['DEPTH_OUT'].mute = True
    st = SS.SHOT[PL.shot(f)['id']]
    for k, v in SS.CYCLES.items():
        setattr(sc.cycles, k, v)
    rig = bpy.data.objects.get('HERO_RIG')
    for ob in (rig.children if rig else []):
        for m in ob.modifiers:
            if m.type == 'SUBSURF':
                m.render_levels = st['subsurf']
    sc.frame_set(f)
    cam = sc.camera
    glares = [n for n in ng.nodes if n.type == 'GLARE']
    for v in variants:
        name, _, spec = v.partition(':')
        o = dict(blur=0.5, dof=1, spp=st['samples'], thr=st['threshold'], denoise=1, filter=1.5,
                 glare=1, prefilter='ACCURATE', fstop=None, res=1920, paths=0)
        for kv in [x for x in spec.split(';') if x]:
            k, val = kv.split('=')
            o[k] = val if k == 'prefilter' else float(val)
        W = int(o['res'])
        r.resolution_x, r.resolution_y = W, int(round(W * 804 / 1920))
        if int(o['paths']):
            for k, val in dict(max_bounces=8, diffuse_bounces=3, glossy_bounces=4, transmission_bounces=6,
                               volume_bounces=1, transparent_max_bounces=12).items():
                setattr(sc.cycles, k, val)
        else:
            for k, val in SS.CYCLES.items():
                setattr(sc.cycles, k, val)
        sc.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        r.use_motion_blur = float(o['blur']) > 0
        if r.use_motion_blur:
            r.motion_blur_shutter = float(o['blur'])
        cam.data.dof.use_dof = bool(int(o['dof']))
        if o['fstop']:
            cam.data.dof.aperture_fstop = float(o['fstop'])
        sc.cycles.samples = int(o['spp'])
        sc.cycles.adaptive_threshold = float(o['thr'])
        sc.cycles.use_denoising = bool(int(o['denoise']))
        sc.cycles.denoising_prefilter = o['prefilter']
        sc.cycles.filter_width = float(o['filter'])
        for g in glares:
            g.mute = not bool(int(o['glare']))
        r.filepath = os.path.join(out, '%s_f%04d.png' % (name, f))
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print('[ab] %s f%d %.1fs %s' % (name, f, time.time() - t, o), flush=True)


if __name__ == '__main__':
    main()
