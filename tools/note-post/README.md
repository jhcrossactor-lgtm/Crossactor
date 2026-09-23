# note-post

noteへの記事自動投稿CLI。topics.csv → Claude APIで記事生成 → 自己チェック → OpenAIで差し込み画像生成 → noteに下書き保存（在庫）→ **人が選んで** 公開。

## セットアップ（ローカルPC）

```bash
cd tools/note-post
npm install
npx playwright install chromium
export ANTHROPIC_API_KEY=...        # 必須
export OPENAI_API_KEY=...           # 任意（未設定なら画像なしで続行）
export SLACK_WEBHOOK_URL=...        # 任意（未設定なら通知はログ出力のみ）
```

## 使い方

```bash
node src/cli.js login              # ブラウザが開く → 手動ログイン → ターミナルでEnter → ~/.note-state.json 保存
node src/cli.js run                # 1本生成してnoteに下書き保存 → 在庫に追加（公開はしない）。cronで毎日回す想定
node src/cli.js list               # 確認待ち在庫の一覧（番号・タイトル・下書きURL・NG指摘）
node src/cli.js publish <番号>      # 選んだ在庫を公開（note上で手直しした内容のまま公開）
node src/cli.js publish <番号> --force  # 自己チェックNGの在庫を、確認の上で公開
node src/cli.js reject <番号>       # 見送り（note上の下書きは残るので不要なら手動削除）
node src/cli.js run --dry-run      # 動作確認用。下書き保存はするが在庫・topics・1日枠に影響しない
node src/cli.js propose [件数]      # ジャンルごとにテーマ案を出す（Slack通知）
node src/cli.js proposals          # 未回答のテーマ案一覧
node src/cli.js accept 1 3 5       # テーマ案を採用 → topics.csv に追加
node src/cli.js decline 2 4        # テーマ案を不採用
```

### 運用の流れ

1. `run` が毎日1本、下書きを作って在庫に積む。**確認待ちが残っていても作り続ける**
2. 追加のたびにSlackへ「在庫追加 #番号・タイトル・下書きURL・在庫本数」を通知
3. ほせもやんが note 上で下書きを読む。直したければ note 上でそのまま直す
4. 出したいものを `publish <番号>` で公開 → 公開URLを posted.csv に記録、Slack通知

| 状態（posted.csv の status） | 意味 |
|---|---|
| `pending` | 確認待ち在庫（自己チェックOK） |
| `pending_ng` | 確認待ち在庫（自己チェックNG。公開には `--force`） |
| `published` | 公開済み（`url` / `published_at` に記録） |
| `rejected` | 見送り |
| `dry_run` | 動作確認の記録（在庫ではない） |

- **1日1本**: `run` の生成も `publish` の公開も、それぞれ1日1本まで（JST）
- `STOP` ファイルを置くと `run` / `publish` は即終了（`touch STOP` / `rm STOP`）
- 生成記事は `out/YYYY-MM-DD-N.md`、チェック結果は `.check.json` にも保存される

## ジャンル（genres.json）

| ID | ジャンル | 有料 | アフィリエイト |
|---|---|---|---|
| `ai-smb` | 小さな会社のAI活用 | 有料（前半無料） | なし |
| `arch-ai` | 建築・不動産×AI／3Dパース | 有料（前半無料） | なし |
| `affiliate` | ASPサービス紹介 | 無料 | あり |

- `run` はジャンルを上から順にローテーションする（前回の次のジャンルで、未処理テーマがあるもの）
- 読者像・切り口・トーン・禁止ルールは genres.json に書いてあり、記事生成と自己チェックの両方に渡る
- `enabled: false` でジャンルを休止できる
- **有料ジャンルの `paid.price` は未設定（null）**。null のままだと下書きは作れるが `publish` できない

### 有料記事

- Claude が無料部分と有料部分の境目に区切りを1つ置く → 本文には `paywallText`（「ここから有料」）の行として入る
- `publish` 時に「有料」を選び、価格を入れ、区切りの行の直後に有料ラインを置く
- 区切りがない・2つ以上ある・無料部分が400字未満 → 自己チェックNG

### アフィリエイト（affiliates.csv）

```
id,name,url,category,description
svc1,サービス名,https://px.a8.net/...,スクール,特徴・向いている人・注意点（Claudeはここに書いてあること以外を書かない）
```

