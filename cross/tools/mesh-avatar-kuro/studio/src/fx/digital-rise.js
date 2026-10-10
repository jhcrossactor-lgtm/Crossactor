// digital-rise — アバターの足元から立ち上るデジタル粒子（Canvas2D、独立レイヤー）
//
// アバター本体（WebGL キャンバスでも img でも何でも）には一切触らない。
// 背面キャンバスと前面キャンバスを 1 枚ずつ作り、同じ矩形に重ねて描くだけ。
//
//   import { createDigitalRise } from './digital-rise.js';
//   import config from './digital-rise.config.js';
//   const fx = createDigitalRise({ container, before: avatarCanvas, config });
//   fx.setSpeaking(true);  fx.setLevel(0.6);   // 口パク中は粒子量・明るさが上がる
//   fx.tick(now);                               // autoLoop: false のとき自分の描画ループから呼ぶ
//   fx.destroy();
//
// 別アプリへの移植：このファイルと digital-rise.config.js を丸ごとコピーして上の 3 行を書くだけ。

import DEFAULTS from './digital-rise.config.js';

const KINDS = ['square', 'pixel', 'glyph', 'line'];
const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function mergeConfig(base, over) {
  if (!over) return structuredClone(base);
  const out = structuredClone(base);
  for (const [k, v] of Object.entries(over)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])) out[k] = mergeConfig(out[k], v);
    else out[k] = v;
  }
  return out;
}

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// にじみ付きの粒スプライトを 1 色 1 サイズにつき 1 回だけ描いて使い回す（shadowBlur を毎フレーム使わない）
function makeSprites(colors, glow, dpr) {
  const sprites = {};
  for (const color of colors) {
    const [r, g, b] = hexToRgb(color);
    const size = 24 * dpr, c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d');
    const cx = size / 2;
    if (glow > 0) {
      const grad = ctx.createRadialGradient(cx, cx, 0, cx, cx, cx);
      grad.addColorStop(0, `rgba(${r},${g},${b},${0.7 * glow})`);
      grad.addColorStop(0.4, `rgba(${r},${g},${b},${0.22 * glow})`);
      grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, size, size);
    }
    sprites[color] = c;
  }
  return sprites;
}

function pickKind(kinds) {
  const total = KINDS.reduce((s, k) => s + (kinds[k] ?? 0), 0) || 1;
  let r = Math.random() * total;
  for (const k of KINDS) { r -= kinds[k] ?? 0; if (r <= 0) return k; }
  return 'square';
}

