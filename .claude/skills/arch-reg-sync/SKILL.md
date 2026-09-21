---
name: arch-reg-sync
description: |
  指定した自治体の建築法規・都市計画関連情報をウェブ検索で収集し、NotebookLM（ノーエル）の「ソースを追加（テキスト）」に直接ペースト可能なMarkdown形式で出力し、さらにIPAゴシックフォントを使ったA4縦レイアウトの日本語PDFとして書き出すスキル。

  トリガーキーワード：「#行政調査同期［自治体名］」が最優先トリガー。このフォーマットを見たら即座にこのスキルを起動すること。その他「建築法規を調査して」「都市計画を調べて」「[自治体名]の法規をまとめて」「建築条例を調査して」「ノーエルに貼り付けたい」「PDFにして」「PDF化して」でも起動する。

  PDFの直接ダウンロードができない環境でも、ウェブ検索・ページ取得で内容を解析し、設計実務に必要な情報を網羅的に収集する。容積率・建蔽率・木三共・駐車場条例・共同住宅指導指針など建築実務で頻出のテーマを必ず押さえること。調査対象が市区町村の場合や「PDFにして」と言われた場合は必ずこのスキルを使うこと。
---

# Arch-Reg-Sync：建築法規・行政調査同期＋PDF生成スキル

## 概要

自治体の公式サイトから建築・都市計画関連情報を収集し、NotebookLMへ直接貼り付け可能な構造化Markdownを生成し、さらにIPAゴシックフォントを使ったA4縦のPDFとしても書き出す一気通貫ワークフロー。

**2フェーズ構成：**
1. **調査フェーズ（ステップ1〜5）**：ウェブ検索→Markdown生成
2. **PDF生成フェーズ（ステップ6）**：reportlabでPDF化→ダウンロードリンク提供

---

## ステップ1：調査計画の立案

ユーザーから `[自治体名]` を受け取ったら、以下の5テーマを必ず調査対象とする。

| # | テーマ | 主な検索キーワード例 |
|---|--------|----------------------|
| 1 | 用途地域・容積率・建蔽率（含む最新変更情報） | `[自治体名] 用途地域 容積率 建蔽率 変更` |
| 2 | 建築基準法施行条例・細則・取扱い | `[自治体名] 建築基準法施行条例` |
| 3 | 木造3階建て共同住宅（木三共）審査基準 | `[自治体名] 木三共 木造3階建て共同住宅 確認申請` |
| 4 | 駐車場・駐輪場 附置義務条例・要綱 | `[自治体名] 駐車場附置義務 駐輪場 共同住宅 条例` |
| 5 | 共同住宅指導指針（ふれあい安心居住条例・開発指導要綱等） | `[自治体名] 開発指導要綱 共同住宅 ふれあい安心居住` |

> **注意**：自治体によって条例名・要綱名が異なる。名称が見つからない場合は類似制度（例：「ふれあい安心居住条例」→「開発指導要綱」「共同住宅指導指針」）を探すこと。

---

## ステップ2：ウェブ検索の実行

1. `[自治体名] 建築基準法施行条例 都市計画 容積率 建蔽率 用途地域 2025 2026`
2. `[自治体名] 駐車場附置義務条例 駐輪場 共同住宅 site:city.[自治体名].lg.jp`
3. `[自治体名] 木造3階建て共同住宅 木三共 審査基準 建築確認`
4. `[自治体名] 開発指導要綱 共同住宅指導 ふれあい安心居住条例`
5. 上記で不足する情報があれば追加検索を実施

- 検索結果にある公式ページURLは `web_fetch` で本文を取得し、テーブル・数値・条文を詳細に読み込む
- 変更情報（「令和〇年〇月〇日より変更」等）は**必ず優先的に取得**する
- PDFリンクはURLを記録するが、ダウンロードはしない（URLのみ記載）

---

## ステップ3：情報の解析・整理

