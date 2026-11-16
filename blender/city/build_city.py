"""Sixty Stories - CITY builder entry point.

    /home/user/tools/bl/bin/python /home/user/sixty/blender/city/build_city.py

Regenerates everything deterministically and writes
    blender/out/city.blend, blender/out/city_meta.json
"""
import os
import sys
import time
import json
import math
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "blender", "common"))

import bpy  # noqa: E402
import lighting  # noqa: E402
import layout as LY  # noqa: E402
import materials as MAT  # noqa: E402
import buildings as BD  # noqa: E402
import tower as TW  # noqa: E402
import street as ST  # noqa: E402
import streetlife as SL  # noqa: E402
import landmarks as LM  # noqa: E402
import horizon as HZ  # noqa: E402
import protos as PR  # noqa: E402
from cutil import MB, new_object, get_collection  # noqa: E402

OUT = os.path.join(ROOT, "blender", "out")


def log(*a):
    print("[city]", *a, flush=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def make_collections(scene):
    root = bpy.data.collections.new("CITY")
    scene.collection.children.link(root)
    names = dict(hero="CITY_buildings_hero", near="CITY_buildings_near", mid="CITY_buildings_mid",
                 far="CITY_buildings_far", roof="CITY_rooftops", street="CITY_street", props="CITY_props",
                 vehicles="CITY_vehicles", atmo="CITY_atmo")
    cols = {}
    for k, n in names.items():
        c = bpy.data.collections.new(n)
        root.children.link(c)
        cols[k] = c
    pc = bpy.data.collections.new("CITY_protos")
    scene.collection.children.link(pc)
    cols['protos'] = pc
    return cols


def render_settings(scene):
    scene.render.engine = 'CYCLES'
    c = scene.cycles
    c.device = 'CPU'
    c.samples = 32
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.03
    c.adaptive_min_samples = 16
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.max_bounces = 6
    c.diffuse_bounces = 2
    c.glossy_bounces = 3
    c.transmission_bounces = 4
    c.volume_bounces = 1
    c.transparent_max_bounces = 8
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = 6.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.5
    c.use_light_tree = False
    c.volume_step_rate = 4.0
    try:
        c.texture_limit_render = 'OFF'
    except Exception:
        pass
    scene.render.use_persistent_data = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 804
    scene.render.resolution_percentage = 100
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    scene.render.fps = 24
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False


def build_buildings(scene, cols, specs, lidx):
    t0 = time.time()
    roof = []
    stats = dict(near=0, mid=0, far=0)
    # near ring: one object per building with real facade geometry
    for s in specs:
        if s['ring'] != 'near':
            continue
        me = BD.build_near(s, lidx, roof)
        s['name'] = me.name
        tcol = cols['hero'] if s['style'] == 'twin' else cols['near']
        ob = new_object(me.name, me, tcol)
        s['_rooms'].build(me.name + "_rooms", tcol, KIT)
        stats['near'] += 1
    log("near buildings", stats['near'], f"{time.time() - t0:.1f}s")
    # mid ring merged per 300 m tile, far ring per 700 m tile
    tiles = {}
    for s in specs:
        if s['ring'] == 'near':
            continue
        cx = (s['lot'][0] + s['lot'][1]) / 2
        cy = (s['lot'][2] + s['lot'][3]) / 2
        size = 300.0 if s['ring'] == 'mid' else 700.0
        key = (s['ring'], int(math.floor(cx / size)), int(math.floor(cy / size)))
        tiles.setdefault(key, []).append(s)
    for key, ss in sorted(tiles.items()):
        mb = MB(attrs=('bcol', 'bprm'))
        for s in ss:
            BD.build_massing(mb, s, roof if s['ring'] == 'mid' else [], detail=(s['ring'] == 'mid'))
            s['name'] = f"{key[0]}_{key[1]}_{key[2]}#{s['id']}"
            stats[s['ring']] += 1
        me = mb.build(f"{key[0].upper()}_{key[1]}_{key[2]}", BD.far_mats())
        new_object(me.name, me, cols['mid'] if key[0] == 'mid' else cols['far'])
    log("mid/far", stats, f"{time.time() - t0:.1f}s")
    # rooftop kit as linked duplicates
    for (proto, loc, rz, sc) in roof:
        if proto in ('water_tower', 'antenna') and abs(loc[0]) < 60 and -1200 < loc[1] < 1450:
            # at a 7 deg sun these throw long dark streaks down the hazy canyon
            continue
        ob = SL.inst(cols['roof'], proto, loc, rz, sc)
        if proto == 'antenna':
            # a 22-60 m mast at 7 deg sun throws a 300 m black line through the canyon haze
            ob.visible_shadow = False
    log("rooftop instances", len(roof))
    return stats


def avenue_face_x(tier, side):
    xs = [p[0] for p in tier['poly']]
    return max(xs) if side < 0 else min(xs)


def web_anchors(specs, tower_spec):
    """Corners / ledges facing the avenue, both sides, every ~60 m, z 90-200."""
    anchors = []
    cand = [s for s in specs if s['ring'] == 'near' and s.get('tiers')] + [tower_spec]
    for side in (-1, 1):
        for yt in range(-450, 901, 60):
            best = None
            for s in cand:
                x0, x1, y0, y1 = s['lot']
                if side < 0 and x1 > -LY.HERO_AVE_W / 2 + 1:
                    continue
                if side > 0 and x0 < LY.HERO_AVE_W / 2 - 1:
                    continue
                if s.get('roof_z', 0) < 92:
                    continue
                for ti, t in enumerate(s['tiers']):
                    fx = avenue_face_x(t, side)
                    if abs(fx) > LY.HERO_AVE_W / 2 + 14:
                        continue
                    ys = [p[1] for p in t['poly']]
                    ya, yb = min(ys), max(ys)
                    # ledge = tier top, or a point on the face
                    for z in ([t['z1']] if 90 <= t['z1'] <= 200 else []) + [min(200.0, t['z1'] - 4.0)]:
                        if not (90 <= z <= 200) or z < t['z0']:
                            continue
                        for yc in (ya + 0.3, yb - 0.3, min(max(yt, ya + 1), yb - 1)):
                            d = abs(yc - yt) + abs(fx) * 0.2
                            if best is None or d < best[0]:
                                best = (d, [round(fx, 2), round(yc, 2), round(z, 2)], s.get('name', 'THE_TOWER'),
                                        'corner_ledge' if abs(yc - ya) < 0.5 or abs(yc - yb) < 0.5 else 'face')
            if best and best[0] < 40:
                anchors.append(dict(side='west' if side < 0 else 'east', xyz=best[1], building=best[2], kind=best[3],
                                    target_y=yt))
    return anchors


def write_meta(specs, tower_spec, sky, traffic, counts):
    perch = TW.perch_info()
    sv = lighting.sun_vector(0.0)
    blds = []
    for s in specs:
        x0, x1, y0, y1 = s['lot']
        if LY.dist_to_hero_ave(x0, x1) > 150:
            continue
        blds.append(dict(name=s.get('name'), ring=s['ring'], style=s['style'],
                         footprint_center=[round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)],
                         size=[round(x1 - x0, 2), round(y1 - y0, 2)], lot=[round(v, 2) for v in s['lot']],
                         height=round(s.get('roof_z', s['height']), 2), roof_z=round(s.get('roof_z', s['height']), 2),
                         top_z=round(s.get('top_z', s['height']), 2),
                         tiers=[dict(z0=round(t['z0'], 2), z1=round(t['z1'], 2),
                                     bbox=[round(min(p[0] for p in t['poly']), 2), round(max(p[0] for p in t['poly']), 2),
                                           round(min(p[1] for p in t['poly']), 2), round(max(p[1] for p in t['poly']), 2)])
                                for t in s.get('tiers', [])]))
    meta = dict(
        version=1,
        units="metres, Z up, street asphalt z=0, sidewalks z=0.15",
        avenue=dict(axis=[0, 1, 0], centre_x=0.0, y_range=[-700, 900], wall_to_wall=LY.HERO_AVE_W,
                    roadway=[-LY.ROAD_HALF, LY.ROAD_HALF], sidewalks=[[-16, -10], [10, 16]],
                    cross_streets_y=[round(y, 2) for y in LY.street_ys()], cross_street_width=LY.ST_W,
                    open_to_water_at_y=LY.SHORE[3]),
        sun=dict(direction_to_sun=[round(v, 5) for v in sv], elevation_deg=round(math.degrees(math.asin(sv[2])), 3),
                 azimuth_deg_from_plus_y_toward_plus_x=lighting.SUN_AZIM_DEG,
                 note="dusk=0 values; lighting.sun_vector(dusk) gives others"),
        tower=dict(name="THE_TOWER", footprint=dict(x=[LY.TOWER['x0'], LY.TOWER['x1']], y=[LY.TOWER['y0'], LY.TOWER['y1']]),
                   footprint_center=[LY.TOWER['cx'], LY.TOWER['cy']], height=240.0, roof_z=240.0,
                   crown_top_z=tower_spec['top_z'], east_face_x=TW.EAST_X, pier_front_x=TW.EAST_X + TW.PIER_DP,
                   tiers=[dict(z0=t['z0'], z1=t['z1'], bbox=[min(p[0] for p in t['poly']), max(p[0] for p in t['poly']),
                                                             min(p[1] for p in t['poly']), max(p[1] for p in t['poly'])])
                          for t in TW.TIERS],
                   storey_height=4.0,
                   gargoyle=dict(top_center=[round(v, 3) for v in perch['top_center']], outward=perch['outward'],
                                 perch_size_outward_m=round(perch['size_outward'], 3),
                                 perch_size_across_m=round(perch['size_across'], 3),
                                 beak_tip=[round(v, 3) for v in perch['tip']], wall_x=perch['wall_x'],
                                 clear_air_below="yes, to the sidewalk at z=0.15 (x=-15.45..-13.4 over the west sidewalk)")),
        s5_gap=LM.gap_info(),
        web_anchors=web_anchors(specs, tower_spec),
        traffic=dict(direction="northbound (+Y) on the hero avenue", lanes=[
            dict(kind='travel', x_centre=round((a + b) / 2, 3), width=round(b - a, 3), direction=[0, 1, 0]) for a, b in ST.LANES] +
            [dict(kind='bike', x_range=list(ST.BIKE)), dict(kind='parking', x_range=list(ST.PARK_W)),
             dict(kind='parking', x_range=list(ST.PARK_E))], counts=traffic),
        buildings=blds,
        counts=counts,
        light_ctrl=dict(object="LIGHT_CTRL", props=sorted(lighting.dusk_values(0).keys()),
                        how="lighting.set_dusk(scene, d, frame) writes+keys all props; everything is driven from them"),
    )
    with open(os.path.join(OUT, "city_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def main():
    t0 = time.time()
    reset()
    scene = bpy.context.scene
    scene.name = "CITY"
    cols = make_collections(scene)
    render_settings(scene)
    lighting.setup_lighting(scene, dusk=0.0)
    log("lighting ok")
    specs = LY.make_lots()
    lidx = BD.LotIndex(specs)
    log("lots", len(specs))
    roof = []
    global KIT
    import interiors as INT
    KIT = INT.build_kit(cols['protos'])
    tower_spec = TW.build_tower(cols, lidx, roof)
    tower_spec['name'] = 'THE_TOWER'
    tower_spec['tiers'] = TW.TIERS
    LM.build_skybridges(cols['hero'])
    log("tower + skybridges", f"{time.time() - t0:.1f}s")
    stats = build_buildings(scene, cols, specs, lidx)
    rng = random.Random(LY.SEED + 5)
    ST.build_ground(cols)
    ST.build_sidewalks(cols)
    ST.build_markings(cols, rng)
    sigs = SL.place_street_furniture(cols, specs, rng)
    SL.build_awnings_and_sheds(cols, specs, rng)
    SL.place_steam(cols, rng)
    log('signs', SL.build_shop_signs(cols, specs, rng))
    traffic = SL.place_traffic(cols, sigs, rng)
    peds = SL.place_pedestrians(cols, rng)
    log("street", traffic, "peds", peds, f"{time.time() - t0:.1f}s")
    HZ.build_horizon(cols)
    log("horizon", f"{time.time() - t0:.1f}s")
    MAT.optimise()
    # prototypes live in an excluded collection
    for name, me in PR._protos.items():
        ob = bpy.data.objects.new("PROTO_" + name, me)
        cols['protos'].objects.link(ob)
    lc = bpy.context.view_layer.layer_collection.children.get("CITY_protos")
    if lc:
        lc.exclude = True
    # a default camera at the aerial establishing view
    import mathutils
    cam = bpy.data.objects.new("CITY_cam", bpy.data.cameras.new("CITY_cam"))
    scene.collection.objects.link(cam)
    cam.location = (-250, -900, 380)
    cam.rotation_euler = (mathutils.Vector((0, 300, 60)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 32
    cam.data.sensor_width = 36
    cam.data.clip_end = 20000
    scene.camera = cam
    nrooms = sum(len(o.data.vertices) for o in bpy.data.objects if o.name.endswith('_rooms'))
    log("room/AC instances", nrooms)
    counts = dict(objects=len(bpy.data.objects), meshes=len(bpy.data.meshes), materials=len(bpy.data.materials),
                  buildings=stats, instances=SL.counts(),
                  polygons=sum(len(m.polygons) for m in bpy.data.meshes))
    meta = write_meta(specs, tower_spec, None, traffic, counts)
    log("meta written", counts)
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "city.blend"), compress=True)
    log("saved", f"total {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
