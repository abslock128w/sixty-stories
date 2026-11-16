"""Vehicle look-dev lineup: $PY veh_test.py out.png"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "common"))
import bpy, mathutils
bpy.ops.wm.read_factory_settings(use_empty=True)
import lighting, materials as MAT, protos as PR, signage as SG, interiors, extras, vehicles as VH
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
lighting.setup_lighting(sc, 0.0, haze=False)
SG._atlas(os.path.join(HERE, "..", "out", "city_tex"))
VH.register([a for a in SG.INFO if 2.0 <= a['aspect'] <= 3.0][:2])
col = bpy.data.collections.new("T"); sc.collection.children.link(col)
g = bpy.data.objects.new("ground", bpy.data.meshes.new("g"))
g.data.from_pydata([(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)], [], [(0, 1, 2, 3)]); g.data.materials.append(MAT.get('asphalt'))
col.objects.link(g)
kinds = sys.argv[-2].split(',')
for i, k in enumerate(kinds):
    o = bpy.data.objects.new(k, PR.get(k)); col.objects.link(o)
    o.location = ((i - (len(kinds) - 1) / 2) * 3.0, 0, 0); o.rotation_euler = (0, 0, math.radians(150 if i % 2 else 30))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (len(kinds) * 1.2, -11, 2.6); cam.data.lens = 35
cam.rotation_euler = (mathutils.Vector((0, 0, 0.8)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sun = bpy.data.objects['SUN']; bpy.data.objects['LIGHT_CTRL']['exposure'] = 0.6; bpy.data.objects['LIGHT_CTRL']['sun_elev'] = 0.5
bpy.data.objects['LIGHT_CTRL']['sun_rot_x'] = -(math.pi / 2 - 0.5); bpy.data.objects['LIGHT_CTRL']['sun_azim'] = 2.3; bpy.data.objects['LIGHT_CTRL']['sun_rot_z'] = -2.3
lighting.touch(sc)
sc.render.resolution_x, sc.render.resolution_y = 1280, 536
sc.cycles.samples = 48; sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
sc.view_settings.view_transform = 'AgX'
sc.render.filepath = sys.argv[-1]
bpy.ops.render.render(write_still=True)
