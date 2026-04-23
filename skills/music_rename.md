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

## 標準パート順（連番の基準）

OCRで認識した楽器名をこの順番にソートして連番を振る。
ファイルの元の番号に関係なく、**この順序が最初の数字になる**。

| 連番 | 省略名 | 備考 |
|---|---|---|
| 1 | Picc. | |
| 2 | 1st & 2nd Fl. / Fl. | 編成による |
| 3 | Ob. | |
| 4 | E.Hrn. | ある場合 |
| 5 | Bsn. | |
| 6 | Eb Cl. | |
| 7 | Cl. / Solo Cl. | ソロまたはunison |
| 8 | 1st Cl. | |
| 9 | 2nd Cl. | |
| 10 | 3rd Cl. | |
| 11 | A.Cl. | |
| 12 | B.Cl. | |
| 13 | 1st A.Sax. | |
| 14 | 2nd A.Sax. | |
| 15 | T.Sax. | |
| 16 | B.Sax. | |
| 17 | 1st Trp. / Cor. | |
| 18 | 2nd Trp. | |
| 19 | 3rd Trp. | |
| 20 | 1st & 2nd Hr. / 1st Hr. | |
| 21 | 2nd Hr. | ある場合 |
| 22 | 3rd & 4th Hr. / 3rd Hr. | |
| 23 | 4th Hr. | ある場合 |
| 24 | 1st Trb. | |
| 25 | 2nd Trb. | |
| 26 | B.Trb. | |
| 27 | Euph. | |
| 28 | Tub. | Bass in C含む |
| 29 | St.Bass | |
| 30 | Timp. | |
| 31 | Perc. 1 | |
| 32 | Perc. 2 | |
| 33 | Perc. 3 | |
| 34 | Perc. 4 | |
| 35 | Pf. | ある場合 |

> **注意**: 編成によってパートが増減する。存在しないパートは飛ばして詰める。

---

## 技術仕様

- **OCRライブラリ**: `pytesseract` + `pymupdf（fitz）`
- **言語**: `eng`（英語）
- **PSMモード**: `--psm 6 --oem 3`
- **解像度**: 200dpi
- **Google Drive API**: files.list / files.patch
- **トークン**: `/home/user/Crossactor/token.json`（自動リフレッシュ）

---

## 楽器名後置ナンバリングルール

楽器名の**後ろ**に数字がついている場合（例: `Flute 1`、`Horn 3`）、
その数字を序数に変換してファイル名の**前**に付ける。

```
Flute 1   → 1st Fl.
Flute 2   → 2nd Fl.
Clarinet 1 → 1st Cl.
Clarinet 3 → 3rd Cl.
Trumpet 3  → 3rd Trp.
Horn 3     → 3rd Hr.
Horn 4     → 4th Hr.
Trombone 1 → 1st Trb.
Trombone 3 → 3rd Trb.
```

OCR抽出後に `re.search(r'InstrumentName\s+(\d)', text)` で末尾の数字を取得し、
`{1:'1st', 2:'2nd', 3:'3rd', 4:'4th'}` テーブルで序数に変換する。

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
