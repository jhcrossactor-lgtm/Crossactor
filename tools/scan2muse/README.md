# scan2muse — スキャン楽譜 → MuseScore 取り込みツール

スキャンした楽譜（PDF / PNG / JPG）のフォルダを指定すると、oemer で読み取り、
パート名を付けて MuseScore の `.mscz` に変換する。

```
scan2muse.bat "G:\google drive_jh\音楽関係\楽譜\三匹の猫"
```

---

## 1. 初回セットアップ（1回だけ）

道具一式（このフォルダ）は `G:\クロードローカル\scan2muse\` に置く。

```
cd "G:\クロードローカル\scan2muse"
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

**② 1ページだけ試す** → 楽譜フォルダの中の `scan2muse_出力\parts\` にできた `.mscz` を MuseScore で開いて確認

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
| `--out フォルダ` | 出力先（既定: 入力フォルダの中の `scan2muse_出力`） |
| `--dpi N` | PDF → 画像の解像度（既定 300） |
| `--timeout 秒` | 1ページあたりの oemer 制限時間（既定 1800） |
| `--no-deskew` | 傾き補正を切る（まっすぐな電子 PDF 向け。速くなる） |
| `--no-combine` | 全パートの総譜を作らない |
| `--force` | 読み取り済みページも oemer をやり直す |
| `--concert-pitch` | 楽譜が実音表記（Score in C）のとき指定。Tp / Hr などのパートを記譜音に移調して出力する |

## 3. 出力

完成品は元の楽譜の隣に、中間ファイルは道具側に分けて置く。

```
G:\google drive_jh\音楽関係\楽譜\三匹の猫\
  （元の楽譜 PDF）
  scan2muse_出力\
    三匹の猫_総譜.mscz      ← 全パートを標準スコア順に並べた総譜
    parts\09_Cl 1.mscz      ← パート譜（番号はスコア順）
    parts\14_Tp 2.mscz
    scan2muse.log           ← 処理ログ（失敗ページの理由もここ）

G:\クロードローカル\scan2muse\work\三匹の猫\
    ← 中間ファイル（ページ画像・ページ毎の MusicXML）。消しても次回作り直されるだけ
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

## 4b. 総譜（スコア）を読む場合

oemer は「1段組に譜表1本（または2本＝ピアノ）」しか扱えず、多段の総譜は `AssertionError` で止まる。
そのため総譜は **楽器ごとに段を切り出してから** scan2muse に渡す。

```
cd "G:\ClaudeLocal\scan2muse"
py prepare_pages.py "<総譜.pdf>" --out "work\<曲名>\straight" --staves 10
py extract_staff.py "work\<曲名>\straight" --staves 10 --index 1 --name "Trumpet 1" --out "work\<曲名>\parts_in\<曲名>_parts"
py extract_staff.py "work\<曲名>\straight" --staves 10 --index 2 --name "Trumpet 2" --out "work\<曲名>\parts_in\<曲名>_parts"
（… 楽器の数だけ --index と --name を変えて繰り返す。全部同じ出力フォルダに入れる）
scan2muse.bat "work\<曲名>\parts_in\<曲名>_parts" --out "<楽譜フォルダ>\scan2muse_出力" --no-deskew --concert-pitch
```

全楽器を1つのフォルダに入れて scan2muse を1回走らせると、パート譜と総譜（`<曲名>_parts_総譜.mscz`）が両方できる。
`--concert-pitch` は楽譜が「Score in C」（実音表記）のときだけ付ける。

| 段階 | 内容 |
|---|---|
| `prepare_pages.py` | 全ページの向きを揃え（五線が横・音部記号が左）、とじ目側の五線の湾曲を補正。段の位置を `_layout.json`、確認用一覧を `_contact.png` に出す。`--staves` は1段組の譜表数 |
| `extract_staff.py` | 各段組の `--index` 番目の譜表を切り出し、線間隔 13px・約340万画素の「パート譜風ページ」にする。3ページ分を1枚にまとめる（`--per-image`） |
| `scan2muse.bat` | 上の出力フォルダをそのまま渡す。ファイル名の楽器名からパート名が付く |

