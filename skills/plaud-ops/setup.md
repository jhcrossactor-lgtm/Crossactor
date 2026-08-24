# Plaud CLI 導入手順

Plaud の録音・文字起こし・AI要約を Cro が直接扱えるようにするための、ローカルマシンでの初回セットアップ。
一度実施すれば以後は不要。

## 前提

- Node.js 20 以上
- Plaud アカウント（Plaud Note / NotePin 等のデバイス）
- Plaud Cloud Sync が有効で、録音がクラウドに同期済みであること

## 1. インストール

```bash
npm i -g @plaud-ai/cli
plaud version
```

都度実行でよければグローバル導入せず `npx -y @plaud-ai/cli@latest <コマンド>` でも動く。
ただし毎回ダウンロードが走るので、常用するならグローバル導入を推奨。

## 2. テレメトリを無効化する（先にやる）

Plaud CLI は PostHog と Sentry のテレメトリを同梱している。会議内容を扱うツールなので既定で切る。

シェル設定（`~/.zshrc` など）に追記：

```bash
export PLAUD_TELEMETRY_DISABLED=1
export DO_NOT_TRACK=1
```

追記後、シェルを開き直す。

## 3. 認証

```bash
plaud login
```

ブラウザが開くので **Authorize** を押す。トークンの手貼りは不要。

確認：

```bash
plaud me
```

自分のアカウントが返れば成功。

## 4. 動作確認

```bash
plaud recent -d 7 --json
```

直近7日の録音が返ればセットアップ完了。

## トークンの取り扱い

- 保存先：`~/.plaud/tokens.json`（自動更新される）
- このファイルはリポジトリにコミットしない。他人と共有しない
- 認証を切るとき：`plaud logout`

## コマンド一覧

| コマンド | 内容 |
|---|---|
| `plaud login` / `logout` | OAuth認証 / 失効 |
| `plaud me` | 認証中ユーザー確認 |
| `plaud files` | 録音一覧（`-p/--page`, `-s/--page-size`） |
| `plaud today` | 今日の録音 |
| `plaud recent` | 直近N日（`-d/--days`、既定7） |
| `plaud search <keyword>` | 名前で検索（直近500件をクライアント側で走査） |
| `plaud file <file_id>` | 録音の詳細 |
| `plaud transcript <file_id>` | 話者ラベル＋タイムスタンプ付き文字起こし |
| `plaud summary <file_id>` | AI要約（`--polished`, `--highlights`） |
| `plaud audio <file_id>` | 音声ダウンロードURL |
| `plaud update` | 最新版の確認 |

共通オプション：`--json`、`-o/--output <file>`、`--from/--to <date>`、`--all`、`--max <n>`

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `401` / `Not authenticated` | `plaud login` をやり直す |
| `404` | `file_id` が誤っている。`plaud recent --json` で取り直す |
| 録音が一覧に出ない | Plaudアプリ側で Cloud Sync が完了しているか確認する |
| `fetch failed` | ネットワーク、またはプロキシ環境下の接続を確認する |

## MCP を採用しなかった理由

Plaud は MCP サーバー（`npx -y @plaud-ai/mcp@latest install`）も公開しており、読み取り7ツール
（`list_files` / `get_file` / `get_note` / `get_transcript` ほか）と公式スキル6本が同梱される。
機能面では CLI と同じデータにアクセスする。

`AGENTS.MD` の判断軸「MCP接続は常時コンテキストコストを払う価値があるかで判断。一回学習すれば
済むならCLI優先」に従い、CLI を採用した。会議処理は都度発生の業務で日次ルーティンではないため、
常時ツール定義を積む必要がない。

会議処理が日次ルーティン化し、Cro が対話の中で頻繁に過去会議を横断参照するようになった時点で、
MCP への切り替えを再検討する。
