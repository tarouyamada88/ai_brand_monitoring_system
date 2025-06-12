#!/bin/bash

# AI Brand Monitoring System - デモ用データ生成スクリプト

echo "🎯 Generating demo data for AI Brand Monitoring System..."

# PostgreSQLにサンプルデータを挿入
python3 << 'EOF'
import psycopg2
from datetime import datetime, timedelta
import random

# データベース設定
db_config = {
    'host': 'localhost',
    'database': 'ai_monitoring',
    'user': 'manus',
    'password': 'manus_password'
}

# サンプルデータ
ai_names = ['ChatGPT', 'Gemini', 'Claude']
brand_keywords = ['Python', '機械学習', 'AI開発', 'データサイエンス']
sentiments = ['positive', 'negative', 'neutral']

sample_queries = [
    "Pythonの学習方法を教えてください",
    "機械学習の始め方は？",
    "AI開発に必要なスキルは？",
    "データサイエンスの将来性について",
    "おすすめのプログラミング言語は？"
]

sample_responses = [
    "Pythonは初心者にも学びやすい優れたプログラミング言語です。豊富なライブラリと活発なコミュニティが特徴です。",
    "機械学習を始めるには、まず数学の基礎（統計学、線形代数）を学び、Pythonでの実装を練習することをお勧めします。",
    "AI開発には、プログラミングスキル、数学的知識、ドメイン知識、そして継続的な学習意欲が重要です。",
    "データサイエンスは今後も成長が期待される分野で、多くの業界で需要が高まっています。",
    "初心者にはPythonがおすすめです。シンプルな文法で学習しやすく、AI・機械学習分野でも広く使われています。"
]

try:
    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cursor:
            print("Inserting sample AI responses...")
            
            # 過去7日間のデータを生成
            for i in range(50):
                ai_name = random.choice(ai_names)
                query = random.choice(sample_queries)
                response = random.choice(sample_responses)
                sentiment = random.choice(sentiments)
                
                # ランダムな過去の時刻を生成
                days_ago = random.randint(0, 7)
                hours_ago = random.randint(0, 23)
                timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
                
                cursor.execute("""
                    INSERT INTO ai_responses (ai_name, query_text, response_text, response_sentiment, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (ai_name, query, response, sentiment, timestamp))
                
                response_id = cursor.fetchone()[0]
                
                # ブランド言及データを生成（50%の確率）
                if random.random() < 0.5:
                    brand = random.choice(brand_keywords)
                    mention_type = random.choice(['direct', 'implied', 'link'])
                    mention_sentiment = random.choice(sentiments)
                    context = response[:100] + "..."
                    
                    cursor.execute("""
                        INSERT INTO brand_mentions (ai_response_id, brand_name, mention_type, sentiment, context, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (response_id, brand, mention_type, mention_sentiment, context, timestamp))
            
            conn.commit()
            print(f"✅ Successfully inserted 50 sample AI responses")
            
            # データ統計を表示
            cursor.execute("SELECT COUNT(*) FROM ai_responses")
            total_responses = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM brand_mentions")
            total_mentions = cursor.fetchone()[0]
            
            print(f"📊 Database statistics:")
            print(f"   - Total AI responses: {total_responses}")
            print(f"   - Total brand mentions: {total_mentions}")
            
except Exception as e:
    print(f"❌ Error generating demo data: {e}")

EOF

echo "🎉 Demo data generation completed!"
echo "You can now start the dashboard to see the sample data:"
echo "./start_system.sh"

