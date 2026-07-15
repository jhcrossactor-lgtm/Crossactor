# MEMORY.md

Croが維持する記憶。セッション開始時に必ず読む。重要な決定・保留中TODOを記録する。

---

## 保留中TODO（未完了・要フォロー）

- [ ] **Supabase MCP のローカルOAuth承認**（保留：ローカルを今開けないため後々）
  - 手順：①PR #2 をマージ → ②ローカルのClaude Codeでリポジトリを開く → ③`/mcp` で `supabase-fujihisa` をOAuth承認
  - 設定ファイルはリポジトリに反映済み。残るは「承認クリック」だけ
  - 書き込みが要るときだけ `supabase-write` を明示承認

---

## 決定事項ログ

### 2026-07-15 — Supabase MCP セキュリティ設定
- **何を決めたか**：Supabase MCPを read_only 既定＋案件別分離＋都度確認（ask）に統一
- **構成**：`supabase-fujihisa`（read_only=true・常用）／`supabase-write`（read_only無し・明示時のみ）。両方 `project_ref=rpmiecrhnjpvgntltftd` に固定
- **理由**：普段は読み取り専用で誤操作を構造的に防ぎ、書き込みは意図的に選んだときだけ効かせるため
- **却下した選択肢**：CRO用に別プロジェクトを今作る案 → 現状フジヒサ1件のみのため不要、将来自社DBを立てたときに追加
- **成果物**：PR #2（`.mcp.json` / `.claude/settings.json` / `.mcp.json.example` / `CLAUDE.md`）
