"""Benchmark full-size frames: $PY bench.py VIEW [VIEW..] --samples 32 --threads 4
Prints seconds/frame and peak RSS, renders at 1920x804 with motion blur off."""
import os
import sys
import time
import resource

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import bpy  # noqa
import lighting  # noqa
import render_preview as RP  # noqa


def main():
    views, opt = RP.args()
    bpy.ops.wm.open_mainfile(filepath=opt['blend'])
    sc = bpy.context.scene
    for v in views:
        lighting.apply_preset(sc, RP.VIEWS[v].get('preset', 'canyon' if v in 'bh' else 'none'), RP.VIEWS[v].get('dusk', 0.0))
        RP.setup_cam(sc, RP.VIEWS[v])
        sc.render.resolution_x, sc.render.resolution_y = 1920, 804
        sc.cycles.samples = int(opt['samples'])
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = int(opt['threads'])
        sc.render.use_motion_blur = True
        sc.render.filepath = os.path.join(RP.OUT, f"bench_{v}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        msg = f"[bench] {v} 1920x804 {opt['samples']}spp {opt['threads']}thr: {dt:.1f}s peakRSS={rss:.2f}GB"
        print(msg, flush=True)
        with open(os.path.join(RP.OUT, "render_log.txt"), "a") as f:
            f.write(msg + "\n")


if __name__ == "__main__":
    main()
