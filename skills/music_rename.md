# スキル: 楽器名変更

## トリガーワード
「楽器名変更」

## 概要
スキャンPDFの楽器パート譜を、OCRで楽器名を読み取り省略名でリネームするスキル。
Google Drive APIを使ってクラウド上で完結する。

---

## 処理フロー

1. **対象フォルダをGoogle Driveで検索**
2. **PDFをダウンロードしてOCR処理**
   - ページ上部20%・左40%を切り出し
   - pytesseract（eng）で楽器名を抽出
   - 左上の楽器名キーワード行を特定
3. **省略名に変換**（下記テーブル参照）
4. **ファイル名ルールに従ってリネーム**
   - 形式: `{連番}.{省略名}.pdf`
   - 重複する楽器は `(2)` `(3)` を付与
5. **Drive API PATCHでリネーム実行**

---

## ファイル名ルール

```
{連番}.{省略名}.pdf
例: 1.Picc..pdf / 7.1st Cl..pdf / 25.1st & 2nd Hr..pdf
```

---

## 楽器省略名テーブル

| 英語フルネーム | 省略名 |
|---|---|
| Piccolo | Picc. |
| Flute | Fl. |
| Oboe | Ob. |
| English Horn | E.Hrn. |
| Bassoon | Bsn. |
| Eb Clarinet / Clarinet in Eb | Eb Cl. |
| Clarinet in Bb / Clarinet | Cl. |
| Alto Clarinet | A.Cl. |
| Bass Clarinet | B.Cl. |
| Alto Saxophone | A.Sax. |
| Tenor Saxophone | T.Sax. |
| Baritone Saxophone | B.Sax. |
| Trumpet | Trp. |
| Cornet | Cor. |
| Flugelhorn | Flug. |
| Horn | Hr. |
| Trombone | Trb. |
| Bass Trombone | B.Trb. |
| Euphonium | Euph. |
| Tuba | Tub. |
| Contrabass / String Bass | St.Bass |
| Bass in C（チューバ記譜） | Tub. |
| Piano | Pf. |
| Timpani | Timp. |
| Drum Set / Drums | Drs. |
| Glockenspiel | Glck. |
| Xylophone | Xylo. |
| Marimba | Mar. |
| Vibraphone | Vib. |
| Snare Drum | S.D. |
| Bass Drum | B.D. |
| Cymbals | Cym. |
| Suspended Cymbal | S.Cym. |
| Cabasa | Cab. |
| Triangle | Tri. |
| Tambourine | Tamb. |
| Bass Guitar | B.Gtr. |
| Electric Guitar | E.Gtr. |

---

## 技術仕様

- **OCRライブラリ**: `pytesseract` + `pymupdf（fitz）`
- **言語**: `eng`（英語）
- **PSMモード**: `--psm 6 --oem 3`
- **解像度**: 200dpi
- **Google Drive API**: files.list / files.patch
- **トークン**: `/home/user/Crossactor/token.json`（自動リフレッシュ）

---

## よくあるOCR誤読と修正ルール

| OCR誤読 | 正しい読み |
|---|---|
| Ist / lst / lsl / isi | 1st |
| Sra / Srd / Sid | 3rd |
| Ain / 4in | 4th |
| ramp | Trumpet |
| pariione / Bariione | Baritone |
| prums | Drums |
| nimpar | Timpani |
| Flectric / Fieciric | Electric |
| int（行末） | in F |

---

## 実行スクリプト参照

`gdrive_upload.py` のトークンリフレッシュ処理を流用。
OCR本体は会話履歴のコードを参照（再利用可能）。
