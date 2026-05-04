---
name: ai-employee
description: テーマを1つ与えると、リサーチ→レポート／スライド／アジェンダの3並列生成までを5分前後で完了する高速版AI社員ワークフロー。承認はリサーチ計画の1回のみで、それ以降は完全自律で完了まで進む。トリガー: 「[テーマ] でAI社員を動かして」「AI社員に任せる」「ai-employee」「テーマ: [...] でリサーチからアジェンダまで」
---

# AI社員ワークフロー（高速版）

## Phase 1: テーマ受領
1. ユーザーからテーマを受け取る
2. `output/status.json` を `running` で初期化（memory の ai_employee_rules.md 参照）

## Phase 2: リサーチ計画の作成・承認
1. テーマに基づきリサーチ計画を作成（観点3個・調査方針・想定アウトプット）
2. **AskUserQuestion** でユーザーに確認（これが唯一の確認ポイント）
3. 承認後、`output/status.json` を更新

## Phase 3a: researcher エージェント起動
- `output/research-notes.md` を生成させる
- 観点3個固定・WebSearch 3回固定・WebFetch 禁止（高速版）
- 完了後 `output/status.json` を更新

## Phase 3b: テンプレートコピー
- `.claude/templates/presentation-template.html` を `output/presentation.html` にコピー
- `output/status.json` を更新

## Phase 3c: 3並列起動（reporter / slide-maker / agenda-planner）
以下を**同時に**バックグラウンド起動：
- **reporter** → `output/report.md`
- **slide-maker** → `output/presentation.html`（テンプレのプレースホルダ差し替え）
- **agenda-planner** → `output/agenda.md`

各完了時に `output/status.json` を更新

## Phase 4: 完了処理
1. `output/status.json` を `done` に更新
2. ブラウザで `output/presentation.html` を自動オープン
   - Windows: `cmd.exe /c start output/presentation.html`
3. 成果物を `成果物/[テーマ名]/` にコピー（memory の ai_employee_rules.md 参照）
4. `INDEX.md` を更新

## 実行ルール
- AskUserQuestion はPhase 2の1回のみ
- EnterPlanMode は使わない
- エラーで止めない（ブラウザオープン失敗等は手動案内で継続）
- status.json の更新は memory の ai_employee_rules.md に従う
