---
title: フジヒサ向けマーケットプレイス構築 — 手順1（仕様確認）＋手順2（棚卸し）
date: 2026-08-24
status: 手順3以降はほせもやんの承認待ち
---

# 手順1：Claude Code プラグインマーケットプレイス 現行仕様（確定）

出典：`code.claude.com/docs/en/plugin-marketplaces` / `.../plugins-reference`（2026-08-24 取得）
検証環境の Claude Code：**v2.1.241**

## 1-1. マニフェストのファイル名と配置

| 項目 | 確定値 |
|---|---|
| マニフェストファイル名 | `marketplace.json` |
| 配置場所 | **リポジトリルート直下の `.claude-plugin/marketplace.json`** |
| プラグイン側マニフェスト | `<plugin>/.claude-plugin/plugin.json`（`name` のみ必須。マニフェスト自体は任意） |
| 相対パスの基準 | **マーケットプレイスルート**（`.claude-plugin/` の親）。`.claude-plugin/` 基準ではない |

## 1-2. marketplace.json の必須フィールド

```json
{
  "name": "kebab-case-識別子",
  "owner": { "name": "維持担当者名" },
  "plugins": [ { "name": "plugin-name", "source": "./plugins/plugin-name" } ]
}
```

- `name`（string・必須）：kebab-case。**ユーザーごとに同名マーケットプレイスは1つだけ**登録可能
- `owner`（object・必須）：`name` 必須／`email`・`url` 任意
- `plugins`（array・必須）：各エントリは **`name` と `source` が必須**

予約名（使用不可）：`claude-code-marketplace` / `claude-code-plugins` / `claude-plugins-official` / `anthropic-*` / `agent-skills` ほか。`org` / `org-provisioned` / `unknown` は Claude Desktop 側で拒否される。

## 1-3. marketplace.json の任意フィールド（今回使うもの）

| フィールド | 用途 |
|---|---|
| `$schema` | エディタ補完用。Claude Code は読み飛ばす |
| `description` / `version` | カタログの説明・版 |
| `metadata.pluginRoot` | ベア名ソースの解決先ディレクトリ（**v2.1.239以降**） |
| `renames` | プラグイン改名・削除時の移行マップ（**v2.1.193以降**） |

## 1-4. プラグインエントリの任意フィールド（今回使うもの）

`displayName` / `description` / `version` / `author` / `license` / `keywords` / `category` / `tags` / `homepage` / `repository` / `defaultEnabled`（v2.1.154以降）／`strict`

## 1-5. プラグイン側のディレクトリ構成

```
<plugin-root>/
├── .claude-plugin/
│   └── plugin.json          # name のみ必須
├── skills/                  # ← スキルはここ。.claude-plugin/ の中には置かない
│   └── <skill-name>/
│       ├── SKILL.md         # frontmatter の name が必須
│       └── references/      # 任意（そのままコピーされる）
├── LICENSE
└── README.md
```

**スキル検出ルール**
- `skills/<name>/SKILL.md` が1スキル
- スキル名は **SKILL.md の frontmatter `name`** が正（ディレクトリ名ではない）
- マーケットプレイス経由のインストールではディレクトリ名がバージョン文字列になり得るため、`name` の明記は必須
- `skills/` も `skills` フィールドも無く、ルートに `SKILL.md` がある場合は「単一スキルプラグイン」として読まれる

## 1-6. プラグインソースの型

| type | フィールド | 今回の適合性 |
|---|---|---|
| 相対パス `"./xxx"` | — | ◎ **これを採用**。1リポジトリ完結・privateでも配布可 |
| `github` | `repo` / `ref?` / `sha?` | △ プラグインを別リポジトリに置く場合 |
| `url` / `git-subdir` / `npm` / `archive` / `command` | — | 今回不要 |

> 組織設定（Organization settings > Plugins）で配布する場合、**private プラグインは相対パスで同一リポジトリ内に置く必要がある**。今回の要件（フジヒサ向け独立Org・機微情報あり）とも一致するため、相対パス一択。

## 1-7. 配布とインストール

```
/plugin marketplace add <org>/<repo>      # 追加（GitHub owner/repo 形式）
/plugin install <plugin>@<marketplace>    # 個別インストール
/plugin marketplace update <name>         # カタログ更新
```

- private リポジトリ対応：`/plugin marketplace add` 等の**手動実行**は既存の git 認証情報（`gh auth login` 等）をそのまま使う
- **バックグラウンド自動更新は HTTPS の認証ヘルパーを無効化するため private では失敗し得る**。SSH remote か、`CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1` の設定を併用する
- 検証コマンド：`claude plugin validate .`（CLI）／`/plugin validate .`（Claude Code内）

## 1-8. ゴールに対する仕様上の結論

「新規PCから1〜2コマンドで全スキルが入る」を満たす構成は次のとおり。

- **プラグインは1本にまとめる**（スキル11本を1プラグインの `skills/` に同梱）
  → `/plugin marketplace add <org>/<repo>` ＋ `/plugin install <name>@<marketplace>` の **2コマンドで完了**
