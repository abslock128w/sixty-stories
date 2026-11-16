#!/bin/bash
# Render "Sixty Stories" on a Mac (Apple Silicon), on the GPU. Resumable: run it again to continue.
#   ./render_mac.sh --frames 0-0        one test frame (time it first!)
#   ./render_mac.sh --shot s1           the opening shot
#   ./render_mac.sh                     everything, progressive order
set -e
cd "$(dirname "$0")"
PYBIN="$(command -v python3.13 || true)"
if [ -z "$PYBIN" ]; then echo "Python 3.13 is needed once to set up: brew install python@3.13"; exit 1; fi
if [ ! -x .venv/bin/python ]; then
  "$PYBIN" -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install bpy==5.3.0 numpy pillow
fi
mkdir -p blender/out/frames/color blender/out/frames/depth
export SIXTY_GPU=METAL
caffeinate -i .venv/bin/python blender/film/render_frames.py --threads 0 "$@"
