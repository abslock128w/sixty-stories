// Hand-written WebGL2 picture engine.
//  pass 1  picture   : blend two frames (one at rest), smooth-depth parallax, gate weave, lens
//                      breathing, scrub smear + channel separation (zero at rest), exposure, cut
//                      flash; bicubic + restrained unsharp mask when shown above native size
//  pass 2  bright    : soft-knee highlight extraction at 1/4 res
//  pass 3/4 bloom    : separable blur -> halation source
//  pass 5  streak    : long horizontal blur of the brightest pixels (anamorphic streak)
//  pass 6  final     : composite halation + streak, vignette, luminance-weighted grain, mattes
//  pass 7  dust      : depth-occluded motes, additive
import { CONFIG, REDUCED } from './config.js';

const VS = `#version 300 es
const vec2 P[3] = vec2[3](vec2(-1.,-1.), vec2(3.,-1.), vec2(-1.,3.));
out vec2 vUv;
void main(){ vec2 p = P[gl_VertexID]; vUv = p*.5+.5; gl_Position = vec4(p,0.,1.); }`;

const PICTURE = `#version 300 es
precision highp float;
uniform sampler2D uColA, uColB, uDepA, uDepB;
uniform float uMix, uHas;
uniform vec4 uWin;        // full picture window in device px (GL origin bottom-left)
uniform vec4 uMatte;      // open part of the window (curtain mattes); outside is black
uniform vec2 uCrop, uCropOff;
uniform vec2 uPar;        // parallax offset (uv) at full depth difference
uniform float uFocus, uZoom, uSmear, uSplit, uExposure, uFlash;
uniform float uCubic;     // 1: bicubic (Catmull-Rom) colour sampling, used when magnified
uniform float uSharp;     // unsharp-mask amount (0 = off)
uniform float uDepthLod;  // mip level of the depth used for the parallax warp (smooth field)
uniform vec2 uWeave;
out vec4 o;
// Depth for the warp comes from a blurred mip level: a smooth displacement field cannot tear,
// duplicate rims or scatter pepper pixels along silhouettes (a sharp depth edge does).
float depthAt(vec2 uv){ return mix(textureLod(uDepA, uv, uDepthLod).r, textureLod(uDepB, uv, uDepthLod).r, uMix); }
vec3 lin(sampler2D t, vec2 uv){ return texture(t, uv).rgb; }
// Catmull-Rom in 9 bilinear taps
vec3 cubic(sampler2D t, vec2 uv){
  vec2 ts = vec2(textureSize(t, 0));
  vec2 sp = uv * ts;
  vec2 p1 = floor(sp - .5) + .5;
  vec2 f = sp - p1;
  vec2 w0 = f * (-.5 + f * (1. - .5 * f));
  vec2 w1 = 1. + f * f * (-2.5 + 1.5 * f);
  vec2 w2 = f * (.5 + f * (2. - 1.5 * f));
  vec2 w3 = f * f * (-.5 + .5 * f);
  vec2 w12 = w1 + w2;
  vec2 p0 = (p1 - 1.) / ts, p3 = (p1 + 2.) / ts, p12 = (p1 + w2 / w12) / ts;
  vec3 r = vec3(0.);
  r += textureLod(t, vec2(p0.x, p0.y), 0.).rgb * w0.x * w0.y;
  r += textureLod(t, vec2(p12.x, p0.y), 0.).rgb * w12.x * w0.y;
  r += textureLod(t, vec2(p3.x, p0.y), 0.).rgb * w3.x * w0.y;
  r += textureLod(t, vec2(p0.x, p12.y), 0.).rgb * w0.x * w12.y;
  r += textureLod(t, vec2(p12.x, p12.y), 0.).rgb * w12.x * w12.y;
  r += textureLod(t, vec2(p3.x, p12.y), 0.).rgb * w3.x * w12.y;
  r += textureLod(t, vec2(p0.x, p3.y), 0.).rgb * w0.x * w3.y;
  r += textureLod(t, vec2(p12.x, p3.y), 0.).rgb * w12.x * w3.y;
  r += textureLod(t, vec2(p3.x, p3.y), 0.).rgb * w3.x * w3.y;
  return max(r, vec3(0.));
}
vec3 colAt(vec2 uv){
  if (uMix <= 0.) return lin(uColA, uv);
  return mix(lin(uColA, uv), lin(uColB, uv), uMix);
}
vec3 colRest(vec2 uv){
  vec3 c = uCubic > .5 ? (uMix <= 0. ? cubic(uColA, uv) : mix(cubic(uColA, uv), cubic(uColB, uv), uMix)) : colAt(uv);
  if (uSharp > 0.) {
    // restrained unsharp mask: c + k * (c - blur), blur = 4 bilinear taps ~1 source px away
    vec2 tx = 1. / vec2(textureSize(uColA, 0));
    vec3 b = (colAt(uv + tx * vec2(.75, .75)) + colAt(uv + tx * vec2(-.75, .75)) + colAt(uv + tx * vec2(.75, -.75)) + colAt(uv + tx * vec2(-.75, -.75))) * .25;
    c = max(c + (c - b) * uSharp, vec3(0.));
  }
  return c;
}
void main(){
  vec2 p = (gl_FragCoord.xy - uWin.xy) / uWin.zw;
  vec2 pm = (gl_FragCoord.xy - uMatte.xy) / uMatte.zw;
  if (uHas < .5 || pm.x < 0. || pm.y < 0. || pm.x > 1. || pm.y > 1.) { o = vec4(0.,0.,0.,1.); return; }
  vec2 q = (p - .5) / uZoom + .5;               // overscan + breathing
  vec2 uv = uCropOff + q * uCrop;               // cover crop / pan
  uv.y = 1. - uv.y;                              // bitmap rows run top-down
  uv += uWeave;
  if (dot(uPar, uPar) > 1e-12) {
    // depth parallax (near moves more than far; the focus plane stays)
    float d0 = depthAt(clamp(uv, 0., 1.));
    uv += uPar * (d0 - uFocus);
  }
  uv = clamp(uv, vec2(.0005), vec2(.9995));
  vec2 dir = (q - .5) * vec2(uCrop.x * 2.39 / max(uCrop.y, 1e-3), 1.);
  vec3 c;
  if (uSmear > .0004) {
    // 8 taps of the blended frame, then one radial channel split (cheap enough for phones)
    vec3 acc = vec3(0.); float wsum = 0.;
    float j = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
    for (int k = 0; k < 8; k++) {
      float t = (float(k) + j) / 8. - .5;
      float w = 1. - abs(t) * 1.7;
      acc += colAt(clamp(uv + vec2(0., t * uSmear), 0., 1.)) * w; wsum += w;
    }
    c = acc / wsum;
    if (uSplit > 0.) {
      vec2 d = dir * uSplit;
      vec3 m = colAt(uv);
      c.r += colAt(clamp(uv + d, 0., 1.)).r - m.r;
      c.b += colAt(clamp(uv - d, 0., 1.)).b - m.b;
      c = max(c, vec3(0.));
    }
  } else if (uSplit > 0.) {
    vec2 d = dir * uSplit;
    c = vec3(colAt(clamp(uv + d, 0., 1.)).r, colAt(uv).g, colAt(clamp(uv - d, 0., 1.)).b);
  } else c = colRest(uv);
  c *= uExposure;
  c = c * (1. + uFlash) + uFlash * .06;
  o = vec4(c, 1.);
}`;

