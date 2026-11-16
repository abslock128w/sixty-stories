// Sliding window of decoded frames on the GPU.
//  - compressed WebP bytes stay in pack Blobs (bounded: the compressed film)
//  - createImageBitmap decodes (off the main thread in Chromium) a prioritised window around the
//    playhead, biased toward the scrub direction
//  - uploads are budgeted per animation frame; a fixed pool of texture pairs is reused, so GPU
//    memory is constant whatever the film length
//  - pick() always returns something to show: the two nearest existing frames if both are
//    resident, else the nearest resident frame of the same shot, else the nearest at all.
import { CONFIG } from './config.js';

export class FrameStore {
  constructor(manifest, blobs) {
    this.m = manifest;
    this.blobs = blobs;
    this.list = manifest.frames;                 // existing frames, sorted by i
    this.idx = new Map(this.list.map((f, k) => [f.i, k]));
    this.byShot = manifest.shots.map((s) => this.list.filter((f) => f.i >= s.start && f.i < s.start + s.count).map((f) => f.i));
    this.inflight = new Map();                   // i -> true
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
    const mk = (w, h) => {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, w, h);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    };
    for (let k = 0; k < CONFIG.frames.slots; k++) {
      this.slots.push({ col: mk(W, H), dep: mk(DW, DH), i: -1, dw: DW, dh: DH });
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

  // Recompute the wanted window. dir: +1 forward / -1 backward.
  plan(f, k, dir) {
    const br = this.bracket(f, k);
    const N = Math.max(4, this.slots.length || CONFIG.frames.slots) - 2;
    this.rank.clear();
    if (!this.list.length) return;
    let center;
    if (br) center = this.idx.get(br[0]);
    else {
      center = 0;
      for (let q = 0; q < this.list.length; q++) if (this.list[q].i <= f) center = q;
    }
    const want = [];
    if (br) { want.push(br[0]); if (br[1] !== br[0]) want.push(br[1]); }
    const ahead = Math.round(N * CONFIG.frames.aheadShare), behind = N - ahead;
    const fw = dir >= 0 ? ahead : behind, bw = dir >= 0 ? behind : ahead;
    let a = 1, b = 1;
    while (want.length < N && (a <= fw || b <= bw)) {
      // interleave 2:1 in the favoured direction
      for (let r = 0; r < 2 && a <= fw; r++, a++) { const q = center + (dir >= 0 ? a : -a + 1); if (q >= 0 && q < this.list.length) want.push(this.list[q].i); }
      if (b <= bw) { const q = center + (dir >= 0 ? -b : b + 1); if (q >= 0 && q < this.list.length) want.push(this.list[q].i); b++; }
    }
    want.forEach((i, r) => { if (!this.rank.has(i)) this.rank.set(i, r); });
  }

  // Start decodes, upload what is ready (budgeted). Call once per animation frame.
  pump() {
    // drop decoded bitmaps no longer wanted
    for (const [i, bm] of this.ready) if (!this.rank.has(i)) { bm.c.close(); bm.d.close(); this.ready.delete(i); this.stats.dropped++; }
    // decodes, most wanted first
    const order = [...this.rank.entries()].sort((x, y) => x[1] - y[1]).map((e) => e[0]);
    for (const i of order) {
      if (this.inflight.size >= CONFIG.frames.maxDecodes) break;
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
    }, (e) => { this.inflight.delete(i); console.warn('decode failed', i, e); });
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
    gl.bindTexture(gl.TEXTURE_2D, slot.dep);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, Math.min(bm.d.width, slot.dw), Math.min(bm.d.height, slot.dh), gl.RGBA, gl.UNSIGNED_BYTE, bm.d);
    bm.c.close(); bm.d.close();
    slot.i = i;
    this.resident.set(i, slot);
    this.stats.uploaded++;
  }

  // What to draw for fractional frame f in shot k. Returns null when the shot has no frames.
  pick(f, k) {
    const br = this.bracket(f, k);
    if (!br) return null;
    const [a, b, mix] = br;
    const A = this.resident.get(a), B = this.resident.get(b);
    if (A && B) return { A, B, mix, exact: true };
    if (A || B) return { A: A || B, B: A || B, mix: 0, exact: false };
    // nearest resident in this shot, else anywhere
    let best = null, bd = 1e9, bestOther = null, bo = 1e9;
    const s = this.m.shots[k];
    for (const [i, slot] of this.resident) {
      const d = Math.abs(i - f);
      if (i >= s.start && i < s.start + s.count) { if (d < bd) { bd = d; best = slot; } }
      else if (d < bo) { bo = d; bestOther = slot; }
    }
    const S = best || bestOther;
    return S ? { A: S, B: S, mix: 0, exact: false } : { A: null, B: null, mix: 0, exact: false };
  }

  memory() {
    return { resident: this.resident.size, ready: this.ready.size, inflight: this.inflight.size, slots: this.slots.length, ...this.stats };
  }
}
