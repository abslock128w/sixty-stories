# LOOKLAB: how to design a look for "Sixty Stories"

You are designing the lighting and grade of a finished, locked film: six shots, 336 frames,
Blender 5.3 Cycles (CPU only). Layout, animation, cameras and hero are done and are
**not yours to change**. You write one Python file that sets the look, and you judge it on
seven reference frames rendered through a shared harness.

## 1. The contract

- A look is one file: `blender/film/looks/<name>.py`, exposing `apply(scene)`.
- `apply(scene)` is called once, on the fully built scene: city, hero, animation, cameras and
  render settings are already in place, with a neutral look. It must set or key **everything
  about the look across the whole 0..335 timeline**:
  - LIGHT_CTRL keys (hold a value across a shot with a key at each end of it; ramps inside
    s6 are fine);
  - world and material overrides;
  - any extra lights or cards (object names must start with `LOOK_`);
  - view transform and look;
  - the compositor tree, built from scratch.
- It must be **idempotent** (calling it twice gives the same result) and **self-contained**. It
  may import only `bpy`, `mathutils`, `lighting` (blender/common), `shot_settings` and
  `lookkit` (the shared helpers next to your file).
- Do not touch hero colours. Hero-specific per-shot tuning lives in `blender/film/hero_tune.py`,
  owned by the FILM builder.
- Do not edit other people's look files. Do not edit `blender/city`, `blender/hero` or
  `blender/common`.
- The compositor must keep the `DEPTH_OUT` file-output node fed by `RenderLayers.Depth`; the
  frame delivery reads it. `lookkit.new_compositor()` creates it for you. If you build a tree
  by hand, call `lookkit.add_depth_out(tree, rl_node)`. render_frames.py also adds it if it
  is missing.
- Integration: `blender/film/build_film.py` calls `looks.<LOOK>.apply(scene)` as its last step,
  with `LOOK` taken from `blender/film/shot_settings.py`. Switching looks is that one constant.

### Files
| path | what |
|---|---|
| `blender/out/looklab/plate.blend` | the look-neutral built scene: hero, animation, cameras, timeline markers. Self-contained. |
| `blender/out/looklab/shots.json` | shot table, telemetry, hero screen position per frame |
| `blender/film/looks/base.py` | the approved v1 look (the Vesper render): the reference starting point |
| `blender/film/looks/incumbent.py` | the FILM builder's current candidate |
| `blender/film/looks/lookkit.py` | helpers (below) |
| `blender/film/looklab/render_look.py` | the harness |

## 2. The harness

```
PY=/home/user/tools/bl/bin/python
$PY blender/film/looklab/render_look.py --look mylook --out blender/out/looklab/cand_x \
    --frames 0,90,130,180,244,276,335 --width 960 [--samples N] [--threads 4] [--exr]
$PY blender/film/looklab/render_look.py --look mylook --comp-only blender/out/looklab/cand_x/exr \
    --out blender/out/looklab/cand_x_grade
```

- `--look` takes a name in `blender/film/looks/` or a path to any `.py` file.
- Output is `<out>/f_XXXX.png`, rendered through your compositor at the given width (2.39:1),
  with the per-shot final quality from `shot_settings.SHOT` (samples, adaptive threshold,
  hero subdivision), motion blur and depth of field on.
- `--exr` also saves `<out>/exr/f_XXXX.exr`: the scene-linear combined pass **before** the
  compositor. `--comp-only <exrdir>` then re-runs only your compositor on those files, at
  about 0.5 s per frame. Use it to iterate glare and grade without re-rendering. The view
  transform and look still apply, because they are part of the colour management.
- **Lock:** the whole run holds an exclusive `flock` on `blender/out/looklab/.render.lock`.
  Several designers share 4 cores and 15 GB, so calls queue. Never render outside the
  harness.
- **Cost:** at 960 px a reference frame takes about 15–25 s on 4 idle threads (s1 and s6
  are cheapest, s2–s5 dearest). All seven take about 2.5 min idle, and 2–3× that while
  another render runs.