- プラグインを11本に分けると `/plugin install` を11回打つことになり、ゴールを満たさない

---

# 手順2：Crossactorスキル 棚卸し（11本）

対象：`~/.claude/skills/synced/` 配下の `source: custom` スキル11本
（`docx`/`pdf`/`pptx`/`xlsx`/`morning`/`import-memory`/`skill-creator` は Anthropic 提供のため対象外）

| # | スキル名 | 用途 | 外部配布可否 | 含まれる機微情報 |
|---|---|---|---|---|
| 1 | `adobe-invoice-download` | Adobe請求書DL＋A4印刷（経費処理） | **不可** | 個人ユーザー名を含む絶対パス `C:\Users\hosokawa\Desktop\invoice_print.py`（L28,L71）／Crossactor契約プラン名（Illustratorプラン・Photography plan 20GB）／Chrome保存済み認証情報の利用手順。Crossactor自社経理業務であり配布価値もない |
| 2 | `arch-reg-sync` | 自治体の建築法規・都市計画調査→Markdown＋A4縦PDF出力 | **要サニタイズ** | 実行環境の絶対パス `/home/claude/...`（L305）／NotebookLM運用名「ノーエル」（社内呼称）／自治体名の実例（守口・門真）。※業務ロジック自体は汎用で、住宅会社には最も価値が高い |
| 3 | `cro-mini` | 10部門40エージェントの部門判定司令塔 | **要サニタイズ** | **Crossactor社内組織構造そのもの**（10部門・人数・各部門の出力姿勢）／`references/09-eigyo.md` に**実クライアント名「松本酒造・フジヒサ」**／`01-keikaku.md` に社名／他スキルへの連携指示 |
| 4 | `deep-verify` | 5役割×3イテレーションの深層検証 | **可**（軽微な修正のみ） | 「CRO深層検証フレームワーク」の呼称のみ。汎用ロジック |
| 5 | `event-lp` | イベント告知LPの単一HTML生成 | **可** | なし（外部URLは Google Fonts のみ） |
| 6 | `grilling` | 計画・要件のストレステスト型ヒアリング | **要サニタイズ** | frontmatter description に**実クライアント名「松本酒造・フジヒサ等」**／本文に「CRO・LINE Webhook・既存ツール群」＝社内システム名 |
| 7 | `haichi-tool` | 木造ハイツ配置検討＋1フロア平面図（単一HTML） | **要サニタイズ** | **特定案件の敷地DXF固定値（間口19,000×奥行16,000mm・304.00㎡）**／出力ファイル名 `haichi_tool_v3.html`。※住宅会社向けに最も転用価値が高い |
| 8 | `promo-design` | チラシ・バナー・LPファーストビューのデザイン設計 | **可** | なし |
| 9 | `seo-lp` | LP/サイトのSEO監査・schema・ローカルSEO・Ahrefs連携 | **要サニタイズ** | 「Crossactor LP・ウェブサイトの」という自社限定記述（description・SKILL.md）／Ahrefs API利用前提（トークン実体は無し。`https://ahrefs.com/api` の記述のみ） |
| 10 | `theme-studio` | 10種プリセットテーマの配色・フォント適用 | **可** | なし。**ただし Anthropic の theme-factory 由来で LICENSE.txt（Apache-2.0）同梱 → 再配布時はライセンス表記を維持すること** |
| 11 | `writing-great-skills` | SKILL.md の作成・改善・レビュー指針＋GLOSSARY | **可**（軽微な修正のみ） | 本文に既存ユーザースキル名の列挙（arch-reg-sync・event-lp・haichi-tool）。社外向けには例示を汎用化 |

## 全文スキャン結果（機微情報の網羅チェック）

| 検査項目 | 結果 |
|---|---|
| APIキー・トークン・パスワードの実体 | **0件**（`token` の語はすべて「トークン数」の意味） |
| メールアドレス | **0件** |
| 自社ドメイン・非公開URL | **0件** |
| Windows絶対パス | 2件（`adobe-invoice-download` のみ） |
| Unix絶対パス | 1件（`arch-reg-sync` L305） |
| 実クライアント名 | 3件（`grilling` ×2、`cro-mini/references/09-eigyo.md` ×2） |
| 自社名 Crossactor | 4件（`cro-mini` ×2、`seo-lp` ×2） |

→ **認証情報の漏洩リスクは無い。**リスクは「社内組織構造」「実クライアント名」「特定案件の敷地寸法」の3点に集約される。

---

# 「要判断」リスト（ほせもやんの判断が要る／削除していない）

## A. cro-mini（最高リスク・1行ずつ確認済み）

