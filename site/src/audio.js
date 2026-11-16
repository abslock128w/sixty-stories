// Score + sound design, synthesised live with the Web Audio API (no files, no third parties).
// Layers: minor-mode drone/pad whose chord follows the shot (opens up in THE CITY and APEX),
// stereo wind driven by altitude/speed/scrub velocity, a distant city bed at low altitude with
// the odd far siren, a sub drop + whoosh into THE DROP, launcher snaps and line tension at the
// swing cuts, and a soft projector-gate tick while scrubbing. A compressor/limiter guards clipping.
import { CONFIG } from './config.js';

const NOTE = (n) => 440 * Math.pow(2, (n - 69) / 12);
// per-shot voicings (MIDI). D minor world; s1 and s6 open up (add9 / maj7 colour, higher voices)
const CHORDS = {
  s1: [38, 45, 50, 53, 57, 64],   // Dm(add9) wide
  s2: [34, 41, 50, 53, 57, 62],   // Bbmaj7-ish, close and suspended
  s3: [31, 38, 46, 50, 55, 58],   // Gm low, tense
  s4: [41, 48, 53, 57, 60, 65],   // F major lift
  s5: [36, 43, 52, 55, 60, 62],   // C(add9)
  s6: [38, 45, 52, 57, 62, 69],   // Dm(add9) open, high
};
const OPEN = { s1: 1, s2: 0.35, s3: 0.15, s4: 0.55, s5: 0.5, s6: 1 };

export class Score {
  constructor() { this.ctx = null; this.muted = false; this.started = false; this.lastShot = null; this.lastTick = 0; this.sirenAt = 0; }

  start() {
    if (this.started) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = (this.ctx = new AC({ latencyHint: 'playback' }));
    this.started = true;
    const now = ctx.currentTime;

    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14; comp.knee.value = 8; comp.ratio.value = 12; comp.attack.value = 0.004; comp.release.value = 0.25;
    this.master = ctx.createGain(); this.master.gain.value = 0;
    // soft clipper after the compressor: transparent below ~-6 dBFS, never exceeds full scale
    const clip = ctx.createWaveShaper();
    const curve = new Float32Array(2048);
    for (let k = 0; k < curve.length; k++) { const x = (k / (curve.length - 1)) * 2 - 1; curve[k] = Math.tanh(x * 1.2) / Math.tanh(1.2) * 0.94; }
    clip.curve = curve; clip.oversample = '2x';
    this.master.connect(comp); comp.connect(clip); clip.connect(ctx.destination);
    this.meter = ctx.createAnalyser(); this.meter.fftSize = 2048; clip.connect(this.meter);
    this.master.gain.setTargetAtTime(CONFIG.audio.master, now, 1.2);

    // reverb: generated stereo impulse, long and dark
    this.verb = ctx.createConvolver();
    const len = Math.round(ctx.sampleRate * 4.2);
    const ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = ir.getChannelData(ch); let lp = 0;
      for (let k = 0; k < len; k++) { lp = lp * 0.82 + (Math.random() * 2 - 1) * 0.18; d[k] = lp * Math.pow(1 - k / len, 2.6); }
    }
    this.verb.buffer = ir;
    this.verbGain = ctx.createGain(); this.verbGain.gain.value = 0.55;
    this.verb.connect(this.verbGain); this.verbGain.connect(this.master);

    // music bus
    this.music = ctx.createGain(); this.music.gain.value = 0.0;
    this.music.gain.setTargetAtTime(0.5, now + 0.5, 2.5);
    this.musicLP = ctx.createBiquadFilter(); this.musicLP.type = 'lowpass'; this.musicLP.frequency.value = 900; this.musicLP.Q.value = 0.3;
    this.music.connect(this.musicLP); this.musicLP.connect(this.master); this.musicLP.connect(this.verb);
    const lfo = ctx.createOscillator(); lfo.frequency.value = 0.045;
    const lfoG = ctx.createGain(); lfoG.gain.value = 260; lfo.connect(lfoG); lfoG.connect(this.musicLP.frequency); lfo.start();

