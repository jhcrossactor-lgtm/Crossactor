#!/usr/bin/env bash
# claude.ai アカウント同期スキル（~/.claude/skills/synced/）のうち、
# ほせもやんの自作スキルだけをリポジトリの .claude/skills/ にコピーする。
#
# claude.ai 側 → リポジトリ の一方向。逆向きに書き戻す手段は存在しない
# （communications/MEMORY.md 2026-09-16 参照）。claude.ai で直したら必ずこれを流す。
#
#   bash scripts/sync_account_skills.sh          # コピーを実行
#   bash scripts/sync_account_skills.sh --check  # 差分があるかだけ見る（CI向け）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO/.claude/skills"

# Anthropic 標準スキル。全PCへ自動配布されるので取り込まない。
# LICENSE.txt を持つもの（docx/pdf/pptx/xlsx/skill-creator/theme-studio）も同様に除外する。
STOCK=" docs import-memory morning "

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

shopt -s nullglob
SRCS=("$HOME"/.claude/skills/synced/*/)
if [[ ${#SRCS[@]} -eq 0 ]]; then
  echo "同期スキルが見つからない: ~/.claude/skills/synced/ が空だ。claude.ai にログイン済みか確認しろ。" >&2
  exit 1
fi

changed=0
copied=0
for base in "${SRCS[@]}"; do
  for dir in "$base"*/; do
    name="$(basename "$dir")"
    [[ "$STOCK" == *" $name "* ]] && continue
    [[ -e "$dir/LICENSE.txt" ]] && continue
    [[ -e "$dir/SKILL.md" ]] || continue

    if [[ ! -d "$DEST/$name" ]] || ! diff -rq "$dir" "$DEST/$name" >/dev/null 2>&1; then
      changed=1
      echo "更新: $name"
      if [[ $CHECK -eq 0 ]]; then
        rm -rf "${DEST:?}/$name"
        cp -r "$dir" "$DEST/$name"
        copied=$((copied + 1))
      fi
    fi
  done
done

find "$DEST" -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

if [[ $CHECK -eq 1 ]]; then
  [[ $changed -eq 0 ]] && { echo "差分なし。リポジトリは claude.ai と一致している。"; exit 0; }
  echo "差分あり。bash scripts/sync_account_skills.sh を流してコミットしろ。" >&2
  exit 1
fi

if [[ $copied -eq 0 ]]; then
  echo "差分なし。コピーするものは無かった。"
else
  echo "${copied}件コピーした。git status で確認してコミットしろ。"
fi