const BRIGHT = `#version 300 es
precision highp float;
in vec2 vUv; uniform sampler2D uSrc; uniform float uThr; uniform vec2 uTexel;
out vec4 o;
void main(){
  vec3 c = vec3(0.);
  c += texture(uSrc, vUv + uTexel * vec2(-1.,-1.)).rgb;
  c += texture(uSrc, vUv + uTexel * vec2( 1.,-1.)).rgb;
  c += texture(uSrc, vUv + uTexel * vec2(-1., 1.)).rgb;
  c += texture(uSrc, vUv + uTexel * vec2( 1., 1.)).rgb;
  c *= .25;
  float l = max(c.r, max(c.g, c.b));
  float k = smoothstep(uThr, 1., l);
  o = vec4(c * k * k, 1.);
}`;

const BLUR = `#version 300 es
precision highp float;
in vec2 vUv; uniform sampler2D uSrc; uniform vec2 uDir; out vec4 o;
void main(){
  vec3 c = texture(uSrc, vUv).rgb * .2270;
  c += (texture(uSrc, vUv + uDir * 1.3846).rgb + texture(uSrc, vUv - uDir * 1.3846).rgb) * .3162;
  c += (texture(uSrc, vUv + uDir * 3.2308).rgb + texture(uSrc, vUv - uDir * 3.2308).rgb) * .0703;
  o = vec4(c, 1.);
}`;

