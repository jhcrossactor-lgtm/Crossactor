# Inspo MCP 導入記録

最終更新：2026-09-16

デザイン系スキル（promo-design / event-lp / seo-lp）に、実装前の実在サイト参照を義務付けるための
Inspo MCP 導入記録と、claude.ai スキル編集画面への貼り付け用テキスト。

---

## 1. 導入コマンド

ローカル環境で1回だけ実行する（user scope）。

```bash
claude mcp add --transport http inspo https://inspomcp.dev/api/mcp --scope user
```

実行後、`claude` を起動して `/mcp` → `inspo` を選び **OAuth認証を完了させる**。
認証しないと `! Needs authentication` のままツールを呼べない。

確認：

```bash
claude mcp list
# inspo: https://inspomcp.dev/api/mcp (HTTP) - connected
```

### 注意：Claude Code on the web / クラウドセッションでは使えない

クラウド実行環境は egress ポリシーで `inspomcp.dev:443` への CONNECT を 403 拒否する。
Inspo MCP は **ローカル実行時のみ利用可能**。クラウド側でスキルが発火した場合は
取得に失敗するので、各スキルに書いたとおり「Inspo未参照」と明記して続行する。

---

## 2. ツール一覧（15件・全て read-only）

2026-09-16 時点。用途はツール名からの推定を含む（公式descriptionは未取得）。

| # | ツール | 用途 | 属性 |
|---|---|---|---|
| 1 | `search_screens` | キーワード・条件で実在サイトの画面を検索（**起点**） | read-only |
| 2 | `get_screen` | 画面1件の詳細取得 | read-only |
| 3 | `get_design_system` | 配色・フォント・トークンの抽出 | read-only, open-world |
| 4 | `find_similar` | 指定画面に似た画面を探す | read-only |
| 5 | `compare` | 複数画面を比較 | read-only |
| 6 | `find_by_color` | 配色から逆引き検索 | read-only |
| 7 | `find_examples_for_macrostructure` | 版面構成（マクロ構造）から実例検索 | read-only |
| 8 | `list_collections` | コレクション一覧 | read-only |
| 9 | `get_filters` | 利用可能な絞り込み条件を取得 | read-only |
| 10 | `get_site_pages` | 特定サイトのページ一覧 | read-only |
| 11 | `find_components` | UIコンポーネント検索（ボタン・ナビ等） | read-only |
| 12 | `get_collection` | コレクション詳細 | read-only |
| 13 | `find_reference_components` | 参照用コンポーネント取得 | read-only |
| 14 | `recommend` | レコメンド | read-only |
| 15 | `get_reference_jsx` | 参照実装のJSXコード取得 | read-only |

書き込み・課金アクションは無い。自動呼び出しを許可して問題ない。

**標準の使い方**：`search_screens` → `get_design_system`
版面型から入るなら `find_examples_for_macrostructure`、配色起点なら `find_by_color`。

---

## 3. スキルへの組み込み（貼り付け用）

`patched/` に追記済みの SKILL.md 全文を置いてある。
claude.ai のスキル編集画面へ反映する場合は、以下の追記ブロックだけをコピーすればよい。

### promo-design — `## 3. 版面を選ぶ` の直後に挿入

```markdown
**着手前に Inspo MCP で実在クリエイティブを3〜5件参照する。**
`search_screens`（媒体・業種で検索）→ `get_design_system`（配色・フォント抽出）
／版面型から探すなら `find_examples_for_macrostructure`、配色起点なら `find_by_color`。
参照結果は下記の型選定と配色判断の根拠にする。取得できない場合はそのまま続行し、成果物に「Inspo未参照」と明記する。
```

### event-lp — `## デザイン方針（必ず守ること）` の直後、`### カラー & テーマ` の前に挿入

```markdown
### 0. 実在サイトの参照（HTML実装前に必ず実行）
Inspo MCP で同ジャンルの実在LPを3〜5件取得し、配色・フォント・版面構成の根拠にする。
手順：`search_screens` → 候補から `get_design_system` で配色・タイポを抽出
（似た1枚を起点にするなら `find_similar`、構成比較は `compare`、実装は `get_reference_jsx` を参考にできる）。
**下記のカラー・タイポ既定値は初期値であり、参照結果に基づく上書きを許可する。**
取得できない場合はそのまま続行し、成果物に「Inspo未参照」と明記する。
```

### seo-lp — `## チャット環境での実行方針` の「対象未指定なら…」の前に1行挿入

```markdown
- デザイン・レイアウト改修まで踏み込む場合は、実装前に Inspo MCP（`search_screens` → `get_design_system`）で同ジャンルの実在サイトを3〜5件取得し、配色・フォント・版面構成を参考にする。取得不可なら続行し、その旨を明記する
```

seo-lp は分析専用スキルでUI実装工程を持たないため、条件付きの文言にしてある。

---

## 4. グローバル CLAUDE.md への追記

`~/.claude/CLAUDE.md` が存在する場合のみ、以下を1行追記する（存在しなければ作成しない）。

```markdown
LP・Webページ・アプリUIを作る時は、実装前に inspo MCP で実在サイトを参照する（search_screens → get_design_system）。取得できなければその旨を明記して続行。
```

---

## 5. 未対応

- **frontend-design スキルは存在しない**（`~/.claude/skills/` にもリポジトリ内にも無し）。対象外とした。
- **テスト検索（「不動産会社のLP」3件）は未実行**。クラウド環境から Inspo へ到達できないため。
  ローカルで「不動産会社のLPをinspoで3件探して」と打てば確認できる。
