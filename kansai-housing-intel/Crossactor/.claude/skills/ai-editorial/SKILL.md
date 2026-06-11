---
name: ai-editorial
description: >
  テーマを1つ与えると、1本のリサーチから「リサーチレポート / ブログ記事（WordPress Gutenberg）/ Xスレッド / YouTube台本（約10分尺）/ メルマガ / インフォグラフィック（複数枚）」の6種類を全自動で並列生成するAI編集部ワークフロー。
  承認はリサーチ計画の1回のみで、それ以降は完全自律で完了まで進む。
  トリガー: 「[テーマ] でAI編集部を動かして」「AI編集部に任せる」「ai-editorial」「テーマ: [...] でブログからYouTubeまで」「/ai-editorial [テーマ]」など。
user-invocable: true
---

# AI編集部 — テーマ1つから6チャネルの発信物を並列生成

## このスキルが守るルール

1. **承認ゲートは Phase 2 の1回のみ**。それ以外で AskUserQuestion を使ってはいけない。
2. **承認後はサブエージェントが自動で動く**。途中で確認を挟まない。
3. **すべての成果物は `output/` 配下に出力する**。既存ファイルは上書き。
4. **完了時にブラウザで `output/infographic.html` を開く**。OSを判定して適切なコマンドを実行。失敗してもエラーで止めず、ファイルパスを案内する。
5. **エラーが出ても止まらず、ベストエフォートで続行**。最後に何ができて何が失敗したか報告。
6. **全てのサブエージェントに「企業ブログ風（硬めと柔らかめの中間）」トーンを明示的に伝える**。

## 配布パッケージ前提

- このスキルは「AI編集部のワーク」フォルダ配下で動作する前提
- `.claude/settings.json` で `output/` への書き込み・ブラウザ起動コマンド・`WebSearch` / `WebFetch` を事前許可済み
- そのため、参加者は許可ダイアログをほぼ目にせずに進む想定
- それでも許可が出た場合は参加者に「許可」を選んでもらう（READMEに記載済み）

## ワークフロー全体像

```
Phase 1: テーマ受領＋プレリサーチ（WebSearch 1〜2回）
   ↓
Phase 2: リサーチ計画ドラフトを提示 → ★承認ゲート（AskUserQuestion 1回）★
   ↓ 承認
Phase 3: サブエージェント実行
   Step A: researcher を呼ぶ（直列）→ output/research-notes.md
   Step B: 以下の6エージェントを1メッセージで並列起動
       - report-writer       → output/report.html（HTML形式 / オレンジ基調）
       - blog-writer         → output/blog-post.html（WordPress Gutenberg / SEO記事構成）
       - x-thread-writer     → output/x-thread.md
       - youtube-script-writer → output/youtube-script.md（約10分尺 / 2,800〜3,200字）
       - newsletter-writer   → output/newsletter.md
       - infographic-maker   → output/infographic.html（複数枚 / オレンジ基調）
   ↓
Phase 4: 完了報告 ＋ OS判定でブラウザ自動オープン（infographic.html）
```

## Phase 1: テーマ受領＋プレリサーチ

1. ユーザーのプロンプトから「テーマ」を抽出する
   - 「〇〇でAI編集部を動かして」の〇〇部分
   - 「/ai-editorial 〇〇」の〇〇部分
   - 例: 「2026年のAIエージェント市場 でAI編集部を動かして」→ テーマは「2026年のAIエージェント市場」
2. WebSearch を 1〜2回だけ実行して、テーマの周辺情報をざっくり把握する
   - 目的: 計画の質を上げるため（本格リサーチは Phase 3 の researcher に任せる）
3. ユーザーへの中間報告は1〜2行のみ：
   ```
   テーマを受け取りました：「[テーマ]」
   リサーチ計画を考えています…
   ```

## Phase 2: リサーチ計画ドラフト提示

以下のフォーマットで計画をMarkdown1ブロックで提示する：

