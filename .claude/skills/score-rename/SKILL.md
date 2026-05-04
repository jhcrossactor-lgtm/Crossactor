---
name: score-rename
description: 吹奏楽の楽譜PDFを読み取り、楽器名・パート名を識別して標準スコア順の連番＋略称でリネームするスキル。スキャンした無名ファイルや出版社命名のファイルを「0.Score.pdf」「1.Picc..pdf」形式に整理する。ファイル名は何でもOK（scan001.pdfでも全く別の名前でも）、中身を読んで判断する。トリガー: 「楽譜をリネームして」「楽器名変更」「score-rename」「楽譜のファイル名を整理して」「[フォルダ名]の楽譜を整理して」「/score-rename」
user-invocable: true
---

# 楽譜PDF リネームスキル

## 概要
吹奏楽楽譜のPDFを読み取り、楽器名・パート名を識別して
**標準スコア順の連番 + 略称** でリネームする。

出力形式: `[番号].[パート略称].pdf`
例: `0.Score.pdf` / `6.1st Cl..pdf` / `15.1st Trp..pdf`

---

## Phase 1: 対象フォルダの確認

ユーザーにフォルダパスを確認（または指定されていれば使用）。
フォルダ内のPDFをリストアップする。

---

## Phase 2: 各PDFの楽器・パート識別

各PDFの**1ページ目**をビジョン（画像として読み取り）で解析し、以下を抽出する：
- 楽器名（例: Clarinet in Bb, Trumpet, Alto Saxophone）
- パート番号（1st / 2nd / 3rd など）
- フルスコアかどうか（Score / Full Score）
- 複数パートが1枚に含まれるか（例: 1st & 2nd Horn）

PDFをビジョンで読む手順:
```
1. pdftoppm または Pythonのpdf2image等でページを画像化
2. 画像をClaudeのビジョンで解析
3. ヘッダー・タイトル・楽器表記から楽器名とパートを特定
```

---

## Phase 3: 標準スコア順へのマッピング

識別した楽器を以下の**吹奏楽標準スコア順**に照合し、ソートする。

### 標準順序テーブル

| 順位 | 略称例 | 正式名 |
|---|---|---|
| 0 | Score | Full Score / スコア |
| 1 | Picc. | Piccolo |
| 2〜 | Fl. / 1st Fl. / 2nd Fl. | Flute |
| 次 | Ob. | Oboe |
| 次 | Bsn. | Bassoon |
| 次 | Eb Cl. | Clarinet in Eb |
| 次 | 1st Cl. / 2nd Cl. / 3rd Cl. | Clarinet in Bb |
| 次 | A.Cl. | Alto Clarinet |
| 次 | B.Cl. | Bass Clarinet |
| 次 | Cb.Cl. | Contra Bass Clarinet |
| 次 | 1st A.Sax. / 2nd A.Sax. | Alto Saxophone |
| 次 | T.Sax. | Tenor Saxophone |
| 次 | B.Sax. | Baritone Saxophone |
| 次 | 1st Trp. / 2nd Trp. / 3rd Trp. | Trumpet / Cornet |
| 次 | 1st Hr. / 2nd Hr. / 1st & 2nd Hr. | French Horn |
| 次 | 1st Trb. / 2nd Trb. | Trombone |
| 次 | B.Trb. | Bass Trombone |
| 次 | Euph. | Euphonium |
| 次 | Tub. | Tuba |
| 次 | St.Bass | String Bass |
| 次 | B.Gtr. | Bass Guitar |
| 次 | E.Gtr. | Electric Guitar |
| 次 | Drs. | Drum Set |
| 次 | Timp. | Timpani |
| 次 | Perc. 1 / Perc. 2 ... | Percussion |
| 次 | その他 | Harp, Piano, Mallet等 |

**番号はファイル数に応じて0から連番で振る（固定ではない）。**

---

## Phase 4: リネーム実行前の確認

リネーム前に以下の対応表をユーザーに提示する：

```
[確認] 以下のようにリネームします。よろしいですか？

現在のファイル名              → リネーム後
scan001.pdf                  → 0.Score.pdf
scan002.pdf                  → 1.Picc..pdf
scan003.pdf                  → 2.1st Fl..pdf
...
```

ユーザーが承認したらリネーム実行。

---

## Phase 5: リネーム実行

Pythonまたは Bash でリネーム：

```python
import os
renames = [
    ("scan001.pdf", "0.Score.pdf"),
    # ...
]
folder = "[対象フォルダ]"
for old, new in renames:
    os.rename(os.path.join(folder, old), os.path.join(folder, new))
print("リネーム完了")
```

---

## 略称ルール

- パートが1つだけ → `Fl.` / `Ob.` など番号なし
- パートが複数 → `1st Fl.` / `2nd Fl.` など番号付き
- 2パート合一 → `1st & 2nd Hr.` 形式
- パーカッション → `Perc. 1` / `Perc. 2` で連番
- 番号の後にピリオド（`.`）、ファイル拡張子の前にもピリオド

## 実行ルール

- AskUserQuestion は Phase 4（確認）の1回のみ
- 識別できなかったPDFは `99.Unknown_[元のファイル名].pdf` として残す
- 元のファイルはリネーム前にバックアップフォルダ（`_backup/`）にコピーする
