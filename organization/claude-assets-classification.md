# Claude資産の棚卸しと分類 — 2026-08-06

Crossactorが現在Claude上で回している全業務を洗い出し、
**Skill / Agent / Plugin / CLAUDE.md** のどこに置くべきかを分類した。

---

## 0. 調査の前提（重要）

この分析はリモートのクラウドコンテナ上で実施した。
**ほせもやんのPCにあるClaudeセッション履歴（`~/.claude/projects/*.jsonl`）は取得できていない。**

代わりに、実体が残っている以下を全数調査した。

| 調査対象 | 件数 |
|---|---|
| リポジトリ内ファイル | 219 |
| 個人スキル（`~/.claude/skills/`） | 自作11 / Anthropic製6 |
| リポジトリスキル（`.claude/skills/`） | 4 |
| 旧スキル（`skills/*.md`） | 3 |
| サブエージェント定義 | 21 |
| 組織ロール定義（`organization/roles/`） | 6 |
| 成果物ディレクトリ | 6案件 |
| gitコミット | 34（2026-03-26〜2026-08-01） |
| 接続中MCP | 12（GitHub / Notion / Slack / Google Drive / Calendar / Gmail / Canva / Supabase / Ahrefs / Supermetrics / Windsor.ai / CCR） |

---

## 1. 先に結論 — 構造的な問題6件

分類の前に、放置すると分類が意味をなさなくなる欠陥がある。

### P1. 21個のエージェントがルートから呼べない【最優先】

エージェント定義は `kansai-housing-intel/Crossactor/.claude/agents/` にしか存在しない。
リポジトリルートに `.claude/agents/` が無い。

`ai-editorial` / `ai-employee` スキルは `researcher` `report-writer` `slide-maker` 等を呼ぶ設計だが、
**ルートでセッションを開いた場合これらは解決できない。**

### P2. リポジトリが自分自身を内包している

`kansai-housing-intel/Crossactor/` が、リポジトリルートの完全コピーになっている。
CLAUDE.md・brand・ceo_system・organization・成果物すべてが二重に存在する。
どちらが正か不明。

### P3. スキルの置き場が4系統に分散

| 場所 | 中身 | 状態 |
|---|---|---|
| `~/.claude/skills/` | 自作11 | 個人環境限定・Git管理外 |
| `.claude/skills/` | 4 | Git管理下 |
| `skills/*.md` | marketing / development / research | 旧形式・SKILL.md未満 |
| `スキル/haichi-tool/` | 1 | 日本語ディレクトリ・ネスト側のみ |

さらに README には「G:\マイドライブ\claude にも反映（二重管理ルール）」とある。**実質5系統。**

### P4. 組織定義が二重管理

同一人物が `organization/roles/*.md` と `.claude/agents/*.md` の両方に定義されている。

- roles にあるのは6名（bone / flut / pet / rin / sx / _template）
- agents にある人格は11名（+ fago / nium / rinet / tim / xylo）

**片方だけ更新すれば必ず食い違う。**

### P5. CLAUDE.mdに未運用のルールが残っている

- 「日次オペレーション（朝：タスクリスト提出／夕方：報告）」— 実行痕跡なし
- 「Rule 03 対話ログを毎回記録」— `communications/logs/` は **2026-04-15の1件のみ**。以後3.7ヶ月ゼロ

守られていないルールが常時トークンを消費している。Rule 09（足すな、削れ）に反する。

### P6. CLAUDE.mdのスキル表がデッドリンク化

CLAUDE.mdは `skills/marketing.md` `skills/development.md` `skills/research.md` を指すが、
実運用は `~/.claude/skills/` の14スキルに移行済み。表が現実を指していない。

---

## 2. 分類の判断軸

| 置き場 | 適する条件 | 適さない条件 |
|---|---|---|
| **CLAUDE.md** | 常時適用。人格・不変ルール・ディレクトリ規約。毎セッション読む価値がある | 条件付きの手順、めったに使わない知識 |
| **Skill** | トリガーが言語化できる。同じ手順を毎回踏む再現性が価値 | 常時必要、または1回きり |
| **Agent** | 別コンテキストで走らせたい。並列化・コンテキスト隔離が価値。入出力が固定 | 単なる知識・口調。メインで足りる |
| **Plugin** | 複数環境へ配る単位。skill+agent+command+hook+MCPを束ねる | 単発・個人限定 |