    this.voices = CHORDS.s1.map((n, k) => {
      const g = ctx.createGain(); g.gain.value = k < 2 ? 0.16 : 0.07;
      const pan = ctx.createStereoPanner(); pan.pan.value = (k % 2 ? 1 : -1) * (0.15 + k * 0.08);
      const oscs = [-7, 6].map((det, j) => {
        const o = ctx.createOscillator(); o.type = j ? 'triangle' : 'sawtooth';
        o.frequency.value = NOTE(n); o.detune.value = det + (k * 1.7);
        const og = ctx.createGain(); og.gain.value = j ? 0.9 : 0.35;
        o.connect(og); og.connect(g); o.start(); return o;
      });
      // slow amplitude breathing per voice
      const am = ctx.createOscillator(); am.frequency.value = 0.03 + k * 0.011;
      const amg = ctx.createGain(); amg.gain.value = 0.025; am.connect(amg); amg.connect(g.gain); am.start();
      g.connect(pan); pan.connect(this.music);
      return { oscs, g, base: k < 2 ? 0.16 : 0.07 };
    });
    // shimmer (high sines) for the open shots
    this.shimmer = ctx.createGain(); this.shimmer.gain.value = 0;
    this.shimmer.connect(this.verb); this.shimmer.connect(this.master);
    this.shimOsc = [74, 81, 86].map((n, k) => {
      const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = NOTE(n);
      const g = ctx.createGain(); g.gain.value = 0.018 / (k + 1);
      const tr = ctx.createOscillator(); tr.frequency.value = 0.15 + k * 0.07;
      const trg = ctx.createGain(); trg.gain.value = 0.012 / (k + 1); tr.connect(trg); trg.connect(g.gain); tr.start();
      o.connect(g); g.connect(this.shimmer); o.start(); return o;
    });

    // noise sources
    const noise = (brown) => {
      const b = ctx.createBuffer(2, ctx.sampleRate * 4, ctx.sampleRate);
      for (let ch = 0; ch < 2; ch++) {
        const d = b.getChannelData(ch); let last = 0;
        for (let k = 0; k < d.length; k++) {
          const w = Math.random() * 2 - 1;
          if (brown) { last = (last + 0.02 * w) / 1.02; d[k] = last * 3.5; } else d[k] = w;
        }
      }
      const s = ctx.createBufferSource(); s.buffer = b; s.loop = true; s.start(); return s;
    };
    this.noiseBuf = noise(false).buffer;

    // wind: two band-passed noises panned apart
    this.wind = ctx.createGain(); this.wind.gain.value = 0; this.wind.connect(this.master);
    this.windF = [-0.6, 0.6].map((p, k) => {
      const src = noise(false);
      const f = ctx.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 500 + k * 200; f.Q.value = 0.7;
      const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2400;
      const pan = ctx.createStereoPanner(); pan.pan.value = p;
      const gust = ctx.createOscillator(); gust.frequency.value = 0.13 + k * 0.07;
      const gg = ctx.createGain(); gg.gain.value = 180; gust.connect(gg); gg.connect(f.frequency); gust.start();
      src.connect(f); f.connect(lp); lp.connect(pan); pan.connect(this.wind); return f;
    });

    // city bed
    this.city = ctx.createGain(); this.city.gain.value = 0;
    const cs = noise(true); const clp = ctx.createBiquadFilter(); clp.type = 'lowpass'; clp.frequency.value = 380;
    const chp = ctx.createBiquadFilter(); chp.type = 'highpass'; chp.frequency.value = 45;
    cs.connect(chp); chp.connect(clp); clp.connect(this.city);
    this.city.connect(this.master); this.city.connect(this.verb);

