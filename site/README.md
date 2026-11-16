# Sixty Stories: the site

A scroll-driven projector for the 336-frame film. Vanilla JS + a hand-written WebGL2 pipeline,
bundled by Vite into one classic script. No runtime dependencies, no third-party requests
except one Google Fonts stylesheet.

## Build

```sh
cd /home/user/sixty/site
npm install            # once (vite only)
npm run build          # vite build + scripts/postbuild.mjs  ->  dist/
npm run serve          # serves dist/ under http://localhost:4173/deep/base/path/
npm test               # Playwright checks + screenshots (tests/run.mjs, see flags inside)
```

`dist/` shape (BIBLE section 7): `page.html` (host fragment), `index.html` (the same fragment in a
full document), `app.js`, `film/manifest.json`, `film/pack-NNN.bin`. `postbuild.mjs` assembles the
fragment from `src/body.html` + `src/style.css` and fails the build if the fragment has
`<html`/`<head`/`<body`/`<!doctype`, any absolute URL other than fonts.googleapis.com, a script
other than `app.js`, if `app.js` references an absolute URL or a forbidden API, if a file is over
12 MB, or if there are more than 250 files.

## Packing frames

```sh
P=/home/user/tools/bl/bin/python
$P tools/pack_frames.py                      # blender/out/frames + shots.json -> site/public/film
cd site && npm run build                     # copies public/film into dist/film
```

Flags: `--quality 88` (colour WebP), `--depth-quality -1` (lossless; or a lossy quality),
`--max-mb 11.5`, `--jobs 2`, `--out DIR`, `--frames DIR`, `--shots FILE`. Testing only:
`--stride 8`, `--skip-shots s4`. Encoded frames are cached in `tools/.packcache` (keyed by source
size + mtime + settings), so re-packing after more frames land only encodes new ones. Incomplete
or unreadable pairs are skipped and picked up on the next run, so it is safe while rendering.

Placeholder frames for development (never written to blender/out):
`$P tools/make_placeholder_frames.py --out tools/dev` then
`$P tools/pack_frames.py --frames tools/dev/frames --shots tools/dev/shots.json`.
`tests/run.mjs --film ../tools/dev/film-stride8` serves another film dir in place of dist/film.

## Engine

| file | role |
|---|---|
| `src/config.js` | **every tunable**: scroll lengths, smoothing, texture window, effect strengths, curtain timing, shot copy |
| `src/loader.js` | manifest + packs with streamed byte progress; packs kept as Blobs (compressed bytes only) |
| `src/frames.js` | sliding window: prioritised `createImageBitmap` decodes around the playhead (biased to scrub direction), budgeted uploads into a fixed pool of 22 colour+depth texture pairs, `pick()` always returns something (nearest resident frame) |
| `src/timeline.js` | scroll px <-> fractional frame: intro hold, shots proportional to frame count, hold after each cut, credits |
| `src/renderer.js` | passes: picture (2-frame blend, blended-depth parallax, weave, breathing, scrub smear + channel split, exposure, cut flash) -> bright -> blur x2 (halation) -> horizontal streak -> final (halation, streak, vignette, luminance-weighted per-channel grain, mattes) -> depth-occluded dust motes |
| `src/audio.js` | Web Audio score: shot-following minor-mode drone + shimmer, telemetry/velocity-driven wind, low-altitude city bed and far sirens, sub drop + whoosh into THE DROP, launcher snap + line tension at the swing cuts, projector-gate ticks while scrubbing; compressor + soft clipper |
| `src/main.js` | overture, curtain, frame loop, cards, HUD, play mode, credits, input, cursor |

Frame blending only happens between the two nearest *existing* frames of the same shot, so any
subset (every 8th, 4th, 2nd frame, or a missing shot) plays fluidly; cuts are never blended.
Velocity effects are exactly zero below `look.vFloor` frames/s and during play mode, so the
image at rest is the untouched frame plus film grain, halation and vignette.

Keys: arrows step a frame, PageUp/PageDown jump a shot, Home/End, Space play/pause, M sound,
H slate, F full screen. `prefers-reduced-motion` disables parallax, smear, weave, flashes, dust
and grain animation, and shortens the curtain.