**判断の要点：人格はエージェントではない。**
「BONE は INTP で情報参謀」は独立コンテキストを必要としない。参照ドキュメントで足りる。
エージェントにすべきなのは「並列で走らせたい」「メインの文脈を汚したくない」処理だけだ。

---

## 3. Skillにすべきもの

### 3-1. 維持（現状のままでよい）— 14件

| スキル | 業務 | 置き場の是正 |
|---|---|---|
| `cro-mini` | 10部門40エージェントの振り分け司令塔 | → Plugin core へ |
| `arch-reg-sync` | 自治体の建築法規・都市計画調査 → MD+PDF | → Plugin 建築 へ |
| `haichi-tool` | 木造ハイツ配置検討ツール・平面図生成 | → Plugin 建築 へ |
| `deep-verify` | 5役割×3イテレーションの深層検証 | → Plugin core へ |
| `grilling` | 計画・要件のストレステスト | → Plugin core へ |
| `writing-great-skills` | スキル設計の参照 | → Plugin core へ |
| `event-lp` | イベント告知LP生成 | → Plugin studio へ |
| `promo-design` | チラシ・バナー・サムネのデザイン設計 | → Plugin studio へ |
| `seo-lp` | SEO監査・構造化データ・Ahrefs連携 | → Plugin studio へ |
| `theme-studio` | 配色テーマ適用 | → Plugin studio へ |
| `ai-editorial` | 1テーマ→6チャネル並列生成 | → Plugin studio へ |
| `ai-employee` | 1テーマ→レポート/スライド/アジェンダ（5分） | → Plugin studio へ |
| `adobe-invoice-download` | Adobe請求書の月次取得 | → Plugin ops へ |
| `score-rename` | 吹奏楽譜PDFの識別・リネーム | → Plugin ops へ |
| `x-skill-scout` | X週次スキル情報収集 | → Plugin ops へ |

### 3-2. 新規に切り出すべき — 4件

いま「毎回手作業でやっている暗黙の手順」がスキル化されていない。

**① `rental-market-report`（賃料相場レポート）— 最優先**

成果物に**同じ工程を3回**繰り返した痕跡がある。

- `守口市家賃相場レポート2026/`
- `守口市菊水通2丁目_2LDK賃料相場/`（レポートMD + インフォグラフィックHTML + PDF）
- `守口市菊水通2丁目_クリニック賃料相場/`（同構成）

工程が完全に固定：**エリア/用途指定 → 相場収集 → レポートMD → インフォグラフィックHTML → PDF出力**。
3回やった時点でスキル化の閾値を超えている。

**② `agent-hire`（AI社員の採用）**

git履歴に「◯◯を採用」コミットが4件（PET / SX / RIN / FLUT）。
毎回 `organization/roles/<name>.md` と `.claude/agents/<name>.md` の両方を作る必要がある（P4の原因）。
手順を固定すれば二重管理の食い違いが構造的に消える。

**③ `monthly-research`（月次リサーチ更新）**

「月次リサーチ更新 2026年07月」「同 2026年08月」が毎月1日に発生。
Routine（cron）+ スキルの組み合わせで自動化すべき典型。

**④ `skill-sync`（スキル同期）**

READMEの「G:\マイドライブ\claude にも反映」を手作業でやっている。
→ **本来はスキルではなくPlugin化で消滅させるべき問題**（後述 §5）。Plugin移行までの暫定措置として定義する。

### 3-3. 廃止すべき — 3件

`skills/marketing.md` `skills/development.md` `skills/research.md`
SKILL.md形式ですらなく、CLAUDE.mdからのリンクも実運用と乖離。
中身は `cro-mini` の `references/04-marketing.md` `07-research.md` 等に吸収済み。削除。

---

## 4. Agentにすべきもの

現在の21エージェントは性質が2系統に混在している。**分けて扱う。**

### 4-1. 工程エージェント — 10件【全て維持・ルートへ移設】

入力 `output/research-notes.md` → 出力ファイル固定。並列実行される。**エージェントとして正しい設計。**

