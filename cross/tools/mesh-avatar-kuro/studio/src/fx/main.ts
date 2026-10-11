// クロ用の配信ビュー：stream.html と同じ動き ＋ 足元から立ち上るデジタル粒子 ＋ 落ち着いた待機動作
//
//   http://127.0.0.1:5173/stream-fx.html?project=kuro
//
// 追加の URL パラメータ（stream.html のものはそのまま使える：bg / fit / idle / light…）
//   fx=0          粒子を出さない
//   fxDensity=0.6 粒子の量（0〜2）
//   calm=0.65     待機中の首振り・体の揺れ・呼吸の振幅倍率（1 で元のまま。0.6〜0.75 が VTuber 的に落ち着く）
//   sway=1.3      髪の揺れゲイン（1 が標準。大きいほど柔らかく遅れて追従）
//   talk=0.6      発話中に声に合わせて首が動く量（1 が標準）
//   motions=0     大きめのランダム反応（うなずき・首かしげ等）を止める。小さな待機モーションは残る
//
// ツール本体の engine / rig 処理には触っていない。公開 API（setParameters の重み・setSwayGain・setTalkGain）だけで調整する。
import { createAvatarView, neutralParameters } from '../live/avatar-view';
import { viewSettings } from '../live/settings';
import { LivePose } from '../live/protocol';
import { receiveLighting, receiveLiveParameters } from '../live/relay';
import { createDigitalRise } from './digital-rise.js';
import fxConfig from './digital-rise.config.js';
import '../live/stream.css';

const query = new URLSearchParams(location.search);
const num = (key: string, def: number, min: number, max: number) => {
  const v = Number(query.get(key)); return query.has(key) && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : def;
};
const settings = viewSettings(location.search);
const tune = {
  fx: query.get('fx') !== '0',
  fxDensity: num('fxDensity', fxConfig.density, 0, 2),
  calm: num('calm', 0.65, 0, 1),
  sway: num('sway', 1.3, 0.3, 3),
  talk: num('talk', 0.6, 0, 2),
  motions: query.get('motions') !== '0',
};
// 待機中に振幅を抑えるパラメータ。0 に向かって (1 - calm) だけ引き寄せる → 振幅 = 元 × calm
const CALM_KEYS = ['angleX', 'angleY', 'angleZ', 'bodyAngleX', 'bodyAngleZ', 'armAngle', 'handAngle', 'breath'];
const calmTargets = Object.fromEntries(CALM_KEYS.map(key => [key, 0]));

document.documentElement.style.background = settings.background;
const stage = document.querySelector<HTMLElement>('#stage')!;
const canvas = document.querySelector<HTMLCanvasElement>('#avatar')!;
const fx = createDigitalRise({ container: stage, before: canvas, autoLoop: false, config: { enabled: tune.fx, density: tune.fxDensity } });
(window as unknown as { kuroFx: typeof fx }).kuroFx = fx;   // コンソールから kuroFx.getStats() で確認できる

const pose = new LivePose(settings.project);
let avatarInstance: import('../engine').MeshAvatar | undefined;
const unsubscribeLighting = receiveLighting(settings.project, value => { settings.lighting = value; avatarInstance?.setLighting(value); });
const unsubscribe = receiveLiveParameters(data => pose.receive(data, performance.now()));

void createAvatarView(canvas, settings, (avatar, now, dt) => {
  const sampled = pose.sample(now, dt);
  canvas.dataset.live = sampled.active ? 'active' : 'idle';
  avatar.setAutoIdle(settings.idle && !sampled.active);
  avatar.setAutoMotion(settings.idle && !sampled.active && tune.motions);
  if (settings.idle) {
    if (sampled.active) avatar.setParameters(sampled.params, sampled.weight);
    else avatar.setParameters(calmTargets, 1 - tune.calm);
  } else {
    const params = { ...neutralParameters };
    for (const [key, value] of Object.entries(sampled.params)) params[key] = (params[key] ?? 0) * (1 - sampled.weight) + value * sampled.weight;
    avatar.setParameters(params);
  }
}, (avatar, now) => {
  // 口の開きを粒子へ：口パク（kana / マイク / Live の値）のどれでも拾える
  const lip = avatar.getLipSyncState();
  const mouth = Math.max(lip.open, avatar.getParameters().mouthOpen ?? 0);
  fx.setSpeaking(lip.active || mouth > 0.08);
  fx.setLevel(mouth);
  fx.tick(now);
}).then(view => {
  avatarInstance = view.avatar;
  view.avatar.setSwayGain(tune.sway);
  view.avatar.setTalkGain(tune.talk);
  if (settings.lighting) view.avatar.setLighting(settings.lighting);
  const destroy = () => { unsubscribe(); unsubscribeLighting(); avatarInstance = undefined; fx.destroy(); view.destroy(); };
  window.addEventListener('pagehide', destroy, { once: true });
  import.meta.hot?.dispose(destroy);
}).catch(() => { unsubscribe(); unsubscribeLighting(); canvas.dataset.state = 'error'; });
