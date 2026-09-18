# Phase 0：環境構築・法令基盤の入口
- [x] git init、.gitignore（patterns/inbox, patterns/own, law/cache, *.pdf）※Crossactorリポジトリ iegen/ 配下で管理（2026-09-18）
- [x] Python環境（uv推奨）：pypdf, pdfplumber, pymupdf, ezdxf, shapely, ortools, pyyaml ※pyproject.toml 作成、uv で導入確認済み（2026-09-18）
- [ ] Obsidian接続：law/obsidian_link.md を埋め、対象ノートを1件読めることを確認
- [ ] 質疑応答集7版をローカル取得（Drive for desktop）→ law/osaka/qa/v7/src.pdf
- [ ] 文字データ有無を判定 → なければ日本語OCR（エンジン比較して選定）
- [ ] 7版の目次から qa_index_v7.json 作成（schemaは6版と同じ）
- [ ] 6版と突合し law/osaka/qa/diff_v6_v7.md（新設・削除・変更）
- [ ] 数値・条番号のOCR誤読チェック（原本画像と照合）
- [ ] e-Gov APIの仕様確認、施行令23条を1件取得してrules/stair.yamlをverified化

## 環境ブロッカー（クラウド実行時）
- Obsidian接続・7版PDF取得・e-Gov取得は本クラウド環境から不可（egress 403 / ローカル資産）。以降はローカル Claude Code で実行する
- G0 未回答（Vaultパス／法令ノートフォルダ／7版PDFローカル保存先）