| エージェント | 出力 |
|---|---|
| `researcher` | research-notes.md |
| `reporter` | report.md |
| `report-writer` | report.html |
| `blog-writer` | blog-post.html（WordPress Gutenberg） |
| `newsletter-writer` | newsletter.md |
| `x-thread-writer` | x-thread.md |
| `youtube-script-writer` | youtube-script.md |
| `infographic-maker` | infographic.html |
| `slide-maker` | presentation.html |
| `agenda-planner` | agenda.md |

**必須対応：`kansai-housing-intel/Crossactor/.claude/agents/` → リポジトリルート `.claude/agents/` へ移設**（P1の解消）。

### 4-2. 人格エージェント — 11件【3件だけ残し、8件は参照ドキュメントへ降格】

**残す3件**（独立コンテキストで走らせる価値がある）

| エージェント | 残す理由 |
|---|---|
| `RINET`（品質管理） | 出荷前レビューをメイン文脈と隔離して回す価値がある。作った本人の文脈で自己採点させない |
| `PET`（ブランディング） | `brand/brand-guide.md` `ng-list.md` との照合を独立実行。同上 |
| `FLUT`（リサーチ） | → **`researcher` に統合**。役割が完全重複。FLUTの「一次情報優先・出所明記」方針をresearcherに吸収 |

**降格する8件** — `BONE` `Cro` `FAGO` `NIUM` `RIN` `SX` `TIM` `XYLO`

理由：これらは「知識と口調」であって「隔離すべき処理」ではない。
`cro-mini` が既に10部門への振り分けを `references/*.md` で担っている。同じ情報が二重に存在している。

- `Cro` → CLAUDE.md本体（メインセッションがCro。エージェント定義は不要）
- `BONE` `RIN` → `cro-mini/references/08-data.md`
- `FAGO` `XYLO` → `cro-mini/references/04-marketing.md`
- `SX` `NIUM` → `promo-design` / `event-lp` スキル
- `TIM` → `youtube-script-writer` エージェント

### 4-3. 新規に作るべき — 1件

**`houki-checker`（法規チェッカー）**

`成果物/建築設計検討ツール/` に稼働するPythonモジュールがある。

- `calculations/coverage_far.py`（建蔽率・容積率）
- `calculations/road_slope_envelope.py`（道路斜線）
- `calculations/setback_shadow.py`（後退・日影）
- `core/law_database.py` / `core/pdf_parser.py` / `output/dxf_generator.py`

これを叩いて検証する専任エージェント。`deep-verify` と組ませれば、誤りコストの高い容積計算のダブルチェックが自動化される。
現状はツールが存在するのに、呼び出す仕組みが無い。

---

## 5. Pluginにすべきもの

**Pluginは「配布単位」。P2・P3（重複と分散）を構造的に解決する唯一の手段。**

いま `~/.claude/skills/`（個人PC）・`.claude/skills/`（Git）・Googleドライブの3箇所を手で同期している。
Plugin化すればリポジトリが単一の正となり、同期作業そのものが消える。

### 分割案 — 4プラグイン

**① `crossactor-core`（会社OS・常時導入）**

```
skills/   cro-mini（+references 10部門）, deep-verify, grilling, writing-great-skills
agents/   RINET, PET
commands/ /hire（AI社員採用）, /log（対話ログ記録）
hooks/    pre-commit（validate-skills）
docs/     organization/rules.md, ceo_profile.md, brand/
```

**② `crossactor-kenchiku`（建築業務・案件時のみ）**

```
skills/   arch-reg-sync, haichi-tool, rental-market-report
agents/   houki-checker
scripts/  建築設計検討ツール一式（coverage_far / road_slope_envelope / setback_shadow / dxf_generator）
```

**③ `crossactor-studio`（発信・制作）**

```
skills/   ai-editorial, ai-employee, event-lp, promo-design, seo-lp, theme-studio
agents/   工程エージェント10件
mcp/      Canva, Ahrefs
```

**④ `crossactor-ops`（定型業務・自動化）**

```
skills/   adobe-invoice-download, score-rename, x-skill-scout, monthly-research
routines/ 月次リサーチ（毎月1日）, X情報収集（毎週水曜）
mcp/      Slack, Google Drive, Notion
```

### 分割の根拠

`cro-mini` は常時必要だが、`score-rename`（吹奏楽譜）と `arch-reg-sync`（建築法規）は同時には要らない。
全部入りにするとコンテキストコストを常時払うことになる。
**AGENTS.MD に既に書いてある判断軸「常時コンテキストコストを払う価値があるか」をプラグイン分割に適用した結果がこれだ。**