- **Final budget:** the film average must stay at or under about 95 s per frame at 1920×804 on
  4 threads; the current looks run 60–100 s. Volume density, extra lights and the number of
  glare nodes affect cost. Glare nodes are cheap at 960 but scale with resolution.

### Reference frames (judge on these)
| frame | shot | what it is |
|---|---|---|
| 0 | s1 THE CITY | high aerial into the sun over the skyline |
| 90 | s2 THE PERCH | 135 mm on the hero crouched on the steel prow, canyon behind |
| 130 | s3 THE DROP | looking down the tower facade at the diving hero |
| 180 | s4 THE SWING | under the hero at the bottom of the swing, canyon toward the sun |
| 244 | s5 THREAD THE NEEDLE | low, looking up through the skybridge slot |
| 276 | s6 APEX | hero against the sun at the top of the arc |
| 335 | s6 end plate | the whole city at dusk; the title sits here |

## 3. Shots, frame ranges, starting presets

The neutral plate keys these shipped presets; `base.py` adds the exposure offsets below.

| shot | frames | preset (dusk) | base exposure offset |
|---|---|---|---|
| s1 | 0–47 | aerial (0) | 0 → +0.1 |
| s2 | 48–95 | closeup (0) | 0 |
| s3 | 96–143 | canyon (0) | −0.7 → −0.3 |
| s4 | 144–215 | canyon (0) | 0 |
| s5 | 216–263 | canyon (0) | −1.6 → −2.5 (252–263 into the sun) |
| s6 | 264–335 | closeup 0.15 → closeup 0.3 (296) → aerial 0.6 (318) → dusk_wide 0.9 (335) | 0 / +0.3 |

## 4. Every knob

### 4.1 LIGHT_CTRL (empty object; everything time-of-day is driven from its custom properties)

Read `blender/common/lighting.py` for the formulas. Drivers read these properties every
frame. Keyed values win at render time.

| property | effect |
|---|---|
| `dusk` | informational 0..1 master (0 golden hour, 1 blue hour) |
| `sun_elev`, `sun_azim` | sun elevation / azimuth (rad; azimuth from +Y toward +X). The sky texture and sun lamp both follow them. Keep the azimuth near 0.035 (the avenue axis). |
| `sun_rot_x`, `sun_rot_z` | sun lamp euler, derived; keep consistent with elev/azim (`set_dusk` computes them) |
| `sun_strength` | sun lamp irradiance (W/m²); 10 at golden hour |
| `sun_r/g/b` | sun lamp colour (1, 0.6, 0.3 at dusk 0) |
| `sun_x/y/z` | unit vector to the sun; the cloud forward-scatter glow and the window grazing glow use it |
| `sky_strength` | multiplier on the sky texture (0.17 at golden hour). Raises sky fill and blue shadows. |
| `cloud_strength`, `cloud_r/g/b` | high cloud layer brightness and sunlit tint |
| `haze_density` | base extinction (1/m) of all haze boxes. **It behaves like a switch near 0.0001: keep it ≥ 0.00012.** |
| `haze_r/g/b` | scattering colour (albedo) of the haze. White-ish reads beige under the orange sun; cooler values make the sun side orange and the rest blue-grey. |
| `window_emit` | interior light multiplier on window materials |
| `window_frac` | fraction of windows lit (0..1) |
| `street_emit` | street lamps, signals, signs, shop light |
| `car_emit` | head and tail lights |
| `exposure` | drives `scene.view_settings.exposure` (stops) |

API (import lighting):
- `lighting.set_dusk(scene, d, frame=None)` writes every property from dusk `d`; with
  `frame` it keys them all.
- `lighting.apply_preset(scene, name, dusk=0, frame=None)` does `set_dusk`, then the overrides
  in `lighting.PRESETS[name]`, keyed when `frame` is given:
  - `canyon`: exposure 1.4
  - `aerial`: haze 0.00012, haze rgb 0.35/0.32/0.30, exposure 0, sky 0.13
  - `closeup`: haze 0.0002, exposure 0.4
  - `dusk_wide`: haze 0.00012, cool haze rgb; use with dusk 1.0
