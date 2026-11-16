"""Look-dev stills from city.blend.

    $PY render_preview.py VIEW [VIEW...] [--w 960] [--samples 48] [--threads 2] [--dusk 0.0] [--tag x]

Views: a aerial, b canyon, c street look-up at The Tower, d gargoyle close-up,
       e dive view, f = b at dusk 1.0, g = a at dusk 1.0, h = reverse canyon (sunlit faces)
"""
import os
import sys
import time
import math
import resource

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "blender", "common"))
import bpy  # noqa
import mathutils  # noqa
import lighting  # noqa

OUT = os.path.join(ROOT, "blender", "out", "preview", "city")

VIEWS = {
    'a': dict(loc=(-250, -900, 380), at=(0, 300, 250), lens=30, preset='aerial'),
    'm': dict(loc=(-700, -450, 360), at=(150, 350, 40), lens=30, preset='aerial'),
    'b': dict(loc=(3, -100, 45), at=(0, 400, 38), lens=24),
    'c': dict(loc=(9.0, -262.0, 1.7), at=(-22, -296, 150), lens=18, exp=0.9),
    'd': dict(loc=(-9.2, -280.6, 229.4), at=(-13.9, -287.7, 227.8), lens=100, fstop=2.8, preset='closeup'),
    'n': dict(loc=(-13.4, -279.5, 228.3), at=(-13.4, -287.7, 227.4), lens=50),
    'q': dict(loc=(400, 0, 300), at=(1500, 3000, 900), lens=24),
    'e': dict(loc=(-12.6, -289.6, 225.5), rot=(0.0, 0.0, math.radians(90)), lens=16, exp=0.8),
    'f': dict(loc=(3, -100, 45), at=(0, 400, 38), lens=24, dusk=1.0, exp=0.3),
    'g': dict(loc=(-250, -900, 380), at=(0, 300, 250), lens=30, dusk=1.0, preset='dusk_wide'),
    'h': dict(loc=(-4, 300, 30), at=(2, -200, 60), lens=24),
    's': dict(loc=(0, -200, 2), at=(20, 300, 330), lens=16),
    'r_close': dict(loc=(-3.0, 98.0, 15.0), at=(-16.0, 111.0, 17.0), lens=35, exp=0.8),
    'r_dusk': dict(loc=(-9.0, 95.0, 14.0), at=(-17.0, 125.0, 17.0), lens=30, dusk=1.0, exp=0.3),
    'r_west': dict(loc=(-2.0, 140.0, 24.0), at=(-16.0, 150.0, 26.0), lens=35, exp=0.6),
    'r_in': dict(loc=(-11.0, 106.5, 11.6), at=(-17.0, 110.0, 11.0), lens=28, exp=0.8),
    'r_close2': dict(loc=(-10.8, -63.1, 10.5), at=(-17.0, -63.1, 10.2), lens=28, exp=1.8),
    'r_office': dict(loc=(-8.0, 100.0, 25.0), at=(19.0, 118.0, 25.0), lens=28, exp=0.8),
    'dbg': dict(loc=(-14.2, 112.74, 7.6), at=(-20.0, 112.74, 7.4), lens=24, exp=0.8),
    's_street': dict(loc=(1.5, -60.0, 8.0), at=(0.0, 300.0, 16.0), lens=22, exp=0.5),
    's_dusk': dict(loc=(1.5, -60.0, 8.0), at=(0.0, 300.0, 16.0), lens=22, dusk=1.0, exp=0.3),
    'car_close': dict(loc=(-6.0, -150.0, 2.2), at=(-2.0, -140.0, 0.8), lens=35, exp=0.8),
    'road_close': dict(loc=(9.0, -128.0, 1.7), at=(4.0, -116.0, 0.0), lens=35, exp=0.9),
    'base_close': dict(loc=(-7.0, -42.0, 1.7), at=(-16.0, -31.0, 2.6), lens=35, exp=0.9),
    'bus_close': dict(loc=(-1.2, -153.0, 1.6), at=(4.5, -141.0, 1.6), lens=28, exp=0.9),
    'xstreet_close': dict(loc=(-9.0, -95.0, 1.8), at=(-1.0, -84.0, 1.4), lens=30, exp=0.9),
    'truck_close': dict(loc=(-3.5, -119.0, 1.7), at=(0.6, -108.5, 1.6), lens=30, exp=0.9),
    'k': dict(loc=(150, 700, 420), at=(-40, -250, 80), lens=30),
    'i': dict(loc=(30, 300, 74), at=(0, 381, 73), lens=35),
}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    views, opt = [], dict(w=960, samples=48, threads=2, dusk=None, tag='', set='', blend=os.path.join(ROOT, 'blender', 'out', 'city.blend'),
                          noise=None)
    i = 0
    while i < len(a):
        if a[i].startswith('--'):
            k = a[i][2:]
            v = a[i + 1]
            opt[k] = type(opt[k])(v) if opt.get(k) is not None and not isinstance(opt[k], str) else v
            i += 2
        else:
            views.append(a[i])
            i += 1
    return views, opt


