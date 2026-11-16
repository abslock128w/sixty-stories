// End-to-end check of site/dist with Playwright + Chromium (software WebGL2).
//   node tests/run.mjs [--sizes 1920x1080,1440x900,400x860] [--out tests/shots] [--quick] [--memory]
// Serves dist under a deep sub-path, then for each viewport: loader (throttled), ready loader,
// curtain, opening title, each shot's title moment, mid-scrub, play mode, end plate. Asserts no
// console errors, no failed requests, no horizontal scroll; --memory scrubs the whole film and
// checks that decoded-frame memory stays bounded.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = (() => { try { return require('playwright'); } catch { return require('/opt/node22/lib/node_modules/playwright'); } })();
import { spawn, execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const sizes = opt('--sizes', '1920x1080,1440x900,400x860').split(',').map((s) => s.split('x').map(Number));
const out = path.resolve(opt('--out', path.join(here, 'shots')));
const quick = args.includes('--quick');
const memory = args.includes('--memory');
const blockFonts = args.includes('--no-fonts');
const reduced = args.includes('--reduced');
const port = 4100 + Math.floor(Math.random() * 500);
const BASE = `http://localhost:${port}/deep/base/path/`;

const server = spawn(process.execPath, [path.join(here, '../scripts/serve.mjs'), String(port), '/deep/base/path/'], { stdio: 'pipe', env: { ...process.env, ...(opt('--film') ? { FILM_DIR: path.resolve(opt('--film')) } : {}) } });
await new Promise((r) => server.stdout.once('data', r));

const results = [];
const check = (name, ok, info = '') => { results.push({ name, ok, info }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${info ? '  ' + info : ''}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required', '--enable-precise-memory-info'] });

function rssOfBrowser() {
  // sum RSS of every Chromium process (only this test's browser runs in the sandbox)
  try {
    const rows = execSync('ps -eo rss,comm').toString().trim().split('\n').slice(1).map((l) => l.trim().split(/\s+/));
    return rows.filter((r) => /chrom|headless_shell/i.test(r[1] || '')).reduce((a, r) => a + Number(r[0]), 0) / 1024;
  } catch { return -1; }
}

for (const [w, h] of sizes) {
  const tag = `${w}x${h}`;
  const dir = path.join(out, tag);
  fs.mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, hasTouch: w < 700, isMobile: w < 700, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage();
  const errors = [], failed = [];
  page.on('console', (m) => { if (m.type() === 'error' && !(blockFonts && /ERR_FAILED/.test(m.text()))) errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('requestfailed', (r) => { if (!(blockFonts && /fonts\.(googleapis|gstatic)/.test(r.url()))) failed.push(`${r.url()} ${r.failure() && r.failure().errorText}`); });
  page.on('response', (r) => { if (r.status() >= 400) failed.push(`${r.url()} ${r.status()}`); });
  if (blockFonts) await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
  // throttle packs after the first so the overture can be photographed mid-load
  let release; const gate = new Promise((r) => (release = r));
  await page.route(/pack-00[1-9]\.bin$/, async (route) => { await gate; route.continue(); });
  const shot = async (name) => { await page.screenshot({ path: path.join(dir, `${name}.png`), timeout: 120000 }); };
  const t0 = Date.now();
  await page.goto(BASE + 'index.html');
  await page.waitForFunction(() => document.getElementById('ov-bar') && document.getElementById('ov-bar').style.transform.includes('scale'), null, { timeout: 30000 });
  await sleep(1800);
  await shot('01-loader');
  release();
  await page.waitForSelector('#ov-enter.show', { timeout: 120000 });
  await sleep(1400);
  await shot('02-loader-ready');
  check(`${tag} loads all packs`, true, `${((Date.now() - t0) / 1000).toFixed(1)}s`);
  await page.click(w < 700 ? '#enter-silent' : '#enter-sound');
  await sleep(1300);
  await shot('03-curtain');
  await sleep(4200);
  await shot('04-opening');

  const settle = async (pos, extraMs = 400, maxMs = 25000) => {
    await page.evaluate((p) => window.scrollTo(0, p), pos);
    const ts = Date.now();
    for (;;) {
      const ok = await page.evaluate(() => {
        const S = window.__sixty.S; const st = S.store;
        const br = st.bracket(S.frame, S.tl.at(S.cur).shot);
        const res = !br || (st.resident.has(br[0]) && st.resident.has(br[1]));
        return Math.abs(S.cur - S.target) < 0.5 && res;
      });
      if (ok || Date.now() - ts > maxMs) break;
      await sleep(150);
    }
    await sleep(extraMs);
  };
  const info = await page.evaluate(() => {
    const tl = window.__sixty.S.tl;
    return { spans: tl.shotSpan.map((s) => [s.p0, s.p1]), length: tl.length, filmEnd: tl.filmEnd, intro: tl.segs[0].p1 };
  });
  const shotsToDo = quick ? [0, 3] : [0, 1, 2, 3, 4, 5];
  for (const k of shotsToDo) {
    const [p0, p1] = info.spans[k];
    await settle(p0 + (p1 - p0) * 0.15, 900);
    await shot(`05-shot${k + 1}-title`);
  }
  // mid-scrub: wheel fast and photograph while moving
  await settle(info.spans[3][0] + (info.spans[3][1] - info.spans[3][0]) * 0.5, 300);
  await page.mouse.move(w * 0.7, h * 0.4);
  await page.evaluate(() => { window.__sixty.S.vPeak = 0; });
  for (let k = 0; k < 6; k++) { await page.mouse.wheel(0, h * 0.5); await sleep(16); }
  await sleep(60);
  await shot('06-midscrub');
  // the velocity look, frozen for inspection (forceV pins the scrub speed the shader sees)
  await settle(info.spans[3][0] + (info.spans[3][1] - info.spans[3][0]) * 0.7, 200);
  await page.evaluate(() => { window.__sixty.S.forceV = 200; });
  await sleep(1500);
  await shot('06b-velocity-look');
  await page.evaluate(() => { window.__sixty.S.forceV = null; });
  const vel = await page.evaluate(() => window.__sixty.S.vPeak);
  check(`${tag} scrub velocity registers`, Math.abs(vel) > 5, `v=${vel.toFixed(1)} fps`);
  // rest frame after scrub
  await settle(info.spans[4][0] + (info.spans[4][1] - info.spans[4][0]) * 0.6, 1200);
  await shot('07-rest');
  // play mode
  await settle(info.spans[1][0] + (info.spans[1][1] - info.spans[1][0]) * 0.8, 300);
  await page.keyboard.press('Space');
  await sleep(2500);
  const playing = await page.evaluate(() => window.__sixty.S.playing);
  await shot('08-play');
  check(`${tag} play mode runs`, playing);
  await page.mouse.wheel(0, 40);
  await sleep(2000);
  check(`${tag} wheel hands control back`, !(await page.evaluate(() => window.__sixty.S.playing)));
  // end plate + credits
  await settle(info.length, 2500);
  await shot('09-end');
  await settle(info.filmEnd + 2, 900);
  await shot('09b-endplate');
  // horizontal overflow
  const hs = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, bw: document.body.scrollWidth }));
  check(`${tag} no horizontal scroll`, hs.sw <= hs.cw && hs.bw <= hs.cw, JSON.stringify(hs));

  if (memory) {
    const base = rssOfBrowser();
    const samples = [];
    const total = info.filmEnd;
    for (let p = 0; p <= total; p += total / 60) {
      await page.evaluate((q) => window.scrollTo(0, q), p);
      await sleep(250);
      const s = await page.evaluate(() => window.__sixty.stats());
      samples.push({ rss: rssOfBrowser(), ...s });
    }
    for (let p = total; p >= 0; p -= total / 30) { await page.evaluate((q) => window.scrollTo(0, q), p); await sleep(120); }
    const after = rssOfBrowser();
    const maxRes = Math.max(...samples.map((s) => s.resident + s.ready + s.inflight));
    const maxRss = Math.max(...samples.map((s) => s.rss));
    const last = samples[samples.length - 1];
    check(`${tag} decoded frames bounded`, maxRes <= 22 + 3 + 22, `max resident+ready+inflight=${maxRes}, decoded=${last.decoded}, evicted=${last.evicted}`);
    check(`${tag} browser RSS bounded`, maxRss - base < 900, `base ${base.toFixed(0)} MB, max ${maxRss.toFixed(0)} MB, after ${after.toFixed(0)} MB`);
    fs.writeFileSync(path.join(dir, 'memory.json'), JSON.stringify(samples, null, 1));
  }

  check(`${tag} no console errors`, errors.length === 0, errors.slice(0, 5).join(' | '));
  check(`${tag} no failed requests`, failed.length === 0, failed.slice(0, 5).join(' | '));
  await ctx.close();
}

await browser.close();
server.kill();
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length - bad.length}/${results.length} checks passed. Screenshots in ${out}`);
process.exit(bad.length ? 1 : 0);