- `lighting.touch(scene)`: call after editing LIGHT_CTRL by hand, so drivers refresh.

**Pitfalls:**
- The plate already has keys on LIGHT_CTRL. A manual `ctrl[k] = v` is overwritten by its
  fcurve at render time. Either key your values, or call `lookkit.clear_ctrl_keys()` first.
  `lookkit.key_light()` clears and re-keys everything.
- Each `apply_preset(..., frame=f)` keys every property, so the values interpolate linearly
  between your keys. To hold a value across a shot, key both of its ends.

### 4.2 Haze (volumes, collection CITY_atmo)

Homogeneous Principled Volume boxes, shadowed by buildings (this is what makes the shafts).
The sun lamp is not attenuated by them. Their density is `haze_density × multiplier`:

| object | material | density × | extent |
|---|---|---|---|
| `ATMO_haze_box` | `ATMO_haze` | 1 | everywhere, z −2..650 |
| `ATMO_haze_low_box` | `ATMO_haze_mat_low` | 2 | everywhere, z −1..140 |
| `ATMO_haze_canyon` | `ATMO_haze_mat_canyon` | 4.5 | the avenue x ±16, y −1200..1460, z 0..80 |

- Each material has a `LowMul` math node (the multiplier) and a `CTRL_haze_density` value
  node. Anisotropy defaults to 0.65 on the `Principled Volume` node.
- Higher anisotropy (0.8+) gives a stronger glow toward the sun and darker air away from it,
  so shafts read better. `lookkit.haze_anisotropy(v)` sets it on all three.
- You may change the per-box multiplier (`LowMul`, inputs[1]) by material, for example a
  thinner canyon for crisper beams.
- Volume cost grows with density; noise lives mostly in the volumes. Adaptive sampling and
  OIDN leave a fine grain on fast, motion-blurred haze.

### 4.3 Sky, world and sun
- World `CITY_world`:
  - two Sky Texture nodes, `SkyDisc` (seen by the camera) and `SkyNoDisc` (lighting),
    type MULTIPLE_SCATTERING, altitude 30, air 1, aerosol 2.2, ozone 1, sun_intensity 0.6,
    all editable;
  - elevation and rotation are driven, so do not set them by hand;
  - `MixSky` picks between them by `Is Camera Ray`;
  - the cloud layer is a procedural projection: nodes `CloudOpacity` (inputs[1] = coverage
    opacity 0.92), `CloudTint` (driven rgb), plus noise nodes you can edit;
  - the result goes through the `CTRL_sky_strength` multiply to a Background node.
- Sun lamp: object `SUN` (angle 0.55°); energy, colour and rotation are driven from
  LIGHT_CTRL.
- The visible sun disc comes from `SkyDisc`; its brightness is the sky texture's
  `sun_intensity` × `sky_strength`.

### 4.4 City emission
- Window material `window`:
  - lit fraction and brightness come from `window_frac` and `window_emit`;
  - it has a grazing-angle glass glow toward the sun that fades with `sun_strength` (value
    nodes `CTRL_sun_x/y/z`, `CTRL_sun_strength`).
- Street and car lights: `lamp_emit`, `flood`, `sig_red/green/amber`, `sign_*`, `shop`,
  `headlight`, `taillight`. Each reads `street_emit` or `car_emit`; scale those, or scale the
  emission in the material.

### 4.5 Materials worth overriding (names in bpy.data.materials)
- `asphalt`: Principled; roughness and base colour come from noise networks (linked).
  - **Wet / glossy avenue:**
    ```
    m, nodes = lookkit.principled('asphalt')
    lookkit.scale_input(m, nodes[0], 'Roughness', 0.2)
    lookkit.set_input(m, nodes[0], 'Specular IOR Level', 0.9)
    lookkit.tint_base(m, nodes[0], (0.6, 0.6, 0.6))
    ```
    The street then mirrors the sun glare, the tail lights and the sky. It is most visible in
    s4 (frames 144–170) and s3.
