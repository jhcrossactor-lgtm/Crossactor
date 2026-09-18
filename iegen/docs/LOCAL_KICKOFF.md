# ローカル起動手順（Phase 0 再開用）

クラウド側のセットアップは完了済み（ブランチ `claude/new-session-geuhry`、`iegen/` 配下）。
以下をローカルで実行すれば Phase 0 の残りから自走できる。

## 1. 取得
既に `%USERPROFILE%\Crossactor` にクローンがある場合（通常こちら）:
```powershell
cd $env:USERPROFILE\Crossactor
git fetch origin claude/new-session-geuhry
git checkout claude/new-session-geuhry
cd iegen
uv venv; uv pip install -e .   # または uv pip install pypdf pdfplumber pymupdf ezdxf shapely ortools pyyaml
claude
```
クローンが無い場合:
```powershell
cd $env:USERPROFILE
git clone -b claude/new-session-geuhry https://github.com/jhcrossactor-lgtm/Crossactor.git
cd Crossactor\iegen
claude
```

## 2. 最初に貼るプロンプト
```
CLAUDE.md・docs/SOW.md・docs/CONTEXT.md・tasks/phase0.md・tasks/log.md を読め。
Obsidian Vault は G:\ClaudeLocal\vault（law/obsidian_link.md）。Vault内の法令ノートフォルダと質疑応答集7版の場所を特定し、
law/obsidian_link.md を確定させてから tasks/phase0.md の未完了項目を上から実行。
確認ゲートは docs/CONTEXT.md の G0〜G6 のみ。Phase 0 完了時に diff_v6_v7.md の要約を3行で報告し、Phase 1 へ進め。
```

## 3. 注意
- 7版がVault内でテキスト化済みなら OCR は不要。スキャンPDFのままなら G1（OCRエンジン選定）で止まる
- e-Gov API はローカルからは到達可（クラウドは403）