const STREAK = `#version 300 es
precision highp float;
in vec2 vUv; uniform sampler2D uSrc; uniform vec2 uTexel; out vec4 o;
void main(){
  vec3 c = vec3(0.); float ws = 0.;
  for (int k = -20; k <= 20; k++) {
    float t = float(k) / 20.;
    float w = exp(-abs(t) * 3.2);
    c += texture(uSrc, vUv + vec2(float(k) * 3. * uTexel.x, 0.)).rgb * w; ws += w;
  }
  o = vec4(c / ws, 1.);
}`;

const FINAL = `#version 300 es
precision highp float;
in vec2 vUv;
uniform sampler2D uPic, uBloom, uStreak;
uniform vec4 uWin, uMatte; uniform vec2 uRes;
uniform float uHal, uStr, uVig, uGrain, uSeed, uFade;
out vec4 o;
float h12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main(){
  vec2 p = (gl_FragCoord.xy - uWin.xy) / uWin.zw;
  vec2 pm = (gl_FragCoord.xy - uMatte.xy) / uMatte.zw;
  if (pm.x < 0. || pm.y < 0. || pm.x > 1. || pm.y > 1.) { o = vec4(0.,0.,0.,1.); return; }
  vec3 c = texture(uPic, vUv).rgb;
  vec3 b = texture(uBloom, vUv).rgb;
  vec3 s = texture(uStreak, vUv).rgb;
  // halation: warm red-orange fringe that hugs highlights (film's anti-halation layer failing)
  c += b * uHal * vec3(1.0, .52, .30);
  c += s * uStr * vec3(1.0, .80, .58);
  // vignette in window space
  vec2 v = (p - .5) * vec2(uWin.z / uWin.w, 1.);
  float vig = 1. - dot(v, v) * .55;
  c *= mix(1., clamp(vig, 0., 1.), uVig);
  // grain: per-channel, triangular distribution, strongest in the mids
  vec2 g = gl_FragCoord.xy + uSeed * vec2(113.1, 71.7);
  vec3 n = vec3(h12(g) + h12(g + 17.3), h12(g + 41.9) + h12(g + 5.1), h12(g + 87.2) + h12(g + 29.7)) - 1.;
  float l = dot(c, vec3(.2126, .7152, .0722));
  float w = clamp(4. * l * (1. - l), 0., 1.) * .85 + .15;
  c += mix(vec3(n.g), n, .35) * uGrain * w;
  c *= uFade;
  c += (h12(gl_FragCoord.xy + uSeed) - .5) / 255.;   // dither
  o = vec4(clamp(c, 0., 1.), 1.);
}`;

const DUST_VS = `#version 300 es
precision highp float;
in vec4 aSeed;
uniform sampler2D uDepA;
uniform vec4 uWin; uniform vec2 uRes, uCrop, uCropOff, uPar;
uniform float uTime, uFocus, uZoom, uDpr;
out float vA; out float vSize;
void main(){
  float z = 6. + aSeed.z * aSeed.z * 70.;                 // metres from lens
  float dv = 1. / (1. + z / 25.);                           // same encoding as the depth maps
  vec2 drift = vec2(.006 + aSeed.w * .012, .004 - aSeed.x * .010) * (8. / z + .2);
  vec2 p = fract(aSeed.xy + uTime * drift + .015 * vec2(sin(uTime * .3 + aSeed.w * 30.), cos(uTime * .23 + aSeed.z * 20.)));
  vec2 q = (p - .5) / uZoom + .5;
  vec2 uv = uCropOff + q * uCrop; uv.y = 1. - uv.y;
  float scene = textureLod(uDepA, clamp(uv, 0., 1.), 0.).r;
  p -= (uPar / uCrop) * vec2(1., -1.) * (dv - uFocus) * uZoom;
  float occl = smoothstep(dv + .01, dv - .03, scene);     // visible only in front of the scene
  float glint = pow(.5 + .5 * sin(uTime * (0.6 + aSeed.w * 1.7) + aSeed.x * 40.), 6.);
  vA = occl * (.12 + .88 * glint) * clamp(10. / z, .2, 1.);
  vSize = clamp(42. / z, 1.2, 7.) * uDpr * (uWin.w / (804. * uDpr) * .9 + .1);
  gl_PointSize = vSize;
  vec2 px = uWin.xy + p * uWin.zw;
  gl_Position = vec4(px / uRes * 2. - 1., 0., 1.);
}`;

