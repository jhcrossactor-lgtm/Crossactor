# MEMORY — Crossactor 重要記憶

Croがセッション開始時に必ず読む。重要な決定・失敗・成功体験を即記録する。
新しい項目は上に追記（新しいものが上）。

---

## 2026-07-14 — X週次スキルスカウトの無人Routine化（失敗と成功の全記録）

### 成功（最終状態）
- **X週次スキルスカウトが本番稼働**。毎週水曜 09:02 JST にクラウドで自動実行 → `#ai` にレポート配信。
- 実弾テスト成功：トークン・X API取得・絞り込み・jq整形・Webhook投稿まで全経路が生きていることを確認済み。
- 構成：**自己完結型Routine**（手順を全部プロンプトに内蔵。スキルファイル・MCPコネクタ・リポジトリに一切依存しない。Bash+curl+環境変数だけで完結）。

### 今回ハマった罠と対処（＝再利用可能な教訓）
1. **環境変数はEnvironment設定に入れる。セッション内 `export` は毎回消える。**
   - `X_API_BEARER_TOKEN` / `SLACK_WEBHOOK_URL` は環境（Crossactor env）の「環境変数」欄に登録して初めて永続。
2. **無人RoutineセッションにはMCPコネクタ（Slack等）が注入されない。**
   - MCP経由（create_trigger）で作ったRoutineは、Web UIで作った他Routineと違いSlackコネクタもgitソースも付かない。
   - → だから `slack_send_message` は無人Routineで使えない。**Slack投稿はIncoming Webhook（curl POST）方式にした。**コネクタ非依存。
3. **無人Routineセッションにはリポジトリがcloneされず、`.claude/skills/` のスキルも存在しない。**
   - → スキル依存をやめ、手順をRoutineプロンプトに丸ごと内蔵（自己完結化）。これが最も堅牢。
4. **許可ドメイン（Allowed domains）に叩く先を全部入れる。**
   - `api.x.com` と `hooks.slack.com` の両方。`hooks.slack.com` が抜けててWebhook POSTがブロックされ、スマホに「ブロックされた」通知が出た。
   - `api.twitter.com` はこの環境で遮断（HTTP 000）。**X APIは `api.x.com` を使う。**
5. **Slack Incoming Webhookは作成時にチャンネル固定。** 発行したURLが `#ai` 紐付けだったので `#ai` に落ちた。配信先を変えるならWebhook再発行＋`SLACK_WEBHOOK_URL`差し替え。
6. **fire_trigger に重い指示テキスト（text）を付けると「suspicious payload（注入攻撃）」と誤検知され実行拒否される。** テスト発火は素で撃つ。
7. **update_trigger ではプロンプト本文やソースは編集できない**（name/cron/enabledのみ）。それらを変えるなら delete → create で作り直す。

### プラットフォーム知識（確認済み）
- クラウド版Claude Code（Routine/環境/環境変数）は**アカウント紐づけ・クラウド実行・端末不問**。全端末オフでも水曜に発火する。ローカルCLI版はデバイスごとで別物。
- `jq` はこの環境に有り（`jq -Rs '{text: .}'` でWebhook用JSONを安全生成できる）。

### 現行Routine ID
- `trig_019MwC1aYSe6TpU4Y6Lfpf6d`（X週次スキルスカウト／自己完結版, cron `2 0 * * 3`, env `env_01KY9St4P1P9531XtSjh1v1y`）

---
