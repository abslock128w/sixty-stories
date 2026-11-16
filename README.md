# Sixty Stories

A short film path traced in Blender Cycles and shown on a scroll-driven website.
`BIBLE.md` is the production spec, `STATUS.md` the running log.

## Render on a Mac (Apple Silicon)

```bash
git clone https://github.com/abslock128w/sixty-stories
cd sixty-stories
./render_mac.sh --frames 0-0
```

The first run creates `.venv` and installs Blender's Python module (about 1 GB, Python 3.13
required: `brew install python@3.13`). Frames land in `blender/out/frames/color` and
`/depth`; timing per frame is logged in `blender/out/frames/render.log`. Then:

```bash
./render_mac.sh --shot s1
```

The script is resumable (finished frames are skipped). Shots s2-s6 contain the hero, whose
costume is not final: render s1 only until told otherwise.

Send frames back with:

```bash
git add -f blender/out/frames/color blender/out/frames/depth && git commit -m "Frames from the Mac" && git push
```
