# mesh-avatar-kuro — クロを Mesh Avatar Studio で動かすための追加キット

[shinshin86/mesh-avatar-studio](https://github.com/shinshin86/mesh-avatar-studio) に **本体を改変せず** 足すもの一式。

```
mesh-avatar-kuro/
  desktop_task.md        デスクトップの Claude（Cowork / Claude Code）に貼る作業指示（立ち絵 → アバター化 → 仕上げ）
  rig-tuning.md          VTuber 的な滑らかさにするための値（rig.json 側／配信ページ側）と記録テンプレ
  variant-prompts.md     目閉じ・母音口の差分絵を ChatGPT で作るプロンプトと取り込み手順
  install.mjs            下の studio/ を clone に入れるスクリプト
  studio/
    stream-fx.html       クロ用の配信ページ（stream.html ＋ 粒子エフェクト ＋ 落ち着いた待機動作）
    src/fx/main.ts       ページのスクリプト。本体の公開 API だけ使う
    src/fx/digital-rise.js         粒子エフェクト本体（Canvas2D、独立レイヤー、移植用）
    src/fx/digital-rise.config.js  粒子の設定ファイル（量・速度・色・明るさ・ON/OFF…）
    src/fx/digital-rise.d.ts       型定義
    tools/merge-variant.py         ChatGPT の差分絵を「マスクの内側だけ」source.png に合成
  demo/index.html        エフェクト単体のデモ（アバター無しで動く。別アプリへ移植する時の見本）
```

## 入れ方

```powershell
cd G:\ClaudeLocal\mesh-avatar-studio        # clone 済み・npm install 済み
node G:\ClaudeLocal\cross\tools\mesh-avatar-kuro\install.mjs .
npm run dev
```

ブラウザで `http://127.0.0.1:5173/stream-fx.html?project=kuro` を開く（`project=` はプロジェクト名）。
OBS に入れる時はこの URL をブラウザソースにする。背景は `bg=transparent`（既定）か `bg=green`。

### URL パラメータ

`stream.html` のもの（`bg` `fit` `idle` `light` …）に加えて：

| パラメータ | 既定 | 意味 |
|---|---|---|
| `fx` | 1 | `0` で粒子を出さない |
| `fxDensity` | 設定ファイルの `density` | 粒子の量 0〜2 |
| `calm` | 0.65 | 待機中の首振り・体の揺れ・呼吸の振幅倍率（1 で本体のまま） |
| `sway` | 1.3 | 髪の揺れゲイン。大きいほど柔らかく遅れて追従 |
| `talk` | 0.6 | 発話中に声で首が動く量 |
| `motions` | 1 | `0` で大きめのランダム反応を止める |

コンソールで `kuroFx.getStats()` を打つと fps・粒子数・自動調整後の density が見える。

## 粒子エフェクト（digital-rise）

- 画面下端からクロの周囲を上に向かって立ち上るデジタル粒子。光る四角・ドット・0/1・細いデータ線。上に行くほど薄く消える
- **背面**（多め・小さめ）と **前面**（少なめ・大きめ）の 2 枚で奥行き。アバターのキャンバスには触らない
- 口パク中は粒子量 ×1.45・明るさ ×1.3 に滑らかに上がり、終わるとゆっくり戻る（`speaking` 設定）
- 60fps を保てない時は粒子量を自動で下げる（`autoQuality`）。負荷は 1080px 四方で 1ms/フレーム未満
- 調整は **`src/fx/digital-rise.config.js` だけ**。色はキャラクターシートの青系が初期値

### 別アプリ（G:\ClaudeLocal\kaname など）へ移植

`digital-rise.js` と `digital-rise.config.js` の 2 ファイルをコピーして、アバター要素を挟む形で呼ぶだけ。

```html
<div id="stage" style="position:relative"><canvas id="avatar"></canvas></div>
<script type="module">
  import { createDigitalRise } from './digital-rise.js';
  const fx = createDigitalRise({ container: document.getElementById('stage'), before: document.getElementById('avatar') });
  // 口パク中に：fx.setSpeaking(true); fx.setLevel(0〜1);   止めたら fx.setSpeaking(false)
  // 自分の描画ループから回すなら createDigitalRise({ ..., autoLoop: false }) にして毎フレーム fx.tick(now)
</script>
```

アバター要素は `z-index: 1`、`.digital-rise-back` を 0、`.digital-rise-front` を 2 にしておく（`stream-fx.html` の `<style>` と同じ）。
`demo/index.html` をローカルサーバーで開くと単体で動きを確認できる。

## 作業の流れ（ざっくり）

1. `desktop_task.md` をデスクトップの Claude に貼る → clone、立ち絵の事前チェック、`docs/agent-guide.md` どおりにアバター化（`projects/kuro/`）
2. エディタで「ポーズ確認」「口の動き」→ 破綻を直す（`rig-tuning.md` の A）
3. `variant-prompts.md` で差分絵を ChatGPT に作らせ、`merge-variant.py` → `build-sprites.py` で取り込む
4. `install.mjs` でこのキットを入れ、`stream-fx.html?project=kuro` で粒子付きの配信ビューを確認（`rig-tuning.md` の B）
