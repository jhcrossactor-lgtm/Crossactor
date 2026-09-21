---
name: seo-lp
description: Crossactor LP・ウェブサイトのSEO分析・改善スキル。「SEO監査して」「LPをチェック」「ページを分析」「スキーマ（構造化データ）を作って」「Core Web Vitals」「ローカルSEO」「Ahrefsで調べて」「検索順位を上げたい」と言われたら起動。単一ページ分析・テクニカルSEO・schema.org・ローカルビジネスSEO・Ahrefs MCP連携をカバー。web_fetch でページを取得して実データに基づき分析すること。
---

# SEO分析スキル（チャット版）

対象タスクに応じて references/ の該当ファイルを読んでから実行する。複数該当なら全部読む。

| タスク | 参照ファイル |
|---|---|
| 単一ページ（LP）の総合分析 | references/page.md |
| クロール・インデックス・Core Web Vitals・meta | references/technical.md |
| schema.org構造化データの監査・生成 | references/schema.md |
| 地域ビジネスSEO（NAP・Googleビジネス） | references/local.md |
| Ahrefs MCPでの被リンク・KW調査 | references/ahrefs.md |

## チャット環境での実行方針

- ページ取得は **web_fetch**（HTML直読み）。JSレンダリング必須の検証は不可と明示する
- Ahrefs接続済みなら references/ahrefs.md の手順でMCPツールを使用（Ahrefsツールは tool_search で先にロード）
- 順位・SERP実データは web_search + Ahrefs で補完
- 出力：問題点を Critical / High / Medium / Low で分類し、修正コード（meta・JSON-LD等）は即貼り付け可能な形で出す
- デザイン・レイアウト改修まで踏み込む場合は、実装前に Inspo MCP（`search_screens` → `get_design_system`）で同ジャンルの実在サイトを3〜5件取得し、配色・フォント・版面構成を参考にする。取得不可なら続行し、その旨を明記する
- 対象未指定なら Crossactor LP（GitHub Pages）をデフォルト対象として確認する
