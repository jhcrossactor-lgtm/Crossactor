# CRO Scripts Scaffold

steipete/agent-scripts の構造を参考にした、CRO用スキル管理・CLIスクリプトの雛形。

## 統合方法
1. 中身を `jhcrossactor-lgtm/Crossactor` リポジトリのルートにコピー
2. 同内容を G:\マイドライブ\claude にも反映（既存の二重管理ルール通り）
3. リポジトリルートで `git config core.hooksPath hooks` を実行（コミット前検証を有効化）
4. 既存スキル（cro-mini, deep-verify, seo-lp, grilling 等）を `skills/` 配下に集約する場合、各SKILL.mdをこの形式に合わせる
5. `scripts/validate-skills` で既存スキルのYAML frontmatterを一括チェック
6. 新規スキルは `scripts/new-skill <name>` で雛形作成

## ファイルの役割
- `AGENTS.MD` — Claude Code / Codex 共通ルール。`~/.claude/CLAUDE.md` からシンボリックリンクする運用も可
- `skills/<name>/SKILL.md` — description はルーティング専用の短いトリガー句、本文は手順/参照
- `scripts/validate-skills` — SKILL.mdのYAML frontmatter（name/description必須）を検証
- `scripts/new-skill` — 新規スキル雛形を生成
- `hooks/pre-commit` — コミット前に自動検証（要有効化）

## 判断軸（MCP vs CLI）
常時コンテキストコストを払う価値があるMCPか、一回ヘルプ叩けば以後タダで使えるCLIで足りるか、で切り分ける。ルーティン業務はClaude Codeで初回構築→動作確認後にCLI化するのが基本フロー。

## 元ネタ
steipete/agent-scripts (https://github.com/steipete/agent-scripts) の構造・思想を参考に、CRO運用向けに再構成。1Password連携やtmux運用など個人的ルールは含めていない。