- Claude は商品IDだけを本文に置き、**URLは書かない**。システムがリンクに置き換え、リンク名に「（PR）」を付ける
- 記事の先頭に `prNotice`（「※本記事はアフィリエイト広告（PR）を含みます。」）を自動で入れる（ステマ規制対応）
- 本文に生のURLがある・リストにないIDを使った・商品リンクがない → 自己チェックNG
- affiliates.csv が空ならアフィリエイトジャンルは飛ばす

### テーマ提案（proposals.csv）

- `run` のあと、未処理テーマが2件未満のジャンルがあれば、Claude がそのジャンルのテーマ案を3件ずつ出してSlackに送る
- 未回答の案が残っている間は追加提案しない
- `accept` したものだけ topics.csv に入る（AIが勝手にテーマを増やすことはない）

## 差し込み画像（OpenAI）

1. Claudeが記事内の画像を入れたい位置に `<!-- image: 英語プロンプト | alt: 日本語説明 -->` を書く（最大 `NOTE_IMAGE_COUNT` 枚）
2. 自己チェックはこの画像指示も審査する（実在人物・ロゴ・作風模倣はNG）
3. **チェックOKのときだけ** OpenAI Images API（既定 `gpt-image-2`、1536x1024、quality medium）で生成 → `out/…-imgN.png`
4. noteエディタの「+」→「画像」→ファイル選択で、マーカー位置に順にアップロード

- 画像生成に失敗した分はその画像だけ省いて続行する（Slack通知）
- 自己チェックNGの在庫は画像なし（`--force` で公開する場合も画像なし）
- dry-run では自己チェックNGでも画像を作る（パイプライン確認のため）
- ローカルの `out/…md` ではマーカーが `![alt](…-imgN.png)` に置き換わる

## topics.csv

```
genre,theme,reader,message,tags,status
ai-smb,テーマ,想定読者,伝えたいこと,タグ1;タグ2,
```

status が空の行から、ローテーション順のジャンルのものを1件処理する。タグ区切りは `;`。

## 失敗時

| 事象 | 終了コード | 動作 |
|---|---|---|
| ログイン切れ（ログイン画面へリダイレクト / state未作成） | 2 | Slack通知 → `login` をやり直す |
| セレクタ不一致（UI変更） | 2 | Slack通知 + `out/error-*.png` 保存 → `selectors.json` を修正 |
| その他（API等） | 1 | Slack通知 |

## selectors.json

note UIのセレクタはすべてここに分離している。**現時点の値は実画面で未検証（確証なし）**。
初回は `NOTE_HEADLESS=0 node src/cli.js run --dry-run` でブラウザを見ながら確認し、不一致なら DevTools で拾って差し替える。

## 環境変数

| 変数 | 既定 |
|---|---|
| `NOTE_POST_MODEL` | `claude-opus-5` |
| `NOTE_TOPIC_LOW` | `2`（ジャンルごとの未処理テーマがこれ未満で提案） |
| `NOTE_PROPOSE_PER_GENRE` | `3` |
| `NOTE_IMAGE_COUNT` | `2`（`0` で画像無効） |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` |
| `OPENAI_IMAGE_QUALITY` | `medium`（`low` / `high` / `auto`） |
| `NOTE_HEADLESS` | `1`（`0` でブラウザ表示） |
| `NOTE_STATE_PATH` | `~/.note-state.json` |
| `NOTE_TOPICS_PATH` / `NOTE_POSTED_PATH` / `NOTE_PROPOSALS_PATH` / `NOTE_GENRES_PATH` / `NOTE_AFFILIATES_PATH` / `NOTE_STOP_PATH` / `NOTE_OUT_DIR` / `NOTE_SELECTORS_PATH` | このディレクトリ配下 |

Claude APIはサーバー側フォールバック（`fallbacks: "default"`）を有効にしている。モデルが応答を拒否した場合、APIが自動で別モデルで再実行する。

## テスト

ダミーnote画面（`test/fake-note.js`）とモックLLMで、login / dry-run（画像差し込み含む）/ 在庫積み上げ / 番号指定公開（note上の手直し保持）/ NG在庫と --force / reject / ジャンルローテーション / 有料ライン・価格設定 / 価格未設定で公開不可 / アフィリエイト展開とPR表記 / ルール違反NG / テーマ提案→採用 / 画像0枚 / STOP / ログイン切れ / セレクタ不一致 を検証する。

```bash
npm test                       # GUIのある環境
xvfb-run -a npm test           # ヘッドレスLinux
```
