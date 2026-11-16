// Sliding window of decoded frames on the GPU.
//  - compressed WebP bytes stay in pack Blobs (bounded: the compressed film)
//  - createImageBitmap decodes (off the main thread in Chromium) a prioritised window around the
//    playhead, biased toward the scrub direction
//  - uploads are budgeted per animation frame; a fixed pool of texture pairs is reused, so GPU
//    memory is constant whatever the film length
//  - pick() always returns something to show: the two nearest existing frames if both are
//    resident, else the nearest resident frame of the same shot, else the nearest at all.
//    At rest the caller asks for a settled pick (exactly one source frame, never a blend).
//  - under a fast scrub the window leads the playhead by the expected decode latency and
//    samples every n-th frame, so decodes land where the playhead will be instead of freezing.
import { CONFIG } from './config.js';

export class FrameStore {
  constructor(manifest, blobs) {
    this.m = manifest;
    this.blobs = blobs;
    this.list = manifest.frames;                 // existing frames, sorted by i
    this.idx = new Map(this.list.map((f, k) => [f.i, k]));
    this.byShot = manifest.shots.map((s) => this.list.filter((f) => f.i >= s.start && f.i < s.start + s.count).map((f) => f.i));
    this.inflight = new Map();                   // i -> true
    this.fails = new Map();                      // i -> failed decode count
    this.bad = new Set();                        // frames that failed to decode twice: skipped
    this.ready = new Map();                      // i -> {c, d} ImageBitmaps awaiting upload
    this.resident = new Map();                   // i -> slot
    this.rank = new Map();                       // i -> priority (lower = more wanted)
    this.slots = [];
    this.gl = null;
    this.stats = { decoded: 0, uploaded: 0, evicted: 0, dropped: 0 };
  }

  attach(gl) {
    this.gl = gl;
    this.slots = [];
    this.resident.clear();
    const W = this.m.width, H = this.m.height;
    const DW = Math.round(W / 2), DH = Math.round(H / 2);
    // full mip chains: colour is trilinear when minified (small windows), depth is read from a
    // blurred level for the parallax warp. Depth is one channel (R8).
    const mk = (w, h, fmt) => {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texStorage2D(gl.TEXTURE_2D, Math.floor(Math.log2(Math.max(w, h))) + 1, fmt, w, h);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    };
    for (let k = 0; k < CONFIG.frames.slots; k++) {
      this.slots.push({ col: mk(W, H, gl.RGBA8), dep: mk(DW, DH, gl.R8), i: -1, dw: DW, dh: DH });
    }
  }

  detach() { this.gl = null; this.slots = []; this.resident.clear(); }

  shotFrames(k) { return this.byShot[k] || []; }

