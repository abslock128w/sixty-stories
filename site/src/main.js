// SIXTY STORIES: scroll-driven projector.
import { CONFIG, SHOT_COPY, REDUCED } from './config.js';
import { loadManifest, loadPacks } from './loader.js';
import { Timeline } from './timeline.js';
import { FrameStore } from './frames.js';
import { Renderer } from './renderer.js';
import { Score } from './audio.js';

const $ = (id) => document.getElementById(id);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (t) => { t = clamp(t); return 1 - Math.pow(1 - t, 3); };
const easeIO = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
const pad = (n, w = 2) => String(Math.max(0, Math.floor(n))).padStart(w, '0');
const lsGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } };

const app = $('app');
const root = document.documentElement;
const S = {
  phase: 'loading', m: null, tl: null, store: null, gl: null, score: null,
  cur: 0, target: 0, frame: 0, lastFrame: 0, v: 0, dir: 1, lastShot: 0,
  playing: false, playPos: 0, playShotT: 0, cutTime: -10,
  curtainT0: 0, introTitleT0: 0, rewind: null, flash: 0,
  ptr: [0, 0], ptrS: [0, 0], pan: 0, panS: 0, tilt: null,
  vw: 0, vh: 0, layoutVh: 0, dpr: 1, win: [0, 0, 0, 0], open: 0,
  lastInput: performance.now(), hud: true, muted: false, sound: false, time: 0,
};

// ---------------------------------------------------------------- boot
function checkFonts() {
  const test = () => {
    let ok = false;
    try { ok = document.fonts && document.fonts.check('300 40px "Big Shoulders Display"'); } catch { ok = false; }
    app.classList.toggle('nofont', !ok);
  };
  app.classList.add('nofont');
  try { document.fonts.ready.then(test); document.fonts.addEventListener && document.fonts.addEventListener('loadingdone', test); } catch { /* */ }
  setTimeout(test, 2500);
}

function boot() {
  checkFonts();
  try { history.scrollRestoration = 'manual'; } catch { /* not allowed */ }
  root.classList.add('lock');
  window.scrollTo(0, 0);
  if (lsGet('sixty.hud') === '0') { S.hud = false; app.classList.add('nohud'); }

  const canvas = $('screen');
  S.renderer = new Renderer(canvas);
  try { S.renderer.init(); } catch (e) { console.warn(e); fatal('This projector needs WebGL2, which this browser could not provide.'); return; }
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); S.renderer.lost = true; if (S.store) S.store.detach(); }, false);
  canvas.addEventListener('webglcontextrestored', () => {
    try { S.renderer.init(); S.renderer.targets = null; layout(true); if (S.store) S.store.attach(S.renderer.gl); } catch (e) { console.warn(e); }
  }, false);

  layout(true);
  addEventListener('resize', () => layout(false));
  addEventListener('orientationchange', () => setTimeout(() => layout(false), 250));
  bindInput();
  overture();
  requestAnimationFrame(loop);
}

function fatal(msg) {
  S.phase = 'error';
  $('ov-bytes').textContent = msg;
  $('ov-copy').textContent = msg;
}

