# scan2muse 引き継ぎ（2026-09-26 クラウド → ローカル）

楽譜スキャン→MuseScore取り込みツール「scan2muse」の続きをやる。前のクラウドセッションで道具は完成済み。今回はこのPCで実データを変換する。

## 場所
- 道具：G:\クロードローカル\scan2muse\
  - 無い・空の場合は、GitHubの公開リポジトリ jhcrossactor-lgtm/Crossactor の claude/bold-thompson-08bi0k ブランチから tools/scan2muse/ の中身だけをここに取ってくる
  - 例：git clone -b claude/bold-thompson-08bi0k --depth 1 https://github.com/jhcrossactor-lgtm/Crossactor.git してから tools\scan2muse をコピー
- 入力：G:\google drive_jh\音楽関係\楽譜\三匹の猫\
  - 三匹の猫.pdf（7.2MB、圧縮版）とスキャン_20260926-1340.pdf（21MB、元のスキャン）の2本が入っている
  - 変換対象は「三匹の猫.pdf」だけ。スキャン_〜.pdf は同じ内容なので処理しない（フォルダ一括だと両方拾うため、別フォルダに分けるなどの対処が必要）
- 出力：入力フォルダの中の scan2muse_出力\（.mscz とログ）
- 中間ファイル：G:\クロードローカル\scan2muse\work\

## 環境
- Windows / PowerShell、Python 3.13（py で起動）
- oemer 0.1.8 インストール済み
- MuseScore 4（通常は C:\Program Files\MuseScore 4\bin\MuseScore4.exe。scan2muse が自動で探して config.json に記録する）

## 道具の構成（詳細は README.md）
- scan2muse.bat フォルダ → scan2muse.py を呼ぶ
- PDF → PyMuPDF で300dpiの画像 → oemer でページごとに MusicXML → music21 で結合・楽器名付け → MuseScore CLI で .mscz
- oemer はページごとに別プロセスで実行する。失敗ページはスキップしてログに残す。読み取り済みのページは再利用する
- 楽器名はファイル名から判定する（instruments.py）。oemer は楽器名を読まず、常に「Piano」で出力するため

## 前のセッションで分かった落とし穴（対処済み）
1. py -m oemer は動かない（oemer 0.1.8 に __main__ が無い）→ oemer_runner.py 経由で呼んでいる
2. onnxruntime 1.28以降だと oemer のモデルが読めない → setup.bat で onnxruntime-gpu<1.28 に固定する。既に oemer が入っていても setup.bat は必ず1回実行すること
3. OpenCV 5 だと oemer の find_lines が IndexError で落ちる → oemer_runner.py で互換パッチを当てている

## 今回の課題：入力がスコア（総譜）
- 今の道具は「1ファイル＝1パート」の前提になっている。スコア1本だと全段が「Score (1)」「Score (2)」…という名前になる
- oemer は多段の総譜が苦手。読めないページや段数のずれが出る可能性が高い
- まず1ページで試し、結果を見せてから、段ごとの楽器名付けなどの改修要否を相談すること

## 進め方
1. G:\クロードローカル\scan2muse\ の中身を確認する。「過去の作りかけ」が別にあれば突き合わせ、使えるものは流用する
2. setup.bat を実行する
3. 三匹の猫.pdf だけを対象にして --list → --limit-files 1 --limit-pages 1 で1ページ試す → できた .mscz を MuseScore 4 で開けるか確認する
4. 結果を見せて、全ページ処理とスコア対応の改修を相談する

## ルール
- oemer 以外の OMR に勝手に切り替えない
- 失敗したらエラーを見せて対処法を提案する
- 楽譜データ（著作物）は GitHub に上げない。Crossactor は公開リポジトリ
- 最終的にこの道具をスキル化する予定。コードの変更は GitHub の上記ブランチにも反映できる形で残す
