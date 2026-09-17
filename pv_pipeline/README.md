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
python run.py connect                # ChatGPT Image との疎通確認
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
| `--smoke` | `connect` で実際に1枚編集して確かめる |
| `--project projects/別物件` | 別物件で回す |

APIを一切叩かない通しテスト:

```bash
bash scripts/selftest.sh
```

## ChatGPT Image と繋ぐ

画像合成は ChatGPT Image（OpenAI画像API）を使う。繋がっているかは専用コマンドで確かめる。

```bash
python run.py connect           # キー・到達性・使えるモデルを順に切り分ける
python run.py connect --smoke   # 実際に1枚編集して確かめる（課金が発生する）
```

`connect` はどこで止まっているかを切り分けて言い切る。キーが無いのか、ホストに
到達できないのか、モデルが使えないのかが1回で分かる。

### ローカルで実行する場合（いちばん速い）

```bash
cp .env.example .env
# OPENAI_API_KEY=sk-... を書く
python run.py connect --smoke
```

`config.yaml` は `auth: bearer` のままでよい。

Windows (PowerShell) の場合:

```powershell
git clone https://github.com/jhcrossactor-lgtm/Crossactor.git
cd Crossactor
git checkout claude/eager-dijkstra-mpf7fg
cd pv_pipeline
Copy-Item .env.example .env
notepad .env                 # OPENAI_API_KEY=sk-... を書いて保存
pip install -r requirements.txt
python run.py connect
```

`.env` と `config.yaml` は BOM 付きで保存されても読めるようにしてある
（メモ帳や `Out-File` は BOM を付けることがある）。
ffmpeg は別途入れること（`winget install Gyan.FFmpeg` など）。

### クラウドセッション（claude.ai/code）で実行する場合

クラウド環境は既定で `api.openai.com` への通信を拒否する。環境設定を変える必要がある。
設定場所は claude.ai/code のメッセージボックス上にある**雲アイコン**
→ 対象の環境にホバーして**歯車アイコン** → 環境ダイアログ。

**方法A: API credentials（推奨 / Pro・Maxプランのみ）**

キーがセッションのVMに入らない。エージェントプロキシが、セッションを出たあとの
リクエストに `Authorization` を付ける。**このホストはネットワーク許可リストを迂回する**ので、
ネットワークレベルの設定は別途不要。

1. 環境ダイアログの **API credentials** → **Add credential**
2. Credential type は既定の **Bearer** のまま
   - Name: `OpenAI Images`
   - Allowed websites: `api.openai.com`
   - Custom headers: Name `Authorization` / Prefix `Bearer` / Value にキーを貼る
3. **Connect** で保存（保存後は値を見られない）
4. `config.yaml` を `auth: proxy` に変える ← **これを忘れると二重に認証ヘッダが付く**

**方法B: ネットワーク許可リスト**

1. 環境ダイアログの **Network access** を **Custom** にする
2. **Allowed domains** に1行で `api.openai.com` を追加
   （動画側もクラウドで回すなら `generativelanguage.googleapis.com` も足す）
3. **Also include default list of common package managers** にチェックを入れる
   （外すと pip なども通らなくなる）
4. **Environment variables** に `OPENAI_API_KEY=sk-...` を書く
5. `config.yaml` は `auth: bearer` のまま

方法Bは環境変数がセッションから見える。キーを見せたくないなら方法Aにすること。

### 送っているパラメータ

| 項目 | 値 | 備考 |
|---|---|---|
| `model` | `gpt-image-2.5-sunburst` | `flare` は高速・低精度。`config.yaml` で変える |
| `size` | `2048x1152` | 16:9ちょうど。幅・高さとも16の倍数という制約を満たす |
| `quality` | `high` | 2.5系は `xhigh` / `max` も指定できる |
| `output_format` | `png` | `webp` / `jpeg` も可 |
| `image[]` | 最大16枚 | 1枚目＝編集対象、2枚目以降＝人物参照 |

**送っていないもの**（送ると失敗する、または不要）:

- `response_format` — gpt-image 系は400で弾く。出力は常にbase64
- `input_fidelity` — gpt-image-2 以降は入力を常に高忠実度で処理する。
  「建物は変更禁止」という要件はモデル既定の挙動で満たされるので指定しない

`size` は実行前に検証している。16の倍数・総画素数・アスペクト比の制約に外れていれば
API を叩く前に落とす（例: `1920x1080` は 1080 が16の倍数でないため不可）。

## Gemini（動画）と繋ぐ

キーは **Google AI Studio** で発行する。https://aistudio.google.com/apikey

これは Gemini Developer API のキーで、パイプラインが叩く
`generativelanguage.googleapis.com` に対応する。**Vertex AI（Google Cloud）のものではない** —
Vertex はエンドポイントも認証方式（サービスアカウント）も別物で、このコードでは使えない。

```
GEMINI_API_KEY=AIza...
```

`.env` に書いたら `python run.py connect` で画像側と一緒に確認できる。
そのアカウントで実際に使えるモデルが一覧で出るので、`config.yaml` の
`video.gemini.model` が使えるかどうかがその場で分かる。

**動画生成は課金を有効にしたプロジェクトでないと使えないことが多い。**
無料枠のキーでモデル一覧は引けても、生成リクエストで弾かれることがある。
一覧に出ていても不安なら `python run.py --cut 01 --stage 2` で1カットだけ実地に試すこと。

## MiniMax H3（動画の切替先）と繋ぐ

既定は Gemini なので、**通常は不要**。Gemini の絵が気に入らないときの差し替え先。

キーは **MiniMax Open Platform** で発行する。地域でサイトが分かれている。

| | サイト | base_url |
|---|---|---|
| 国際版（日本から使うのはこちら） | https://platform.minimax.io/ | `https://api.minimax.io/v1` |
| 中国本土版 | https://platform.minimaxi.com/ | `https://api.minimaxi.com/v1` |

**キーとホストは対応していないと通らない。** 国際版のキーを `api.minimaxi.com` に投げても認証が落ちる。
`config.yaml` の既定は国際版。中国本土アカウントなら `video.minimax.base_url` を書き換えること。

ログイン後、**API Keys**（または Access）から新規キーを作る。支払い方法の登録が要る。

切り替えるには `config.yaml` の `video.provider` を `minimax` にするか、その場で：

```bash
python run.py --stage 2 --video-provider minimax
```

### 確証レベル

非同期3ステップ（`POST /v1/video_generation` → `GET /v1/query/video_generation` →
`GET /v1/files/retrieve`）という構成は複数の情報源と一致したが、**公式ドキュメントに
直接到達できていないため、リクエストの項目名までは確認できていない。**
初回は1カットだけ回してログで確かめること。

```bash
python run.py --cut 01 --stage 2 --video-provider minimax
```

項目名が違っていれば `config.yaml` の `image_field` / `duration_field` / `prompt_field` /
各パスを書き換えるだけで直る。コードには手を入れなくてよい。

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
  詳細は上の「ChatGPT Image と繋ぐ」を読むこと。
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