// ---------------------------------------------------------------- overture (loader)
const SCRAMBLE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
async function overture() {
  let m;
  try { m = await loadManifest(); } catch (e) {
    console.warn(e); fatal('The reel could not be opened. Reload the page to try again.'); return;
  }
  S.m = m;
  S.tl = new Timeline(m);
  layout(true);
  const n = m.frames.length;
  $('ov-of').textContent = `/ ${pad(m.total, 4)}`;
  if (n < m.total) $('ov-unit').textContent = `frames threaded · ${m.total - n} still in the render queue`;
  // shot list
  const ol = $('ov-shots');
  const shotState = m.shots.map((s, k) => {
    const have = m.frames.filter((f) => f.i >= s.start && f.i < s.start + s.count).length;
    const li = document.createElement('li');
    li.innerHTML = `<span class="n"><b>${pad(k + 1)}</b><span>${have ? have + ' frames' : 'in render'}</span></span><span class="t"></span>`;
    const t = li.querySelector('.t');
    t.textContent = s.title.replace(/./g, (c) => (c === ' ' ? ' ' : '·'));
    if (!have) li.classList.add('none');
    ol.appendChild(li);
    return { li, t, title: s.title, need: have, got: 0, done: !have, resolveT: have ? null : -1 };
  });
  buildCards(m);
  buildRail(m);

  // leader sweep: a wedge revolving once a second, like the countdown leader
  const sweep = $('ov-sweep'), arc = $('ov-arc');
  let shown = 0, prog = 0, bytesText = 'Opening the reel', loaded = false;
  const wedge = (a) => {
    const r = 112, x = 120 + r * Math.sin(a), y = 120 - r * Math.cos(a);
    return `M120 120 L120 8 A${r} ${r} 0 ${a > Math.PI ? 1 : 0} 1 ${x.toFixed(2)} ${y.toFixed(2)} Z`;
  };
  const t0 = performance.now();
  const tick = () => {
    if (S.phase !== 'loading') return;
    const now = performance.now();
    const target = S.arrivedCount || 0;
    shown += (target - shown) * 0.12;
    if (Math.abs(target - shown) < 0.5) shown = target;
    $('ov-count').textContent = pad(Math.round(shown), 4);
    $('ov-bar').style.transform = `scaleX(${prog})`;
    arc.style.strokeDashoffset = String(1 - prog);
    const a = REDUCED ? 0.0001 : (((now - t0) / 1000) % 1) * Math.PI * 2;
    sweep.setAttribute('d', loaded ? '' : wedge(Math.max(0.0001, a)));
    $('ov-bytes').textContent = bytesText;
    for (const st of shotState) {
      if (st.resolveT == null || st.resolveT < 0) continue;
      const u = clamp((now - st.resolveT) / 700);
      const k = Math.floor(u * st.title.length);
      st.t.textContent = st.title.slice(0, k) + st.title.slice(k).replace(/[^ ]/g, () => SCRAMBLE[(Math.random() * SCRAMBLE.length) | 0]);
      if (u >= 1) { st.t.textContent = st.title; st.resolveT = -1; }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  const mb = (b) => (b / 1e6).toFixed(1);
  let blobs;
  try {
    blobs = await loadPacks(m, ({ bytes, totalBytes, arrived, newly }) => {
      S.arrivedCount = arrived.size;
      prog = totalBytes ? bytes / totalBytes : 1;
      bytesText = `${mb(bytes)} of ${mb(totalBytes)} MB`;
      for (const i of newly) {
        const k = m.shots.findIndex((s) => i >= s.start && i < s.start + s.count);
        const st = shotState[k];
        if (st && ++st.got >= st.need && !st.done) { st.done = true; st.li.classList.add('done'); st.resolveT = performance.now(); }
      }
    });
  } catch (e) {
    console.warn(e); fatal('Part of the reel failed to arrive. Reload the page to try again.'); return;
  }
  S.store = new FrameStore(m, blobs);
  if (S.renderer.gl && !S.renderer.lost) S.store.attach(S.renderer.gl);
  S.store.plan(0, 0, 1);
  loaded = true; prog = 1; S.arrivedCount = n;
  bytesText = n
    ? `Reel threaded · ${n} frames · ${mb(m.totalBytes)} MB${m.placeholder ? ' · placeholder frames' : ''}`
    : 'No frames have been delivered yet. The projector will run as soon as they are.';
  window.__sixty = { S, stats: () => ({ ...S.store.memory(), frame: S.frame, phase: S.phase }) };
  const enter = $('ov-enter');
  enter.hidden = false;
  requestAnimationFrame(() => requestAnimationFrame(() => enter.classList.add('show')));
  $('enter-sound').addEventListener('click', () => begin(true));
  $('enter-silent').addEventListener('click', () => begin(false));
}

function begin(sound) {
  if (S.phase !== 'loading') return;
  S.sound = sound;
  if (sound) {
    S.score = new Score();
    try { S.score.start(); } catch (e) { console.warn(e); S.score = null; }
  }
  setMuted(!sound, false);
  try { const el = document.documentElement; if (el.requestFullscreen && document.fullscreenEnabled) el.requestFullscreen({ navigationUI: 'hide' }).catch(() => {}); } catch { /* refused */ }
  try { if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === 'function') DeviceOrientationEvent.requestPermission().catch(() => {}); } catch { /* */ }
  S.phase = 'curtain';
  S.curtainT0 = performance.now();
  S.introTitleT0 = S.curtainT0 + CONFIG.curtain.titleDelayMs * (REDUCED ? 0.3 : 1);
  app.classList.add('entered');
  root.classList.remove('lock');
  window.scrollTo(0, 0); S.cur = S.target = 0;
  if (matchMedia('(pointer: fine)').matches && !REDUCED) app.classList.add('cursor-on');
  setTimeout(() => { if (S.phase === 'curtain') { S.phase = 'film'; app.classList.add('film'); } }, CONFIG.curtain.mattesMs * (REDUCED ? 0.3 : 1));
  $('live').textContent = 'The film has started. Scroll to advance it, or press Space to play.';
}

// ---------------------------------------------------------------- layout
function layout(force) {
  const vw = document.documentElement.clientWidth || innerWidth;
  const vh = innerHeight;
  const dpr = Math.min(CONFIG.view.maxDpr, window.devicePixelRatio || 1);
  if (!force && vw === S.vw && vh === S.vh && dpr === S.dpr) return;
  const widthChanged = vw !== S.vw;
  S.vw = vw; S.vh = vh; S.dpr = dpr;
  if (S.renderer && S.renderer.gl) S.renderer.resize(Math.round(vw * dpr), Math.round(vh * dpr));
  // timeline length tracks the viewport height, but ignore small mobile URL-bar jitter
  if (S.tl && (force || widthChanged || Math.abs(vh - S.layoutVh) > 160 || !S.layoutVh)) {
    const keepFrame = S.frame, keepIn = S.tl.at(S.cur);
    S.layoutVh = vh;
    S.tl.layout(vh);
    $('scroll-space').style.height = `${Math.ceil(S.tl.length + vh)}px`;
    if (S.phase !== 'loading') {
      const p = keepIn.kind === 'intro' ? keepIn.intro * S.tl.segs[0].len
        : keepIn.kind === 'credits' ? S.tl.filmEnd + keepIn.credits * S.tl.segs[S.tl.segs.length - 1].len
          : S.tl.posForFrame(keepFrame);
      window.scrollTo(0, p); S.cur = S.target = p;
    }
  }
}

function windowRect(open) {
  const { vw, vh } = S;
  const fa = S.m ? S.m.width / S.m.height : 1920 / 804;
  const A = vw / vh;
  const wa = clamp(A * CONFIG.view.landscapeFactor, CONFIG.view.portraitAspect, fa);
  let ww = vw, wh = vw / wa;
  if (wh > vh) { wh = vh; ww = vh * wa; }
  const h = wh * open;
  return { x: (vw - ww) / 2, y: (vh - h) / 2, w: ww, h, fullH: wh, wa, fa };
}

// ---------------------------------------------------------------- titles
function splitChars(el, text) {
  el.textContent = '';
  const chars = [];
  text.split(' ').forEach((word, wi, arr) => {
    const w = document.createElement('span'); w.className = 'w';
    for (const c of word) {
      const m = document.createElement('span'); m.className = 'mask';
      const ch = document.createElement('span'); ch.className = 'ch'; ch.textContent = c;
      m.appendChild(ch); w.appendChild(m); chars.push(ch);
    }
    el.appendChild(w);
    if (wi < arr.length - 1) el.appendChild(document.createTextNode(' '));
  });
  return chars;
}

const opening = { chars: [] };
const cards = [];
function buildCards(m) {
  opening.chars = splitChars($('op-title'), 'Sixty Stories');
  const host = $('cards');
  m.shots.forEach((s, k) => {
    const copy = SHOT_COPY[s.id] || { line: '', side: k % 2 ? 'right' : 'left' };
    const el = document.createElement('div');
    el.className = 'card'; el.dataset.side = copy.side;
    el.innerHTML = `<p class="card-meta mono">${pad(k + 1)} / ${pad(m.shots.length)}<span aria-hidden="true">  ·  </span>${s.lens_mm ? Math.round(s.lens_mm) + ' mm' : ''}</p><h2 class="card-title"></h2><p class="card-line"><span></span></p>`;
    const chars = splitChars(el.querySelector('.card-title'), s.title);
    el.querySelector('.card-line span').textContent = copy.line;
    host.appendChild(el);
    cards.push({ el, chars, meta: el.querySelector('.card-meta'), line: el.querySelector('.card-line span'), on: false });
  });
}

function drawCard(c, u) {
  const visible = u > 0 && u < 1;
  if (visible !== c.on) { c.on = visible; c.el.classList.toggle('on', visible); }
  if (!visible) return;
  const n = c.chars.length;
  c.chars.forEach((ch, k) => {
    const a = ease((u - 0.02 - k * 0.011) / 0.16);
    const b = easeIO((u - 0.80 - (n - k) * 0.004) / 0.12);
    ch.style.transform = `translate3d(0, ${((1 - a) * 106 - b * 106).toFixed(2)}%, 0)`;
  });
  const meta = clamp((u - 0.0) / 0.12) * (1 - clamp((u - 0.82) / 0.1));
  c.meta.style.opacity = meta.toFixed(3);
  const l = ease((u - 0.14) / 0.22), lo = 1 - clamp((u - 0.78) / 0.12);
  c.line.style.clipPath = `inset(-20% ${((1 - l) * 100).toFixed(2)}% -20% 0)`;
  c.line.style.opacity = (Math.min(1, l * 1.5) * lo).toFixed(3);
  c.line.style.transform = `translate3d(${((1 - l) * -8).toFixed(1)}px,0,0)`;
  c.el.style.setProperty('--scrim', (Math.min(meta, lo) * 1).toFixed(3));
}

// ---------------------------------------------------------------- HUD
function buildRail(m) {
  const host = $('rail-ticks');
  const T = m.total;
  // existing-frame coverage as thin segments, cuts as ticks
  const have = new Set(m.frames.map((f) => f.i));
  let runStart = -1;
  for (let i = 0; i <= T; i++) {
    if (have.has(i) && runStart < 0) runStart = i;
    if ((!have.has(i) || i === T) && runStart >= 0) {
      const u = document.createElement('u');
      u.style.left = `${(runStart / (T - 1)) * 100}%`; u.style.width = `${(Math.max(1, i - 1 - runStart) / (T - 1)) * 100}%`;
      if (i - runStart > 1) host.appendChild(u);
      runStart = -1;
    }
  }
  m.shots.forEach((s, k) => {
    if (!k) return;
    const t = document.createElement('i');
    t.style.left = `${(s.start / (T - 1)) * 100}%`;
    host.appendChild(t);
  });
  $('rail').addEventListener('click', (e) => {
    const r = $('rail').getBoundingClientRect();
    const f = clamp((e.clientX - r.left) / r.width) * (T - 1);
    stopPlay(); seek(S.tl.posForFrame(f));
  });
}

let hudCache = {};
function setText(id, v) { if (hudCache[id] !== v) { hudCache[id] = v; $(id).textContent = v; } }
function telemetryAt(f) {
  const T = S.m.telemetry;
  if (!T || !T.length) return null;
  const a = T[clamp(Math.floor(f), 0, T.length - 1)], b = T[clamp(Math.floor(f) + 1, 0, T.length - 1)];
  const t = f - Math.floor(f);
  return { alt: a.altitude_m + (b.altitude_m - a.altitude_m) * t, spd: a.speed_kmh + (b.speed_kmh - a.speed_kmh) * t };
}
function drawHud(st, tel) {
  const s = S.m.shots[st.shot];
  setText('h-shot', s.id.toUpperCase());
  setText('h-title', s.title);
  setText('h-lens', s.lens_mm ? `${Math.round(s.lens_mm)} mm` : '—');
  if (tel) {
    setText('h-alt', `${Math.round(tel.alt)} m`);
    setText('h-st', `${Math.max(0, Math.round(tel.alt / 4))} st`);
    setText('h-spd', `${Math.round(tel.spd)} km/h`);
  }
  const fi = Math.round(st.frame);
  const fps = S.m.fps || 24;
  setText('h-tc', `00:${pad(fi / (fps * 60))}:${pad((fi / fps) % 60)}:${pad(fi % fps)}`);
  setText('h-fr', pad(fi, 4));
  $('rail-head').style.transform = `translate3d(${((st.frame / (S.m.total - 1)) * $('rail').clientWidth).toFixed(1)}px,0,0)`;
}

// ---------------------------------------------------------------- input
function bindInput() {
  const touchInput = () => { S.lastInput = performance.now(); };
  addEventListener('pointermove', (e) => {
    S.lastInput = performance.now();
    if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
      S.ptr[0] = clamp((e.clientX / S.vw) * 2 - 1, -1, 1);
      S.ptr[1] = clamp((e.clientY / S.vh) * 2 - 1, -1, 1);
      S.pan = S.ptr[0];
      S.cx = e.clientX; S.cy = e.clientY;
    }
    const t = e.target;
    $('cursor').classList.toggle('hover', !!(t && t.closest && t.closest('button, .rail')));
  }, { passive: true });
  addEventListener('wheel', () => { touchInput(); stopPlay(); }, { passive: true });
  addEventListener('scroll', touchInput, { passive: true });
  let tx = null, ty = null;
  addEventListener('touchstart', (e) => { touchInput(); stopPlay(); tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
  addEventListener('touchmove', (e) => {
    if (tx == null) return;
    const x = e.touches[0].clientX, y = e.touches[0].clientY;
    const dx = x - tx, dy = y - ty;
    if (Math.abs(dx) > Math.abs(dy)) S.pan = clamp(S.pan - dx / (S.vw * 0.6), -1, 1);
    tx = x; ty = y;
  }, { passive: true });
  addEventListener('deviceorientation', (e) => {
    if (e.gamma == null) return;
    const portrait = S.vh > S.vw;
    const g = portrait ? e.gamma : e.beta;
    const b = portrait ? e.beta - 45 : e.gamma;
    S.tilt = [clamp(g / 25, -1, 1), clamp(b / 30, -1, 1)];
  }, { passive: true });
  addEventListener('keydown', onKey);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { stopPlay(); if (S.score) S.score.suspend(true); }
    else if (S.score && !S.muted) S.score.suspend(false);
  });
  $('c-play').addEventListener('click', () => (S.playing ? stopPlay() : play()));
  $('c-sound').addEventListener('click', () => toggleSound());
  $('c-hud').addEventListener('click', () => toggleHud());
  $('c-fs').addEventListener('click', () => toggleFs());
  $('again').addEventListener('click', () => rewind());
  if (!document.fullscreenEnabled) $('c-fs').style.display = 'none';
}

