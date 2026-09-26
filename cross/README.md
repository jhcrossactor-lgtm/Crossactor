# AI相棒クロス — Phase1

SNS動画用の「見せる」音声対話AI。仕様は `CLAUDE.md`、人格は `persona.md`。

## 進捗
- [x] ① テキスト会話（`/chat` Edge Function + `index.html` テロップ）— 2026-09-26 動作確認済み
- [ ] ② 音声合成（`/tts` Azure Speech、文単位キュー再生、口パク用Analyser）
- [ ] ③ 音声認識（Web Speech API、ウェイクワード「クロス」、割り込み）
- [ ] ④ 3Dの部屋と2Dキャラ（three.js、ビルボード、カメラドリー）

## 構成
```
cross/
├── index.html                 # フロント（単一ファイル）
├── config.js                  # 公開設定（キャラ名・モデル・色・voice）
├── config.local.js            # .env から生成。Supabase URL / anon key（gitignore）
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
