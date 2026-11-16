"""Proof that hero.blend works when appended into a fresh scene: key three poses, move
the rig, add a line, render in-between frames with motion blur.
   python test_append.py  -> blender/out/preview/hero/test_append.png
"""
import sys, os, time
sys.path.insert(0, '/home/user/sixty/blender/hero')
import bpy
from mathutils import Vector
import hero_api as H
import lookdev as LD

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 25
rig = H.append_hero()
assert rig is not None and rig.name.startswith('HERO_RIG')
# no world in the empty scene: the hero must not depend on it -> add a plain one for light
LD.setup_scene(sc, samples=24, res=(640, 268))
LD.world_gradient(sc, strength=0.8)
LD.rim_rig(sc, key_az=150, key_el=12, key_energy=4.0)
H.apply_pose(rig, 'swing_R', 1)
H.apply_pose(rig, 'swing_tuck', 13)
H.apply_pose(rig, 'release_arch', 25)
# rig travels along +Y and arcs
for f, (y, z) in ((1, (-3.0, 2.2)), (13, (0.0, 1.4)), (25, (3.0, 2.4))):
    H.place_rig(rig, f, hips=(0, y, z), forward=(0, 1, 0), up=(0, 0, 1))
web = H.add_web(rig, 'R', anchor=(0.0, 0.5, 12.0), frame_on=1, frame_off=20, name='test_web', slack=0.0)
H.key_slack(web, 1, 0.3); H.key_slack(web, 6, 0.0)
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
cam = LD.camera(sc, (7.5, 0.0, 2.6), (0, 0, 2.0), lens=35)
paths = []
for f in (4, 9, 18, 22):
    sc.frame_set(f)
    t = time.time()
    paths.append(LD.render(sc, f'/tmp/claude-0/ta_{f}.png'))
    print('frame', f, 'grip', tuple(round(x, 3) for x in H.grip_world(rig, 'R')), round(time.time() - t, 1), 's')
LD.contact_sheet(paths, os.path.join(LD.OUT, 'test_append.png'), 2, ['f4', 'f9', 'f18', 'f22 (line off)'])
print('OK test_append')