function onKey(e) {
  if (S.phase === 'loading' || e.metaKey || e.ctrlKey || e.altKey) return;
  const tag = (e.target && e.target.tagName) || '';
  const k = e.key;
  S.lastInput = performance.now();
  if (k === ' ' || k === 'Spacebar') {
    if (tag === 'BUTTON') return;              // let Space activate the focused control
    e.preventDefault(); S.playing ? stopPlay() : play(); return;
  }
  if (k === 'm' || k === 'M') { toggleSound(); return; }
  if (k === 'h' || k === 'H') { toggleHud(); return; }
  if (k === 'f' || k === 'F') { toggleFs(); return; }
  if (!S.tl) return;
  const st = S.tl.at(S.target);
  let pos = null;
  if (k === 'ArrowRight' || k === 'ArrowDown') pos = st.kind === 'intro' ? S.tl.segs[0].p1 : S.tl.posForFrame(Math.floor(st.frame + 1e-3) + 1);
  if (k === 'ArrowLeft' || k === 'ArrowUp') pos = S.tl.posForFrame(Math.ceil(st.frame - 1e-3) - 1);
  if (k === 'PageDown') pos = st.kind === 'credits' ? S.tl.length : st.kind === 'intro' ? S.tl.posForShot(0) : S.tl.posForShot(st.shot + 1 >= S.m.shots.length ? 99 : st.shot + 1);
  if (k === 'PageDown' && st.shot === S.m.shots.length - 1 && st.kind !== 'intro') pos = S.tl.filmEnd;
  if (k === 'PageUp') pos = st.kind === 'credits' ? S.tl.posForShot(S.m.shots.length - 1) : (st.shotQ > 0.08 || st.shot === 0) ? (st.shot === 0 ? 0 : S.tl.posForShot(st.shot)) : S.tl.posForShot(st.shot - 1);
  if (k === 'Home') pos = 0;
  if (k === 'End') pos = S.tl.length;
  if (pos != null) { e.preventDefault(); stopPlay(); seek(pos); }
}

