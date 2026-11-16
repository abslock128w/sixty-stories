"""Pack rendered frames into the site's film packs (BIBLE section 6).

Reads   <frames>/color/f_%04d.png + <frames>/depth/f_%04d.png  (any subset)
        <shots>  (shots.json from the film render)
Writes  <out>/manifest.json + <out>/pack-NNN-<hash>.wasm  (each pack <= --max-mb, decimal MB)
        Pack names carry a hash of their bytes, so a republished manifest can never be paired
        with a stale cached pack. New packs are written first, then the manifest (atomically),
        then packs the new manifest no longer names are deleted.
        The manifest also carries per-frame hero_screen [x, y, h] and lens_mm from shots.json.

Colour -> lossy WebP (quality --quality, method 6); depth -> lossless WebP (or --depth-quality).
Encoded frames are cached in --cache keyed by source size+mtime+settings, so re-packing after
more frames land only encodes the new ones. Safe while the renderer is writing: frames whose
pair is incomplete or unreadable are skipped (and picked up next run).

Run with Blender's python (Pillow + numpy):
  /home/user/tools/bl/bin/python tools/pack_frames.py
  /home/user/tools/bl/bin/python tools/pack_frames.py --frames tools/dev/frames \
      --shots tools/dev/shots.json --stride 8 --skip-shots s4      # dev/test subsets
"""
import argparse, hashlib, io, json, math, os, re, sys, time
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = re.compile(r"^f_(\d{4})\.png$")


def encode_one(job):
    """Encode (or fetch from cache) one frame pair. Returns (i, color_path, depth_path) or (i, None, err)."""
    i, cpath, dpath, cache, q, dq, expect = job
    try:
        out = []
        for kind, src in (("c", cpath), ("d", dpath)):
            st = os.stat(src)
            setting = f"q{q}" if kind == "c" else ("lossless-m4" if dq < 0 else f"q{dq}")
            key = hashlib.sha1(f"{os.path.abspath(src)}|{st.st_size}|{st.st_mtime_ns}|{setting}|v1".encode()).hexdigest()[:16]
            dst = os.path.join(cache, f"{kind}_{i:04d}_{key}.webp")
            if not os.path.exists(dst):
                with Image.open(src) as im:
                    im.load()
                    if kind == "c":
                        im = im.convert("RGB")
                        if expect and im.size != expect:
                            print(f"  warn: f_{i:04d} colour is {im.size}, expected {expect}", flush=True)
                        kw = dict(quality=q, method=6)
                    else:
                        im = im.convert("L").convert("RGB")
                        # lossless effort 60 / method 4: within a few % of max effort at a fraction
                        # of the CPU (the final render shares these cores)
                        kw = dict(lossless=True, quality=60, method=4) if dq < 0 else dict(quality=dq, method=6)
                    buf = io.BytesIO(); im.save(buf, "WEBP", **kw)
                tmp = dst + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(buf.getvalue())
                os.replace(tmp, dst)
                # drop stale cache entries for this frame/kind
                for f in os.listdir(cache):
                    if f.startswith(f"{kind}_{i:04d}_") and f.endswith(".webp") and os.path.join(cache, f) != dst:
                        try: os.remove(os.path.join(cache, f))
                        except OSError: pass
            out.append(dst)
        return (i, out[0], out[1])
    except Exception as e:  # unreadable / half-written: skip this run
        return (i, None, f"{type(e).__name__}: {e}")


def atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def _num(v):
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def per_frame_hero(shots, total):
    """[x, y, h] per frame index (x, y from the top-left of the frame, h = hero height as a
    fraction of frame height), or None where shots.json has no position for that frame."""
    out = [None] * total
    for e in shots.get("hero_screen") or []:
        if not isinstance(e, dict): continue
        i = e.get("i")
        x, y, h = _num(e.get("x")), _num(e.get("y")), _num(e.get("h"))
        if isinstance(i, int) and 0 <= i < total and x is not None and y is not None:
            out[i] = [round(x, 4), round(y, 4), round(h or 0.0, 4)]
    return out


