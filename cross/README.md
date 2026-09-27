# AI相棒クロス — Phase1

SNS動画用の「見せる」音声対話AI。仕様は `CLAUDE.md`、人格は `persona.md`。

## 進捗
- [x] ① テキスト会話（`/chat` Edge Function + `index.html` テロップ）— 2026-09-26 動作確認済み
- [x] ② 音声合成（`/tts` Azure Speech、文単位キュー再生、口パク用Analyser）— 2026-09-27 声が出ることを確認
- [x] ③ 音声認識（Web Speech API、ウェイクワード「クロス」、割り込み）— 実装済み、動作確認待ち
- [ ] ④ 3Dの部屋と2Dキャラ（three.js、ビルボード、カメラドリー）

## 構成
```
cross/
├── index.html                 # フロント（単一ファイル）
├── config.js                  # 公開設定（キャラ名・モデル・色・voice）
├── config.env.js              # .env から自動生成。Supabase URL / key（gitignore、手で触らない）
├── config.local.js            # 自分用の上書き設定。更新で消えない（gitignore）
├── persona.md / knowledge.md  # system prompt の素材
├── .env                       # サーバー側シークレット（gitignore）
├── scripts/deploy.mjs         # prompt.ts 生成 → Secrets → deploy
└── supabase/functions/chat/   # Claude ストリーミング中継（SSE）
```