function seek(pos) { window.scrollTo(0, Math.max(0, Math.min(S.tl.length, pos))); }

function setMuted(m, persist = true) {
  S.muted = m;
  if (S.score) S.score.setMuted(m);
  $('c-sound-v').textContent = m ? 'Off' : 'On';
  $('c-sound').setAttribute('aria-pressed', String(!m));
}
function toggleSound() {
  if (!S.score) { S.score = new Score(); try { S.score.start(); } catch { S.score = null; } setMuted(false); return; }
  setMuted(!S.muted);
}
function toggleHud() {
  S.hud = !S.hud; app.classList.toggle('nohud', !S.hud);
  $('c-hud').setAttribute('aria-pressed', String(S.hud));
  lsSet('sixty.hud', S.hud ? '1' : '0');
}
function toggleFs() {
  try {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else if (document.fullscreenEnabled) document.documentElement.requestFullscreen().catch(() => {});
  } catch { /* refused */ }
  setTimeout(() => $('c-fs').setAttribute('aria-pressed', String(!!document.fullscreenElement)), 300);
}

// ---------------------------------------------------------------- play mode
function play() {
  if (!S.tl || S.phase === 'loading') return;
  const st = S.tl.at(S.cur);
  S.playPos = st.kind === 'credits' && st.credits > 0.9 ? 0 : S.cur;
  if (S.playPos >= S.tl.length - 1) S.playPos = 0;
  S.playing = true; S.cutTime = -10;
  $('c-play').setAttribute('aria-pressed', 'true');
  $('c-play').querySelector('.lbl').textContent = 'Pause';
}
function stopPlay() {
  if (!S.playing) return;
  S.playing = false;
  $('c-play').setAttribute('aria-pressed', 'false');
  $('c-play').querySelector('.lbl').textContent = 'Play film';
}
function advancePlay(dt) {
  const tl = S.tl;
  let seg = tl.segs.find((g) => S.playPos < g.p1) || tl.segs[tl.segs.length - 1];
  if (seg.kind === 'hold') { S.playPos = seg.p1; seg = tl.segs[tl.segs.indexOf(seg) + 1]; }
  const fps = S.m.fps || 24;
  const rate = seg.kind === 'intro' ? seg.len / 1.8 : seg.kind === 'credits' ? seg.len / 16 : tl.ppf * fps;
  S.playPos += rate * dt;
  if (S.playPos >= tl.length) { S.playPos = tl.length; stopPlay(); }
  window.scrollTo(0, S.playPos);
  S.cur = S.target = S.playPos;
}