class Layer {
  constructor(canvas, cfg, layerCfg, shared) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.cfg = cfg; this.lc = layerCfg; this.shared = shared;
    this.particles = [];
    this.spawnAcc = 0;
    this.w = 1; this.h = 1;
  }
  resize(w, h, dpr) {
    this.w = w; this.h = h; this.dpr = dpr;
    this.canvas.width = Math.max(1, Math.round(w * dpr));
    this.canvas.height = Math.max(1, Math.round(h * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  // 起動直後から定常状態に見えるよう、高さ方向にばらして先に撒いておく
  prewarm(density) {
    const target = Math.round(this.lc.count * density);
    this.particles.length = 0;
    for (let i = 0; i < target; i++) {
      this.spawn();
      const p = this.particles[this.particles.length - 1];
      p.y = this.h * (1 - Math.random() * this.cfg.fade.end);
      p.life = 1;
    }
  }
  spawn() {
    const { cfg, lc } = this;
    const kind = pickKind(cfg.kinds);
    const size = rand(lc.size[0], lc.size[1]);
    const half = this.w * cfg.spawn.xSpread * 0.5, cx = this.w * cfg.spawn.xCenter;
    const x = Math.random() < (cfg.spawn.edgeBias ?? 0)
      ? cx + (Math.random() < 0.5 ? -1 : 1) * half * rand(0.75, 1.1)
      : cx + (Math.random() * 2 - 1) * half;
    this.particles.push({
      kind, size,
      x, y: this.h + rand(0, cfg.spawn.jitterY),
      vy: rand(lc.speed[0], lc.speed[1]),
      color: cfg.colors[Math.floor(Math.random() * cfg.colors.length)],
      phase: Math.random() * Math.PI * 2,
      wf: cfg.wobble.freq * rand(0.7, 1.3),
      glyph: Math.random() < 0.5 ? '0' : '1',
      len: kind === 'line' ? rand(10, 42) : 0,
      flicker: rand(0.75, 1),
      life: 0,
    });
  }
  step(dt, density, boost) {
    const { cfg, lc } = this;
    const target = Math.round(lc.count * density * boost.rate);
    // 画面の高さを平均速度で割った時間が「寿命」なので、それに合わせて発生させる
    const meanSpeed = (lc.speed[0] + lc.speed[1]) / 2;
    const travel = this.h * cfg.fade.end + cfg.spawn.jitterY;
    const perSecond = target / Math.max(0.5, travel / meanSpeed);
    this.spawnAcc += perSecond * dt;
    while (this.spawnAcc >= 1 && this.particles.length < target * 1.3) { this.spawn(); this.spawnAcc -= 1; }
    if (this.spawnAcc > 4) this.spawnAcc = 4;

    const keep = [];
    for (const p of this.particles) {
      p.life += dt;
      p.y -= p.vy * dt;
      const progress = 1 - p.y / this.h;           // 0 = 下端, 1 = 上端
      if (progress >= cfg.fade.end) continue;
      keep.push(p);
    }
    this.particles = keep;
  }
  draw(t, boost) {
    const { ctx, cfg, lc } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = 'lighter';
    if (this.isBack && cfg.ground && cfg.ground.alpha > 0) {
      const gh = this.h * cfg.ground.height, pulse = 0.9 + 0.1 * Math.sin(t * 1.1);
      const grad = ctx.createLinearGradient(0, this.h - gh, 0, this.h);
      grad.addColorStop(0, 'rgba(0,0,0,0)');
      grad.addColorStop(1, this.shared.groundColor);
      ctx.globalAlpha = cfg.ground.alpha * pulse * (0.8 + 0.2 * boost.brightness);
      ctx.fillStyle = grad;
      ctx.fillRect(0, this.h - gh, this.w, gh);
    }
    const sprites = this.shared.sprites;
    const fs = cfg.fade;
    for (const p of this.particles) {
      const progress = clamp(1 - p.y / this.h, 0, 1);
      const fade = progress <= fs.start ? 1 : Math.pow(1 - (progress - fs.start) / (fs.end - fs.start), fs.power);
      const born = clamp(p.life / 0.35, 0, 1);        // 生まれ際はふわっと出す
      const flick = 0.85 + 0.15 * Math.sin(t * 7 * p.flicker + p.phase);
      const a = clamp(lc.alpha * fade * born * flick * boost.brightness, 0, 1);
      if (a <= 0.01) continue;
      const x = p.x + Math.sin(t * p.wf * Math.PI * 2 + p.phase) * cfg.wobble.amp * (0.4 + progress);
      const y = p.y;
      ctx.globalAlpha = a;
      if (cfg.glow > 0 && p.kind !== 'pixel') {
        const s = sprites[p.color], d = p.size * 5;
        ctx.drawImage(s, x - d / 2, y - d / 2, d, d);
      }
      ctx.fillStyle = p.color;
      if (p.kind === 'square') ctx.fillRect(x - p.size / 2, y - p.size / 2, p.size, p.size);
      else if (p.kind === 'pixel') ctx.fillRect(x, y, Math.max(1, p.size * 0.4), Math.max(1, p.size * 0.4));
      else if (p.kind === 'line') ctx.fillRect(x, y - p.len, Math.max(1, p.size * 0.25), p.len);
      else {
        ctx.font = `${Math.max(7, p.size * 2.2)}px ui-monospace, Menlo, Consolas, monospace`;
        ctx.textBaseline = 'middle';
        ctx.fillText(p.glyph, x, y);
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }
}

/**
 * @param {object} opts
 * @param {HTMLElement} opts.container  重ねる親要素（position が static なら relative にする）
 * @param {HTMLElement} [opts.before]   アバター要素。背面キャンバスをこの前、前面をこの後ろに差し込む
 * @param {object} [opts.config]        digital-rise.config.js の上書き
 * @param {boolean} [opts.autoLoop=true] 自前の requestAnimationFrame で回す。false なら tick(now) を呼ぶ
 */
export function createDigitalRise(opts) {
  const cfg = mergeConfig(DEFAULTS, opts.config);
  const container = opts.container;
  if (getComputedStyle(container).position === 'static') container.style.position = 'relative';

  const mk = name => {
    const c = document.createElement('canvas');
    c.className = `digital-rise digital-rise-${name}`;
    c.dataset.fxLayer = name;
    Object.assign(c.style, { position: 'absolute', inset: '0', width: '100%', height: '100%', pointerEvents: 'none', display: cfg.enabled ? 'block' : 'none' });
    return c;
  };
  const backCanvas = mk('back'), frontCanvas = mk('front');
  if (opts.before && opts.before.parentElement === container) {
    container.insertBefore(backCanvas, opts.before);
    opts.before.insertAdjacentElement('afterend', frontCanvas);
    if (getComputedStyle(opts.before).position === 'static') opts.before.style.position = 'relative';
  } else {
    container.prepend(backCanvas); container.append(frontCanvas);
  }

  const dpr = Math.min(cfg.maxDpr, window.devicePixelRatio || 1);
  const [gr, gg, gb] = hexToRgb(cfg.colors[0]);
  const shared = { sprites: makeSprites(cfg.colors, cfg.glow, dpr), groundColor: `rgba(${gr},${gg},${gb},1)` };
  const back = new Layer(backCanvas, cfg, cfg.back, shared); back.isBack = true;
  const front = new Layer(frontCanvas, cfg, cfg.front, shared);

  let density = cfg.density, enabled = cfg.enabled;
  let speaking = false, level = 0, boostRate = 1, boostBright = 1;
  const stats = { fps: 0, frameMs: 0, density, particles: 0 };
  let frames = 0, accMs = 0, lastQualityCheck = 0;

  const resize = () => {
    const r = container.getBoundingClientRect();
    back.resize(r.width, r.height, dpr); front.resize(r.width, r.height, dpr);
    back.prewarm(density); front.prewarm(density);
  };
  resize();
  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
  ro?.observe(container);

  let prev = performance.now(), t = 0, prevFrameTs = 0;
  function tick(now = performance.now()) {
    const dt = clamp((now - prev) / 1000, 0.001, 0.05); prev = now;
    if (!enabled) return;
    t += dt;
    const start = performance.now();

    // 発話ブースト：attack で立ち上がり、release でゆっくり戻る
    const want = speaking ? 1 : 0;
    const tau = want > boostRate - 1 ? cfg.speaking.attack : cfg.speaking.release;
    const k = 1 - Math.exp(-dt / Math.max(0.01, tau));
    const strength = want * (0.6 + 0.4 * clamp(level, 0, 1));
    const targetRate = 1 + (cfg.speaking.rate - 1) * strength;
    const targetBright = 1 + (cfg.speaking.brightness - 1) * strength;
    boostRate += (targetRate - boostRate) * k;
    boostBright += (targetBright - boostBright) * k;
    const boost = { rate: boostRate, brightness: boostBright };

    back.step(dt, density, boost); front.step(dt, density, boost);
    back.draw(t, boost); front.draw(t, boost);

    // 自動品質：粒子描画にかかった時間と実フレーム間隔の両方を見る
    const ms = performance.now() - start;
    frames++; accMs += Math.max(ms, (now - (prevFrameTs || now)));
    prevFrameTs = now;
    stats.frameMs = ms; stats.particles = back.particles.length + front.particles.length;
    if (cfg.autoQuality.enabled && now - lastQualityCheck > 1000 && frames >= 20) {
      const avg = accMs / frames;
      stats.fps = 1000 / Math.max(1e-3, avg);
      if (avg > cfg.autoQuality.targetMs * 1.15 && density > cfg.autoQuality.minDensity) density = Math.max(cfg.autoQuality.minDensity, density * cfg.autoQuality.step);
      else if (avg < cfg.autoQuality.targetMs * 0.75 && density < cfg.density) density = Math.min(cfg.density, density / cfg.autoQuality.step);
      stats.density = density;
      frames = 0; accMs = 0; lastQualityCheck = now;
    }
  }
  let raf = 0;
  const loop = now => { tick(now); raf = requestAnimationFrame(loop); };
  if (opts.autoLoop !== false) raf = requestAnimationFrame(loop);

  return {
    tick,
    /** 口パク中 true。粒子量と明るさが少し上がる */
    setSpeaking(on) { speaking = !!on; },
    /** 0..1 の声の大きさ（口の開き）。speaking 中のブースト量に効く */
    setLevel(v) { level = clamp(Number(v) || 0, 0, 1); },
    setEnabled(on) {
      enabled = !!on;
      backCanvas.style.display = frontCanvas.style.display = enabled ? 'block' : 'none';
      if (!enabled) { back.particles.length = 0; front.particles.length = 0; back.ctx.clearRect(0, 0, back.w, back.h); front.ctx.clearRect(0, 0, front.w, front.h); stats.particles = 0; }
      else { back.prewarm(density); front.prewarm(density); }
    },
    setDensity(v) { density = clamp(Number(v) || 0, 0, 2); cfg.density = density; },
    getStats() { return { ...stats, enabled, speaking, boostRate: +boostRate.toFixed(2) }; },
    config: cfg,
    canvases: { back: backCanvas, front: frontCanvas },
    destroy() {
      cancelAnimationFrame(raf); ro?.disconnect();
      backCanvas.remove(); frontCanvas.remove();
    },
  };
}
