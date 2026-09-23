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
theme,reader,message,tags,status
テーマ,想定読者,伝えたいこと,タグ1;タグ2,
```

status が空の先頭行を1件処理する。タグ区切りは `;`。

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
| `NOTE_IMAGE_COUNT` | `2`（`0` で画像無効） |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` |
| `OPENAI_IMAGE_QUALITY` | `medium`（`low` / `high` / `auto`） |
| `NOTE_HEADLESS` | `1`（`0` でブラウザ表示） |
| `NOTE_STATE_PATH` | `~/.note-state.json` |
| `NOTE_TOPICS_PATH` / `NOTE_POSTED_PATH` / `NOTE_STOP_PATH` / `NOTE_OUT_DIR` / `NOTE_SELECTORS_PATH` | このディレクトリ配下 |

Claude APIはサーバー側フォールバック（`fallbacks: "default"`）を有効にしている。モデルが応答を拒否した場合、APIが自動で別モデルで再実行する。

## テスト

ダミーnote画面（`test/fake-note.js`）とモックLLMで、login / dry-run（画像差し込み含む）/ 在庫積み上げ / 番号指定公開（note上の手直し保持）/ NG在庫と --force / reject / 画像0枚 / STOP / ログイン切れ / セレクタ不一致 を検証する。

```bash
npm test                       # GUIのある環境
xvfb-run -a npm test           # ヘッドレスLinux
```
