# スキル置き場

リポジトリをクローンした全PCで使えるスキル。**業務スキルはここに置く。**

## 2種類ある

| 種別 | 正本 | 更新方法 |
|---|---|---|
| **リポジトリ生まれ** | ここ | 直接編集してコミット |
| **claude.ai ミラー** | claude.ai アカウント側 | claude.ai で編集 → `bash scripts/sync_account_skills.sh` → コミット |

**リポジトリ生まれ**：`ai-editorial` `ai-employee` `score-rename` `x-skill-scout` `マーカー`

**claude.ai ミラー**：`adobe-invoice-download` `arch-reg-sync` `cro-mini` `deep-verify`
`event-lp` `grilling` `haichi-tool` `promo-design` `seo-lp` `writing-great-skills`

## claude.ai ミラーの注意

claude.ai アカウント側スキルへ**書き戻す手段は存在しない**（CLI・プラグイン経由とも不可。
`communications/MEMORY.md` 2026-09-16 参照）。同期は claude.ai → リポジトリ の一方向。

そのため、ミラー側のファイルをここで直接編集しても claude.ai 側には反映されず、
次に同期スクリプトを流した時点で**上書きされて消える**。ミラー側を直すときは必ず
claude.ai のスキル編集画面で直し、そのあと同期スクリプトを流すこと。

ミラーされたスキルは claude.ai 経由では `anthropic-skills:` 接頭辞付きで、
リポジトリ経由では接頭辞なしで見える（例：`/cro-mini` と `/anthropic-skills:cro-mini`）。
中身が同じなのでどちらを呼んでも結果は同じだが、**ズレていたら同期スクリプトを流していない**
サインなので、`bash scripts/sync_account_skills.sh --check` で確認する。

## 取り込まないもの

Anthropic 標準スキル（`docx` `pdf` `pptx` `xlsx` `skill-creator` `theme-studio`
`docs` `import-memory` `morning`）は全PCへ自動配布されるため対象外。
同期スクリプトが LICENSE.txt の有無と除外リストで自動的に弾く。

## 新しくスキルを作るとき

`~/.claude/skills/` の個人スキルには**置かない**。PC間で同期されず、そのPCが使えなくなると
業務が止まる（2026-09-21 に `/マーカー` で実際に起きた）。ここに置いてコミットする。
