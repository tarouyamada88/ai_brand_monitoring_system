#!/usr/bin/env python3
"""
AI Brand Monitoring System - 統合テストスクリプト
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemTester:
    """システム統合テストクラス"""
    
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'database': 'ai_monitoring',
            'user': 'manus',
            'password': 'manus_password'
        }
        self.test_results = []
    
    def test_database_connection(self) -> bool:
        """データベース接続テスト"""
        logger.info("Testing database connection...")
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                    logger.info(f"Database connected successfully: {version}")
                    return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def test_database_schema(self) -> bool:
        """データベーススキーマテスト"""
        logger.info("Testing database schema...")
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    # 必要なテーブルの存在確認
                    required_tables = ['ai_responses', 'brand_mentions']
                    
                    for table in required_tables:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = %s
                            );
                        """, (table,))
                        
                        exists = cursor.fetchone()[0]
                        if not exists:
                            logger.error(f"Required table '{table}' does not exist")
                            return False
                        
                        logger.info(f"Table '{table}' exists")
                    
                    return True
        except Exception as e:
            logger.error(f"Database schema test failed: {e}")
            return False
    
    def test_monitoring_engine_import(self) -> bool:
        """監視エンジンのインポートテスト"""
        logger.info("Testing monitoring engine import...")
        try:
            from monitoring_engine import MonitoringEngine, DatabaseManager, AICollector
            logger.info("Monitoring engine imported successfully")
            return True
        except Exception as e:
            logger.error(f"Monitoring engine import failed: {e}")
            return False
    
    def test_data_processor_import(self) -> bool:
        """データ処理エンジンのインポートテスト"""
        logger.info("Testing data processor import...")
        try:
            from data_processor import DataProcessor, TextAnalyzer, BrandMentionDetector
            logger.info("Data processor imported successfully")
            return True
        except Exception as e:
            logger.error(f"Data processor import failed: {e}")
            return False
    
    def test_dashboard_import(self) -> bool:
        """ダッシュボードのインポートテスト"""
        logger.info("Testing dashboard import...")
        try:
            import streamlit
            from dashboard import DashboardData, DatabaseConnection
            logger.info("Dashboard imported successfully")
            return True
        except Exception as e:
            logger.error(f"Dashboard import failed: {e}")
            return False
    
    def test_alert_system_import(self) -> bool:
        """アラートシステムのインポートテスト"""
        logger.info("Testing alert system import...")
        try:
            from alert_system import AlertEngine, EmailNotifier, AlertRule
            logger.info("Alert system imported successfully")
            return True
        except Exception as e:
            logger.error(f"Alert system import failed: {e}")
            return False
    
    def test_sample_data_insertion(self) -> bool:
        """サンプルデータ挿入テスト"""
        logger.info("Testing sample data insertion...")
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    # サンプルデータを挿入
                    cursor.execute("""
                        INSERT INTO ai_responses (ai_name, query_text, response_text, response_sentiment)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (
                        "TestAI",
                        "Pythonについて教えてください",
                        "Pythonは素晴らしいプログラミング言語です。",
                        "positive"
                    ))
                    
                    response_id = cursor.fetchone()[0]
                    
                    # ブランド言及データを挿入
                    cursor.execute("""
                        INSERT INTO brand_mentions (ai_response_id, brand_name, mention_type, sentiment, context)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        response_id,
                        "Python",
                        "direct",
                        "positive",
                        "Pythonは素晴らしいプログラミング言語です。"
                    ))
                    
                    conn.commit()
                    logger.info("Sample data inserted successfully")
                    return True
                    
        except Exception as e:
            logger.error(f"Sample data insertion failed: {e}")
            return False
    
    def test_data_retrieval(self) -> bool:
        """データ取得テスト"""
        logger.info("Testing data retrieval...")
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # AI応答データの取得
                    cursor.execute("SELECT COUNT(*) as count FROM ai_responses")
                    response_count = cursor.fetchone()['count']
                    
                    # ブランド言及データの取得
                    cursor.execute("SELECT COUNT(*) as count FROM brand_mentions")
                    mention_count = cursor.fetchone()['count']
                    
                    logger.info(f"Retrieved {response_count} AI responses and {mention_count} brand mentions")
                    return True
                    
        except Exception as e:
            logger.error(f"Data retrieval failed: {e}")
            return False
    
    def test_text_analyzer(self) -> bool:
        """テキスト解析機能テスト"""
        logger.info("Testing text analyzer...")
        try:
            from data_processor import TextAnalyzer
            
            analyzer = TextAnalyzer()
            
            # 感情分析テスト
            test_text = "This is a great product!"
            sentiment = analyzer.analyze_sentiment(test_text)
            
            if isinstance(sentiment, dict) and 'positive' in sentiment:
                logger.info("Text analyzer working correctly")
                return True
            else:
                logger.error("Text analyzer returned unexpected result")
                return False
                
        except Exception as e:
            logger.error(f"Text analyzer test failed: {e}")
            return False
    
    def test_streamlit_dashboard(self) -> bool:
        """Streamlitダッシュボードテスト"""
        logger.info("Testing Streamlit dashboard...")
        try:
            # Streamlitアプリが正常に起動するかテスト
            result = subprocess.run([
                'streamlit', 'run', 'dashboard.py', '--server.headless', 'true', '--server.port', '8502'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 or "started" in result.stderr.lower():
                logger.info("Streamlit dashboard can be started")
                return True
            else:
                logger.error(f"Streamlit dashboard failed to start: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.info("Streamlit dashboard started successfully (timeout as expected)")
            return True
        except Exception as e:
            logger.error(f"Streamlit dashboard test failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """全てのテストを実行"""
        logger.info("Starting comprehensive system tests...")
        
        tests = [
            ("Database Connection", self.test_database_connection),
            ("Database Schema", self.test_database_schema),
            ("Monitoring Engine Import", self.test_monitoring_engine_import),
            ("Data Processor Import", self.test_data_processor_import),
            ("Dashboard Import", self.test_dashboard_import),
            ("Alert System Import", self.test_alert_system_import),
            ("Sample Data Insertion", self.test_sample_data_insertion),
            ("Data Retrieval", self.test_data_retrieval),
            ("Text Analyzer", self.test_text_analyzer),
            ("Streamlit Dashboard", self.test_streamlit_dashboard)
        ]
        
        results = {}
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
                if result:
                    passed += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                results[test_name] = False
                logger.error(f"❌ {test_name}: ERROR - {e}")
        
        # テスト結果サマリー
        logger.info(f"\n{'='*50}")
        logger.info(f"TEST SUMMARY: {passed}/{total} tests passed")
        logger.info(f"{'='*50}")
        
        if passed == total:
            logger.info("🎉 All tests passed! System is ready for deployment.")
        else:
            logger.warning(f"⚠️  {total - passed} test(s) failed. Please check the issues above.")
        
        return results

class PerformanceOptimizer:
    """パフォーマンス最適化クラス"""
    
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'database': 'ai_monitoring',
            'user': 'manus',
            'password': 'manus_password'
        }
    
    def create_database_indexes(self):
        """データベースインデックスを作成"""
        logger.info("Creating database indexes for performance optimization...")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_ai_responses_timestamp ON ai_responses(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_ai_responses_ai_name ON ai_responses(ai_name);",
            "CREATE INDEX IF NOT EXISTS idx_ai_responses_sentiment ON ai_responses(response_sentiment);",
            "CREATE INDEX IF NOT EXISTS idx_brand_mentions_brand_name ON brand_mentions(brand_name);",
            "CREATE INDEX IF NOT EXISTS idx_brand_mentions_sentiment ON brand_mentions(sentiment);",
            "CREATE INDEX IF NOT EXISTS idx_brand_mentions_ai_response_id ON brand_mentions(ai_response_id);"
        ]
        
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    for index_sql in indexes:
                        cursor.execute(index_sql)
                        logger.info(f"Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
                    
                    conn.commit()
                    logger.info("Database indexes created successfully")
                    
        except Exception as e:
            logger.error(f"Failed to create database indexes: {e}")
    
    def optimize_database_settings(self):
        """データベース設定を最適化"""
        logger.info("Optimizing database settings...")
        
        optimizations = [
            "VACUUM ANALYZE ai_responses;",
            "VACUUM ANALYZE brand_mentions;"
        ]
        
        try:
            with psycopg2.connect(**self.db_config) as conn:
                conn.autocommit = True
                with conn.cursor() as cursor:
                    for optimization in optimizations:
                        cursor.execute(optimization)
                        logger.info(f"Executed: {optimization}")
                    
                    logger.info("Database optimization completed")
                    
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")

def main():
    """メイン関数"""
    print("🚀 AI Brand Monitoring System - Integration Test & Optimization")
    print("=" * 60)
    
    # システムテストを実行
    tester = SystemTester()
    test_results = tester.run_all_tests()
    
    # パフォーマンス最適化を実行
    optimizer = PerformanceOptimizer()
    optimizer.create_database_indexes()
    optimizer.optimize_database_settings()
    
    print("\n" + "=" * 60)
    print("🎯 Integration test and optimization completed!")
    print("=" * 60)
    
    return all(test_results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

