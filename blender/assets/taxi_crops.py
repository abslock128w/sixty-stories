"""Sharpness check crops for the taxi proofs.

/home/user/tools/bl/bin/python blender/assets/taxi_crops.py [--noisy-samples 512]

1. taxi_wheel_crop.png / taxi_lamp_crop.png: 960x540 pixel-for-pixel (100 %) crops from the
   centre of the 1920 px wheel_close / lamp_close proofs (no resampling).
2. taxi_wheel_crop_nodenoise.png: the same wheel region re-rendered with the same camera at
   1920 px (render border, cropped) with denoising OFF at higher samples, to show that the
   denoiser is not what softens detail.
"""
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxi  # noqa: E402
import taxi_proof as tp  # noqa: E402

BOX = (480, 270, 1440, 810)       # centre 960 x 540 of a 1920 x 1080 frame


def crops():
    from PIL import Image
    for shot, out in (("wheel_close", "taxi_wheel_crop.png"), ("lamp_close", "taxi_lamp_crop.png")):
        im = Image.open(os.path.join(tp.OUT, "taxi_" + shot + ".png"))
        im.crop(BOX).save(os.path.join(tp.OUT, out))
        print("wrote", out)


def noisy(samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    taxi.build("yellow_cab")
    tp.setup_stage(sc)
    tp.setup_render(sc, 1920, samples, 2)
    sc.cycles.use_denoising = False
    sc.cycles.use_adaptive_sampling = False
    tp.setup_world(sc, tp.SHOTS["wheel_close"]["sun_az"], 32.0)
    tp.set_camera(sc, "wheel_close")
    r = sc.render
    r.use_border = True
    r.use_crop_to_border = True
    r.border_min_x, r.border_max_x = BOX[0] / 1920, BOX[2] / 1920
    r.border_min_y, r.border_max_y = 1 - BOX[3] / 1080, 1 - BOX[1] / 1080
    r.filepath = os.path.join(tp.OUT, "taxi_wheel_crop_nodenoise.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print("wrote", r.filepath, "%.1fs" % (time.time() - t))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    n = int(argv[argv.index("--noisy-samples") + 1]) if "--noisy-samples" in argv else 512
    crops()
    noisy(n)
