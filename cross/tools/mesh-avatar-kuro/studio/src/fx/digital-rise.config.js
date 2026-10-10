// デジタル粒子エフェクトの設定（ここだけ触れば見た目が変わる）
// 色はキャラクターシート（青いホログラムスーツ）に合わせた初期値。好みで差し替える。
export default {
  enabled: true,

  // 粒子の総量（1 = 標準）。重い端末では自動で下がる（autoQuality 参照）
  density: 1,

  // 背面レイヤー（アバターの後ろ）：多め・小さめ・暗め
  back: {
    count: 260,          // 粒子数（density 1 のとき）
    size: [1.5, 5],      // 1粒の大きさ px（最小, 最大）
    alpha: 0.6,          // 基本の不透明度
    speed: [28, 72],     // 上昇速度 px/s（最小, 最大）
  },
  // 前面レイヤー（アバターの前）：少なめ・大きめ・明るめ → 奥行き
  front: {
    count: 60,
    size: [2.5, 7],
    alpha: 0.8,
    speed: [40, 95],
  },

  // 粒子の種類の混ぜ方（合計 1 でなくてよい。比率で使う）
  kinds: {
    square: 0.50,        // 光る小さな四角
    pixel: 0.25,         // 1〜2px のドット
    glyph: 0.15,         // 0 / 1 の文字
    line: 0.10,          // 細いデータの縦線
  },

  // 色（キャラクターシートの配色に合わせる）。ランダムに選ばれる
  colors: ['#8fe9ff', '#3fb0ff', '#cdf6ff', '#ffffff', '#6cd0ff'],
  glow: 1.0,             // にじみの強さ 0〜1（0 でシャープ）

  // 発生位置：画面の下端。中心からの広がり（画面幅に対する割合）。
  // edgeBias はキャラの左右の縁あたりに寄せる割合（0 で一様、1 で全部縁寄り）→ 体の裏に隠れにくくなる
  spawn: { xCenter: 0.5, xSpread: 0.66, jitterY: 20, edgeBias: 0.55 },

  // 足元の淡い光の帯（粒子の発生源に見せる）。height は画面高さに対する割合
  ground: { height: 0.16, alpha: 0.22 },

  // 上に行くほど薄く消える。fadeStart から消え始め、fadeEnd で完全に消える（0=下端, 1=上端）
  fade: { start: 0.08, end: 0.78, power: 1.4 },

  // 横揺れ
  wobble: { amp: 6, freq: 0.6 },

  // 発話中（口パク中）の変化：粒子量・明るさを少し上げる
  speaking: { rate: 1.45, brightness: 1.3, attack: 0.25, release: 0.8 },  // attack/release は秒

  // 60fps を保てないときの自動調整
  autoQuality: { enabled: true, targetMs: 16.7, minDensity: 0.3, step: 0.85 },

  // 描画解像度の上限（DPR）。2 以上はコストが跳ねるので 1.5 に抑える
  maxDpr: 1.5,
};
