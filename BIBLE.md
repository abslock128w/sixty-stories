# SIXTY STORIES — production bible

An original short film, path traced frame by frame in Blender Cycles, presented as a
scroll-driven cinematic website. The owner asked for: an "insane", photoreal, IMAX-feeling
site; a full photoreal city built in Blender; a photoreal masked hero who swings through
it on lines; a camera that follows him with wild moves.

THE HERO IS AN ORIGINAL CHARACTER: VESPER. The owner asked for Spider-Man; that cannot be
built here (it was blocked by a safety check and then declined by the hero builder as a
reproduction of a protected character), and this must not be worked around: no existing
hero's name, costume, emblem, mask, colour blocking, web pattern or logo anywhere in the
film, site copy, file names or credits. The owner found the first Vesper (graphite
tactical suit and helmet) too far from a classic comic-book swinger, so VESPER v2 is a
bold, colourful, skin-tight costume of our own design: deep cobalt blue with bone-white
panels and gold-amber piping, a masked head with large expressive mirrored-gold lenses in
an original swept-blade shape, an original kite/diamond emblem, slim wrist launchers,
swinging on pale high-tensile lines. Site copy says "an original short film". Loading time is explicitly a non-goal ("5 hours is fine"). Quality is
the only goal. The owner is asleep: nobody can answer questions or approve anything. Never
stop to ask; decide, note the decision in your final report, and keep going.

This file is the contract between builders working in parallel. Do not change a contract
in it; if one is truly unworkable, implement the nearest thing and say so in your report.

## 1. Machine facts (verified)

- 4 CPU cores, 15 GB RAM, ~30 GB free disk, NO GPU. Cycles CPU only (EEVEE unusable).
- Blender is the `bpy` 5.3.0 Python module: `/home/user/tools/bl/bin/python your_script.py`
  (alias below as `$PY`). numpy and Pillow are installed there; `$PY -m pip install` works.
  OpenImageDenoise works. Sky texture types: SINGLE_SCATTERING, MULTIPLE_SCATTERING,
  PREETHAM, HOSEK_WILKIE. Blender 5.x API differs from 2.8-4.x in places (compositor node
  groups, action slots/layered actions, `World.use_nodes` deprecated, EEVEE renames):
  introspect with `dir()` / `bl_rna.properties` instead of trusting memory.
- Node 22 + npm, ffmpeg (libx264, libwebp, libvpx-vp9, libsvtav1), Playwright + Chromium
  preinstalled (`require('playwright')`, `chromium.launch()`; do NOT `playwright install`).
  Headless WebGL2 works with args
  `['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']`.
- Network: npm and PyPI work. Public GitHub works via `git clone` and
  `raw.githubusercontent.com`. Almost everything else is blocked (polyhaven, blender.org,
  jsdelivr, huggingface...). Do not try to change network settings. Any third-party asset
  must be CC0 / MIT / similarly permissive, and be listed in `/home/user/sixty/CREDITS.md`
  (name, source URL, licence). Procedural-first.
- Several builders share the 4 cores. During the build phase set
  `scene.render.threads_mode='FIXED'; scene.render.threads=2` for look-dev renders and keep
  previews small (<= 960 px wide, <= 64 samples + denoise). Only the final film render uses
  all cores.
- You can LOOK at images with the Read tool. Do it constantly: render, look, criticise like
  a VFX supervisor, fix, repeat. Never report something as good that you have not looked at.

## 2. Layout

```
/home/user/sixty/
  BIBLE.md  CREDITS.md
  blender/
    common/        shared python helpers (anyone may add files; do not edit others' files)
    city/          CITY builder's scripts
    hero/          HERO builder's scripts
    film/          FILM builder's scripts (shots, cameras, render)
    out/
      city.blend  city_meta.json
      hero.blend
      film.blend  shots.json
      preview/<role>/*.png            look-dev stills (keep the good ones)
      frames/color/f_0000.png ...     final frames (see 6)
      frames/depth/f_0000.png ...
  site/            Vite project; `npm run build` -> site/dist
  tools/           pack_frames.py etc.
```

## 3. World conventions

- Metres. Z up. Ground (street asphalt) at z = 0. One Blender unit = 1 m.
- The hero avenue ("the canyon") runs along the Y axis, centred on x = 0, from y = -700 to
  y = +900. The hero travels toward +Y. Avenue is ~32 m wall to wall (roadway ~20 m plus
  two ~6 m sidewalks). Cross streets ~18 m wall to wall, every ~80-90 m. City extends at
  least 1.2 km in every direction from the origin, lower detail with distance; beyond that
  a horizon treatment (haze, water, far skyline silhouettes) so no shot ever shows an edge.