**① 用途地域・容積率・建蔽率**
- 各用途地域の容積率・建蔽率の一覧表
- 最新の変更情報（変更日・変更内容・対象エリア）
- 前面道路幅員による容積率低減係数
- 防火地域・準防火地域の指定状況・変更予定

**② 建築基準法施行条例・取扱い**
- 防火規制の特記事項
- 日影規制の条例上乗せ規定
- 大阪府施行条例との重畳適用（大阪府内の自治体の場合）

**③ 木三共（木造3階建て共同住宅）**
- 告示255号の4条件を市の防火地域状況に当てはめて解説
- 中間検査の特定工程（自治体独自の告示がある場合）

**④ 駐車場・駐輪場附置義務**
- 自動車・自転車の地域区分ごとの附置義務基準と閾値・台数表
- 共同住宅専用の附置義務（戸数・割合）
- 条例・要綱の名称とダウンロードURL

**⑤ 共同住宅指導指針（開発指導要綱等）**
- 適用対象（戸数・面積の閾値）
- 小世帯向共同住宅の最低床面積規制
- 住民への事前説明・協議義務

---

## ステップ4：Markdownの生成

以下の章構成で出力する：

```
# 【[自治体名]公式】建築法規・都市計画 調査レポート_[西暦]年版
1. 都市計画の基本情報（用途地域・容積率・建蔽率）
2. 建築基準法施行条例・細則
3. 木造3階建て共同住宅（木三共）の審査基準
4. 駐車場・駐輪場 附置義務条例
5. 共同住宅指導指針（開発指導要綱等）
6. 関連する府条例（大阪府内の場合）
7. 問い合わせ先まとめ（表）
8. 関連法令・条例リスト（表）
9. 設計実務上の重要ポイント（3〜5点）
```

---

## ステップ5：品質チェック

- [ ] 容積率・建蔽率の数値が具体的に記載されている
- [ ] **最新の変更情報**（施行予定を含む）が反映されている
- [ ] 木三共の4条件が当該自治体の防火地域状況に当てはめて解説されている
- [ ] 駐車場条例の台数基準が表形式で記載されている（共同住宅専用要綱含む）
- [ ] 各項目にURLが付いている（PDFは直リンクURL）
- [ ] 担当課の電話番号が記載されている
- [ ] ⚠️マークで設計上の注意点が強調されている

---

## ステップ6：PDF生成

Markdownの出力完了後、**必ず続けてPDFを生成**する。

### 6-1. フォント（必須）

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# 必ずIPAゴシックを使うこと。NotoSansCJKはCFF形式でreportlab非対応のため使用禁止。
pdfmetrics.registerFont(TTFont('IPA', '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'))
F = 'IPA'
```

### 6-2. カラー定数

```python
from reportlab.lib import colors
NAVY  = colors.HexColor('#1a3a5c')   # 見出し1背景（紺）
BLUE  = colors.HexColor('#2563eb')   # 見出し2・表ヘッダ（青）
LBLUE = colors.HexColor('#e8f0fe')   # ポイントカード背景
WARN  = colors.HexColor('#fff3cd')   # 警告ブロック背景
WARNB = colors.HexColor('#856404')   # 警告テキスト
TBLA  = colors.HexColor('#f0f4ff')   # 表の偶数行
GRAY  = colors.HexColor('#6b7280')   # 注釈・フッター
```

### 6-3. スタイル定義

```python
from reportlab.lib.styles import ParagraphStyle

def S(name, **kw):
    d = dict(fontName=F, fontSize=8.5, leading=14,
             textColor=colors.HexColor('#1f2937'))
    d.update(kw)
    return ParagraphStyle(name, **d)

