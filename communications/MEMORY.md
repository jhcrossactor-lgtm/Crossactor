# MEMORY — Crossactor 意思決定記録

重要な決定を、何を決めたか・理由・却下した選択肢の3点で記録する。セッション開始時に必ず読む。

---

## 2026-08-24 — Plaud連携は CLI で導入する

**決めたこと**
Plaud の録音・文字起こし・AI要約を Cro が扱えるようにする。導入形態は **CLI**（`@plaud-ai/cli`）。
MCP サーバー（`@plaud-ai/mcp`）は採用しない。

**理由**
`AGENTS.MD` の判断軸「MCP接続は常時コンテキストコストを払う価値があるかで判断。一回学習すれば
済むならCLI優先」に従った。Plaud MCP は読み取り7ツールと軽量ではあるが、CLI で完全に同じデータを
取得できる。会議処理は都度発生の業務であり日次ルーティンではないため、常時ツール定義を積む理由がない。

**却下した選択肢**
- **MCPプラグイン導入**（`npx -y @plaud-ai/mcp@latest install`）— 公式スキル6本が同梱され設定は3分で済むが、
  常時コンテキストコストが発生する。会議処理が日次ルーティン化した時点で再検討する
- **MCPとCLIの併用** — カバー範囲は最大になるが二重管理になる。現時点の利用頻度に見合わない

**付帯方針**
- Plaud CLI は PostHog / Sentry のテレメトリを同梱している。会議内容を扱うため
  `PLAUD_TELEMETRY_DISABLED=1` と `DO_NOT_TRACK=1` で既定オフとする
- 音声ファイル・文字起こし全文はリポジトリにコミットしない。議事録として要約したもののみ残す

**成果物**
- `skills/plaud-ops/SKILL.md` — 録音取得から `communications/logs/` への記録までの手順
- `skills/plaud-ops/setup.md` — ローカル導入手順書

**残タスク**
ほせもやんがローカルで `npm i -g @plaud-ai/cli` → `plaud login` → `plaud recent -d 7 --json` を実施し、
実際の会議1本でスキルを通す。詰まった箇所は `setup.md` のトラブルシュートに追記する。