def setup_cam(scene, v):
    cam = bpy.data.objects.get("PREVIEW_cam")
    if cam is None:
        cam = bpy.data.objects.new("PREVIEW_cam", bpy.data.cameras.new("PREVIEW_cam"))
        scene.collection.objects.link(cam)
    cam.location = v['loc']
    if 'at' in v:
        d = mathutils.Vector(v['at']) - mathutils.Vector(v['loc'])
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    else:
        cam.rotation_euler = v['rot']
    cam.data.lens = v['lens']
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.05
    cam.data.clip_end = 30000
    if 'fstop' in v:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = v['fstop']
        cam.data.dof.focus_distance = (mathutils.Vector(v['at']) - mathutils.Vector(v['loc'])).length
    else:
        cam.data.dof.use_dof = False
    scene.camera = cam


def main():
    views, opt = args()
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=opt['blend'])
    scene = bpy.context.scene
    log = []
    print(f"[preview] loaded in {time.time() - t0:.1f}s", flush=True)
    for name in views:
        v = VIEWS[name] if name in VIEWS else VIEWS[name[0]]
        dusk = float(opt['dusk']) if opt['dusk'] is not None else v.get('dusk', 0.0)
        lighting.apply_preset(scene, v.get('preset', 'canyon' if (name[0] in 'bh' or name.startswith('s_street')) else 'none'), dusk)
        ctrl = bpy.data.objects['LIGHT_CTRL']
        for kv in (opt.get('set') or '').split(','):
            if '=' in kv:
                k, val = kv.split('=')
                if k == 'look':
                    scene.view_settings.look = val.replace('_', ' ')
                elif k == 'wb':
                    scene.view_settings.use_white_balance = True
                    scene.view_settings.white_balance_temperature = float(val)
                else:
                    ctrl[k] = float(val)
        if 'exp' in v and 'exposure=' not in (opt.get('set') or ''):
            ctrl['exposure'] = float(ctrl['exposure']) + v['exp']
        lighting.touch(scene)
        setup_cam(scene, v)
        w = int(opt['w'])
        scene.render.resolution_x = w
        scene.render.resolution_y = int(round(w * 804 / 1920))
        scene.cycles.samples = int(opt['samples'])
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = int(opt['threads'])
        scene.render.use_motion_blur = False
        os.makedirs(OUT, exist_ok=True)
        fn = os.path.join(OUT, f"{name}{opt['tag']}.png")
        scene.render.filepath = fn
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        msg = f"[preview] {name} {w}px {opt['samples']}spp {opt['threads']}thr dusk={dusk}: {dt:.1f}s peakRSS={rss:.2f}GB -> {fn}"
        print(msg, flush=True)
        log.append(msg)
    with open(os.path.join(OUT, "render_log.txt"), "a") as f:
        f.write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
