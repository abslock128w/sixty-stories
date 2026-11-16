// Fetches manifest + every pack with real byte progress. Packs are kept as Blobs (compressed
// bytes); frames are Blob slices decoded later on demand. A frame counts as "arrived" the moment
// the bytes for both its colour and depth images have streamed in.
import { CONFIG } from './config.js';

export async function loadManifest() {
  const r = await fetch('film/manifest.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`manifest ${r.status}`);
  const m = await r.json();
  m.frames.sort((a, b) => a.i - b.i);
  m.packSizes = m.packs.map(() => 0);
  for (const f of m.frames) m.packSizes[f.pack] = Math.max(m.packSizes[f.pack], f.doff + f.dlen, f.off + f.len);
  m.totalBytes = m.packSizes.reduce((a, b) => a + b, 0);
  return m;
}

// onProgress({bytes, totalBytes, arrived:Set<i>, newly:[i...]})
export async function loadPacks(m, onProgress) {
  const blobs = new Array(m.packs.length);
  const byPack = m.packs.map(() => []);
  for (const f of m.frames) byPack[f.pack].push(f);
  const arrived = new Set();
  let bytes = 0;

  const one = async (k) => {
    let attempt = 0;
    for (;;) {
      let got = 0;
      try {
        const r = await fetch('film/' + m.packs[k]);
        if (!r.ok) throw new Error(`${m.packs[k]} ${r.status}`);
        const list = byPack[k];
        let next = 0;
        const chunks = [];
        if (r.body && r.body.getReader) {
          const rd = r.body.getReader();
          for (;;) {
            const { done, value } = await rd.read();
            if (done) break;
            chunks.push(value); got += value.byteLength; bytes += value.byteLength;
            const newly = [];
            while (next < list.length && list[next].doff + list[next].dlen <= got) {
              arrived.add(list[next].i); newly.push(list[next].i); next++;
            }
            onProgress({ bytes, totalBytes: m.totalBytes, arrived, newly });
          }
        } else {
          const ab = await r.arrayBuffer();
          chunks.push(new Uint8Array(ab)); got = ab.byteLength; bytes += got;
        }
        blobs[k] = new Blob(chunks, { type: 'application/octet-stream' });
        const newly = [];
        for (; next < list.length; next++) { arrived.add(list[next].i); newly.push(list[next].i); }
        onProgress({ bytes, totalBytes: m.totalBytes, arrived, newly });
        return;
      } catch (e) {
        bytes -= got;
        if (++attempt > 3) throw e;
        await new Promise((res) => setTimeout(res, 800 * attempt));
      }
    }
  };

  let cursor = 0;
  const worker = async () => { while (cursor < m.packs.length) await one(cursor++); };
  await Promise.all(Array.from({ length: Math.min(CONFIG.frames.packConcurrency, m.packs.length) }, worker));
  return blobs;
}