  // neighbours of fractional frame f inside shot k: [a, b, mix] over *existing* frames
  bracket(f, k) {
    const L = this.byShot[k];
    if (!L || !L.length) return null;
    if (f <= L[0]) return [L[0], L[0], 0];
    if (f >= L[L.length - 1]) return [L[L.length - 1], L[L.length - 1], 0];
    let lo = 0, hi = L.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (L[mid] <= f) lo = mid; else hi = mid; }
    const a = L[lo], b = L[hi];
    return [a, b, b === a ? 0 : (f - a) / (b - a)];
  }

  // Recompute the wanted window. dir: +1 forward / -1 backward; v: scrub speed (frames/s).
  plan(f, k, dir, v = 0) {
    const br = this.bracket(f, k);
    const N = Math.max(4, this.slots.length || CONFIG.frames.slots) - 2;
    const F = CONFIG.frames;
    this.rank.clear();
    const L = this.list;
    if (!L.length) return;
    const want = [];
    if (br) { want.push(br[0]); if (br[1] !== br[0]) want.push(br[1]); }
    const fwd = dir >= 0 ? 1 : -1;
    // lead the playhead by the decode latency; sample sparsely when the scrub outruns decoding
    const sp = Math.abs(v);
    const lead = Math.max(-F.maxLead, Math.min(F.maxLead, v * F.leadS));
    const stride = sp > F.fastV ? Math.max(1, Math.round(sp * F.strideS)) : 1;
    const nearest = (x) => {   // list index of the last existing frame <= x (or 0)
      let lo = 0, hi = L.length - 1, r = 0;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if (L[mid].i <= x) { r = mid; lo = mid + 1; } else hi = mid - 1; }
      return r;
    };
    const c0 = nearest(f);
    const cl = nearest(f + lead);
    const ahead = Math.round(N * F.aheadShare), behind = N - ahead;
    // ahead in the direction of travel, starting at the led position; behind, one by one
    const aheadList = [], behindList = [];
    // first frame ahead: just past the playhead, or at the led position when that is further
    const aStart = fwd > 0 ? Math.max(c0 + 1, cl) : Math.min(c0, cl + 1);
    for (let q = aStart, n = 0; n < ahead && q >= 0 && q < L.length; q += fwd * stride, n++) aheadList.push(L[q].i);
    for (let q = fwd > 0 ? c0 : c0 + 1, n = 0; n < behind && q >= 0 && q < L.length; q -= fwd, n++) behindList.push(L[q].i);
    let a = 0, b = 0;
    while (want.length < N + 2 && (a < aheadList.length || b < behindList.length)) {
      for (let r = 0; r < 2 && a < aheadList.length; r++) want.push(aheadList[a++]);   // 2:1 toward travel
      if (b < behindList.length) want.push(behindList[b++]);
    }
    want.forEach((i, r) => { if (!this.bad.has(i) && !this.rank.has(i)) this.rank.set(i, this.rank.size); });
  }

  // Start decodes, upload what is ready (budgeted). Call once per animation frame.
  pump() {
    // drop decoded bitmaps no longer wanted
    for (const [i, bm] of this.ready) if (!this.rank.has(i)) { bm.c.close(); bm.d.close(); this.ready.delete(i); this.stats.dropped++; }
    // decodes, most wanted first; back-pressure: never hold more than a few undrained bitmaps
    const order = [...this.rank.entries()].sort((x, y) => x[1] - y[1]).map((e) => e[0]);
    for (const i of order) {
      if (this.inflight.size >= CONFIG.frames.maxDecodes || this.inflight.size + this.ready.size >= CONFIG.frames.maxPending) break;
      if (this.resident.has(i) || this.ready.has(i) || this.inflight.has(i)) continue;
      this.decode(i);
    }
    if (!this.gl) return;
    const t0 = performance.now();
    let n = 0;
    const readyOrder = [...this.ready.keys()].sort((x, y) => this.rank.get(x) - this.rank.get(y));
    for (const i of readyOrder) {
      if (n >= CONFIG.frames.uploadsPerFrame || performance.now() - t0 > CONFIG.frames.uploadBudgetMs) break;
      const slot = this.freeSlot(this.rank.get(i));
      if (!slot) break;
      const bm = this.ready.get(i); this.ready.delete(i);
      this.upload(slot, i, bm);
      n++;
    }
  }

  decode(i) {
    const f = this.list[this.idx.get(i)];
    const blob = this.blobs[f.pack];
    if (!blob) return;
    this.inflight.set(i, true);
    const c = blob.slice(f.off, f.off + f.len, 'image/webp');
    const d = blob.slice(f.doff, f.doff + f.dlen, 'image/webp');
    const opt = { premultiplyAlpha: 'none', colorSpaceConversion: 'none' };
    Promise.all([createImageBitmap(c), createImageBitmap(d, opt)]).then(([cb, db]) => {
      this.inflight.delete(i);
      this.stats.decoded++;
      if (!this.rank.has(i) || this.resident.has(i)) { cb.close(); db.close(); this.stats.dropped++; return; }
      this.ready.set(i, { c: cb, d: db });
    }, (e) => {
      this.inflight.delete(i);
      const n = (this.fails.get(i) || 0) + 1;
      this.fails.set(i, n);
      if (n >= 2) { this.bad.add(i); this.rank.delete(i); }   // stop retrying a broken frame
      console.warn('decode failed', i, e);
    });
  }

  freeSlot(r) {
    let best = null, bestRank = -1;
    for (const s of this.slots) {
      if (s.i < 0) return s;
      const sr = this.rank.has(s.i) ? this.rank.get(s.i) : 1e9;
      if (sr > bestRank) { bestRank = sr; best = s; }
    }
    return bestRank > r ? best : null;
  }

  upload(slot, i, bm) {
    const gl = this.gl;
    if (slot.i >= 0) { this.resident.delete(slot.i); this.stats.evicted++; }
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.bindTexture(gl.TEXTURE_2D, slot.col);
    if (bm.c.width === this.m.width && bm.c.height === this.m.height) {
      gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, bm.c);
    } else gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, Math.min(bm.c.width, this.m.width), Math.min(bm.c.height, this.m.height), gl.RGBA, gl.UNSIGNED_BYTE, bm.c);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.bindTexture(gl.TEXTURE_2D, slot.dep);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, Math.min(bm.d.width, slot.dw), Math.min(bm.d.height, slot.dh), gl.RED, gl.UNSIGNED_BYTE, bm.d);
    gl.generateMipmap(gl.TEXTURE_2D);
    bm.c.close(); bm.d.close();
    slot.i = i;
    this.resident.set(i, slot);
    this.stats.uploaded++;
  }

  // What to draw for fractional frame f in shot k. Returns null when the shot has no frames.
  //  rest (0..1): how settled the playhead is. At 1 the pick is exactly one source frame (the
  //    nearest existing one), never a blend; in between the blend eases toward it.
  //  discrete: play mode. Adjacent frames are shown as discrete frames (no dissolve); only
  //    gaps in a partial cut are bridged by blending.
  // .shown is the frame index on screen (for the HUD).
  pick(f, k, rest = 0, discrete = false) {
    const br = this.bracket(f, k);
    if (!br) return null;
    let [a, b, mix] = br;
    if (discrete && b - a <= 1) mix = 0;
    if (rest > 0) { const s = mix < 0.5 ? 0 : 1; mix = rest >= 1 ? s : mix + (s - mix) * rest; }
    if (mix >= 1) { a = b; mix = 0; }
    if (mix <= 0) { b = a; mix = 0; }
    const A = this.resident.get(a), B = this.resident.get(b);
    const shown = mix < 0.5 ? a : b;
    if (A && B) return { A, B, mix, exact: true, shown };
    if (A || B) return { A: A || B, B: A || B, mix: 0, exact: false, shown: A ? a : b };
    // nearest resident in this shot, else anywhere
    let best = null, bd = 1e9, bi = -1, bestOther = null, bo = 1e9, oi = -1;
    const s = this.m.shots[k];
    for (const [i, slot] of this.resident) {
      const d = Math.abs(i - f);
      if (i >= s.start && i < s.start + s.count) { if (d < bd) { bd = d; best = slot; bi = i; } }
      else if (d < bo) { bo = d; bestOther = slot; oi = i; }
    }
    const S = best || bestOther;
    return S ? { A: S, B: S, mix: 0, exact: false, shown: best ? bi : oi } : { A: null, B: null, mix: 0, exact: false, shown: -1 };
  }

  memory() {
    return { resident: this.resident.size, ready: this.ready.size, inflight: this.inflight.size, slots: this.slots.length, ...this.stats };
  }
}
