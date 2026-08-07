---
name: haichi-tool
description: |
  木造ハイツ（低層集合住宅）の配置検討ツール・1フロア平面図を生成するスキル。
  シングルファイルHTML（サーバーレス）で、DXF敷地データを固定値として組み込み、
  法規チェック・建物配置スライダー・1フロア平面図（階段室・廊下・住戸・バルコニー・エントランス）をリアルタイム描画する。

  トリガー：「配置検討ツール」「平面図を作って」「ハイツの配置」「haichi_tool」「haichi-tool」
  「1フロア平面図」「木造ハイツ 平面」「フロアプラン」と言われたら必ずこのスキルを使うこと。
  敷地DXFデータが提供された場合も即座にこのスキルを参照すること。
---

# 配置検討ツール・木造ハイツ平面図ジェネレータースキル

## 概要

敷地（DXF固定値）に対して、木造3階建てハイツの配置検討と1フロア平面図をSVGで生成するHTML単体ツール。
法規チェック（建蔽率・容積率）、セットバック確認、リアルタイムスライダー操作に対応。

---

## 確定した設計仕様（ベースモデル）

### 敷地（DXF固定値）
- 間口：**19,000mm**、奥行：**16,000mm**、面積：**304.00㎡**（矩形）

### 建物構成（1フロア）

#### 間口方向（西→東）
```
[階段室 1,400mm] [廊下 1,400mm] [住戸×4 各3,600mm]
建物全幅 = 1,400 + 1,400 + 3,600×4 = 17,200mm
```

#### 奥行方向（北→南・南道路の場合）
```
[廊下帯 X1〜X2 : 1,400mm]  ← 隣地側（北）
[専有部 X2〜X3 : 7,200mm]
[バルコニー X3〜X4 : 1,200mm]  ← 道路側（南）
```

#### 階段室（Y1〜Y2 × 奥行方向）
```
[上踊り場 X1〜X2 : 1,400mm]  ← 廊下帯と共用
[走行 X2〜Xd : 16段×250mm = 4,000mm]  ← 直線階段
[下踊り場 Xd〜Xb : 1,400mm]
突出合計: 1,400 + 4,000 + 1,400 = 6,800mm < 専有部7,200mm ✓
```

#### 廊下（Y2〜Y3）のXb側延長
- X2〜Xb部分（走行+下踊り場）も廊下色で塗る（廊下扱い）

#### エントランス（Y1〜Y3 × Xb〜X3）
```
幅: 1,400 + 1,400 = 2,800mm（階段室＋廊下幅）
奥行: 7,200 - 5,400 = 1,800mm（専有部奥行 - 階段室突出）
位置: 下踊り場南端(Xb)〜専有部南端(X3)
```

#### バルコニー
- **Y3〜（住戸4戸分のみ）**：Y1〜Y3（階段室・廊下部分）にはバルコニーなし

---

## 建物配置ルール

### 隣地後退（東西方向）
```javascript
const actualW = ST_W_MM + P.hallW + bldgW; // 階段室+廊下+住戸の実際の全幅
const sideMargin = Math.max(P.sideSetback, Math.round((SITE.W - actualW) / 2));
const bX = sideMargin; // 600mm確保 + 余りは左右均等
```
- デフォルト: 隣地後退600mm、余り900mm（両側均等）

### 廊下側後退（南北方向）
```javascript
// 南道路 → 廊下=北側 → bY = sideSetback（600mm）から配置
bY = (hallSide==='north') ? P.sideSetback : 0;
```

---

## コード構成（JSの主要変数）

```javascript
// 敷地固定値
const SITE = {W:19000, D:16000};  // mm

// 階段室定数（固定）
const ST = {
  roomW: 1400,   // 階段室幅（間口方向）
  run:   4000,   // 走行長（16段×250mm）
  land:  1400,   // 踊り場奥行
  steps: 16,
  tread: 250,
};

// 可変パラメータ（デフォルト値）
let P = {
  roadW: 6, roadSide: 'south',
  youto: '60_200', boka: 'none', kakuchi: 'no',
  unitW: 3600, unitD: 7200, balcD: 1200, hallW: 1400, sideSetback: 600,
  bldgPos: 'N', floors: 3,
};
```

