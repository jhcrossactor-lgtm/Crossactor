#!/bin/bash
# Crossactor AI CEO System 起動スクリプト

echo "================================================"
echo "  Crossactor AI CEO System"
echo "  Cro（クロ）& BONE（ボーン）起動中..."
echo "================================================"

# .env ファイルの確認
if [ ! -f backend/.env ]; then
  if [ -f backend/.env.example ]; then
    cp backend/.env.example backend/.env
    echo ""
    echo "⚠️  backend/.env を作成しました。"
    echo "   ANTHROPIC_API_KEY を設定してください。"
    echo "   例: echo 'ANTHROPIC_API_KEY=sk-ant-...' > backend/.env"
    echo ""
  fi
fi

# 依存パッケージのインストール確認
cd backend
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "依存パッケージをインストール中..."
  pip install -r requirements.txt
fi

echo ""
echo "サーバー起動中... http://localhost:8000"
echo "ダッシュボード: http://localhost:8000"
echo ""
echo "停止するには Ctrl+C を押してください"
echo "================================================"

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
