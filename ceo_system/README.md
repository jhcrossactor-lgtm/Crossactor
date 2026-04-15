# Crossactor AI CEO System

**Cro（クロ）& BONE（ボーン）による AI 経営支援システム**

---

## 組織構成

```
オーナー（社長）
    │  最高権限・最終決定
    ▼
  Cro（クロ）- AI CEO
  ・全業務・全人員を統括
  ・オーナーの指示を実行
  ・必要に応じてAI人員を増員
    │
    ├── 相談 ──▶ BONE（ボーン）- AI 情報参謀
    │              ・決定権なし
    │              ・最新情報を常に収集
    │              ・膨大な知識でCroの相談に応える
    │
    └── 指揮 ──▶ [増員されたAIエージェント群]
```

---

## セットアップ

```bash
# 1. APIキーを設定
echo "ANTHROPIC_API_KEY=sk-ant-your-key" > ceo_system/backend/.env

# 2. 依存パッケージをインストール
pip install -r ceo_system/backend/requirements.txt

# 3. 起動
bash ceo_system/start.sh
```

ブラウザで `http://localhost:8000` を開く

---

## ファイル構成

```
ceo_system/
├── backend/
│   ├── main.py              # FastAPI サーバー
│   ├── requirements.txt     # 依存パッケージ
│   ├── .env.example         # APIキー設定テンプレート
│   ├── agents/
│   │   ├── cro.py           # Cro（AI CEO）エージェント
│   │   ├── bone.py          # BONE（参謀）エージェント
│   │   └── agent_manager.py # AI人員管理システム
│   └── memory/
│       ├── cro_memory.json  # Croの業務メモリ
│       ├── bone_knowledge.json # BONEの知識ベース
│       └── personnel.json   # 組織・人員情報
├── dashboard/
│   ├── index.html           # オーナー向けダッシュボード
│   ├── style.css            # スタイル
│   └── app.js               # フロントエンドロジック
└── start.sh                 # 起動スクリプト
```

---

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/chat` | Croへのメッセージ送信 |
| GET  | `/api/org` | 組織図取得 |
| GET  | `/api/org/agents` | エージェント一覧 |
| POST | `/api/org/hire` | AI人員を採用 |
| POST | `/api/session/reset` | セッションリセット |
