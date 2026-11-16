"""Render-cost bench: one frame, several settings variants, prints seconds.
    $PY bench.py FRAME W THREADS variant[,variant...]"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
import shot_settings as SS
import plan as PL

V = {
    'base': {},
    'lite': dict(samples=20, adaptive_threshold=0.05, diffuse_bounces=1, glossy_bounces=2,
                 transmission_bounces=2, volume_bounces=0, max_bounces=4),
    'lite12': dict(samples=12, adaptive_threshold=0.05, diffuse_bounces=1, glossy_bounces=2,
                   transmission_bounces=2, volume_bounces=0, max_bounces=4),
    'noblur': dict(_blur=False),
    'l16': dict(samples=16, adaptive_threshold=0.04, diffuse_bounces=1, glossy_bounces=2,
                transmission_bounces=2, volume_bounces=0, max_bounces=4),
    'l28': dict(samples=28, adaptive_threshold=0.02, diffuse_bounces=1, glossy_bounces=2,
                transmission_bounces=2, volume_bounces=0, max_bounces=4),
    'noclamp': dict(sample_clamp_indirect=2.0, sample_clamp_direct=8.0),
    'novol': dict(_novol=True),
}
f, W, thr, vs = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4].split(',')
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '..', 'out', 'film.blend'))
sc = bpy.context.scene
r = sc.render
r.compositor_device = 'CPU'
r.threads_mode = 'FIXED'; r.threads = thr
r.resolution_x = W; r.resolution_y = round(W * 804 / 1920)
sc.compositing_node_group.nodes['DEPTH_OUT'].mute = True
st = SS.SHOT[PL.shot(f)['id']]
sc.cycles.samples = st['samples']; sc.cycles.adaptive_threshold = st['threshold']
bpy.data.objects['HERO_body'].modifiers['Subdivision'].render_levels = st['subsurf']
sc.frame_set(f)
for vname in vs:
    for part in vname.split('+'):
        for k, v in V[part].items():
            if k == '_blur':
                r.use_motion_blur = v
            elif k == '_novol':
                for ob in bpy.data.objects:
                    if ob.name.startswith('ATMO_haze'):
                        ob.hide_render = True
            else:
                setattr(sc.cycles, k, v)
    r.filepath = '/tmp/claude-0/-home-user/3b110407-c811-597d-a6a3-85d5f1bba0d5/scratchpad/bench_%d_%s.png' % (f, vname)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('[bench] f%d %dpx thr%d %s: %.1fs' % (f, W, thr, vname, time.time() - t), flush=True)
