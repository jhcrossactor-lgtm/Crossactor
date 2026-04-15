# スキル：開発・技術

Crossactorの技術スタックと開発業務で活用するノウハウ。

---

## 現在の技術スタック

### AI CEO System（本システム）
- **Backend**：Python / FastAPI / Uvicorn
- **AI**：Anthropic Claude API（claude-sonnet-4-6）
- **通知**：LINE Messaging API（Webhook）
- **デプロイ**：Railway
- **ストレージ**：JSON（メモリ・人員情報）

### フロントエンド（ダッシュボード）
- Vanilla HTML / CSS / JavaScript
- Railway の Static Files として配信

---

## 開発原則

1. **シンプルに保つ** — 必要なものだけ実装。過剰な抽象化をしない
2. **セキュリティ最優先** — APIキー・認証情報は環境変数で管理、コミットしない
3. **エラーをユーザーに見せる** — 障害発生時はCroがユーザーに即座に報告
4. **ドキュメントと一緒に動かす** — コード変更は必ず関連ドキュメントも更新

---

## 標準開発フロー

```
1. ほせもやんから要件受領
2. Croが要件を分解・タスク化
3. 実装（コード変更）
4. テスト確認
5. Railwayへデプロイ（git push → 自動デプロイ）
6. ほせもやんに完了報告
```

---

## リポジトリ構成

```
Crossactor/
├── CLAUDE.md               # Claude Code 動作定義
├── organization/           # 組織定義
├── skills/                 # 専門スキル
├── communications/         # 対話ログ
└── ceo_system/
    └── backend/
        ├── main.py         # FastAPI メインサーバー
        ├── agents/         # Cro・BONE エージェント
        ├── dashboard/      # Web ダッシュボード
        └── memory/         # 永続化データ（JSON）
```

---

## 今後の技術拡張候補

- データベース移行（SQLite or Supabase）
- ベクトル検索によるメモリ高度化
- Webhook対応の拡充（Slack, Notion等）
- 3Dレンダリングパイプラインの自動化
