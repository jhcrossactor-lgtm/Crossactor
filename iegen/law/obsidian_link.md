# Obsidian接続（実行時に設定）
- Vault: `G:\ClaudeLocal\vault` ※デスクトップの「Claude - Vault」ショートカット（作業ディレクトリ）から特定。要確認
- 対象フォルダ: `（法令ノートのフォルダ名を記入）`
- 質疑応答集7版: Vault内に格納済みとのこと（2026-09-18 ほせもやん談）。ローカル起動時に場所を特定し、文字データ有無を確認する
- 紐付け: frontmatterの `law_id`（e-Gov法令ID）・`article`（条番号）で rules/ と照合
- 未接続時: e-Gov＋質疑応答集で動作
- クラウド実行環境（Claude Code on the web）からは到達不可。Phase 0 以降はローカルで実行
