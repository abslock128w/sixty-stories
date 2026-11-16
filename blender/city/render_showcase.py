"""Render the CAMERAS_SHOWCASE compositions: $PY render_showcase.py [--w 1280] [--samples 32] [--threads 4]"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "common"))
import bpy, lighting
import render_preview as RP

PRESET = {'showcase_aerial_skyline': 'aerial', 'showcase_rooftop_across': 'aerial', 'showcase_waterfront_skyline': 'aerial',
          'showcase_commercial_avenue': 'canyon', 'showcase_side_street': 'canyon', 'showcase_facade_closeup': 'closeup',
          'showcase_street_architecture': 'none'}
EXP = {'showcase_commercial_avenue': 0.5, 'showcase_facade_closeup': 0.8, 'showcase_street_architecture': 0.9,
       'showcase_side_street': 1.4}

views, opt = RP.args()
bpy.ops.wm.open_mainfile(filepath=opt['blend'])
sc = bpy.context.scene
for cam in sorted(bpy.data.collections['CAMERAS_SHOWCASE'].objects, key=lambda o: o.name):
    if views and not any(v in cam.name for v in views):
        continue
    lighting.apply_preset(sc, PRESET.get(cam.name, 'none'), 0.0)
    c = bpy.data.objects['LIGHT_CTRL']
    c['exposure'] = float(c['exposure']) + EXP.get(cam.name, 0.0)
    lighting.touch(sc)
    sc.camera = cam
    sc.render.resolution_x = int(opt['w']); sc.render.resolution_y = int(round(int(opt['w']) * 804 / 1920))
    sc.cycles.samples = int(opt['samples']); sc.render.threads = int(opt['threads']); sc.render.use_motion_blur = False
    sc.render.filepath = os.path.join(RP.OUT, cam.name + ".png")
    t = time.time(); bpy.ops.render.render(write_still=True)
    print(f"[showcase] {cam.name} {time.time() - t:.1f}s", flush=True)
