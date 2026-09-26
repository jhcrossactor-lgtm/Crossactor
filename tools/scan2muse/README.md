# scan2muse — スキャン楽譜 → MuseScore 取り込みツール

スキャンした楽譜（PDF / PNG / JPG）のフォルダを指定すると、oemer で読み取り、
パート名を付けて MuseScore の `.mscz` に変換する。

```
scan2muse.bat "G:\google drive_jh\音楽関係\楽譜\三匹の猫"
```

---

## 1. 初回セットアップ（1回だけ）

```
cd <このフォルダ>\tools\scan2muse
setup.bat
```

`requirements.txt` の依存パッケージを入れる。**既に oemer を入れていても1回は実行すること。**
oemer と一緒に入る最新の onnxruntime（1.28 以降）では oemer のモデルが読めない。
setup.bat で 1.28 未満に入れ替える（詳細は「既知の問題」）。

MuseScore は初回実行時に自動で探し、見つかったパスを `config.json` に保存する。
見つからない場合は `config.json` を次の内容で作成する。

```json
{ "musescore_path": "C:\\Program Files\\MuseScore 4\\bin\\MuseScore4.exe" }
```

## 2. 使い方（段階的に）

**① 入力の確認**（処理はせず、ファイルと判定されたパート名だけ表示）

```
scan2muse.bat "G:\google drive_jh\音楽関係\楽譜\三匹の猫" --list
```

「楽器名を判定できず」と出たファイルは、ファイル名を楽器名に変えると判定される（例: `scan001.pdf` → `Clarinet 1.pdf`）。

**② 1ページだけ試す** → `output\三匹の猫\parts\` にできた `.mscz` を MuseScore で開いて確認

```
scan2muse.bat "G:\google drive_jh\音楽関係\楽譜\三匹の猫" --limit-files 1 --limit-pages 1
```

**③ 一括処理**

```
scan2muse.bat "G:\google drive_jh\音楽関係\楽譜\三匹の猫"
```

読み取り済みのページは再利用されるので、②の後に③を実行しても同じページは再処理されない。
途中で止めた場合も、同じコマンドをもう一度実行すれば続きから処理される。

> パスにスペースが入る場合は `"` で囲むこと。

### オプション

| オプション | 内容 |
|---|---|
| `--list` | 入力ファイルと判定パート名の一覧だけ表示 |
| `--limit-files N` | 先頭 N ファイルだけ処理 |
| `--limit-pages N` | 各ファイルの先頭 N ページだけ処理 |
| `--out フォルダ` | 出力先（既定: `tools\scan2muse\output`） |
| `--dpi N` | PDF → 画像の解像度（既定 300） |
| `--timeout 秒` | 1ページあたりの oemer 制限時間（既定 1800） |
| `--no-deskew` | 傾き補正を切る（まっすぐな電子 PDF 向け。速くなる） |
| `--no-combine` | 全パートの総譜を作らない |
| `--force` | 読み取り済みページも oemer をやり直す |

## 3. 出力

```
output\三匹の猫\
  三匹の猫_総譜.mscz        ← 全パートを標準スコア順に並べた総譜
  parts\09_Cl 1.mscz        ← パート譜（番号はスコア順）
  parts\14_Tp 2.mscz
  scan2muse.log             ← 処理ログ（失敗ページの理由もここ）
  work\                     ← 中間ファイル（ページ画像・ページ毎の MusicXML）
```

- 失敗したページは飛ばして続行し、ログ末尾に `[失敗]` として一覧が出る
- 1ページも読めなかったファイルはパート譜を出力しない
- フルスコア（ファイル名に Score / スコア / 総譜）はパート譜として出力し、総譜の結合からは外す

## 4. 入力ファイルのルール

- **1ファイル＝1パート**。PDF の複数ページは順に連結する
- 画像は1枚＝1パート。複数ページの画像は `Cl1_p1.png` `Cl1_p2.png` のように
  `p` / `page` / `ページ` ＋番号を付けると1パートにまとめる
  （`Clarinet 1.png` `Clarinet 2.png` は別パート扱い）
- JPG のスマホ写真は EXIF の向きを反映してから読む

### パート名の判定

oemer は楽器名を読み取らない（どの楽譜も「Piano」として出力する）。そのため**パート名はファイル名から判定**する。
英語・略称・日本語のどれでもよく、先頭の整理番号（`1.` `03_`）と調性表記（`in Bb` など）は無視する。