| # | 該当箇所 | 内容 | 論点 |
|---|---|---|---|
| A-1 | `SKILL.md` 振り分け表 全体 | 10部門40エージェントの部門名・参照先・「主力/控え」区分 | **これはCrossactorの組織設計そのもの＝商品**。フジヒサに丸ごと渡すのか、部門名を汎用化して渡すのか、cro-mini自体を配布対象外にするのか |
| A-2 | `references/09-eigyo.md` L3 | 「（松本酒造・フジヒサ等のクライアント案件）」 | 松本酒造は**第三者クライアント名**。フジヒサ向け配布物に他社名が載る。削除は確定として、置換文言をどうするか（「クライアント案件」に丸めるか、例示ごと削るか） |
| A-3 | `references/09-eigyo.md` L3 | 「フジヒサ」の記載 | 配布先本人に「あなたは弊社のクライアントです」と書かれた行が渡る。体裁の問題 |
| A-4 | `references/01-keikaku.md` L2 | 「Crossactorの中長期戦略の頭脳」 | 汎用化（「自社の」）でよいか |
| A-5 | `SKILL.md` 他スキル連携 | `theme-factory` を参照（現行名は `theme-studio`）。また配布対象外スキルへの参照が残ると壊れる | 連携表を配布セットに合わせて作り直す方針でよいか |
| A-6 | `SKILL.md` 行動原則 | 「本体CLAUDE.md準拠」／「会話は関西弁でよい」 | フジヒサ側に本体CLAUDE.mdは無い。関西弁指定はCrossactorの文化 |

## B. arch-reg-sync

| # | 該当箇所 | 内容 | 論点 |
|---|---|---|---|
| B-1 | L305付近 | `/home/claude/[jichitai]_...pdf` の絶対パス | 環境変数／相対パス化は**サニタイズ確定**（判断不要） |
| B-2 | description・本文 | 「NotebookLM（ノーエル）」 | 「ノーエル」は社内呼称。汎用化するか、そのまま渡すか |
| B-3 | 例示 | 自治体名の実例（守口・門真） | 大阪＝**フジヒサの営業圏そのもの**。残した方が実用的とも言える。残す／汎用例に差し替える |
| B-4 | PDFフッター | 「Arch-Reg-Sync / Claude（Anthropic）による自動調査レポート」 | 配布先名義に変えるか、そのままか |

## C. haichi-tool

| # | 該当箇所 | 内容 | 論点 |
|---|---|---|---|
| C-1 | 敷地DXF固定値 | 間口19,000×奥行16,000mm・304.00㎡ | **特定案件の実敷地**の可能性。汎用サンプル値に置換するか、入力パラメータ化するか |
| C-2 | 確定設計仕様 一式 | 階段室1,400／住戸3,600×7,200／バルコニー1,200／16段×250mm 等 | これはCrossactorの**設計ノウハウ**。住宅会社に渡す＝ノウハウ移転。渡す範囲の線引き |

## D. seo-lp

| # | 該当箇所 | 内容 | 論点 |
|---|---|---|---|
| D-1 | description・SKILL.md | 「Crossactor LP・ウェブサイトの」 | 汎用化は確定。ただし社名記述の削除だけでよいか |
| D-2 | `references/ahrefs.md` | Ahrefs MCP連携が前提 | フジヒサがAhrefs未契約なら動かない。同梱するか、ahrefs参照を外した縮小版にするか |

## E. 配布セット全体

| # | 論点 |
|---|---|
| E-1 | `adobe-invoice-download` を**配布対象外（不可）**と判定した。結果、配布は**10本**になる。これでよいか |
| E-2 | マーケットプレイス名・プラグイン名・`owner.name` / `owner.email` の確定値（例：`fujihisa-tools` / `fujihisa-skills`）。予約名は使用不可 |
| E-3 | プラグインは**1本にまとめる**方針（手順1-8の結論）。「2コマンドで全部入る」を満たすにはこれが必須。分割案があるか |
| E-4 | `theme-studio` は Anthropic の theme-factory 由来で **Apache-2.0**。再配布自体は可だが LICENSE.txt を同梱し表記を維持する。この形で配布してよいか |

---

# 着手前のブロッカー（回答が要る）

1. **配布先のGitHub Org / リポジトリ名が未確定。**
   本セッションのGitHubアクセス範囲は `jhcrossactor-lgtm/crossactor` のみ。フジヒサ向けOrgは**このセッションからは読めも書けもしない**。
   → Org名/リポジトリ名を教えてもらった上で、リポジトリをこのセッションに追加する必要がある。

2. **`G:\ClaudeLocal\` / `G:\マイドライブ\claude\` はこの実行環境に存在しない。**
   今回のセッションはクラウド上のLinuxコンテナで動いている。ローカルGドライブ指定の作業はここでは実行できない。
   → 代替案：本リポジトリの `fujihisa-marketplace/` をステージングとして構築 → 検証まで完了 → その後ほせもやんのPC側でG:\へ配置＆フジヒサOrgへpush。

3. 手順3のサニタイズは、上記「要判断」A〜Eの回答が出てから着手する（先に作ると作り直しになる）。

---

# 次アクション

上記「要判断」A-1〜E-4 とブロッカー1〜3に回答をもらい次第、手順3（サニタイズ）→ 手順4（構築）→ 手順5（検証3周）を実行する。
検証3周目の `marketplace add` → `install` 実試行は、本コンテナの Claude Code v2.1.241 でローカルパス指定により実行可能。