## セットアップ（初回）
前提：Node 18+、[Supabase CLI](https://supabase.com/docs/guides/cli)、Supabase プロジェクト1つ、Anthropic APIキー。

1. `.env.example` を `.env` にコピーして値を入れる
   - `ANTHROPIC_API_KEY`（必須）
   - `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY`（Supabase ダッシュボード → Project Settings → API Keys →「Publishable and secret API keys」タブの `sb_publishable_...`。Legacy タブの anon key は使わない）
   - `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` は Step② から
2. Supabase プロジェクトにリンク
   ```
   supabase login
   supabase link --project-ref <YOUR_PROJECT_REF>
   ```
3. 生成・Secrets 登録・デプロイ（1コマンド）
   ```
   node scripts/deploy.mjs --secrets
   ```
   2回目以降、キーが変わっていなければ `node scripts/deploy.mjs` でよい。
   persona.md / knowledge.md を変えたときも同じコマンドで反映する。
4. `index.html` をブラウザで開く（ダブルクリックで可。全画面 F11 推奨）
   - 下の入力欄に日本語で話しかける → 字幕にストリーム表示
   - `M` または右上チップで Sonnet 切替。「分析／事業／計算／比較」を含む発話は自動で上位モデル
   - `S` 字幕ON/OFF、`T` 入力欄ON/OFF、`Esc` 中断
   - DevTools コンソールに model・首トークンまでのms・キャッシュ読み取りトークン数を出す

## 更新（2回目以降）
GitHub の最新版を取り込む。`.env` と `config.local.js` は消えない。
```
powershell -ExecutionPolicy Bypass -File scripts\update.ps1
node scripts\deploy.mjs
```

## Step② 音声合成のセットアップ
1. Azure ポータルで「Speech」リソースを作成（リージョンは Japan East 推奨、価格レベル Free F0 で可）
2. リソースの「キーとエンドポイント」から キー1 とリージョン名（例 `japaneast`）を `.env` に入れる
   ```
   AZURE_SPEECH_KEY=...
   AZURE_SPEECH_REGION=japaneast
   ```
3. `node scripts/deploy.mjs --secrets`（chat と tts の両方がデプロイされる）
4. `index.html` を開く → 最初に「クリックまたは Enter で開始」が出る（ブラウザの音声再生許可のため）→ 話しかける
- 声の種類・話速・高さは `config.js` の `voice` で変更。`enabled: false` で音声なし
- 再生中は Space か画面タップで即停止

### 自分用の設定は config.local.js に書く
`config.js` は更新（update.ps1）で上書きされる。声やサイズなど自分の好みは `config.local.js` を作って書く。
必要な項目だけ書けばよく、`config.js` に深くマージされる。
```js
window.CROSS_LOCAL = {
  voice: { engine: "voicevox", voicevox: { speaker: 16, speedScale: 1.1 } },
  subtitle: { scale: 1.2 },
};
```

### 声を選ぶ（V キー）
画面で `V` を押すと、日本語を話せる Azure の声の一覧（ネイティブ約8種＋多言語対応の声）が出る。
クリックで試聴、「この声にする」でそのブラウザに保存される。他の端末にも効かせるには表示される1行を `config.local.js` に書く。
元に戻すにはコンソールで `cross.voices.reset()`。

### VOICEVOX を使う場合（PC専用・不採用。参考として残置）
1. VOICEVOX を起動しておく（エンジンが `http://127.0.0.1:50021` で待ち受ける）
2. `config.local.js` に `voice: { engine: "voicevox" }` を書き、`voicevox.speaker` で声を選ぶ（上の例）
3. 画面は `file://` ではなく localhost で開く（ブラウザの制限）
   ```
   node scripts\serve.mjs
   ```
   → ブラウザで http://localhost:8787
- キャラごとに利用規約が異なる。動画公開・販売時はクレジット表記（例「VOICEVOX:九州そら」）と各キャラの規約を確認すること
- スマホからは使えない（エンジンがPC内にあるため）。スマホ運用時は `engine: "azure"` に戻す

### 動作確認（Step②）
- [ ] 返答の最初の一文が、字幕の表示とほぼ同時に鳴り始める（コンソール `[tts] ready XXXms`）
- [ ] 文と文の間が不自然に空かない
- [ ] 再生中に Space で止まり、すぐ次の発話を受け付ける
- [ ] 球体が声に合わせて脈打つ（口パクの仮表現）

## Step③ 音声認識
- 画面は **http://localhost:8787**（`node scripts\serve.mjs`）か https で開く。マイクは file:// では使えない
- 「クリックまたは Enter で開始」でマイクの許可が出るので「許可」
- 使い方：「クロス、おはよう」のように呼びかけて話す。返答が終わってから20秒は呼び名なしで続けて話せる。無発話が続くと待機（idle）に戻る
- クロスが喋っている間はマイクを止めている（自分の声を拾わない）。割り込みは Space か画面タップ
- 右上の 🎙 チップ：`on` 聞き取り中 ／ `off` 停止（クリックか L キーで切替）／ 赤字はマイク拒否など
- 認識ゆれ（「くろす」「黒須」など）は `config.js` の `wakeWordAliases` で吸収。誤反応は仕様として許容

### 動作確認（Step③）
- [ ] 「クロス、おはよう」→ 字幕に「おはよう」→ 声で返答
- [ ] 返答直後に呼び名なしで続けて質問できる
- [ ] 返答中に自分の声を拾って暴走しない（テレビの音などがある部屋でも試す）
- [ ] 20秒黙ると idle に戻り、以後は呼び名が要る
- [ ] 認識途中の文字が薄い字幕で流れる

## 収益報告（Notion 連携）
クロスに「売上どう？」「今月の入金は？」「収益報告して」のように聞くと、Notion の収益管理DBを読んで声で報告し、画面に数字の表（情報パネル）を重ねる。

セットアップ：
1. https://www.notion.so/profile/integrations で「内部インテグレーション」を作り、シークレット（`ntn_...`）を控える
2. Notion で「売上DB」と「LINEスタンプ売上DB」を開き、右上「…」→「接続」→ 作ったインテグレーションを追加（両方）
3. `.env` に追記して `node scripts\deploy.mjs --secrets`
   ```
   NOTION_TOKEN=ntn_...
   NOTION_SALES_DS=売上DBのデータソースID
   NOTION_LINE_DS=LINEスタンプ売上DBのデータソースID
   ```
   データソースIDは Notion の DB ページで「…」→「データソースを管理」に表示される UUID（DBページの URL 末尾の ID とは別物）
- 反応する語：売上 / 収益 / 入金 / 請求 / 報告 / 利益 / 見積 など（`_shared/notion_revenue.ts` の `REVENUE_KEYWORDS`）
- 未設定なら「連携が未設定」と短く答える。数字は作らない
- パネルは喋り終わって数秒で閉じる（`config.js` の `panelLingerMs`）。Space やタップでも閉じる

## 動作確認（Step①）
- [ ] 5往復続けて破綻しない（履歴は直近10往復を送る）
- [ ] 「事業の話やけど」と言うと `[chat] model: claude-sonnet-5` になる
- [ ] 1往復目のレスポンスが体感2秒以内（首トークンのmsを確認）

## よくある間違い
- `.env` の `SUPABASE_URL` は `https://<20文字のref>.supabase.co`。末尾の `.supabase.co` を落とすと画面に「Failed to fetch」が出る。`node scripts/deploy.mjs --build` が形式を検証して警告する
- Supabase の API Keys は「Publishable and secret API keys」タブの `sb_publishable_...` を使う。Legacy タブの anon key ではない
- Anthropic のキー作成画面の「スコープ」は「デフォルトワークスペース」を選ぶ
- ブラウザが古い画面を出すときは Ctrl+F5 で強制再読み込み

## 補足
- 認可：Edge Function 内で `apikey` ヘッダを publishable キーと照合する（新キーは JWT ではないため `verify_jwt = false`）。publishable キーは公開前提の値なので、公開URLで運用する場合は `.env` に `CROSS_ACCESS_KEY`（合言葉）を設定して `--secrets` で送る。画面側は `x-cross-key` ヘッダで送る
- プロンプトキャッシュは system に `cache_control` を付けているが、Haiku 4.5 は最小キャッシュ長（約2048トークン）未満だと効かない。knowledge.md が育つと効き始める