| ファイル名の例 | パート名 |
|---|---|
| `1.Picc..pdf` / `ピッコロ.pdf` | Picc |
| `Flute 1.pdf` / `フルート１.pdf` | Fl 1 |
| `Clarinet in Bb 2.pdf` / `3rd Clarinet.pdf` | Cl 2 / Cl 3 |
| `Alto Saxophone 1.pdf` / `アルトサックス1.pdf` | A.Sax 1 |
| `Trumpet 1.pdf` / `Tp.2,3.pdf` | Tp 1 / Tp 2&3 |
| `Horn in F 1.pdf` / `ホルン.pdf` | Hr 1 / Hr |
| `Trombone II.pdf` / `Bass Trombone.pdf` | Tb 2 / B.Tb |
| `Euphonium.pdf` / `ユーフォニアム.pdf` | Euph |
| `Tuba.pdf` / `String Bass.pdf` / `弦バス.pdf` | Tuba / St.B |
| `Percussion 1.pdf` / `打楽器2.pdf` / `Timpani.pdf` | Perc 1 / Perc 2 / Timp |

判定できる楽器の一覧と並び順は `instruments.py` の `INSTRUMENTS` にある。1行足せば判定を増やせる。

移調楽器（Cl / Sax / Tp / Hr など）は、スキャンした楽譜の記譜音のまま取り込み、MuseScore 側に移調設定を付ける。
MuseScore の「移調楽器表示」を切り替えると実音でも表示できる。

## 5. 所要時間と精度の目安

- oemer は1ページあたり 3〜4分かかる（CPU、A4・300dpi）。10パート×2ページなら 1時間強
- 読み取り精度は oemer 次第。音符の抜け・リズムの崩れ・小節数のずれは起こる。取り込み後に MuseScore で手直しする前提
- パートごとに小節数が揃わないと総譜で縦がずれる。ログに `小節数が揃っていません` と出るので、そのパートを確認する

## 6. 既知の問題と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `ConvTranspose ... pads must not contain negative values` | onnxruntime 1.28 以降と oemer のモデルの非互換 | `setup.bat` を実行（`onnxruntime-gpu<1.28` に入れ替え）。CPU版を入れている場合は `py -m pip install "onnxruntime<1.28"` |
| `py -m oemer` が `No module named oemer.__main__` | oemer 0.1.8 は `-m` 実行に非対応 | scan2muse は `oemer_runner.py` 経由で呼ぶので対処不要 |
| oemer が `IndexError: invalid index to scalar variable`（bbox.py） | OpenCV 5 で `HoughLinesP` の戻り値の形が変わった | `oemer_runner.py` が自動で互換パッチを当てる。対処不要 |
| 初回だけ oemer の開始が遅い | モデル（約 100MB）を GitHub から自動ダウンロードしている | 待つ。2回目以降は不要 |
| `MuseScore が見つかりません` | 標準以外の場所にインストール | `config.json` にパスを書く（セットアップ参照） |

## 7. ファイル構成

| ファイル | 役割 |
|---|---|
| `scan2muse.bat` | 起動用（`py scan2muse.py` を呼ぶだけ） |
| `setup.bat` / `requirements.txt` | 依存パッケージのインストール |
| `scan2muse.py` | 本体（収集 → 画像化 → oemer → 結合・楽器名 → MuseScore） |
| `oemer_runner.py` | oemer を1ページずつ別プロセスで実行（互換パッチ込み） |
| `instruments.py` | ファイル名 → パート名の判定テーブル |
| `config.json` | MuseScore のパス（自動生成） |

## 動作確認の記録（2026-09-26）

Linux 環境（Python 3.11 / oemer 0.1.8 / onnxruntime 1.26 / MuseScore 3 CLI（apt 版））で、生成したテスト楽譜を使って確認した。

- 1ページ: PDF → 画像 → oemer → `.mscz` → MuseScore で再度開けることを確認（パート名 Cl 1、B♭ の移調設定あり）
- 一括: PDF 1本＋連番画像2枚＋壊れた PDF 1本 → 壊れた PDF はスキップしてログに記録、画像2枚は1パートに連結、総譜も出力

**Windows 実機（MuseScore 4）と実データ「三匹の猫」では未確認。** 上の「使い方②」で最初に確認すること。
