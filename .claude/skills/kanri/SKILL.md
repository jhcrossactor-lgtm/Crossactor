---
name: kanri
description: RentBook（フジヒサハウジング管理台帳）システムを起動・操作するスキル。ローカル開発サーバの起動、Supabase上の台帳データ（物件・部屋・入居者・入金・賃料履歴・修繕・点検）の照会と更新を扱う。トリガー: 「/kanri」「管理台帳」「台帳を開いて」「RentBook起動」「レントブック」「フジヒサの台帳」「家賃の入金状況」「空室状況を出して」「滞納を確認」「賃料履歴を見たい」
user-invocable: true
---

# RentBook — フジヒサハウジング管理台帳

`/kanri` はこのシステムを起動・操作するためのトリガー。

---

## システム構成

| 要素 | 所在 |
|---|---|
| アプリ本体 | `github.com/Fujihisahousing/fujihisa-housing`（別リポジトリ） |
| 業務データ | Supabase `rpmiecrhnjpvgntltftd`（ap-northeast-1 / PostgreSQL 17.6） |
| 移行SQL・取込スクリプト | Google Drive `★　Crossactor/フジヒサ/rentbook_data/`（アプリは実行時に読まない） |

---

## 起動手順

```bash
cd <fujihisa-housing のクローン先>
# ルートに .env.local が無ければ Drive の rentbook_data/rentbook-data-backup/ から配置
npm install
npm run dev
```

`.env.local` の中身は Supabase URL と **publishable キー**。
publishable キーは公開アプリのバンドルにも含まれる公開前提のキーなので、
Drive に置いてあること自体は設計どおり。

---

## データ照会

アプリを起動せずデータだけ見たい場合は Supabase MCP を直接使う。

```
project_id: rpmiecrhnjpvgntltftd
```

### 本番テーブル

| テーブル | 行数 | 内容 |
|---|---:|---|
| `properties` | 15 | 物件 |
| `units` | 157 | 部屋 |
| `leases` | 0 | 契約（**未使用。要確認**） |
| `payment_records` | 6,917 | 入金記録 |
| `transactions` | 3,104 | 取引 |
| `rent_history` | 258 | 賃料履歴 |
| `property_repairs` | 675 | 修繕 |
| `property_documents` | 335 | 書類 |
| `property_opex` | 289 | 運営費 |
| `property_inspections` | 182 | 点検 |
| `audit_logs` | 2,820 | 監査ログ |
| `move_events` / `move_out_ledger` | 6 / 5 | 入退去 |
| `arrears_notes` / `payment_notes` | 1 / 0 | 滞納・入金メモ |
| `profiles` / `settings` | 4 / 2 | ユーザー・設定 |

### 管理物件

プランドール堂島／阿波座／道頓堀、ルネスプランドール守口、シャーメゾン新大阪、
近畿吉田ビル、富士マンション、東大阪松原、東中浜、五月田町、大庭町、豊野町、川西市久代

---

## 扱う際のルール

1. **入居者名・金額は個人情報**。外部サービスへの送信、公開リポジトリへのコミットは禁止
2. **書き込み前に必ず確認を取る**。台帳は業務の正本であり、誤更新は実害に直結する
3. **参照は読み取り専用クエリで行う**。`SELECT` で足りる用件に `UPDATE` を使わない
4. **数字を出すときは集計条件を明記する**。期間・対象物件・除外条件を添える

---

## 作業用テーブルについて（触らない）

`tmp_backup_*` / `backup_*` が24本ある。依存0・ポリシー0・作成後の更新0を確認済みで、
**アプリは一切参照していない**。照会対象に含めないこと。

うち3本は RLS が無効（`rent_history_backup_dojima_20260903`、
`backup_runes202_20260904`、`backup_runes202_hist_20260904`）。
対応方針は `communications/agenda/pending.md` の議題で保留中。

---

## 要確認（未確定）

- `fujihisa-housing` のローカルクローン先パス
- `leases` テーブルが0行である理由（設計どおりか、未移行か）

---

## 関連

- 台帳の所在と構成 → `CLAUDE.md` の「フジヒサハウジング管理台帳（rentbook）」節
- 調査の経緯 → `communications/logs/2026-09-21.md`