    // projector gate tick bus
    this.tick = ctx.createGain(); this.tick.gain.value = 0.0; this.tick.connect(this.master);
  }

  oneShotNoise(t, dur, type, f0, f1, gain, q = 1, dest = this.master) {
    const ctx = this.ctx;
    const s = ctx.createBufferSource(); s.buffer = this.noiseBuf;
    const f = ctx.createBiquadFilter(); f.type = type; f.Q.value = q;
    f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + Math.min(0.03, dur * 0.2));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(dest); g.connect(this.verb);
    s.start(t, Math.random() * 2); s.stop(t + dur + 0.05);
  }

  tone(t, dur, type, f0, f1, gain, dest = this.master) {
    const ctx = this.ctx;
    const o = ctx.createOscillator(); o.type = type;
    o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest); o.start(t); o.stop(t + dur + 0.05);
  }

  drop() {
    if (!this.ctx) return; const t = this.ctx.currentTime + 0.01;
    this.tone(t, 2.6, 'sine', 78, 26, 0.55);
    this.tone(t, 1.6, 'triangle', 156, 40, 0.08);
    this.oneShotNoise(t, 2.2, 'bandpass', 300, 3200, 0.35, 0.8);
  }

  launcher(pan = 0) {
    if (!this.ctx) return; const ctx = this.ctx; const t = ctx.currentTime + 0.01;
    const p = ctx.createStereoPanner(); p.pan.value = pan; p.connect(this.master);
    this.oneShotNoise(t, 0.05, 'highpass', 3500, 6000, 0.35, 0.7, p);          // snap
    this.tone(t, 0.18, 'square', 2300, 1900, 0.025, p);                         // metallic ping
    this.tone(t, 0.25, 'sine', 3410, 3300, 0.03, p);
    this.oneShotNoise(t + 0.02, 0.32, 'bandpass', 1800, 700, 0.12, 2.5, p);     // line paying out
    // line tension: rising, slightly beating cable creak
    const o = ctx.createOscillator(); o.type = 'sawtooth';
    o.frequency.setValueAtTime(140, t + 0.25); o.frequency.exponentialRampToValueAtTime(330, t + 1.0);
    const f = ctx.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 900; f.Q.value = 6;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t + 0.25);
    g.gain.exponentialRampToValueAtTime(0.06, t + 0.45); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.25);
    const tr = ctx.createOscillator(); tr.frequency.value = 17; const tg = ctx.createGain(); tg.gain.value = 0.03;
    tr.connect(tg); tg.connect(g.gain);
    o.connect(f); f.connect(g); g.connect(p); g.connect(this.verb);
    o.start(t + 0.25); o.stop(t + 1.3); tr.start(t + 0.25); tr.stop(t + 1.3);
  }

  siren() {
    const ctx = this.ctx, t = ctx.currentTime;
    const o = ctx.createOscillator(); o.type = 'triangle'; o.frequency.value = 760;
    const l = ctx.createOscillator(); l.frequency.value = 0.22; const lg = ctx.createGain(); lg.gain.value = 170;
    l.connect(lg); lg.connect(o.frequency);
    const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 1300;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.012, t + 2.5); g.gain.exponentialRampToValueAtTime(0.0001, t + 9);
    const p = ctx.createStereoPanner(); p.pan.value = Math.random() * 1.6 - 0.8;
    o.connect(f); f.connect(g); g.connect(p); p.connect(this.verb); p.connect(this.master);
    o.start(t); l.start(t); o.stop(t + 9.2); l.stop(t + 9.2);
  }

  // called every animation frame
  update(st) {
    const ctx = this.ctx; if (!ctx || ctx.state === 'closed') return;
    const t = ctx.currentTime;
    const sid = st.shotId;
    if (sid !== this.lastShot) {
      const chord = CHORDS[sid] || CHORDS.s1;
      this.voices.forEach((v, k) => v.oscs.forEach((o) => o.frequency.setTargetAtTime(NOTE(chord[k]), t, 0.9)));
      const open = OPEN[sid] ?? 0.4;
      this.shimmer.gain.setTargetAtTime(open > 0.9 ? 1 : open * 0.25, t, 2.0);
      this.musicLP.frequency.setTargetAtTime(500 + open * 1400, t, 1.6);
      // cut events only when travelling forward at roughly playback speed
      if (this.lastShot && st.dir > 0 && Math.abs(st.v) < 140) {
        if (sid === 's3') this.drop();
        if (sid === 's4') this.launcher(-0.3);
        if (sid === 's5') this.launcher(0.35);
      }
      this.lastShot = sid;
    }
    // swing re-fire mid-shot (s5 fires again on its way out)
    const alt = st.alt ?? 120, spd = st.speed ?? 0, vel = Math.min(1, Math.abs(st.v) / 200);
    const windAmt = Math.min(1, 0.08 + (alt / 400) * 0.25 + (spd / 180) * 0.55 + vel * 0.4);
    this.wind.gain.setTargetAtTime(0.16 * windAmt * st.level, t, 0.25);
    this.windF.forEach((f, k) => f.Q.setTargetAtTime(0.6 + windAmt * 1.4, t, 0.3));
    this.windF.forEach((f, k) => f.frequency.setTargetAtTime(350 + windAmt * 1300 + k * 220, t, 0.3));
    const low = Math.max(0, 1 - alt / 110);
    this.city.gain.setTargetAtTime((0.05 + 0.4 * low) * st.level, t, 0.6);
    if (low > 0.3 && t > this.sirenAt) { this.sirenAt = t + 18 + Math.random() * 20; if (Math.random() < 0.6) this.siren(); }
    this.music.gain.setTargetAtTime(0.5 * st.musicLevel, t, 0.8);
    // projector gate tick on integer frame changes while scrubbing by hand
    if (st.frameStep && !st.playing && Math.abs(st.v) > 4 && t - this.lastTick > 1 / 30) {
      this.lastTick = t;
      this.oneShotNoise(t + 0.005, 0.03, 'bandpass', 2600, 1800, Math.min(0.05, 0.012 + Math.abs(st.v) / 3000), 3, this.master);
    }
  }

  peak() {
    if (!this.meter) return 0;
    const b = new Float32Array(this.meter.fftSize); this.meter.getFloatTimeDomainData(b);
    let p = 0; for (const v of b) p = Math.max(p, Math.abs(v)); return p;
  }

  setMuted(m) {
    this.muted = m; if (!this.ctx) return;
    this.master.gain.setTargetAtTime(m ? 0 : CONFIG.audio.master, this.ctx.currentTime, 0.15);
  }

  suspend(hidden) {
    if (!this.ctx) return;
    if (hidden) this.ctx.suspend().catch(() => {}); else this.ctx.resume().catch(() => {});
  }
}
