---
name: x-skill-scout
description: X（旧Twitter）からClaudeの最新情報・エージェント設計思想・新しいskill/有用なskillの事例を週次で収集するスキル。「Xスキル調査」「今週のX情報」「スキルスカウト」と言われたら起動。毎週水曜のRoutineから呼び出される想定。
---

# X週次スキルスカウト

## 収集対象
- Claude本体の最新情報・アップデート
- エージェント設計思想（agentic pattern, orchestrator設計等）
- 新しいskill・有用なskillの事例

## 採用基準（両方満たすものだけ残す）
- `public_metrics.impression_count` が1万以上
- 著者の `public_metrics.followers_count` が1万以上

## 固定ウォッチ対象（基準未達でも毎週必ず確認）
- @ClaudeCode_UT
- @tetumemo
- @ozaken_AI
- @ai_Prompt_1144
- @kosuke_agos
- @MacopeninSUTABA
- @masahirochaen
- @Claude_Digest
- @Claudeai

上記アカウントは上記の採用基準を満たさなくても、直近1週間の投稿を毎週必ずチェックし「指定アカウント枠」として出力する（一般枠の上位2〜4件とは別枠）。

## 手順（X API v2、Bash toolでcurl実行）
1. 一般検索：`GET https://api.x.com/2/tweets/search/recent`
   - `query`: `(claude skill OR claude agent OR "claude code" OR "claude.ai skill") -is:retweet`
   - `tweet.fields=public_metrics,created_at,author_id`
   - `expansions=author_id`
   - `user.fields=public_metrics`
   - 認証: `Authorization: Bearer $X_API_BEARER_TOKEN`
   - search/recentは直近7日のみ対象（週次運用と相性◎）
2. 固定ウォッチ検索：`query`を `from:ClaudeCode_UT OR from:tetumemo OR from:ozaken_AI OR from:ai_Prompt_1144 OR from:kosuke_agos OR from:MacopeninSUTABA OR from:masahirochaen OR from:Claude_Digest OR from:Claudeai` に変えて同条件でもう1回叩く（クエリ長がAPI上限に当たる場合は2回に分割）
3. 一般検索側は採用基準を両方満たす投稿だけ残す。固定ウォッチ側は基準を適用せず全件対象
4. 宣伝・広告・重複ネタは除外
5. 一般枠は上位2〜4件に厳選。指定アカウント枠は各アカウントの直近投稿から見るべきものがあれば全部出す（無ければ「今週投稿なし」と明記）

### Routine実行時の前提（初回セットアップ時に一度だけ）
- **環境（Environment）の環境変数**に登録する（セッション内での`export`は毎回消えるので不可）：
  - `X_API_BEARER_TOKEN` … X API v2のBearerトークン
  - `SLACK_WEBHOOK_URL` … `#ai` に紐づいたSlack Incoming WebhookのURL（現行の配信先。Webhookのチャンネル差し替えはURL再発行で行う）
- Allowed domainsに以下を追加：
  - `api.x.com`（開発者ポータルで現行ベースURLを確認。`api.twitter.com`は本環境では遮断されているため使わない）
  - `hooks.slack.com`（Incoming Webhookの投稿先）
- この方式はSlack MCPコネクタに依存しない。無人Routineセッションに`mcp__Slack__`が無くても、Bash+curl+上記2つの環境変数だけで完結する。

## 出力（一般枠・指定アカウント枠とも1件ずつ、採用可否コメント付きでまとめる）
- 投稿リンク／投稿者（フォロワー数）
- 内容要約（本文の引用はしない、要約のみ）
- Crossactorのskill体系にどう活きるか
- 推奨度：採用 / 様子見 / 不要

## Slack配信（Incoming Webhook / curl方式）
上記の出力をまとめて `#ai` に **Slack Incoming Webhook** で投稿する。無人Routineでも確実に届くよう、MCPコネクタではなくBash+curlで叩く。Webhookは作成時に投稿先チャンネルが固定されるので（現行は`#ai`紐付け）、`SLACK_WEBHOOK_URL` にそのURLを入れておけば宛先指定は不要。配信先を変えたい場合は目的チャンネル宛のWebhookを再発行し、`SLACK_WEBHOOK_URL` を差し替える。

手順：
1. レポート本文を作ってファイルに書き出す（例：`/tmp/report.txt`）。
2. 本文を安全にJSONへ包む。`jq` があれば `jq -Rs '{text: .}'` が確実（改行・引用符のエスケープを自動処理）：
   ```bash
   jq -Rs '{text: .}' /tmp/report.txt > /tmp/payload.json
   curl -s -X POST -H 'Content-Type: application/json' \
     --data @/tmp/payload.json "$SLACK_WEBHOOK_URL"
   ```
   `jq`が無い環境では、本文を組み立てる段階で改行を`\n`・`"`を`\"`にエスケープした文字列を作り、`-d '{"text":"...本文..."}'` で送る。
3. curlの応答が `ok` かつHTTP 200なら成功。それ以外（`invalid_token`, `no_service` 等）はWebhookのURL失効か未設定なので、ほせもやんに通知する。

Routineは無人実行なのでその場での承認待ちはせず、投稿して終了。採用可否はユーザーが後からSlackスレッド返信 or 別途Claudeとのセッションで指示する。

## 承認後
承認された件のみ、該当skillの新規作成 or 既存skill（cro-mini配下等）への反映案を出す。未承認分は次週以降も再提示しない（週次ログとして扱う）。

## 精度の限界
impression_countはX側の既知の不具合で実際より低く出ることがある。極端に低い値のみで足切りせず、フォロワー数基準も併せて総合判断する。候補が無い週は「今週は基準を満たす候補なし」と正直に報告する。