- `sidewalk`, `curb`
- Facades: `limestone`, `brick`, `terracotta`, `concrete`, `panel`, `cw_spandrel`,
  `tower_stone`, `tower_spandrel`, `trim`, `metal_dark`, `metal_alu`, `metal_bronze`
- Glass: `window` (all facade glazing), `glass_clear` (skybridges), `car_glass`, `water`
- Steel: `steel_deco` (The Tower crown, mirror-like), `steel_prow` (the hero's perch)
- Hero materials start with `HERO_`. Do not touch them; that is hero_tune's job.
- `lookkit` helpers create nodes named `LOOK_…`, so a second `apply()` updates them instead
  of stacking.

### 4.6 Extra lights / cards (motivated only)
Create lights in `apply()` with names starting `LOOK_`, and remove old ones first
(`lookkit.remove_look_objects()`). A fill or rim parented to the hero:
```python
import bpy
ld = bpy.data.lights.new('LOOK_hero_fill', 'AREA'); ld.energy = 30; ld.size = 2
ld.color = (0.55, 0.7, 1.0)
ob = bpy.data.objects.new('LOOK_hero_fill', ld)
bpy.context.scene.collection.objects.link(ob)
ob.parent = bpy.data.objects['HERO_RIG']; ob.parent_type = 'BONE'; ob.parent_bone = 'spine03'
ob.location = (0, -1.5, 0)            # bone space (bone Y = along the spine)
ob.visible_camera = False
```
Key the energy per shot (`ld.keyframe_insert('energy', frame=f)`), with CONSTANT
interpolation at shot boundaries. To avoid spill, restrict it with light linking
(`ob.light_linking.receiver_collection`) to the `HERO` collection.

### 4.7 Compositor (Blender 5.x: node-group based)
- The tree is a `CompositorNodeTree` node group assigned to `scene.compositing_node_group`.
  It has a Group Output with one `Image` socket, which is the final image. There is no
  Composite node in 5.x.
- `lookkit.new_compositor(scene)` returns `(tree, rl, out)` with `DEPTH_OUT` already wired.
  `lookkit.chain(tree, rl.outputs['Image'], [n1, n2, ...], out.inputs[0])` links a linear
  chain.
- Glare `CompositorNodeGlare`: every parameter is an input socket.
  - `Type`: Bloom, Streaks, Ghosts, Fog Glow, Simple Star, Sun Beams, Kernel
  - `Quality`: Low, Medium, High
  - Numeric inputs: `Threshold`, `Smoothness`, `Strength`, `Size` (bloom), `Saturation`,
    `Tint`, `Streaks`, `Streaks Angle` (radians; 0 is horizontal, i.e. anamorphic),
    `Fade`, `Iterations`, `Color Modulation`, `Sun Position`, `Jitter`
  - Outputs: `Image` (image + glare), `Glare` (glare only), `Highlights`
  - Use `lookkit.glare(tree, name, Type=..., ...)`.
- Colour Balance `CompositorNodeColorBalance`:
  - `Type` menu: 'Lift/Gamma/Gain', 'Offset/Power/Slope (ASC-CDL)', 'White Point'
  - Value and colour sockets share names (`Lift` VALUE and `Lift` RGBA, etc.).
    `lookkit.cdl()` handles ASC-CDL.
  - It works in **scene-linear, before** the view transform.
- Colour Correction `CompositorNodeColorCorrection`: master, highlights, midtones and shadows
  sets of Saturation, Contrast, Gamma, Gain and Offset (the sockets repeat in that order;
  index them), plus `Midtones Start` and `Midtones End`.
- RGB Curves `CompositorNodeCurveRGB`: `node.mapping.curves[0..3]` (C, R, G, B). Add points
  with `.points.new(x, y)`, then call `node.mapping.update()`. The input is scene-linear, so
  curve on a log-ish range.
- Also available: Lens Distortion (`CompositorNodeLensdist`), Exposure, Hue/Sat, Tonemap,
  Blur, Defocus, Separate/Combine Color (`CompositorNodeSeparateColor` /
  `CompositorNodeCombineColor`). For blending images in 5.x, use `ShaderNodeMix`
  (`data_type='RGBA'`, any `blend_type`) and `ShaderNodeMath`: both work inside compositor
  trees here, but `ShaderNodeSeparateColor` / `ShaderNodeCombineColor` do not. Introspect
  with `dir(bpy.types)`.
- **No film grain, no heavy vignette, no chromatic aberration:** the website adds those.
- **The compositor must run on CPU** (`scene.render.compositor_device = 'CPU'`); GPU crashes
  headless. `new_compositor` sets it.

### 4.8 View transform
- `scene.view_settings.view_transform = 'AgX'`. The look is set by string; verified to work
  here: 'AgX - Punchy', 'AgX - Very High Contrast', 'AgX - High Contrast',
  'AgX - Medium High Contrast', 'AgX - Base Contrast', 'AgX - Low Contrast' (the usual AgX
  set). Introspecting the enum in background mode only lists 'NONE' (it is a dynamic enum),
  so set the string and read it back.
- Exposure is keyed through LIGHT_CTRL['exposure'] (the scene exposure is driven). Do not set
  `view_settings.exposure` directly.

## 5. A worked minimal look
```python
"""mylook: example."""
import lookkit as K

LIGHT = [  # (frame, preset, dusk, exposure offset[, {overrides}])
    (0, 'aerial', 0.0, -0.3), (47, 'aerial', 0.0, -0.3),
    (48, 'closeup', 0.0, -0.2), (95, 'closeup', 0.0, -0.2),
    (96, 'canyon', 0.0, -0.8, {'haze_density*': 0.7}), (215, 'canyon', 0.0, -0.6, {'haze_density*': 0.7}),
    (216, 'canyon', 0.0, -2.0), (263, 'canyon', 0.0, -2.4),
    (264, 'closeup', 0.15, -0.3), (318, 'aerial', 0.6, 0.0), (335, 'dusk_wide', 0.95, 0.2),
]

def apply(scene):
    K.remove_look_objects()
    K.key_light(scene, LIGHT, base_ovr={'sun_g': 0.5, 'haze_b': 1.0, 'haze_r': 0.8})
    K.haze_anisotropy(0.8)
    K.view(scene, 'AgX - High Contrast')
    ng, rl, out = K.new_compositor(scene)
    bloom = K.glare(ng, 'BLOOM', Type='Bloom', Quality='High', Threshold=1.0, Strength=0.3, Size=0.6)
    grade = K.cdl(ng, 'GRADE', offset=(-0.005, 0, 0.008), slope=(1.05, 1.0, 0.95))
    K.chain(ng, rl.outputs['Image'], [bloom, grade], out.inputs[0])
```
Render it with:
`$PY blender/film/looklab/render_look.py --look mylook --out blender/out/looklab/cand_mine --exr`

## 6. Pitfalls we hit
- Never build on the factory startup scene (it has a default cube). Always open the plate.
- The compositor must be CPU, or Blender aborts (Vulkan/EGL) in background mode.
- After editing LIGHT_CTRL by hand, call `lighting.touch(scene)`. At render time the keyed
  fcurves override manual values (see 4.1).
- `haze_density` below about 0.0001 switches the haze off abruptly.
- Haze looking into the sun at canyon level (s5, s4 end, s6 start) clips to white easily.
  Exposure for those frames sits 1.5–2.5 stops below the canyon preset.
- Material node edits accumulate unless you name your nodes and reuse them (lookkit does
  this).
- Keys at shot boundaries: a look key at a cut frame interpolates into the neighbouring shot
  over one frame. Put keys at both the last frame of a shot and the first of the next.
- Motion blur samples the timeline at ±0.25 frame. Values that jump at a cut are fine, as
  long as they are keyed on both sides.
- The hero is being replaced by Vesper v2 (cobalt blue, bone white, gold lenses; an
  original design). Judge him for readability only; colour tuning of the hero is not part
  of a look.