const DUST_FS = `#version 300 es
precision highp float;
in float vA; in float vSize; uniform float uStrength; uniform vec4 uMatte; out vec4 o;
void main(){
  vec2 p = (gl_FragCoord.xy - uMatte.xy) / uMatte.zw;
  if (p.x < 0. || p.y < 0. || p.x > 1. || p.y > 1.) discard;
  vec2 d = gl_PointCoord * 2. - 1.;
  float r = dot(d, d);
  float soft = clamp((vSize - 2.) / 8., 0., 1.);                  // big near motes are out of focus
  float a = mix(exp(-r * 5.), smoothstep(1., .55, r) * .55 + exp(-r * 3.) * .2, soft);
  o = vec4(vec3(1., .86, .66) * a * vA * uStrength, 1.);
}`;

function compile(gl, vs, fs) {
  const mk = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS) && !gl.isContextLost()) throw new Error(gl.getShaderInfoLog(s) + '\n' + src.slice(0, 200));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
  gl.bindAttribLocation(p, 0, 'aSeed');
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS) && !gl.isContextLost()) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let k = 0; k < n; k++) { const info = gl.getActiveUniform(p, k); u[info.name] = gl.getUniformLocation(p, info.name); }
  return { p, u };
}

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = null;
    this.lost = false;
    this.targets = null;
  }

  init() {
    const gl = this.canvas.getContext('webgl2', { alpha: false, antialias: false, depth: false, stencil: false, premultipliedAlpha: false, preserveDrawingBuffer: false, powerPreference: 'high-performance' });
    if (!gl) throw new Error('WebGL2 unavailable');
    this.gl = gl;
    this.pic = compile(gl, VS, PICTURE);
    this.bright = compile(gl, VS, BRIGHT);
    this.blur = compile(gl, VS, BLUR);
    this.streak = compile(gl, VS, STREAK);
    this.fin = compile(gl, VS, FINAL);
    this.dust = compile(gl, DUST_VS, DUST_FS);
    this.vao = gl.createVertexArray();
    // dust seeds
    const n = REDUCED ? Math.round(CONFIG.look.dust * 0.5) : CONFIG.look.dust;
    const seeds = new Float32Array(n * 4);
    let s = 1234567;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let k = 0; k < seeds.length; k++) seeds[k] = rnd();
    this.dustN = n;
    this.dustVao = gl.createVertexArray();
    gl.bindVertexArray(this.dustVao);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, seeds, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
    // 1x1 black fallback
    this.black = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.black);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));
    this.targets = null;
    this.lost = false;
  }

  target(w, h) {
    const gl = this.gl;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, w, h);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fb = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    return { tex, fb, w, h };
  }

  resize(w, h) {
    const gl = this.gl;
    if (!gl) return;
    if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h; }
    if (this.targets && this.targets.w === w && this.targets.h === h) return;
    if (this.targets) for (const t of Object.values(this.targets)) if (t && t.tex) { gl.deleteTexture(t.tex); gl.deleteFramebuffer(t.fb); }
    const qw = Math.max(1, Math.round(w / 4)), qh = Math.max(1, Math.round(h / 4));
    this.targets = { w, h, pic: this.target(w, h), br: this.target(qw, qh), b1: this.target(qw, qh), b2: this.target(qw, qh), st: this.target(qw, qh) };
  }

  pass(prog, fbo, w, h) {
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.viewport(0, 0, w, h);
    gl.useProgram(prog.p);
  }

  tex(prog, name, unit, t) {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.uniform1i(prog.u[name], unit);
  }

  // s: full frame state, see main.js
  draw(s) {
    const gl = this.gl;
    if (!gl || this.lost || !this.targets) return;
    const T = this.targets, W = T.w, H = T.h;
    gl.bindVertexArray(this.vao);
    gl.disable(gl.BLEND);
    // 1 picture
    const P = this.pic;
    this.pass(P, T.pic.fb, W, H);
    const A = s.pick && s.pick.A, B = s.pick && s.pick.B;
    this.tex(P, 'uColA', 0, A ? A.col : this.black);
    this.tex(P, 'uColB', 1, B ? B.col : this.black);
    this.tex(P, 'uDepA', 2, A ? A.dep : this.black);
    this.tex(P, 'uDepB', 3, B ? B.dep : this.black);
    gl.uniform1f(P.u.uMix, s.pick ? s.pick.mix : 0);
    gl.uniform1f(P.u.uHas, A ? 1 : 0);
    gl.uniform4f(P.u.uWin, ...s.win);
    gl.uniform4f(P.u.uMatte, ...(s.matte || s.win));
    gl.uniform1f(P.u.uCubic, s.cubic ? 1 : 0);
    gl.uniform1f(P.u.uSharp, s.sharp || 0);
    gl.uniform1f(P.u.uDepthLod, CONFIG.look.parallaxDepthLod);
    gl.uniform2f(P.u.uCrop, ...s.crop);
    gl.uniform2f(P.u.uCropOff, ...s.cropOff);
    gl.uniform2f(P.u.uPar, ...s.par);
    gl.uniform1f(P.u.uFocus, CONFIG.look.parallaxFocus);
    gl.uniform1f(P.u.uZoom, s.zoom);
    gl.uniform1f(P.u.uSmear, s.smear);
    gl.uniform1f(P.u.uSplit, s.split);
    gl.uniform1f(P.u.uExposure, s.exposure);
    gl.uniform1f(P.u.uFlash, s.flash);
    gl.uniform2f(P.u.uWeave, ...s.weave);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // 2 bright
    const Bp = this.bright;
    this.pass(Bp, T.br.fb, T.br.w, T.br.h);
    this.tex(Bp, 'uSrc', 0, T.pic.tex);
    gl.uniform1f(Bp.u.uThr, CONFIG.look.halationThreshold);
    gl.uniform2f(Bp.u.uTexel, 1 / W, 1 / H);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // 3/4 blur
    const Bl = this.blur;
    this.pass(Bl, T.b1.fb, T.b1.w, T.b1.h);
    this.tex(Bl, 'uSrc', 0, T.br.tex);
    gl.uniform2f(Bl.u.uDir, 1.6 / T.br.w, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.pass(Bl, T.b2.fb, T.b2.w, T.b2.h);
    this.tex(Bl, 'uSrc', 0, T.b1.tex);
    gl.uniform2f(Bl.u.uDir, 0, 1.6 / T.br.h);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // 5 streak
    const St = this.streak;
    this.pass(St, T.st.fb, T.st.w, T.st.h);
    this.tex(St, 'uSrc', 0, T.br.tex);
    gl.uniform2f(St.u.uTexel, 1 / T.br.w, 1 / T.br.h);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // 6 final
    const F = this.fin;
    this.pass(F, null, W, H);
    this.tex(F, 'uPic', 0, T.pic.tex);
    this.tex(F, 'uBloom', 1, T.b2.tex);
    this.tex(F, 'uStreak', 2, T.st.tex);
    gl.uniform4f(F.u.uWin, ...s.win);
    gl.uniform4f(F.u.uMatte, ...(s.matte || s.win));
    gl.uniform2f(F.u.uRes, W, H);
    gl.uniform1f(F.u.uHal, CONFIG.look.halation);
    gl.uniform1f(F.u.uStr, CONFIG.look.streak);
    gl.uniform1f(F.u.uVig, CONFIG.look.vignette);
    gl.uniform1f(F.u.uGrain, s.grain);
    gl.uniform1f(F.u.uSeed, s.seed);
    gl.uniform1f(F.u.uFade, s.fade);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // 7 dust
    if (A && s.dust > 0) {
      const D = this.dust;
      gl.useProgram(D.p);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE);
      gl.bindVertexArray(this.dustVao);
      this.tex(D, 'uDepA', 0, A.dep);
      gl.uniform4f(D.u.uWin, ...s.win);
      gl.uniform4f(D.u.uMatte, ...(s.matte || s.win));
      gl.uniform2f(D.u.uRes, W, H);
      gl.uniform2f(D.u.uCrop, ...s.crop);
      gl.uniform2f(D.u.uCropOff, ...s.cropOff);
      gl.uniform2f(D.u.uPar, ...s.par);
      gl.uniform1f(D.u.uTime, s.time);
      gl.uniform1f(D.u.uFocus, CONFIG.look.parallaxFocus);
      gl.uniform1f(D.u.uZoom, s.zoom);
      gl.uniform1f(D.u.uDpr, s.dpr);
      gl.uniform1f(D.u.uStrength, s.dust * s.exposure * s.fade);
      gl.drawArrays(gl.POINTS, 0, this.dustN);
      gl.disable(gl.BLEND);
    }
    gl.bindVertexArray(null);
  }
}