ST = {
    'cover_t': S('ct', fontSize=18, leading=26, textColor=colors.white, alignment=1),
    'cover_s': S('cs', fontSize=10, leading=16, textColor=colors.HexColor('#bfdbfe'), alignment=1),
    'cover_m': S('cm', fontSize=8,  leading=13, textColor=colors.HexColor('#93c5fd'), alignment=1),
    'h1':      S('h1', fontSize=12, leading=18, textColor=colors.white),
    'h2':      S('h2', fontSize=10, leading=15, textColor=NAVY, spaceBefore=6, spaceAfter=2),
    'body':    S('bo', spaceAfter=3),
    'ind':     S('in', leftIndent=12, spaceAfter=2),
    'warn':    S('wa', textColor=WARNB, spaceAfter=2),
    'note':    S('no', fontSize=7.5, leading=12, textColor=GRAY, leftIndent=6),
    'th':      S('th', fontSize=7.5, leading=12, textColor=colors.white, alignment=1),
    'td':      S('td', fontSize=7.5, leading=12),
    'footer':  S('ft', fontSize=7.5, leading=12, textColor=GRAY, alignment=1),
    'pt_no':   S('pn', fontSize=10, leading=15, textColor=BLUE),
    'pt_body': S('pb', spaceAfter=2),
}
```

### 6-4. ページ設定

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

W = 170*mm  # 本文幅（A4 - 左右マージン各20mm）

doc = SimpleDocTemplate(
    path, pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm,
    topMargin=16*mm, bottomMargin=16*mm,
    title='[自治体名] 建築法規・都市計画 調査レポート [西暦]年版'
)
```

### 6-5. 共通ヘルパー関数

```python
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable

def h1(text, s):
    """紺帯の見出し1"""
    t = Table([[Paragraph(text, ST['h1'])]], colWidths=[W])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), NAVY),
        ('TOPPADDING',(0,0),(-1,-1), 6), ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',(0,0),(-1,-1), 10),
    ]))
    s += [Spacer(1,4), t, Spacer(1,5)]

def h2(text, s):
    """青横罫の見出し2"""
    s += [HRFlowable(width='100%', thickness=1.5, color=BLUE, spaceAfter=2),
          Paragraph(f'<font color="#2563eb">■</font>  {text}', ST['h2'])]

def warn(lines, s):
    """黄背景の警告ブロック"""
    rows = [[Paragraph('※ '+l, ST['warn'])] for l in lines]
    t = Table(rows, colWidths=[W-8])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), WARN),
        ('BOX',(0,0),(-1,-1), 0.8, colors.HexColor('#ffc107')),
        ('TOPPADDING',(0,0),(-1,-1), 4), ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ('LEFTPADDING',(0,0),(-1,-1), 8),
    ]))
    s += [t, Spacer(1,4)]

def tbl(header, rows, cw, s, alt=True):
    """交互行色・繰り返しヘッダ付きテーブル"""
    data = [[Paragraph(h, ST['th']) for h in header]]
    for r in rows:
        data.append([Paragraph(str(c), ST['td']) for c in r])
    t = Table(data, colWidths=cw, repeatRows=1)
    ts = [
        ('BACKGROUND',(0,0),(-1,0), BLUE),
        ('GRID',(0,0),(-1,-1), 0.4, colors.HexColor('#d1d5db')),
        ('TOPPADDING',(0,0),(-1,-1), 3), ('BOTTOMPADDING',(0,0),(-1,-1), 3),
        ('LEFTPADDING',(0,0),(-1,-1), 4), ('RIGHTPADDING',(0,0),(-1,-1), 4),
        ('VALIGN',(0,0),(-1,-1), 'TOP'),
    ]
    if alt:
        for i in range(1, len(data)):
            if i % 2 == 0: ts.append(('BACKGROUND',(0,i),(-1,i), TBLA))
    t.setStyle(TableStyle(ts))
    s += [t, Spacer(1,4)]
```

### 6-6. 表紙・フッターのパターン

**⚠️ 表紙の構造に関する重要ルール：**

reportlabの `Table` は `[[要素1, 要素2, ...]]` と書くと**1つのセルに複数要素を詰め込む**形になり、最初の要素しか表示されない。表紙の各行は必ず **1行1列（`[[要素], [要素], ...]`）** の形式で書くこと。

**表紙の見出し表示ルール：**
- `[自治体名]　調査データ　[西暦]年版` を `cover_t`（大見出し・18pt）で1行に書く
- サブタイトルは `cover_s`（10pt）で別行に書く
- 調査日・URLは `cover_m`（8pt）で別行に書く