- THE TOWER: an Art Deco masonry skyscraper, the hero's perch. Footprint centred at
  (x = -46, y = -300), so its east face is the avenue's west street wall. Height 240 m
  (sixty stories), with setbacks and a crown. On the north-east corner at z ~= 228 m there
  is a stone gargoyle/eagle ledge that cantilevers out toward the avenue: a flat-topped
  perch at least 0.8 m x 1.6 m with clear air below. `city_meta.json` gives its exact
  top-centre coordinate and outward direction.
- Time: golden hour, the sun low (elevation 5-9 degrees) and aligned almost straight down
  the avenue from the +Y end (azimuth within ~6 degrees of the avenue axis, chosen so the
  east-facing canyon wall still catches raking light). The hero swings INTO the sun:
  backlight, rim light, flares, long shadows, haze shafts between towers. Windows are just
  beginning to glow. The final shot drifts toward dusk (lights up, sky deepens).
- Colour pipeline: scene-linear Rec.709, AgX view transform. Final look is graded in
  Blender (look + compositor). Film grain is NOT baked into frames; the site adds it.

## 4. The film: shot list (24 fps timeline, 336 frames total)

Global frame index `i` runs 0..335 across all shots. Every frame is a keeper: scroll
position on the site maps directly to `i`, so each shot must read as one continuous,
elegant move with no dead frames, and first/last frames must be strong stills.

| id | frames | i range | title | content |
|----|--------|---------|-------|---------|
| s1 | 48 | 0-47 | THE CITY | High aerial over the skyline at ~350 m, slow push-in and tilt-down through sun-shot haze, discovering the canyon and The Tower. No hero (or a speck on the gargoyle in the last frames). |
| s2 | 48 | 48-95 | THE PERCH | Long-lens (85-135 mm) slow arc around the hero crouched on the gargoyle, 228 m up. Shallow depth of field, city bokeh, sun kissing the lenses, suit fabric detail visible. He lifts his head. |
| s3 | 48 | 96-143 | THE DROP | He tips forward and dives. Camera goes over the shoulder then looks straight down the tower face: full vertigo, facade streaking past, street rushing up. |
| s4 | 72 | 144-215 | THE SWING | Web fires to a tower across the avenue, the line snaps taut ~25 m above the traffic and he pendulums down the canyon. Camera chases close behind and low, whips underneath him, overtakes and looks back at him with the sun flaring behind. |
| s5 | 48 | 216-263 | THREAD THE NEEDLE | Second swing: he releases, tucks, flips through a tight gap (skybridge / between two close towers / over an elevated crossing), then fires again. Side tracking on a long lens, then a snap-zoom. |
| s6 | 72 | 264-335 | APEX | Top of the arc: he hangs weightless against the sun, classic pose. Camera spirals up around him then pulls far back and up until he is a speck and the entire city fills the frame at dusk. Last frame holds as the end-title plate. |

Frame size 1920 x 804 (2.39:1). Motion blur on (shutter ~0.5), real depth of field.

## 5. Asset contracts

### city.blend (CITY builder)
- Top collection `CITY`; children by kind (`CITY_buildings_hero`, `CITY_buildings_mid`,
  `CITY_buildings_far`, `CITY_street`, `CITY_props`, `CITY_vehicles`, `CITY_atmo`...).
- The world (sky + sun) and atmosphere live in city.blend and are created by
  `blender/common/lighting.py: setup_lighting(scene, dusk=0.0)`; `dusk` in 0..1 moves from
  golden hour toward blue hour (sun lower/redder, sky deeper, window + street-light emission
  up). It must be callable again on an existing scene and be animatable per frame (expose
  the driven values as custom properties on an empty named `LIGHT_CTRL`, or document how).
- `city_meta.json`: avenue axis and width, sun direction, The Tower (footprint, height,
  gargoyle top-centre xyz, outward vector), every building within 150 m of the avenue
  (name, footprint centre, size x/y, height, style, roof z), skybridge/gap location for s5
  (two towers 12-18 m apart or a bridge at 60-90 m altitude, located y in 250..450),
  suggested web anchor points (xyz on building corners/ledges along the canyon, both sides,
  every ~60 m, z 90-200 m), traffic lanes.
- Must load and render a 1920x804 frame within ~9 GB RAM. Use instancing / shared mesh data.

