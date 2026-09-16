@AGENTS.md

---

# Claude Code 固有設定

共通ルール（ミッション・人格・組織・規約・コマンド・命名・出力ルール・行動制約）は
すべて **`AGENTS.md` が正本**。上の `@AGENTS.md` で読み込まれる。
このファイルにはClaude Code固有の内容だけを書く。共通ルールをここに再掲しないこと。

---

## Skills索引

専門業務が発生したとき、対応するスキルファイルを参照する。

### 参照ドキュメント型（`skills/`）

| スキル | ファイル |
|---|---|
| マーケティング | `skills/marketing/SKILL.md` |
| 開発・技術 | `skills/development/SKILL.md` |
| リサーチ | `skills/research/SKILL.md` |

雛形 → `skills/_example/SKILL.md`（`scripts/new-skill` で生成）

### 自動起動型（`.claude/skills/`）

| スキル | 役割 | 出所 |
|---|---|---|
| `ai-editorial` | 1テーマ→6種コンテンツを並列生成 | 自社 |
| `ai-employee` | 1テーマ→リサーチ/レポート/スライド/アジェンダ（高速版） | 自社 |
| `score-rename` | 吹奏楽の楽譜PDFを標準スコア順にリネーム | 自社 |
| `x-skill-scout` | Xからskill・エージェント情報を週次収集 | 自社 |
| `secretary` | Slack/Gmail/カレンダー横断の未読要約・ドラフト・タスク抽出 | 自社 |
| `apple-design` | Apple流のUI設計・流体モーション | emilkowalski/skills |
| `emil-design-eng` | UIの磨き込み・コンポーネント設計 | emilkowalski/skills |

第三者スキルのバージョンは `skills-lock.json` で固定。更新時は導入前に中身を再監査すること。

---

## Subagents

`.claude/agents/` は**未作成**。現時点でプロジェクト定義のサブエージェントはゼロ。

追加する場合：
- 置き場所 → `.claude/agents/<name>.md`
- `organization/roles/` の役割定義と1対1で対応させる（役割の二重管理をしない）

---

## Permissions

`.claude/settings.json` は**未作成**。現時点ではClaude Codeの既定の権限設定で動いている。

設定する場合の方針：
- `AGENTS.md` の行動制約が上位。外部送信を伴うツールは自動許可しない
- 許可を足すなら `.claude/settings.json`（共有）、個人用は `.claude/settings.local.json`