def per_frame_lens(shots, total):
    """Focal length per frame: telemetry lens_mm where present, else the shot's nominal lens."""
    out = [None] * total
    for s in shots.get("shots", []):
        lm = _num(s.get("lens_mm"))
        for i in range(s["start"], min(total, s["start"] + s["count"])):
            out[i] = lm
    for e in shots.get("telemetry") or []:
        i, lm = e.get("i"), _num(e.get("lens_mm"))
        if isinstance(i, int) and 0 <= i < total and lm is not None:
            out[i] = round(lm, 2)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", default=os.path.join(ROOT, "blender/out/frames"))
    ap.add_argument("--shots", default=os.path.join(ROOT, "blender/out/shots.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "site/public/film"))
    ap.add_argument("--cache", default=os.path.join(ROOT, "tools/.packcache"))
    ap.add_argument("--quality", type=int, default=92, help="colour WebP quality (default 92)")
    ap.add_argument("--depth-quality", type=int, default=-1, help="-1 = lossless (default), else lossy quality")
    ap.add_argument("--max-mb", type=float, default=11.5, help="max pack size in decimal MB (contract: <= 12,000,000 bytes)")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--stride", type=int, default=1, help="testing: keep only frames with i %% stride == 0")
    ap.add_argument("--skip-shots", default="", help="testing: comma list of shot ids to leave out")
    a = ap.parse_args()

    with open(a.shots) as fh:
        shots = json.load(fh)
    total = int(shots.get("total", 336))
    expect = (int(shots.get("width", 1920)), int(shots.get("height", 804)))
    skip = {s for s in a.skip_shots.split(",") if s}
    skip_ranges = [(s["start"], s["start"] + s["count"]) for s in shots["shots"] if s["id"] in skip]

    cdir, ddir = os.path.join(a.frames, "color"), os.path.join(a.frames, "depth")
    present = []
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        m = NAME.match(f)
        if not m: continue
        i = int(m.group(1))
        if i >= total or i % a.stride: continue
        if any(lo <= i < hi for lo, hi in skip_ranges): continue
        dp = os.path.join(ddir, f)
        if not os.path.exists(dp): continue
        present.append((i, os.path.join(cdir, f), dp))

    os.makedirs(a.cache, exist_ok=True); os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    jobs = [(i, c, d, a.cache, a.quality, a.depth_quality, expect) for i, c, d in present]
    results = []
    with ProcessPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for n, r in enumerate(ex.map(encode_one, jobs, chunksize=4)):
            if r[1] is None:
                print(f"  skip f_{r[0]:04d}: {r[2]}", flush=True)
            else:
                results.append(r)
            if n and n % 48 == 0:
                print(f"  encoded {n}/{len(jobs)}", flush=True)
    results.sort()

    limit = int(a.max_mb * 1e6)
    if limit > 12_000_000:
        sys.exit("--max-mb must be <= 12 (decimal MB, BIBLE section 7)")
    packs, pack_bytes, frames, cur, cur_len = [], [], [], [], 0

    def flush():
        nonlocal cur, cur_len
        if not cur: return
        data = b"".join(cur)
        name = f"pack-{len(packs):03d}-{hashlib.sha256(data).hexdigest()[:12]}.wasm"
        dst = os.path.join(a.out, name)
        if not (os.path.exists(dst) and os.path.getsize(dst) == len(data)):
            atomic_write(dst, data)
        packs.append(name); pack_bytes.append(len(data)); cur, cur_len = [], 0

    for i, cp, dp in results:
        cb = open(cp, "rb").read(); db = open(dp, "rb").read()
        if cur_len + len(cb) + len(db) > limit:
            flush()
        frames.append(dict(i=i, pack=len(packs), off=cur_len, len=len(cb), doff=cur_len + len(cb), dlen=len(db)))
        cur += [cb, db]; cur_len += len(cb) + len(db)
    flush()

    manifest = dict(
        width=expect[0], height=expect[1], fps=shots.get("fps", 24), total=total,
        shots=shots["shots"], telemetry=shots.get("telemetry", []), packs=packs, packBytes=pack_bytes,
        frames=frames, hero_screen=per_frame_hero(shots, total), lens_mm=per_frame_lens(shots, total),
        placeholder=bool(shots.get("placeholder", False)), generated=int(time.time()),
    )
    atomic_write(os.path.join(a.out, "manifest.json"), json.dumps(manifest, separators=(",", ":")).encode())

    # only now that the new manifest is live: remove packs it no longer names (old fixed names
    # included), and any temp left by an interrupted run
    for f in os.listdir(a.out):
        if (re.match(r"^pack-\d{3}(-[0-9a-f]+)?\.(wasm|bin)$", f) and f not in packs) or f.endswith(".tmp"):
            try: os.remove(os.path.join(a.out, f))
            except OSError: pass

    have = {f["i"] for f in frames}
    print(f"\nPacked {len(frames)}/{total} frames into {len(packs)} packs in {time.time() - t0:.1f}s -> {a.out}")
    for s in shots["shots"]:
        n = sum(1 for i in range(s["start"], s["start"] + s["count"]) if i in have)
        print(f"  {s['id']:<3} {s['title']:<18} {n:>3}/{s['count']}")
    tot = sum(os.path.getsize(os.path.join(a.out, p)) for p in packs)
    cb = sum(f["len"] for f in frames); db = sum(f["dlen"] for f in frames)
    print(f"  total {tot / 1e6:.1f} MB (colour {cb / 1e6:.1f} MB, depth {db / 1e6:.1f} MB)")
    if frames:
        print(f"  avg colour {cb / len(frames) / 1e3:.0f} KB, avg depth {db / len(frames) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
