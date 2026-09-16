---
name: event-lp
description: >
  イベント告知ページ（ランディングページ / LP）のHTMLファイルを生成するスキル。
  ユーザーがイベント概要・テーマ・ターゲット・開催情報などを提示したとき、必ずこのスキルを使用すること。
  「LPを作って」「イベントページを作りたい」「告知ページの構成を考えて」「ハンズオンのLPを書いて」
  「勉強会の案内ページを作りたい」といったキーワードがあれば迷わずこのスキルを使う。
  出力は単一HTMLファイルで、そのままブラウザで開けるかconnpassなどに転用できる形式にする。
---

# Event LP Skill

イベント概要テキストをもとに、参加者が「これは自分のためのイベントだ！」と感じる
魅力的なランディングページ（単一HTMLファイル）を生成するスキル。

---

## インプットの収集

ユーザーから以下を確認する（会話中にすでにある情報はそのまま使い、不足分だけ質問する）:

| 項目 | 例 |
|---|---|
| イベントテーマ / タイトル | 「AIエージェント育成ハンズオン」 |
| 開催日時 | 2026年3月22日 15:00–17:00 |
| 会場 | 大阪（詳細は参加者へ） |
| ターゲット像 | AIを日常的に使っているが効率が頭打ちの中級者 |
| コア体験 | その場でSkillsを実装・調整して持ち帰る |
| 盛り込む要素 | 共感リード文、ベネフィット、タイムテーブル、持ち物、クロージング |
| トーン | 煽らず、実利重視、親しみやすく知的 |
| 申込URL | connpassなど（未定なら `#register` プレースホルダ） |

---

## デザイン方針（必ず守ること）

### 0. 実在サイトの参照（HTML実装前に必ず実行）
Inspo MCP で同ジャンルの実在LPを3〜5件取得し、配色・フォント・版面構成の根拠にする。
手順：`search_screens` → 候補から `get_design_system` で配色・タイポを抽出
（似た1枚を起点にするなら `find_similar`、構成比較は `compare`、実装は `get_reference_jsx` を参考にできる）。
**下記のカラー・タイポ既定値は初期値であり、参照結果に基づく上書きを許可する。**
取得できない場合はそのまま続行し、成果物に「Inspo未参照」と明記する。

### カラー & テーマ
- **ベース**: ダークテーマ（`#0d0e0f` 系）
- **アクセント1**: 黄緑（`#c8f542`）— 強調・CTA・ハイライト
- **アクセント2**: 青緑（`#42f5c8`）— サブ強調・ゴール文
- **ミュート**: `#5a6270` 系でラベル・補助テキスト

### タイポグラフィ（Google Fonts使用）
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;600;900
  &family=Noto+Sans+JP:wght@300;400;500
  &family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```
- 見出し: `Noto Serif JP`（weight 900）
- 本文: `Noto Sans JP`（weight 300/400）
- ラベル・バッジ・時刻: `DM Mono`

### レイアウト & 演出
- グリッド背景（細線 48px ピッチ）をヒーロー背景に
- ノイズテクスチャを `body::before` でオーバーレイ（opacity 0.4）
- 放射グラデーション（Glow）を右上・左下に配置
- スクロール時に `IntersectionObserver` で `.reveal` クラスを付与しフェードイン

### 禁止事項
- 白背景＋紫グラデーションのような「AI量産LPスタイル」は使わない
- Inter / Roboto / Arial などの汎用フォントは使わない
- `<form>` タグは使わない（ボタンは `<a>` または `<button>` で）

---

## ページ構成（セクション順）

### 1. HERO
```
[グリッド背景 + Glow]
  OSAKA HANDS-ON 2026  ← event-badge（mono、黄緑、点滅●付き）
  副題ラベル（eyebrow、mono、muted）
  メインタイトル h1（serif 900、キーワードを黄緑/青緑で色分け）
  サブコピー（sans、text-dim）
  メタカード群（日付 / 時刻 / 会場 / フォーマット）← surface背景、border囲み
  CTAボタン → #register
```

### 2. PAIN（共感リード）
```
section-label: // あなたの「しんどい」に名前をつける
h2: こんなモヤモヤ、ありませんか？
pain-quote × N件（border-left 3px、hover で黄緑に変化）
説明文（問題の構造を言語化 → Skillsが解決策と示す）
```

### 3. FOR WHO（対象者）
```
section-label: // こんな方におすすめ
h2: あなたのための90分です。
カード × 4（01〜04の連番、hover で border-top 青緑）
```

### 4. BENEFITS（参加メリット）
```
section-label: // 90分後のあなたへ
h2: 参加後に手に入るもの。
2×2 グリッドカード（絵文字アイコン + タイトル + 説明）
  - 2枚目（または1枚）に accent-card スタイル（黄緑の薄い背景）
