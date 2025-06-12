#!/bin/bash

# AI Brand Monitoring System - 起動スクリプト
# このスクリプトを実行するだけでシステム全体が起動します

echo "🚀 AI Brand Monitoring System - Starting..."
echo "=============================================="

# 現在のディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# PostgreSQLサービスの起動確認
echo "📊 Checking PostgreSQL service..."
if ! sudo systemctl is-active --quiet postgresql; then
    echo "Starting PostgreSQL..."
    sudo systemctl start postgresql
    sudo pg_ctlcluster 14 main start
fi

# 必要なPythonパッケージのインストール確認
echo "📦 Checking Python dependencies..."
python3 -c "import streamlit, plotly, psycopg2, chromadb" 2>/dev/null || {
    echo "Installing missing dependencies..."
    pip install streamlit plotly altair psycopg2-binary chromadb
}

# データベースの初期化
echo "🗄️  Initializing database..."
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(host='localhost', database='ai_monitoring', user='manus', password='manus_password')
    print('Database connection successful')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
    print('Please check PostgreSQL setup')
"

# Streamlitダッシュボードを起動
echo "🌐 Starting Streamlit dashboard..."
echo "Dashboard will be available at: http://localhost:8501"
echo ""
echo "To stop the system, press Ctrl+C"
echo "=============================================="

# バックグラウンドでデータ処理を開始（オプション）
# python3 monitoring_engine.py &
# python3 data_processor.py &

# Streamlitダッシュボードを起動（フォアグラウンド）
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0

