// Maps page scroll (px) <-> fractional global frame. Each shot gets scroll length proportional
// to its frame count; a short hold follows every cut; an intro hold precedes the film and the
// credits segment follows it.
// Every frame owns a zone of exactly ppf px; the frame is a whole number at the centre of its
// zone (posForFrame returns that centre). So a scroll position that browsers snap to whole (or
// device) pixels still lands on the intended frame, and the last frame of a shot is reachable.
import { CONFIG } from './config.js';

export class Timeline {
  constructor(manifest) {
    this.m = manifest;
    this.shots = manifest.shots;
    this.total = manifest.total;
    this.layout(800);
  }

  layout(vh) {
    const S = CONFIG.scroll;
    this.vh = vh;
    this.ppf = vh / S.framesPerVh;
    const segs = [];
    let p = 0;
    const push = (o) => { o.p0 = p; p += o.len; o.p1 = p; segs.push(o); return o; };
    push({ kind: 'intro', len: S.introHoldVh * vh, frame: 0, shot: 0 });
    this.shotSpan = [];
    this.shots.forEach((s, k) => {
      const hold = k > 0 ? push({ kind: 'hold', len: S.cutHoldVh * vh, frame: s.start, shot: k }) : null;
      const seg = push({ kind: 'shot', len: Math.max(1, s.count) * this.ppf, start: s.start, count: s.count, shot: k });
      this.shotSpan[k] = { p0: hold ? hold.p0 : seg.p0, p1: seg.p1, seg };
    });
    const last = this.shots[this.shots.length - 1];
    this.filmEnd = p;
    push({ kind: 'credits', len: S.creditsVh * vh, frame: last.start + last.count - 1, shot: this.shots.length - 1 });
    this.segs = segs;
    this.length = p;
  }

  // scroll position -> state
  at(pos) {
    pos = Math.max(0, Math.min(this.length, pos));
    let seg = this.segs[this.segs.length - 1];
    for (const s of this.segs) if (pos < s.p1) { seg = s; break; }
    const t = (pos - seg.p0) / seg.len;
    let frame = seg.kind === 'shot' ? seg.start + Math.max(0, Math.min(seg.count - 1, (pos - seg.p0) / this.ppf - 0.5)) : seg.frame;
    const span = this.shotSpan[seg.shot];
    return {
      pos, frame, shot: seg.shot, kind: seg.kind,
      intro: seg.kind === 'intro' ? t : 1,
      credits: seg.kind === 'credits' ? t : 0,
      shotQ: (pos - span.p0) / (span.p1 - span.p0),
    };
  }

  // fractional frame -> scroll position (centre of the frame's zone, after any hold)
  posForFrame(f) {
    for (const span of this.shotSpan) {
      const g = span.seg;
      if (f < g.start + g.count) {
        const lf = Math.max(0, Math.min(g.count - 1, f - g.start));
        return g.p0 + (lf + 0.5) * this.ppf;
      }
    }
    return this.shotSpan[this.shotSpan.length - 1].seg.p1 - 0.5 * this.ppf;
  }

  shotIndexOf(f) {
    for (let k = 0; k < this.shots.length; k++) {
      const s = this.shots[k];
      if (f < s.start + s.count) return k;
    }
    return this.shots.length - 1;
  }

  // where to land for "go to shot k": the start of its hold so its title plays
  posForShot(k) {
    k = Math.max(0, Math.min(this.shots.length - 1, k));
    return k === 0 ? this.segs[0].p1 : this.shotSpan[k].p0;
  }
}