state-box: 「90分後のゴール状態」を短い宣言文で（青緑枠）
```

### 5. TIMETABLE（タイムテーブル）
```
section-label: // タイムテーブル
h2: 120分の流れ。
tt-row 構成: [時刻列 120px | コンテンツ列]
ハンズオン行に border-left: 3px solid var(--accent) でハイライト
```

タイムテーブルのひな型（120分構成 = 開場30分 + 本編90分）:

| 時刻 | ブロック | 内容 |
|---|---|---|
| 開始-30min | 開場・受付・環境確認 | PC開いて環境セットアップ、スタッフサポート |
| 開始 | オープニング（15分） | ゴール共有、全体像の説明 |
| +15min | ハンズオン Part 1（25分）★ | サンプルSkillを動かして構造を理解 |
| +40min | ハンズオン Part 2（30分）★ | 自業務向けにカスタマイズ・スタッフ巡回 |
| +70min | 成果共有 + ミニLT（15分） | 各自1〜2分で紹介・気づきの共有 |
| +85min | クロージング（10分） | 今後の育て方・持ち帰りリソース共有 |
| +95min | 懇親・フリーセッション（〜終了） | 個別相談・参加者交流 |

★ = `tt-row highlight` クラスを付ける

### 6. PREP（持ち物・事前準備）
```
section-label: // 事前準備・持ち物
h2: 当日スムーズに始めるために。
prep-grid × 3列（必須 / 推奨 / あると良い）
各カラムに prep-list（→ 矢印アイコン付きリスト）
state-box: 「初心者でもスタッフがサポートします」の安心メッセージ
```

持ち物リストのひな型:

**必須**
- ノートPC（Mac / Windows どちらも可）
- 充電器
- Claude.ai アカウント（無料プランでも参加可）
- インターネット接続（会場Wi-Fiあり）

**推奨**
- VS Code または Cursor インストール済み
- Node.js（LTS版）インストール済み
- GitHub アカウント
- Claude Pro または API キー（より深く試したい方向け）

**あると良い**
- 自分の「定型業務」のメモ・サンプルデータ
- 「これを自動化できたら」というタスクの具体例
- 普段使っているプロンプトのメモ

### 7. CLOSING（クロージング）
```
id="register"
背景: 黄緑+青緑の薄いグラデーション
section-label: // 一緒にAIを育てる仲間へ
h2（serif 900）: キャッチコピー（"育てる"を黄緑で強調）
body: 「完成した答えを教える場ではなく、一緒に手を動かす仲間が集まる場所」
CTAボタン（申込URL or #）
closing-note: 定員・料金などの補足
```

---

## CSS設計のポイント

```css
:root {
  --bg: #0d0e0f;
  --surface: #141618;
  --surface2: #1c1f22;
  --border: #2a2e33;
  --accent: #c8f542;
  --accent2: #42f5c8;
  --muted: #5a6270;
  --text: #e8eaed;
  --text-dim: #9aa3b0;
  --serif: 'Noto Serif JP', Georgia, serif;
  --sans: 'Noto Sans JP', sans-serif;
  --mono: 'DM Mono', monospace;
}
```

### スクロールリビール
```js
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
```

### ノイズテクスチャ
```css
body::before {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,…feTurbulence…");
  pointer-events: none;
  z-index: 1000;
  opacity: 0.4;
}
```

---

## 出力ルール

1. **単一HTMLファイル** として出力する（CSS・JSはすべてインライン）
2. ファイル名: `event-lp.html`（または `イベント名-lp.html`）
3. `/mnt/user-data/outputs/` に保存し `present_files` で提示する
4. レスポンシブ対応: モバイルではグリッドを1列に折り返す
5. 申込URLが未確定の場合は `href="#register"` または `href="#"` をプレースホルダとして使用し、コメントで置換箇所を明示する
6. 生成後にセクション構成を箇条書きで簡潔に説明する

---

## カスタマイズポイント（ユーザーへの案内）

生成後、以下の変更点をユーザーに伝えること:

- 申込URL → `href="#"` をconnpassなどの実URLに置換
- 会場住所 → 「大阪（詳細は参加者へ）」を正式住所に更新
- タイムテーブル → 実際のアジェンダに合わせて行を追加/削除
- ファビコン・OGP → 必要に応じて `<head>` 内に追加