```python
# 表紙（紺背景ブロック）
# ✅ 正しい書き方：各要素を別行 [[要素], [要素], ...] にする
cover = Table([
    [Paragraph('建築法規・都市計画 調査データ', ST['cover_s'])],
    [Paragraph('[自治体名]　調査データ　[西暦]年版', ST['cover_t'])],
    [Spacer(1,4)],
    [Paragraph('調査日：[日付]　特定行政庁：[自治体名]', ST['cover_m'])],
    [Paragraph('情報ソース：[公式URL]', ST['cover_m'])],
], colWidths=[W])
cover.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,-1), NAVY),
    ('TOPPADDING',(0,0),(-1,-1), 4), ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ('TOPPADDING',(0,0),(0,0), 16), ('BOTTOMPADDING',(0,4),(0,4), 16),
    ('LEFTPADDING',(0,0),(-1,-1), 14), ('RIGHTPADDING',(0,0),(-1,-1), 14),
]))

# ❌ 誤った書き方（これだと最初の要素しか表示されない）
# cover = Table([[
#     Paragraph('...', ST['cover_s']),
#     Paragraph('...', ST['cover_t']),  ← 表示されない
#     Spacer(1,6),                       ← 表示されない
# ]], colWidths=[W])

# 設計実務ポイントカード（水色背景）
for no, title, body in points:  # [('①','タイトル','本文'), ...]
    row = Table([[
        Paragraph(no, ST['pt_no']),
        Paragraph(f'{title}\n{body}', ST['pt_body'])
    ]], colWidths=[10*mm, 160*mm])
    row.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',(0,0),(-1,-1), 5), ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('LEFTPADDING',(0,0),(-1,-1), 5),
        ('BACKGROUND',(0,0),(-1,-1), LBLUE),
        ('BOX',(0,0),(-1,-1), 0.5, colors.HexColor('#bfdbfe')),
    ]))
    story += [row, Spacer(1,3)]

# フッター
story += [
    Spacer(1,8),
    HRFlowable(width='100%', thickness=0.5, color=GRAY),
    Spacer(1,3),
    Paragraph('本資料は[調査日]時点の[自治体名]公式ウェブサイト掲載情報を基に作成。法令・条例・要綱は随時改正されるため、設計・申請時は必ず担当窓口に最新情報を確認すること。', ST['footer']),
    Paragraph('Arch-Reg-Sync / Claude（Anthropic）による自動調査レポート', ST['footer']),
]
```

### 6-7. 出力先とファイル命名規則

```python
import shutil

# ファイル名：[自治体名ローマ字]_kenchiku_houki_[西暦].pdf
# 例：moriguchi_kenchiku_houki_2026.pdf / kadoma_kenchiku_houki_2026.pdf
build_path = '/home/claude/[jichitai]_kenchiku_houki_[year].pdf'
doc.build(story)
shutil.copy(build_path, f'/mnt/user-data/outputs/[jichitai]_kenchiku_houki_[year].pdf')
# → present_files でダウンロードリンクを提供する
```

### 6-8. 列幅の制約

- 全カラム幅の合計は **170mm以内**（左右マージン各20mm）
- テーブルのフォントサイズは **7.5〜8pt**（小さすぎると潰れる）

---

## 注意事項

- **ファイルの直接ダウンロードは行わない**（URLの記録にとどめる）
- 公式サイトで情報が見つからない場合は「要現地確認」と明記する
- 自治体によっては「ふれあい安心居住条例」が存在しない。機能的に相当する条例・要綱を特定して記載する
- 大阪府内の特定行政庁は大阪府施行条例と市条例の重畳適用に注意する
- **フォントは必ず `/usr/share/fonts/truetype/fonts-japanese-gothic.ttf`（IPAゴシック）を使用すること**
- **NotoSansCJKはCFFアウトライン形式のためreportlab非対応。絶対に使用しないこと**