```markdown
## リサーチ計画

### テーマ
[抽出したテーマ]

### リサーチ観点（3〜5項目）
1. [観点1]
2. [観点2]
3. [観点3]
（必要なら4〜5）

### 想定する成果物（6種類＋リサーチノート）
- リサーチノート（中間成果物）: output/research-notes.md
- (a) リサーチレポート（HTML形式）: output/report.html
- (b) ブログ記事（WordPress Gutenberg / SEO記事構成）: output/blog-post.html
- (c) Xスレッド: output/x-thread.md
- (d) YouTube台本（約10分尺）: output/youtube-script.md
- (e) メルマガ: output/newsletter.md
- (f) インフォグラフィック（複数枚を1ファイル内）: output/infographic.html

### 共通トーン
- 企業ブログ風（硬めと柔らかめの中間・です/ます調）
- 絵文字は原則不使用、専門用語は初出で補足
- 各チャネル最適化は行うが、トーンの芯はぶれさせない

### 共通デザイン（HTML系成果物）
- **オレンジ基調**（#C2410C / #EA580C / #7C2D12 / Surface #FFF7ED / Muted #57534E）
- レポート・ブログ・インフォグラフィックで統一感を担保

### 各発信物の構成案
- **レポート（HTML）**: 表紙 / リード / 目次 / 本文（5〜6章）/ まとめ / 参考資料（3,000〜5,000字）
- **ブログ（Gutenberg / SEO記事型）**: H1 / リード / 目次 / H2×3〜5（ナンバリング無し）/ まとめH2（2,500〜4,000字、参考資料セクション無し・出典は本文インライン）
- **Xスレッド**: フック1 + 本編4〜7 + 締め1（各1ツイート、日本語140字以内）
- **YouTube台本**: オープニング / 本編3〜5パート / 締め（約10分、2,800〜3,200字）
- **メルマガ**: 件名 / 冒頭挨拶 / 本文 / CTA / 署名（800〜1,500字）
- **インフォグラフィック**: 3〜6枚（例: 市場規模 / プロセス / 比較 / 事例 / 次のアクション）
```

提示直後に **AskUserQuestion を1回だけ** 呼ぶ：

質問: 「この計画で進めてOKですか？」
選択肢:
- 「このまま進める」（Recommended）
- 「修正して進める（修正点を教えてください）」

### 承認後の分岐
- **「このまま進める」** → Phase 3 へ即進行
- **「修正して進める」** → ユーザーから修正点を受け取り、計画を1回だけ更新してから Phase 3 へ進行（**再承認は求めない**）

## Phase 3: サブエージェント実行

### Step A: researcher を呼ぶ（直列・先行）

Agent ツールを呼び出す。subagent_type は `"researcher"`。

プロンプトには以下を含める：
- 確定したリサーチ計画の全文
- 出力先: `output/research-notes.md`
- 「このノートは後段で report-writer / blog-writer / x-thread-writer / youtube-script-writer / newsletter-writer / infographic-maker の6エージェントが並列で読むため、観点ごとに整理し、引用元URLを必ず記載すること」
- 「WebSearchが弱いテーマでも諦めず、クエリを変えて再検索し、それでも薄ければ不確実性を明示した最小構成で出力すること」

researcher が完了するまで待つ。完了したら次へ。

### Step B: 6エージェントを並列起動

**1メッセージ内で6つの Agent ツールを同時に呼ぶ**こと。
全エージェントのプロンプトには、以下の共通指示を必ず含める：
- テーマ名
- 入力: `output/research-notes.md` を読むこと
- **共通トーン: 「企業ブログ風（硬めと柔らかめの中間・です/ます調）、絵文字は原則不使用、専門用語は初出で補足、読み手を突き放さずフランクすぎない」**
- 各エージェントの SKILL ファイル（`.claude/agents/<name>.md`）のルールを必ず守ること

呼び出し1: subagent_type `"report-writer"`
- プロンプト: 「`output/research-notes.md` を読み、**HTML形式のリサーチレポート**を `output/report.html` に作成してください。テーマ: [テーマ]。3,000〜5,000字を目安に、表紙ヘッダー + リード + 目次 + 5〜6章 + まとめ + 参考資料の構成。オレンジ基調デザイン（#C2410C / #EA580C / #7C2D12）、Google Fonts Noto Sans JP、印刷対応。トーン: 企業ブログ風。report-writer.md のルール厳守。」

呼び出し2: subagent_type `"blog-writer"`
- プロンプト: 「`output/research-notes.md` を読み、**WordPress Gutenberg形式のSEO記事**を `output/blog-post.html` に作成してください。テーマ: [テーマ]。2,500〜4,000字。構成は H1 + リード + 目次 + H2（3〜5本、**ナンバリング無し**）+ H3 + まとめH2。**参考資料セクションは作らず、出典は本文内のインライン `<a href>` で埋め込む**こと。各Gutenbergブロックコメント（<!-- wp:xxx -->）を正しく含めること。トーン: 企業ブログ風。blog-writer.md のルール厳守。」

呼び出し3: subagent_type `"x-thread-writer"`
- プロンプト: 「`output/research-notes.md` を読み、**Xスレッド**を `output/x-thread.md` に作成してください。テーマ: [テーマ]。日本語140字以内のツイートを6〜9個でスレッド化（フック + 本編 + 締め）。`---`区切り。トーン: 企業ブログ風だが短く切れ味よく。絵文字最小限。x-thread-writer.md のルール厳守。」

