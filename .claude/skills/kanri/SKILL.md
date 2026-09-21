---
name: kanri
description: RentBook（フジヒサハウジング管理台帳／収益物件管理システム）を起動するスキル。本番URLを開くか、ローカル開発サーバを立ち上げる。起動後はユーザーの指示に従って台帳データ（物件・部屋・入金・賃料履歴・修繕・点検）の照会や資料出力を行う。トリガー: 「/kanri」「管理台帳」「台帳を開いて」「台帳起動」「RentBook」「レントブック」「フジヒサの台帳」「収益物件管理システム」
user-invocable: true
---

# RentBook — フジヒサハウジング管理台帳

`/kanri` はこのシステムを**起動する**トリガー。
起動したら止まってほせもやんの指示を待つ。先回りして操作しない。

Excel手入力をやめ、入出金を会計アプリ風UIで記帳してSupabaseに蓄積し、
どの端末からでも「本日時点の最新版」として4資料を出力するシステム。

**出力する4資料**：物件概要書／レントロール／収支表／入金状況

---

## 起動

### A. 本番（通常はこっち）

```
https://fujihisahousing.github.io/fujihisa-housing/
```

GitHub Pages 配信。`main` へのpushで自動デプロイされる。
**ブラウザで開くだけ。** 環境構築は不要。

### B. ローカル開発（改修・検証時）

```bash
git clone https://github.com/Fujihisahousing/fujihisa-housing
cd fujihisa-housing
npm install
cp .env.example .env.local    # VITE_SUPABASE_ANON_KEY を埋める
npm run dev                   # → http://localhost:5173/
```

| コマンド | 内容 |
|---|---|
| `npm run dev` | 開発サーバ起動（Vite / ポート5173） |
| `npm run build` | 本番ビルド（`tsc -b && vite build`） |
| `npm run preview` | ビルド結果の確認 |
| `npm run typecheck` | 型チェックのみ |

`.env.local` が無い場合は Drive の
`★　Crossactor/フジヒサ/rentbook_data/rentbook-data-backup/.env.local` から持ってくる。

---

## 構成

| 要素 | 内容 |
|---|---|
| リポジトリ | `github.com/Fujihisahousing/fujihisa-housing`（public） |
| 技術 | React + TypeScript + Vite / Tailwind / Zustand / SheetJS |
| DB | Supabase `rpmiecrhnjpvgntltftd`（ap-northeast-1 / PostgreSQL 17.6） |
| ホスティング | GitHub Pages |
| 仕様書 | リポジトリ内 `docs/SOW.md` |

---

## セキュリティ設計（遵守すること）

このシステムは設計として以下を前提にしている。**崩さない。**

- **`service_role` キーはリポジトリにもアプリにも絶対に置かない。** 守りは Supabase の RLS
- `anon key` はクライアントに公開される前提のキー。`.env.local` や Drive にあるのは設計どおり
- 個人情報は**サーバ側で暗号化**（pgcrypto + Vault）。復号は `is_admin()` のみ
- `leases`（個人情報）は RLS で **admin 限定**
- 退去後 `pii_retention_years`（既定2年）で個人情報を自動匿名化（pg_cron 日次ジョブ）

---

## データ照会（アプリを起動せず直接見る場合）

Supabase MCP を使う。`project_id: rpmiecrhnjpvgntltftd`

| テーブル | 行数 | | テーブル | 行数 |
|---|---:|---|---|---:|
| `payment_records` | 6,917 | | `property_documents` | 335 |
| `transactions` | 3,104 | | `property_opex` | 289 |
| `audit_logs` | 2,820 | | `rent_history` | 258 |
| `property_repairs` | 675 | | `property_inspections` | 182 |
| `units` | 157 | | `properties` | 15 |
| `move_events` | 6 | | `move_out_ledger` | 5 |
| `profiles` | 4 | | `settings` | 2 |
| `arrears_notes` | 1 | | `leases` / `payment_notes` | 0 |

**管理物件**：プランドール堂島／阿波座／道頓堀、ルネスプランドール守口、
シャーメゾン新大阪、近畿吉田ビル、富士マンション、東大阪松原、東中浜、
五月田町、大庭町、豊野町、川西市久代

### 照会時のルール

1. **書き込み前に必ず確認を取る。** 台帳は業務の正本。誤更新は実害に直結する
2. 参照で足りる用件に `UPDATE` を使わない
3. 数字を出すときは集計条件（期間・対象物件・除外条件）を明記する
4. 入居者名・金額を外部サービスへ送信しない
5. `tmp_backup_*` / `backup_*` の24本は**作業用。照会対象に含めない**

---

## 関連

- 台帳の所在と経緯 → `CLAUDE.md` の「フジヒサハウジング管理台帳（rentbook）」節
- 未決議題 → `communications/agenda/pending.md`