// ---------------------------------------------------------------- rewind ("Watch again")
function rewind() {
  stopPlay();
  S.rewind = { t0: performance.now(), jumped: false };
}

// ---------------------------------------------------------------- frame loop
let lastT = performance.now(), lastIdle = false, lastShotAnnounced = -1;
function loop(now) {
  requestAnimationFrame(loop);
  const dt = Math.min(0.1, Math.max(0.001, (now - lastT) / 1000));
  lastT = now; S.time += dt;
  if (!S.m || !S.tl) { drawBlack(); return; }
  if (S.phase === 'loading') { drawBlack(); return; }
  if (S.store && !S.store.gl && S.renderer.gl && !S.renderer.lost) S.store.attach(S.renderer.gl);

  // rewind: dip to black, jump to the top, fade back up through the opening
  let dip = 1;
  if (S.rewind) {
    const t = (now - S.rewind.t0) / 1000;
    if (t < 0.8) dip = 1 - easeIO(t / 0.8);
    else {
      if (!S.rewind.jumped) { S.rewind.jumped = true; window.scrollTo(0, 0); S.cur = S.target = 0; S.introTitleT0 = now + 300; S.curtainT0 = now - CONFIG.curtain.mattesMs; S.expT0 = now; }
      dip = 0; S.rewind = t > 0.9 ? null : S.rewind;
    }
  }

  // playhead: smoothed follow of scroll, or the play clock
  if (S.playing) advancePlay(dt);
  else {
    S.target = window.scrollY || document.documentElement.scrollTop || 0;
    const k = REDUCED ? CONFIG.scroll.smoothingReduced : CONFIG.scroll.smoothing;
    S.cur += (S.target - S.cur) * (1 - Math.exp(-k * dt));
    if (Math.abs(S.target - S.cur) < 0.05) S.cur = S.target;
  }
  const st = S.tl.at(S.cur);
  const df = st.frame - S.frame;
  S.frame = st.frame;
  const vInst = df / dt;
  S.v += (vInst - S.v) * (1 - Math.exp(-14 * dt));
  S.vPeak = Math.max(S.vPeak || 0, Math.abs(S.v));
  if (Math.abs(df) > 1e-4) S.dir = df > 0 ? 1 : -1;
  const frameStep = Math.floor(st.frame) !== Math.floor(S.lastFrame);
  S.lastFrame = st.frame;
  if (st.shot !== S.lastShot) {
    if (Math.abs(S.v) < 400) S.flash = CONFIG.look.cutFlash;
    S.cutTime = S.time; S.lastShot = st.shot;
  }
  S.flash *= Math.exp(-dt / 0.045);
  if (S.flash < 0.002) S.flash = 0;

  // frames
  const store = S.store;
  let pick = null;
  if (store) { store.plan(st.frame, st.shot, S.dir); store.pump(); pick = store.pick(st.frame, st.shot); }

  // curtain: mattes open, exposure ramps up
  const rm = REDUCED ? 0.3 : 1;
  const ct = (now - S.curtainT0) / (CONFIG.curtain.mattesMs * rm);
  S.open = S.phase === 'curtain' || S.phase === 'film' ? easeIO(ct) : 0;
  const et = (now - (S.expT0 || S.curtainT0 + 500 * rm)) / (CONFIG.curtain.exposureMs * rm);
  const exposure = Math.pow(easeIO(et), 1.6) * dip;

  // pointer / tilt / pan smoothing
  const pt = S.tilt || S.ptr;
  const pe = 1 - Math.exp(-CONFIG.look.pointerEase * dt);
  S.ptrS[0] += (pt[0] - S.ptrS[0]) * pe; S.ptrS[1] += (pt[1] - S.ptrS[1]) * pe;
  const panT = S.tilt ? S.tilt[0] : S.pan;
  S.panS += (panT - S.panS) * (1 - Math.exp(-2.2 * dt));

  const R = windowRect(S.open);
  // CSS vars for the DOM stage (full-height window, so text does not jump during the curtain)
  const full = windowRect(1);
  const css = `${full.x}|${full.y}|${full.w}|${full.h}`;
  if (css !== S.cssWin) {
    S.cssWin = css;
    app.style.setProperty('--wx', `${full.x}px`); app.style.setProperty('--wy', `${full.y}px`);
    app.style.setProperty('--ww', `${full.w}px`); app.style.setProperty('--wh', `${full.h}px`);
    app.classList.toggle('thin', full.y < 76);
  }
  const d = S.dpr;
  const win = [R.x * d, (S.vh - R.y - R.h) * d, R.w * d, Math.max(0.5, R.h * d)];
  let crop = [1, 1], cropOff = [0, 0];
  if (R.wa < R.fa - 1e-3) {
    crop = [R.wa / R.fa, 1];
    cropOff = [((1 - crop[0]) / 2) * (1 + clamp(S.panS, -1, 1) * 0.92), 0];
  }

  // velocity response (zero below vFloor, so the frame at rest is pristine)
  const L = CONFIG.look;
  const vEff = S.forceV != null ? S.forceV : S.v;
  const e = REDUCED || S.playing ? 0 : easeIO((Math.abs(vEff) - L.vFloor) / (L.vMax - L.vFloor));
  const parAmp = REDUCED ? 0 : L.parallax;
  const weaveOn = REDUCED ? 0 : 1;
  const wt = Math.floor(S.time * 24) / 24;
  const weave = [
    weaveOn * (L.weavePx / S.m.width) * (Math.sin(wt * 2.1) * 0.6 + Math.sin(wt * 5.3 + 1) * 0.4),
    weaveOn * (L.weavePx / S.m.height) * (Math.sin(wt * 1.7 + 2) * 0.6 + Math.sin(wt * 4.1) * 0.4),
  ];
  // credits fade
  const fade = 1 - 0.6 * easeIO(st.credits / 0.3);

  S.renderer.draw({
    pick, win, crop, cropOff,
    par: [S.ptrS[0] * parAmp * crop[0], S.ptrS[1] * parAmp * 0.6],
    zoom: L.overscan * (1 + L.breathing * e),
    smear: L.smear * e, split: L.rgbSplit * e,
    exposure, flash: REDUCED ? 0 : S.flash, weave,
    grain: L.grain, seed: REDUCED ? 1 : (Math.floor(S.time * L.grainFps) % 997) + 1,
    fade, dust: REDUCED ? 0 : L.dustStrength, time: S.time, dpr: d,
  });

  // ---- DOM: opening title, cards, HUD, credits, missing-shot slate
  const tt = (now - S.introTitleT0) / 1000;
  const introFade = 1 - easeIO((st.kind === 'intro' ? st.intro : 1) / 0.55);
  opening.chars.forEach((ch, k) => {
    const a = ease((tt - k * 0.06) / 1.3);
    ch.style.transform = `translate3d(0, ${((1 - a) * 106).toFixed(2)}%, 0)`;
  });
  const op = $('opening');
  op.style.opacity = introFade.toFixed(3);
  op.style.visibility = introFade < 0.002 ? 'hidden' : 'visible';
  op.style.transform = `translate3d(0, ${(-(1 - introFade) * 24).toFixed(1)}px, 0)`;
  op.querySelector('.op-eyebrow').style.opacity = clamp((tt - 0.9) / 1.2).toFixed(3);
  op.querySelector('.op-cue').style.opacity = (clamp((tt - 2.2) / 1.0) * 0.9).toFixed(3);

  if (st.kind !== S.lastKind) { if (S.lastKind === 'intro' && st.kind === 'shot') S.cutTime = S.time; S.lastKind = st.kind; }
  cards.forEach((c, k) => {
    let u = -1;
    if (k === st.shot && st.kind !== 'intro' && st.kind !== 'credits') u = S.playing ? (S.time - S.cutTime) / 1.9 : st.shotQ / 0.4;
    drawCard(c, u);
  });

  const missing = store && !store.shotFrames(st.shot).length;
  const mEl = $('missing');
  if (missing !== !mEl.hidden) {
    mEl.hidden = !missing;
    if (missing) mEl.textContent = `Shot ${pad(st.shot + 1)} is still in the render queue`;
    app.classList.toggle('gate-empty', missing);
  }

  const tel = telemetryAt(st.frame);
  if (S.phase === 'film' || S.phase === 'curtain') drawHud(st, tel);

  const cr = $('credits');
  const ctT = st.credits;
  cr.style.opacity = easeIO((ctT - 0.06) / 0.2).toFixed(3);
  if (ctT > 0) {
    const inner = $('cr-inner');
    const h = inner.offsetHeight || 1;
    const yEnd = h < S.vh * 0.86 ? (S.vh - h) / 2 : S.vh - h - 40;
    const y = S.vh + (yEnd - S.vh) * easeIO((ctT - 0.04) / 0.8);
    inner.style.transform = `translate3d(0, ${y.toFixed(1)}px, 0)`;
  }
  cr.classList.toggle('inert', ctT < 0.6);

  // idle chrome
  const idle = now - S.lastInput > CONFIG.ui.idleMs && st.credits < 0.6;
  if (idle !== lastIdle) { lastIdle = idle; app.classList.toggle('idle', idle); }

  // cursor
  if (S.cx != null) {
    const c = $('cursor');
    S.ccx = S.ccx == null ? S.cx : S.ccx + (S.cx - S.ccx) * (REDUCED ? 1 : 1 - Math.exp(-22 * dt));
    S.ccy = S.ccy == null ? S.cy : S.ccy + (S.cy - S.ccy) * (REDUCED ? 1 : 1 - Math.exp(-22 * dt));
    const sv = Math.min(0.6, Math.abs(S.v) / 600);
    c.style.transform = `translate3d(${S.ccx.toFixed(1)}px, ${S.ccy.toFixed(1)}px, 0) scale(${(1 - sv * 0.4).toFixed(3)}, ${(1 + sv).toFixed(3)})`;
  }

  if (st.shot !== lastShotAnnounced && st.kind !== 'intro' && S.phase === 'film') {
    lastShotAnnounced = st.shot;
    const s = S.m.shots[st.shot];
    $('live').textContent = `Shot ${st.shot + 1} of ${S.m.shots.length}: ${s.title.toLowerCase()}`;
  }

  if (S.score) {
    S.score.update({
      shotId: S.m.shots[st.shot].id, v: S.v, dir: S.dir, alt: tel ? tel.alt : 120, speed: tel ? tel.spd : 0,
      level: (1 - st.credits * 0.7) * exposure, musicLevel: 1 - 0.3 * Math.min(1, Math.abs(S.v) / 300),
      frameStep, playing: S.playing,
    });
  }
}

function drawBlack() {
  if (!S.renderer || !S.renderer.gl || S.renderer.lost || !S.renderer.targets) return;
  if (S._blackDrawn) return;
  S._blackDrawn = true;
  const gl = S.renderer.gl;
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