呼び出し4: subagent_type `"youtube-script-writer"`
- プロンプト: 「`output/research-notes.md` を読み、**約10分尺のYouTube台本**を `output/youtube-script.md` に作成してください。テーマ: [テーマ]。2,800〜3,200字、話し言葉、オープニング / 本編3〜5パート / 締めの構成。ト書き（[間]、[強調]等）も添える。トーン: 企業ブログ風の話し言葉化。youtube-script-writer.md のルール厳守。」

呼び出し5: subagent_type `"newsletter-writer"`
- プロンプト: 「`output/research-notes.md` を読み、**メルマガ**を `output/newsletter.md` に作成してください。テーマ: [テーマ]。件名 / 冒頭挨拶 / 本文 / CTA / 署名の構成、800〜1,500字。トーン: 企業ブログ風。newsletter-writer.md のルール厳守。」

呼び出し6: subagent_type `"infographic-maker"`
- プロンプト: 「`output/research-notes.md` を読み、**複数枚のインフォグラフィック**を `output/infographic.html` に作成してください。テーマ: [テーマ]。3〜6枚（内容に応じて調整）、1ファイル内にスライド風に並べる。**オレンジ基調デザイン（#C2410C / #EA580C / #7C2D12）**、ブラウザ単体で表示可能。infographic-maker.md のルール厳守。」

6つすべての完了を待ってから Phase 4 へ。

## Phase 4: 完了報告＋ブラウザでインフォグラフィックを自動オープン

### 1. 完了報告

```
AI編集部のワークフローが完了しました。

成果物（すべて output/ フォルダ内）:
- リサーチノート（中間）: output/research-notes.md
- (a) リサーチレポート（HTML）: output/report.html
- (b) ブログ記事（Gutenberg / SEO記事構成）: output/blog-post.html
- (c) Xスレッド: output/x-thread.md
- (d) YouTube台本: output/youtube-script.md
- (e) メルマガ: output/newsletter.md
- (f) インフォグラフィック: output/infographic.html

ブラウザでインフォグラフィックを開きます。
各チャネルへの展開は output/ 配下のファイルを各媒体にコピペしてご利用ください。
```

### 2. ブラウザ自動オープン（単発コマンドのみ実行）

**重要**: `.claude/settings.json` で許可されているのは **単発コマンド** のみ。`if/case` などの複合 Bash スクリプトは許可リストにマッチせず、ダイアログが出てしまう。
そのため、OS 判定は Claude Code 自身がセッション開始時に渡されている環境情報（`Platform: darwin` 等）から行い、**該当する単発コマンドを Bash ツールで1回だけ実行する**。

OSと実行コマンドの対応表（このうち1つだけ実行）:

| OS / 環境 | 実行する単発コマンド |
|---|---|
| macOS | `open output/infographic.html` |
| Linux (デスクトップ環境あり) | `xdg-open output/infographic.html` |
| WSL | `explorer.exe output/infographic.html` |
| Windows (Git Bash等) | `cmd.exe /c start "" output/infographic.html` |
| 判定不能 | コマンドを実行せず、案内メッセージのみ出力 |

**ルール**:
- Bash ツールには **1つのコマンドだけ** を渡す（`&&`、`||`、`;`、改行で繋がない）
- パス区切りは **必ずフォワードスラッシュ `/`** を使う
- 実行が失敗（exit code != 0）してもエラーで止めない。最後の案内メッセージで「自動で開けなかった場合は output/infographic.html をダブルクリックで開いてください」と伝える
- 判定に迷ったら macOS 想定で `open` を試す

## エラーハンドリング方針

- **researcher が失敗した場合**: research-notes.md がないため、6エージェントは起動できない。失敗を報告して終了。
- **Step B の6エージェントのうち一部が失敗した場合**: 成功した成果物のみ完了報告に含め、失敗したチャネルのみ「生成できませんでした」と明示。Phase 4 のブラウザオープンは `infographic.html` が存在する場合のみ実行（なければスキップし、代替として `blog-post.html` → `report.md` → いずれも無ければ案内のみ、の優先順で案内）。
- **AskUserQuestion は Phase 2 の1回のみ**。それ以外で確認を取りたくなっても絶対に使わない。困ったらベストエフォートで進める。
- **EnterPlanMode は使わない**。このスキルは即実行が前提。
- **ブラウザ自動オープンが失敗してもエラーにしない**。手動で開ける案内を最後に出すだけ。

## このスキルが「やってはいけない」こと

- Phase 2 以外で AskUserQuestion を呼ぶ
- 計画修正のループを2回以上回す
- ユーザーに「次は何をしますか？」と聞く
- 成果物を `output/` 以外に保存する
- Step B の6エージェントを直列で呼ぶ（必ず1メッセージ内で並列起動する。並列性がこのスキルの見せ場）
- 参加者のローカル環境を変更する操作（npm install 等）を提案する
- ブラウザ自動オープンの失敗をエラーとしてユーザーに見せて止める
- トーン指示（企業ブログ風）を各エージェントへのプロンプトから省略する