---

## 6. CLAUDE.mdにまとめるべきもの

### 6-1. 残す（現状維持）

- Cro人格定義（ENTJ・話し方のルール）
- 会社ミッション
- ほせもやんとの関係・最終決定権
- 絶対遵守ルールへの参照（`organization/rules.md`）
- 行動制約（頼まれた箇所だけ変える／確証なしは明示／外部アクションは許可制）

### 6-2. 追加すべき — 4件

**① ディレクトリ規約（どこに何を置くか）**

いま `AGENTS.MD` に断片的にあるだけで、CLAUDE.md本体に無い。P3の根本原因。

```
.claude/skills/   スキル（SKILL.md形式）— ここが唯一の正
.claude/agents/   サブエージェント — ルート直下に置くこと
organization/     組織の決定事項・ロール定義
communications/   対話ログ・MEMORY.md
brand/            ブランドガイド・NGリスト
成果物/           案件ごとの納品物
scripts/ hooks/   再利用ヘルパー・検証
```

**② MCP vs CLI の判断軸**

README に埋もれているが、これは条件発火ではなく**常時適用の判断基準**。CLAUDE.mdに昇格させる。

> 常時コンテキストコストを払う価値があるMCPか、1回ヘルプを叩けば以後タダで使えるCLIか。
> ルーティン業務はClaude Codeで初回構築 → 動作確認後にCLI化。

**③ 単一の正（Single Source of Truth）の宣言**

> スキル・エージェント・組織定義の正はこのリポジトリのみ。
> `~/.claude/skills/` とGoogleドライブは配布先であって編集元ではない。

**④ `communications/MEMORY.md` の運用**

CLAUDE.mdに「維持する」と書いてあるが、**ファイルが存在しない**。作るか、記述を削る。

### 6-3. CLAUDE.mdから出すべき — 3件

| 項目 | 理由 | 移動先 |
|---|---|---|
| スキル一覧表（marketing / development / research） | デッドリンク。実運用と乖離（P6） | 削除 |
| 日次オペレーション（朝夕の報告フロー） | 4ヶ月間ゼロ実行。守られないルールは害 | Routine（cron）で実装するか削除 |
| 対話ログの記録方法（詳細フォーマット） | 手順であって常時ルールではない | `/log` コマンド化（core Plugin） |

---

## 7. 実行順序

依存関係で並べた。上から順に潰す。

| # | 作業 | 効果 |
|---|---|---|
| 1 | `.claude/agents/` をリポジトリルートへ移設（21件） | P1解消。ai-editorial / ai-employee が実際に動くようになる |
| 2 | `kansai-housing-intel/Crossactor/` の重複を削除、正を確定 | P2解消。219ファイル→約120に |
| 3 | 人格エージェント8件を `cro-mini/references/` へ降格 | P4解消。二重管理が消える |
| 4 | `skills/*.md`（旧3件）を削除、CLAUDE.mdの表を除去 | P6解消 |
| 5 | CLAUDE.mdにディレクトリ規約・MCP判断軸・SSoT宣言を追加 | P3の再発防止 |
| 6 | `rental-market-report` スキル新規作成 | 最頻出の手作業を自動化 |
| 7 | `houki-checker` エージェント新規作成 | 既存Pythonツールを稼働させる |
| 8 | 4プラグインへ再編・配布 | P3完全解消。同期作業が消滅 |
| 9 | 日次オペレーションをRoutine化 or 削除 | P5解消 |

**1〜5は構造の是正。6以降の新規作成は、1〜5を終えてから着手する。**
順序を逆にすると、重複したディレクトリのどちらに作るかで再び分岐する。

---

## 8. 数値サマリ

| 分類 | 現状 | 分類後 |
|---|---|---|
| Skill | 18（4系統に分散） | 18（維持14 + 新規4 − 廃止3 = 15、+Anthropic製は別枠） |
| Agent | 21（ルートから不可視） | 14（工程10 + 品質2 + 統合1 + 新規1） |
| Plugin | 0 | 4（core / kenchiku / studio / ops） |
| CLAUDE.md | 4,153バイト・うち3項目が未運用 | 未運用3項目を除去、常時適用4項目を追加 |