---

## 描画関数の構成

### `drawHaichi(C)` - 配置図
- グリッド（1m）・道路・敷地・セットバック線
- 建物フットプリント：階段室（段線付き）・廊下・住戸・バルコニー・エントランス
- 敷地外枠（破線）・寸法線・余裕距離表示・方位記号・スケールバー

### `drawFloor(C)` - 1フロア平面図
- スケール: `Math.min(dW/totalW, dH2/totalD) * 0.82`
- 描画順（上塗り対策）:
  1. グリッド
  2. バルコニー（Y3〜のみ）
  3. 専有部（玄関マーク付き）
  4. 共用廊下（廊下帯 + Y2側X2〜Xb延長）
  5. 階段室（背景→上踊り場→走行段線→下踊り場）
  6. **エントランス（最後に描画して上塗りされないよう注意）**
  7. 通り芯・寸法線・方向ラベル

---

## 法規チェック

```javascript
const YOUTO = {
  '60_200': {bc:0.60, far:2.00},  // 第1住居（デフォルト）
  '60_300': {bc:0.60, far:3.00},
  '40_200': {bc:0.40, far:2.00},
  '60_400': {bc:0.60, far:4.00},
  '80_400': {bc:0.80, far:4.00},
};
// 道路容積率制限
const roadFAR = P.roadW < 12 ? P.roadW * 0.4 : yt.far;
const effFAR  = Math.min(yt.far, roadFAR);
```

---

## スタイル仕様（元ツールと統一）

```css
body { font-family: 'Hiragino Sans','Yu Gothic',sans-serif; background: #f5f4f0; }
.wrap { display: grid; grid-template-columns: 1fr 280px; }
/* タブ: .tab / .tab.on */
/* 右パネル: .sec / .row / .rk / .rv / .srow / .slbl / .sval */
/* バッジ: .fix（#BA7517/FAEEDA）/ .var（#185FA5/E6F1FB）*/
/* ゲージ: .gauge-wrap / .gauge-fill.ok|warn|ng */
```

### 色定義
| 要素 | fill | stroke |
|------|------|--------|
| 専有部（住戸） | `#E1F5EE` | `#1D9E75` |
| 共用廊下 | `#B5D4F4` | `#378ADD` |
| 上下踊り場 | `#D4EAF7` | `#185FA5` |
| 階段走行 | `#EBF4FB` | `#378ADD` |
| バルコニー | `#FAEEDA` | `#BA7517` |
| エントランス | `#E6F1FB` | `#185FA5` |
| 道路 | `#EFF6FF` | `#93C5FD` |

---

## 重要な実装上の注意点

### 1. 描画順（エントランスは最後）
エントランスを先に描くと廊下・階段室に上塗りされて消える。
必ず他の要素をすべて描いた後にエントランスを描くこと。

### 2. `curTab`の宣言
```javascript
let curTab = 'haichi'; // ← 必ず宣言。ないとタブ切替が動かない
```

### 3. 実際の建物全幅
```javascript
// NG: bldgW（住戸分のみ）をbXの基準にしてはいけない
// OK: actualW（階段室+廊下+住戸）を使う
const actualW = ST_W_MM + P.hallW + bldgW;
```

### 4. タブ切替
```javascript
function show(t){
  curTab = t;
  document.querySelectorAll('.tab').forEach(el=>el.classList.toggle('on', el.dataset.tab===t));
  render();
}
function render(){
  const C = calc();
  document.getElementById('sv').innerHTML = (curTab==='floor') ? drawFloor(C) : drawHaichi(C);
  updatePanel(C);
}
```

### 5. 黒枠線は使わない
外壁の黒枠線（`stroke="#3d3d3a"`）は不要。各ゾーンの色と線で十分。

### 6. SVGビューボックス
```html
<svg id="sv" width="100%" viewBox="0 0 600 460" preserveAspectRatio="xMidYMid meet">
```

---

## 出力ファイル
- `haichi_tool_v3.html`（最新版）
- シングルファイルHTML・サーバーレス・ブラウザで即開ける