### hero.blend (HERO builder)
- Collection `HERO` holding armature object `HERO_RIG` and its meshes (all parented to the
  rig, so moving/rotating `HERO_RIG` moves everything). Height 1.78 m, origin between the
  feet on the ground, rest pose facing -Y (Blender front view shows his front).
- `blender/hero/hero_api.py` (importable from any bpy script, no side effects on import):
  - `append_hero(blend_path=DEFAULT) -> rig object` (appends collection `HERO` into the
    current scene).
  - `POSES: dict[str, ...]` and `apply_pose(rig, name, frame, weight=1.0)`: sets every pose
    bone and inserts keyframes at `frame` (weight < 1 blends from the current pose), so
    shots are animated by keying named poses over time plus moving `HERO_RIG`.
  - `add_web(rig, hand='R'|'L', anchor=(x,y,z), frame_on, frame_off, name) -> object`:
    a web line from that hand to a world-space anchor, taut, following the hand every
    frame, visible only between those frames; `slack` option for a just-fired sagging line.
  - `GRIP` info: which local point on the hand the line attaches to.
- Required poses (minimum): `perch_crouch`, `perch_look_up`, `leap`, `dive`, `dive_reach`,
  `shoot_R`, `shoot_L`, `swing_R`, `swing_L`, `swing_tuck`, `release_arch`, `flip_tuck`,
  `apex_classic`, `freefall_spread`.

### film.blend + frames (FILM builder)
- Built by a script that opens city.blend, appends the hero, creates per-shot cameras and
  animation on one timeline (frame = global index i), binds cameras with timeline markers.
- `shots.json`: `{fps, width, height, total, shots:[{id, title, start, count, lens_mm,
  logline}], telemetry:[{i, altitude_m, speed_kmh}]}` (hero altitude above street and
  speed, for the site's HUD; for s1 use the camera).

## 6. Frame delivery contract (FILM -> site)

- `blender/out/frames/color/f_%04d.png`: 1920x804, 8-bit sRGB, final graded image.
- `blender/out/frames/depth/f_%04d.png`: 960x402, 8-bit greyscale,
  `v = round(255 / (1 + z/25))` with z = camera-space distance in metres
  (0 m -> 255, 25 m -> 128, 250 m -> 23, sky -> 0).
- Frames are written atomically (write to a temp name, then rename), any subset may exist
  at any moment, and the render order is progressive: every 8th frame of the whole film
  first, then every 4th, every 2nd, then the rest. The site must look right with any subset.
- `tools/pack_frames.py` (SITE builder) turns whatever frames exist plus `shots.json` into
  `site/public/film/manifest.json` + `pack-NNN.bin` (each <= 12 MB):
  `{width, height, fps, total, shots:[...], telemetry:[...], packs:[names],
    frames:[{i, pack, off, len, doff, dlen}]}` where off/len locate the colour WebP and
    doff/dlen the depth WebP inside the pack. Only existing frames are listed, sorted by i.

## 7. Website contract (SITE builder)

- Ships as static files with only relative URLs. It will be published inside a locked-down
  hosted frame, so:
  - `site/dist/page.html` is an HTML *fragment*: no doctype/html/head/body tags. It starts
    with `<title>Sixty Stories</title>`, then
    `<meta name="claude:viewport-fit-sides" content="cover">`, then one `<style>`, then
    markup, then `<script src="app.js"></script>` (one bundled classic or module script
    file; everything, three.js etc. included, is bundled into it or sibling files).
    `site/dist/index.html` wraps the same fragment in a full document for normal hosting.
  - No runtime requests to any other host. Only exception: one Google Fonts `<link
    rel="stylesheet">` (always with a real fallback stack; the page must look deliberate
    with the fallback too).
  - `fetch()` of sibling files works. Web Workers from own files or blob: URLs work.
    Service workers, `alert/confirm/prompt`, `window.open`, downloads, query strings and
    pushState do not. Audio only starts after a click. Fullscreen may be refused: optional.
  - Dark single-theme by choice: set every colour explicitly as tokens on `:root`, plus
    `color-scheme: dark`, explicit `body` background. Side gutters on text use
    `max(16px, env(safe-area-inset-left, 0px))` (and -right). Fixed edge elements add
    `env(safe-area-inset-*)`. Must work at 400 px wide; the body never scrolls sideways.
    Respect `prefers-reduced-motion`. Wrap any localStorage use in try/catch.
  - Total: at most ~250 files, no single file over 12 MB.
- Loading may take as long as it likes but must never crash the tab: keep compressed frames
  in memory and decode a sliding window around the playhead; never hold all 336 decoded.
