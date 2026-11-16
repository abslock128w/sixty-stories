// Assemble dist/page.html (host fragment) + dist/index.html (full document) and verify the
// dist shape required by BIBLE section 7. Fails loudly (exit 1) on any violation.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const site = path.resolve(here, '..');
const dist = path.join(site, 'dist');
const MAX = 12 * 1024 * 1024;
const FONTS = 'https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@300;500&family=Instrument+Serif:ital@0;1&family=Azeret+Mono:wght@300;400&display=swap';

const errors = [];
const fail = (m) => errors.push(m);

if (!fs.existsSync(path.join(dist, 'app.js'))) fail('dist/app.js missing (vite build failed?)');
// vite lib mode may emit a stray css file; we inline our own stylesheet instead
for (const f of fs.readdirSync(dist)) if (/\.css$/.test(f)) fs.rmSync(path.join(dist, f));

const css = fs.readFileSync(path.join(site, 'src/style.css'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\s*\n\s*/g, '\n')
  .replace(/\s*([{};,>])\s*/g, '$1')
  .replace(/;}/g, '}')
  .trim();
const body = fs.readFileSync(path.join(site, 'src/body.html'), 'utf8').trim();

const fragment = [
  '<title>Sixty Stories</title>',
  '<meta name="claude:viewport-fit-sides" content="cover">',
  `<link rel="stylesheet" href="${FONTS}">`,
  `<style>${css}</style>`,
  body,
  '<script src="app.js"></script>',
  '',
].join('\n');

const doc = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Sixty Stories: an original short film, path traced frame by frame in Blender Cycles. Scroll to run the projector.">
</head>
<body>
${fragment}</body>
</html>
`;
fs.writeFileSync(path.join(dist, 'page.html'), fragment);
fs.writeFileSync(path.join(dist, 'index.html'), doc);

// ---- verify the fragment
const low = fragment.toLowerCase();
for (const bad of ['<html', '<head', '<body', '<!doctype']) if (low.includes(bad)) fail(`page.html contains ${bad}`);
if (!fragment.startsWith('<title>Sixty Stories</title>\n<meta name="claude:viewport-fit-sides" content="cover">')) fail('page.html must start with <title> then the viewport-fit meta');
if ((fragment.match(/<style[\s>]/g) || []).length !== 1) fail('page.html must contain exactly one <style>');
const urls = [...fragment.matchAll(/(?:https?:)?\/\/[a-z0-9.-]+\.[a-z]{2,}[^\s"')<]*/gi)].map((m) => m[0]);
for (const u of urls) if (!/^https:\/\/fonts\.googleapis\.com\//.test(u)) fail(`page.html has a non-relative URL: ${u}`);
const scripts = [...fragment.matchAll(/<script[^>]*src="([^"]+)"/g)].map((m) => m[1]);
if (scripts.length !== 1 || scripts[0] !== 'app.js') fail(`page.html must load exactly app.js, found ${scripts.join(', ')}`);

// ---- verify the bundle makes no requests to other hosts
const js = fs.readFileSync(path.join(dist, 'app.js'), 'utf8');
const jsUrls = [...js.matchAll(/https?:\/\/[^\s"'`)]+/g)].map((m) => m[0]).filter((u) => !/^http:\/\/www\.w3\.org\//.test(u));
for (const u of jsUrls) fail(`app.js references an absolute URL: ${u}`);
if (/serviceWorker|window\.open\(|\balert\(|\bconfirm\(|\bprompt\(|pushState|replaceState/.test(js)) fail('app.js uses an API the host forbids (service worker / window.open / alert / confirm / prompt / pushState)');

// ---- verify film + sizes
const film = path.join(dist, 'film');
if (!fs.existsSync(path.join(film, 'manifest.json'))) fail('dist/film/manifest.json missing (run tools/pack_frames.py)');
else {
  const m = JSON.parse(fs.readFileSync(path.join(film, 'manifest.json'), 'utf8'));
  for (const k of ['width', 'height', 'fps', 'total', 'shots', 'telemetry', 'packs', 'frames']) if (!(k in m)) fail(`manifest missing "${k}"`);
  for (const p of m.packs || []) if (!/^pack-\d{3}\.bin$/.test(p) || !fs.existsSync(path.join(film, p))) fail(`pack ${p} missing or misnamed`);
  for (const f of fs.readdirSync(film)) if (/\.tmp$/.test(f)) fail(`stray temp file ${f}`);
}
let count = 0, total = 0;
const walk = (d) => {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    const st = fs.statSync(p);
    if (st.isDirectory()) { walk(p); continue; }
    count++; total += st.size;
    if (st.size > MAX) fail(`${path.relative(dist, p)} is ${(st.size / 1e6).toFixed(1)} MB (> 12 MB)`);
  }
};
walk(dist);
if (count > 250) fail(`dist has ${count} files (> 250)`);

if (errors.length) {
  console.error('\npostbuild: FAILED\n  - ' + errors.join('\n  - '));
  process.exit(1);
}
console.log(`postbuild: ok  ${count} files, ${(total / 1e6).toFixed(1)} MB  (page.html ${(fragment.length / 1024).toFixed(1)} KB, app.js ${(js.length / 1024).toFixed(1)} KB)`);
