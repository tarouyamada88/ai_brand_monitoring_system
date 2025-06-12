import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import altair as alt
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import logging

# ページ設定
st.set_page_config(
    page_title="AI Brand Monitoring Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .alert-positive {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }
    .alert-negative {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    .alert-neutral {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
    }
</style>
""", unsafe_allow_html=True)

class DatabaseConnection:
    """データベース接続管理"""
    
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'database': 'ai_monitoring',
            'user': 'manus',
            'password': 'manus_password'
        }
    
    def get_connection(self):
        """データベース接続を取得"""
        try:
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            st.error(f"データベース接続エラー: {e}")
            return None
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """クエリを実行してデータを取得"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
        except Exception as e:
            st.error(f"クエリ実行エラー: {e}")
            return None

class DashboardData:
    """ダッシュボード用データ取得クラス"""
    
    def __init__(self):
        self.db = DatabaseConnection()
    
    def get_summary_stats(self) -> Dict:
        """サマリー統計を取得"""
        # 総応答数
        total_responses = self.db.execute_query(
            "SELECT COUNT(*) as count FROM ai_responses"
        )
        
        # 今日の応答数
        today_responses = self.db.execute_query(
            "SELECT COUNT(*) as count FROM ai_responses WHERE DATE(timestamp) = CURRENT_DATE"
        )
        
        # ブランド言及数
        total_mentions = self.db.execute_query(
            "SELECT COUNT(*) as count FROM brand_mentions"
        )
        
        # 感情分析結果
        sentiment_stats = self.db.execute_query("""
            SELECT response_sentiment, COUNT(*) as count 
            FROM ai_responses 
            WHERE response_sentiment IS NOT NULL 
            GROUP BY response_sentiment
        """)
        
        return {
            'total_responses': total_responses[0]['count'] if total_responses else 0,
            'today_responses': today_responses[0]['count'] if today_responses else 0,
            'total_mentions': total_mentions[0]['count'] if total_mentions else 0,
            'sentiment_stats': sentiment_stats or []
        }
    
    def get_ai_response_trends(self, days: int = 7) -> pd.DataFrame:
        """AI応答のトレンドデータを取得"""
        query = """
            SELECT 
                DATE(timestamp) as date,
                ai_name,
                COUNT(*) as response_count
            FROM ai_responses 
            WHERE timestamp >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(timestamp), ai_name
            ORDER BY date DESC
        """
        
        data = self.db.execute_query(query, (days,))
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    
    def get_brand_mention_analysis(self) -> pd.DataFrame:
        """ブランド言及分析データを取得"""
        query = """
            SELECT 
                bm.brand_name,
                bm.sentiment,
                COUNT(*) as mention_count,
                ar.ai_name
            FROM brand_mentions bm
            JOIN ai_responses ar ON bm.ai_response_id = ar.id
            GROUP BY bm.brand_name, bm.sentiment, ar.ai_name
            ORDER BY mention_count DESC
        """
        
        data = self.db.execute_query(query)
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    
    def get_recent_responses(self, limit: int = 10) -> pd.DataFrame:
        """最近の応答データを取得"""
        query = """
            SELECT 
                ar.ai_name,
                ar.query_text,
                ar.response_text,
                ar.response_sentiment,
                ar.timestamp,
                COUNT(bm.id) as mention_count
            FROM ai_responses ar
            LEFT JOIN brand_mentions bm ON ar.id = bm.ai_response_id
            GROUP BY ar.id, ar.ai_name, ar.query_text, ar.response_text, ar.response_sentiment, ar.timestamp
            ORDER BY ar.timestamp DESC
            LIMIT %s
        """
        
        data = self.db.execute_query(query, (limit,))
        if data:
            df = pd.DataFrame(data)
            # テキストを短縮
            df['response_preview'] = df['response_text'].str[:100] + '...'
            return df
        return pd.DataFrame()

def create_sentiment_chart(sentiment_data: List[Dict]) -> go.Figure:
    """感情分析結果のチャートを作成"""
    if not sentiment_data:
        return go.Figure()
    
    sentiments = [item['response_sentiment'] for item in sentiment_data]
    counts = [item['count'] for item in sentiment_data]
    
    colors = {
        'positive': '#28a745',
        'negative': '#dc3545',
        'neutral': '#ffc107'
    }
    
    fig = go.Figure(data=[
        go.Pie(
            labels=sentiments,
            values=counts,
            marker_colors=[colors.get(s, '#6c757d') for s in sentiments],
            hole=0.4
        )
    ])
    
    fig.update_layout(
        title="感情分析結果",
        font=dict(family="Arial, sans-serif", size=12),
        showlegend=True
    )
    
    return fig

def create_trend_chart(trend_data: pd.DataFrame) -> go.Figure:
    """トレンドチャートを作成"""
    if trend_data.empty:
        return go.Figure()
    
    fig = px.line(
        trend_data,
        x='date',
        y='response_count',
        color='ai_name',
        title='AI応答数の推移',
        labels={'date': '日付', 'response_count': '応答数', 'ai_name': 'AI名'}
    )
    
    fig.update_layout(
        font=dict(family="Arial, sans-serif", size=12),
        xaxis_title="日付",
        yaxis_title="応答数"
    )
    
    return fig

def create_brand_mention_chart(mention_data: pd.DataFrame) -> go.Figure:
    """ブランド言及チャートを作成"""
    if mention_data.empty:
        return go.Figure()
    
    fig = px.bar(
        mention_data,
        x='brand_name',
        y='mention_count',
        color='sentiment',
        title='ブランド言及数（感情別）',
        labels={'brand_name': 'ブランド名', 'mention_count': '言及数', 'sentiment': '感情'},
        color_discrete_map={
            'positive': '#28a745',
            'negative': '#dc3545',
            'neutral': '#ffc107'
        }
    )
    
    fig.update_layout(
        font=dict(family="Arial, sans-serif", size=12),
        xaxis_title="ブランド名",
        yaxis_title="言及数"
    )
    
    return fig

def main():
    """メインダッシュボード"""
    
    # ヘッダー
    st.markdown('<h1 class="main-header">🔍 AI Brand Monitoring Dashboard</h1>', unsafe_allow_html=True)
    
    # データ取得
    dashboard_data = DashboardData()
    
    # サイドバー
    st.sidebar.title("📊 設定")
    
    # 期間選択
    days_range = st.sidebar.selectbox(
        "表示期間",
        [7, 14, 30],
        index=0,
        format_func=lambda x: f"過去{x}日間"
    )
    
    # 自動更新
    auto_refresh = st.sidebar.checkbox("自動更新（30秒）", value=False)
    if auto_refresh:
        st.rerun()
    
    # サマリー統計
    st.subheader("📈 概要")
    
    summary_stats = dashboard_data.get_summary_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="総応答数",
            value=summary_stats['total_responses'],
            delta=f"+{summary_stats['today_responses']} (今日)"
        )
    
    with col2:
        st.metric(
            label="ブランド言及数",
            value=summary_stats['total_mentions']
        )
    
    with col3:
        positive_count = sum(1 for s in summary_stats['sentiment_stats'] if s['response_sentiment'] == 'positive')
        st.metric(
            label="ポジティブ応答",
            value=positive_count
        )
    
    with col4:
        negative_count = sum(1 for s in summary_stats['sentiment_stats'] if s['response_sentiment'] == 'negative')
        st.metric(
            label="ネガティブ応答",
            value=negative_count
        )
    
    # チャート表示
    st.subheader("📊 分析結果")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 感情分析チャート
        sentiment_chart = create_sentiment_chart(summary_stats['sentiment_stats'])
        st.plotly_chart(sentiment_chart, use_container_width=True, key="sentiment_chart")
    
    with col2:
        # トレンドチャート
        trend_data = dashboard_data.get_ai_response_trends(days_range)
        trend_chart = create_trend_chart(trend_data)
        st.plotly_chart(trend_chart, use_container_width=True, key="trend_chart")
    # ブランド言及分析
    st.subheader("🏷️ ブランド言及分析")
    
    mention_data = dashboard_data.get_brand_mention_analysis()
    if not mention_data.empty:
        mention_chart = create_brand_mention_chart(mention_data)
        st.plotly_chart(mention_chart, use_container_width=True, key="mention_chart")
        
        # 詳細テーブル
        st.subheader("📋 詳細データ")
        st.dataframe(mention_data, use_container_width=True)
    else:
        st.info("ブランド言及データがありません。")
    
    # 最近の応答
    st.subheader("🕒 最近の応答")
    
    recent_data = dashboard_data.get_recent_responses(20)
    if not recent_data.empty:
        # 応答の表示
        for _, row in recent_data.iterrows():
            sentiment_class = f"alert-{row['response_sentiment']}" if row['response_sentiment'] else "alert-neutral"
            
            st.markdown(f"""
            <div class="alert-box {sentiment_class}">
                <strong>{row['ai_name']}</strong> - {row['timestamp']}<br>
                <strong>質問:</strong> {row['query_text']}<br>
                <strong>応答:</strong> {row['response_preview']}<br>
                <strong>感情:</strong> {row['response_sentiment'] or 'N/A'} | 
                <strong>言及数:</strong> {row['mention_count']}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("応答データがありません。")
    
    # フッター
    st.markdown("---")
    st.markdown("**AI Brand Monitoring System** - リアルタイムでAIによるブランド言及を監視")

if __name__ == "__main__":
    main()