- 譜表数が `--staves` の倍数でないページ（休みの楽器が省略された段組）は飛ばして `_skipped.txt` に記録する。そのページの楽器割り当ては別途判断が要る
- 埋め込み画像が PDF の表示と違う向きで保存されていることがある（表示上は正しくても画像は逆さ）。prepare_pages.py は画像の中身で判定するので問題ない

### 線間隔 13px に揃える理由（重要）

oemer は入力を 300万〜435万画素に自動でリサイズする（`inference.resize_image`）。
そのため**入力画像の大きさが、oemer が見る五線の線間隔を決める**。実測（三匹の猫 Tp I・1ページ目）：

| 五線の線間隔（oemer が見るサイズ） | 結果 |
|---|---|
| 27px（切り出し段を2倍に拡大した画像） | 12小節中7小節、4分音符が8分・16分に化ける |
| **13px**（白余白で画素数を調整） | **12小節中11小節、リズムもほぼ正しい** |

`extract_staff.py` はこれを自動で行う。手で画像を作るときも「線間隔 12〜14px × 画素数 340万」に揃えること。

## 4c. 総譜を Audiveris で読む（推奨・2026-10-01〜）

Audiveris（5.11.0、Java 同梱）は多段の総譜をそのまま読める。三匹の猫（金管10段）で1ページ約30秒、
パートごとの小節数も揃う。oemer＋切り出し（4b）より速く精度も高いので、総譜はこちらを使う。

```
cd "G:\ClaudeLocal\scan2muse"
rem ① 見開き（横長ページ）を左右に分けて 1ページ1枚の PNG にする
py split_pages.py "<総譜.pdf>" "work\<曲名>\pages"
rem ② Audiveris でページごとに .mxl にする（1ページ失敗しても他は止まらない）
"G:\ClaudeLocal\Audiveris\Audiveris\Audiveris.exe" -batch -export -output "work\<曲名>\aud" -- work\<曲名>\pages\page_001.png work\<曲名>\pages\page_002.png ...
rem ③ 楽章ごとにページを継ぎ合わせ、楽器名を付ける
py merge_pages.py "work\<曲名>\mvt1.musicxml" --title "<題名>" --drop-fermatas --names "Tp 1,Tp 2,...,Tuba" work\<曲名>\aud\page_001.mxl work\<曲名>\aud\page_002.mxl ...
rem ④ MuseScore で .mscz にする（終了コード0でも、保存した .mscz を開き直して確かめる）
"C:\Program Files\MuseScore 4\bin\MuseScore4.exe" -o "<出力>.mscz" "work\<曲名>\mvt1.musicxml"
"C:\Program Files\MuseScore 4\bin\MuseScore4.exe" -o "work\<曲名>\check.pdf" "<出力>.mscz"
```

- **楽章の切れ目**: Audiveris は楽章が変わるページを `page_005.mvt1.mxl` / `page_005.mvt2.mxl` のように分けて出す。
  `mvt1` を前の楽章、`mvt2` を次の楽章に入れる。字下げを楽章の頭と誤認して1段×1小節の断片ができることがあるので、中身の小節数を見て捨てる
- **段数が違うページ**（楽章の頭で休みの楽器が省略されている等）: `page_013.mxl@4,5,6,7,9` のように、
  そのページの上から順の段が `--names` の何番目かを書く。書いていない楽器は全休符で埋まる
- **読み取れないページ**: `GAP:14` と書くと全休符14小節を入れ、先頭パートに「★ここから読み取り失敗ページ」の目印を付ける。後で手入力する
- `--names` は楽章ごとに楽譜の楽器名に合わせる（楽章によって Flh / Tp 3 などの持ち替えが変わる）

`merge_pages.py` が各ページにかける補正（`audiveris_fix.py` の関数。ログに場所が出る）:

| 補正 | 理由 |
|---|---|
| フェルマータを外す（`--drop-fermatas`） | Audiveris は松葉（< >）をフェルマータと読み違える。外した松葉は戻らないので手で付ける。本物のフェルマータも消えるので、ログを見て戻す |
| 抜けた小節を全休符で補う | パートによって小節が抜けることがある。MuseScore は小節数の違うパートを開けない |
| 中身の長さから拍子を推定 | 拍子変更（例 2/4→9/8）を読み落とすと、後ろの小節が全部切り詰められて音が消える。音のあるパートの6割以上・3パート以上が同じ長さのときだけ拍子を変える（短くする方向は8割以上）。ページをまたいで引き継ぐ |
| 崩れた連符を全休符にする | 3連符の1音を読み落とすと小節の長さが半端な分数になり、MuseScore が楽章ごと開かない（Incomplete measure）。その声部のその小節を全休符にする |
| はみ出しを切る／足りない分を休符で埋める | MuseScore 4 の CLI は拍子と長さの合わない小節があると開かない（終了コード1320） |

1ページだけなら `py audiveris_fix.py <入力.mxl> <出力.musicxml> --names "..." --drop-fermatas` でも同じ補正ができる。

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
| oemer が `'NoneType' object has no attribute '__array_interface__'`（inference.py） | Windows の `cv2.imread` が日本語を含むパスを開けない | `oemer_runner.py` が `imdecode` 版に差し替える。対処不要 |
| oemer が `AssertionError: 4`（build_system.py の `track_nums == 2`） | 多段の総譜を直接読ませた | 「4b. 総譜を読む場合」の手順で楽器ごとに切り出す |
| MuseScore が .mscz を開くとクラッシュ | 小節の長さが異常な MusicXML（読み取り失敗）から作った | ログで該当ページを確認し、そのページを除いて作り直す |
| Audiveris が `Error processing stub ... Measure.purgeVoices()` → `Error in export` | Audiveris 内部の不具合（MeasureStack の NullPointerException）。解像度・余白・段ごとの分割・右端の切りそろえでは直らなかった | そのページは `merge_pages.py` に `GAP:<小節数>` を渡して全休符にし、手入力する |
| MuseScore の読み込みは終了コード0なのに、保存した .mscz を開き直すと1320 | 崩れた連符など、読み込み時に丸められた小節が保存後に Incomplete measure になる | `merge_pages.py` で作り直す（崩れた連符を全休符にする）。原因の小節は `%LOCALAPPDATA%\MuseScore\MuseScore4\logs` の最新ログに `Incomplete measure: ... measure N, staff M` と出る |
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
| `prepare_pages.py` | 総譜用：ページの向き揃え・湾曲補正・段位置の検出 |
| `extract_staff.py` | 総譜用：1楽器の段を切り出して scan2muse 用の画像にする |
| `split_pages.py` | Audiveris 用：PDF を1ページ1枚の PNG に（見開きは左右に分割） |
| `merge_pages.py` | Audiveris 用：ページごとの .mxl を補正して1楽章の総譜に継ぎ合わせる |
| `audiveris_fix.py` | Audiveris 用：MuseScore が開ける形にする補正（1ページ単体でも使える） |
| `config.json` | MuseScore のパス（自動生成） |

## 動作確認の記録（2026-09-26）

Linux 環境（Python 3.11 / oemer 0.1.8 / onnxruntime 1.26 / MuseScore 3 CLI（apt 版））で、生成したテスト楽譜を使って確認した。

- 1ページ: PDF → 画像 → oemer → `.mscz` → MuseScore で再度開けることを確認（パート名 Cl 1、B♭ の移調設定あり）
- 一括: PDF 1本＋連番画像2枚＋壊れた PDF 1本 → 壊れた PDF はスキップしてログに記録、画像2枚は1パートに連結、総譜も出力

2026-09-27 以降は Windows 実機（Python 3.13 / MuseScore 4）と実データ「三匹の猫」で確認済み。
2026-10-01: 新スキャン（600dpi・見開き含む20ページ・3楽章）を 4c の手順で楽章ごとの .mscz 3本にし、MuseScore 4 で開き直せることを確認。1ページは Audiveris の不具合で読めず全休符で仮置き。
