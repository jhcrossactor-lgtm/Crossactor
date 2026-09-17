# ヴィラPV生成パイプライン

写真とMOVから16:9のPR動画を組み立てる社内CLI。
`projects/<物件名>/cuts.yaml` と `input/` を差し替えれば別物件に流用できる。

## 工程

| 工程 | 内容 | 使うもの |
|---|---|---|
| 1 | カット定義 | `projects/<物件>/cuts.yaml` |
| 2 | 人物合成（16:9出力） | 画像編集API → `stage1/` |
| 3 | **目視確認で停止** | `stage1/` を人が見る |
| 4 | 動画化 | image-to-video API → `stage2/` |
| 5 | MOVの16:9切り出し | ffmpegのみ（AIを使わない） |
| 6 | 結合（xfade 0.5秒＋末尾フェードアウト2秒） | ffmpeg → `output/pv_16x9.mp4` |
| 7 | 音楽 | 音源があれば載せる／無ければ無音 |
| 8 | ログとプロンプト保存 | `logs/` と `logs/prompts/` |

## セットアップ

```bash
pip install -r requirements.txt
# ffmpeg は別途入れておく（macOS: brew install ffmpeg / Ubuntu: apt install ffmpeg）
cp .env.example .env     # APIキーを書く
```

素材は `projects/villa_test/input/` に置く。ファイル名は `cuts.yaml` の `source` と
`character_sheet` に合わせること。HEIC のまま置いても自動で JPEG に変換する
（変換結果は `input/_converted/` に入る）。

```
input/
  character_sheet.png   ← 人物設定シート（Drive上の "ChatGPT Image ....png" をリネーム）
  4446557_l.jpg  IMG_8613.jpg(.HEIC)  ICED2685.JPEG  GGBM1602.JPEG
  IMG_5558.JPG   IMG_5625.MOV         IMG_5565.JPG   BIEV8282.JPEG
  IMG_8628.jpg(.HEIC)  IMG_5577.JPG
```

## 使い方

```bash
python run.py check                  # 素材・ffmpeg・APIキー・完成尺の事前チェック
python run.py --stage 1              # 人物合成。1カットごとに合否を聞く
python run.py --stage 2              # 動画化（stage1が全部合格していないと止まる）
python run.py --stage 3              # 結合して output/pv_16x9.mp4 を書き出す
python run.py status                 # 進み具合
```

カット単位でのやり直し:

```bash
python run.py --cut 04 --stage 1     # cut04の画像だけ作り直す
python run.py --cut 04 --stage 2     # cut04の動画だけ作り直す
python run.py --stage 3              # 作り直したら結合だけ回す
```

その他のオプション:

| オプション | 用途 |
|---|---|
| `--provider mock` | APIを叩かずに配線だけ確認する |
| `--video-provider minimax` | 動画プロバイダをその場で切り替える |
| `--yes` | 目視確認を省いて自動合格にする（非対話実行用） |
| `--no-chain` | 合格カットを人物参照に足さず、設定シートだけ使う |
| `--force` | stage1の合格チェックを飛ばして stage2 に進む |
| `--music path.mp3` | BGMを載せて書き出す |
| `--project projects/別物件` | 別物件で回す |

APIを一切叩かない通しテスト:

```bash
bash scripts/selftest.sh
```

## 人物の一貫性

`cuts.yaml` の `stage1_order`（既定 `02 → 03 → 05 → 04 → 07 → 09`）の順に生成する。
後ろ姿のカットを先に固め、**合格したカットの画像を以降のカットの人物参照に追加添付する**。
合否は `logs/approvals.json` に残るので、あとから `--cut NN --stage 1` で作り直しても
参照の連鎖は保たれる。

画像APIには常に「1枚目＝編集対象の建物写真（建物は変更禁止）、2枚目以降＝人物参照」と
明記して渡している（`config.yaml` の `prompts.image_attachment_note`）。

## 別物件への流用

```bash
mkdir -p projects/新物件/input
cp projects/villa_test/config.yaml projects/villa_test/cuts.yaml projects/新物件/
# cuts.yaml の source / instruction / duration を書き換え、input/ に素材を置く
python run.py --project projects/新物件 check
```

## モデル・エンドポイントの出どころ

`config.yaml` にしか書いていない。コードにハードコードしていないので、
仕様が変わったら YAML を直すだけでよい。

- **画像**: `POST https://api.openai.com/v1/images/edits`（multipart、`image[]` に最大16枚）。
  モデルは `gpt-image-2.5-sunburst`（2026-09-08 リリース。`flare` は高速版）。
  サイズ `2048x1152` は「16:9ちょうど」かつ「幅・高さとも16の倍数」という制約を満たす値。
- **動画（既定）**: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning`
  → `GET /v1beta/{operation.name}` でポーリング。
  この2本のパスは Gemini API の公式ディスカバリドキュメントで確認済み。
  `instances` / `parameters` は API 定義上 free-form なので、項目名は `config.yaml` で差し替えられる。
  モデルは `gemini-omni-1.1-flash`。
- **動画（切替）**: MiniMax H3（`MiniMax-H3`）。非同期3ステップ（作成→照会→DL）。
  **パスと項目名は未検証**（構築時のネットワークから公式ドキュメントに到達できなかった）。
  初回実行前に platform.minimax.io で照合すること。`config.yaml` で全部差し替えられる。

## 既知の制約

- **完成尺は約31.5秒**。カット合計36秒から、クロスディゾルブ0.5秒×9回ぶんの重なり
  4.5秒が引かれるため。35秒に寄せたいときは `config.yaml` の `assemble.xfade_duration`
  を下げるか、`cuts.yaml` の `duration` を足す。
- **音楽は既定で無音**。画像APIにも動画APIにも「30秒級のBGMを単体で書き出す」公開
  エンドポイントが無い。音源を用意したら `--music` か `config.yaml` の `music.file` に
  指定して stage3 だけ回す。
- `cut10` の `【施設名】` は差し替えが要る（`cuts.yaml` の TODO）。
- 生成尺は指定どおりに返らないことがあるので、stage2 で必ず目標秒数に詰めている
  （長ければ切り、短ければ最終フレームを複製）。
