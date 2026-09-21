#!/usr/bin/env bash
# 未決議題があれば systemMessage として表示する。
# SessionStart と Skill 起動時（PreToolUse）から呼ばれる。
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-$PWD}"
f="$root/communications/agenda/pending.md"
[ -s "$f" ] || exit 0
jq -Rs '{systemMessage: ("\n" + .)}' < "$f"
