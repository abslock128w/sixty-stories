// Fetches manifest + every pack with real byte progress. Packs are kept as Blobs (compressed
// bytes); frames are Blob slices decoded later on demand. A frame counts as "arrived" the moment
// the bytes for both its colour and depth images have streamed in.
//  - pack names carry a content hash (tools/pack_frames.py), so the HTTP cache can never pair a
//    new manifest with an old pack; the manifest itself is always revalidated
//  - every request has a stall watchdog, and failed requests are retried with backoff
//  - a pack is accepted only if its length matches the manifest and it starts like a WebP
//  - loadPacks() can be called again with the same blobs array: packs already held are kept,
//    so "Try again" only fetches what is missing
import { CONFIG } from './config.js';

const L = () => CONFIG.load;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const backoff = (attempt) => Math.min(L().backoffMaxMs, L().backoffMs * Math.pow(2, attempt - 1)) * (0.85 + Math.random() * 0.3);

// fetch with a watchdog that aborts when no bytes arrive for stallMs
async function fetchWatched(url, init, onChunk) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null;
  let timer = 0;
  const arm = () => { clearTimeout(timer); if (ac) timer = setTimeout(() => ac.abort(), L().stallMs); };
  arm();
  try {
    const r = await fetch(url, { ...init, signal: ac ? ac.signal : undefined });
    if (!r.ok) throw new Error(`${url} ${r.status}`);
    const chunks = [];
    if (r.body && r.body.getReader) {
      const rd = r.body.getReader();
      for (;;) {
        arm();
        const { done, value } = await rd.read();
        if (done) break;
        chunks.push(value);
        if (onChunk) onChunk(value.byteLength);
      }
    } else {
      const ab = await r.arrayBuffer();
      chunks.push(new Uint8Array(ab));
      if (onChunk) onChunk(ab.byteLength);
    }
    return { r, chunks };
  } finally { clearTimeout(timer); }
}

export async function loadManifest() {
  let attempt = 0;
  for (;;) {
    try {
      const { chunks } = await fetchWatched('film/manifest.json', { cache: 'no-cache' });
      const m = JSON.parse(new TextDecoder().decode(await new Blob(chunks).arrayBuffer()));
      if (!m || !Array.isArray(m.frames) || !Array.isArray(m.packs) || !Array.isArray(m.shots)) throw new Error('manifest malformed');
      m.frames.sort((a, b) => a.i - b.i);
      m.packSizes = m.packs.map(() => 0);
      for (const f of m.frames) m.packSizes[f.pack] = Math.max(m.packSizes[f.pack], f.doff + f.dlen, f.off + f.len);
      // packBytes (exact pack length) is written by the packer; older manifests fall back to the
      // extent of the frames listed in each pack
      m.packLen = m.packs.map((_, k) => (Array.isArray(m.packBytes) && m.packBytes[k] > 0 ? m.packBytes[k] : m.packSizes[k]));
      m.totalBytes = m.packLen.reduce((a, b) => a + b, 0);
      return m;
    } catch (e) {
      if (++attempt > L().retries) throw e;
      await sleep(backoff(attempt));
    }
  }
}

function validate(m, k, chunks, got) {
  const want = m.packLen[k];
  const exact = Array.isArray(m.packBytes) && m.packBytes[k] > 0;
  if (exact ? got !== want : got < want) throw new Error(`${m.packs[k]}: ${got} bytes, expected ${want}`);
  // the first frame of each pack starts at offset 0 and must be a RIFF/WEBP image
  const head = new Uint8Array(12);
  let n = 0;
  for (const c of chunks) { for (let j = 0; j < c.length && n < 12; j++) head[n++] = c[j]; if (n >= 12) break; }
  const tag = (o) => String.fromCharCode(head[o], head[o + 1], head[o + 2], head[o + 3]);
  if (n < 12 || tag(0) !== 'RIFF' || tag(8) !== 'WEBP') throw new Error(`${m.packs[k]}: not a frame pack`);
}

// onProgress({bytes, totalBytes, arrived:Set<i>, newly:[i...], retrying})
export async function loadPacks(m, onProgress, blobs = new Array(m.packs.length), state = { arrived: new Set() }) {
  const byPack = m.packs.map(() => []);
  for (const f of m.frames) byPack[f.pack].push(f);
  const arrived = state.arrived;
  let bytes = blobs.reduce((a, b, k) => a + (b ? m.packLen[k] : 0), 0);
  const report = (newly, retrying = false) => onProgress({ bytes, totalBytes: m.totalBytes, arrived, newly, retrying });

  const one = async (k) => {
    if (blobs[k]) return;
    const list = byPack[k];
    let attempt = 0;
    for (;;) {
      let got = 0, next = 0;
      try {
        const { chunks } = await fetchWatched('film/' + m.packs[k], {}, (len) => {
          got += len; bytes += len;
          const newly = [];
          while (next < list.length && list[next].doff + list[next].dlen <= got) {
            const i = list[next++].i;
            if (!arrived.has(i)) { arrived.add(i); newly.push(i); }   // a retry never reports a frame twice
          }
          report(newly);
        });
        validate(m, k, chunks, got);
        blobs[k] = new Blob(chunks, { type: 'application/octet-stream' });
        const newly = [];
        for (; next < list.length; next++) { const i = list[next].i; if (!arrived.has(i)) { arrived.add(i); newly.push(i); } }
        report(newly);
        return;
      } catch (e) {
        bytes -= got;
        if (++attempt > L().retries) throw e;
        report([], true);
        await sleep(backoff(attempt));
      }
    }
  };

  let cursor = 0, failure = null;
  const worker = async () => {
    while (cursor < m.packs.length) {
      const k = cursor++;
      try { await one(k); } catch (e) { failure = failure || e; }   // keep fetching the others
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Math.min(CONFIG.frames.packConcurrency, m.packs.length)) }, worker));
  if (failure) { const e = new Error(String(failure && failure.message || failure)); e.blobs = blobs; e.state = state; throw e; }
  return blobs;
}
