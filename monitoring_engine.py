import os
import time
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
import google.generativeai as genai
from anthropic import Anthropic
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """データベース接続とクエリ管理"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        
    def get_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(**self.db_config)
    
    def insert_ai_response(self, ai_name: str, query_text: str, response_text: str, 
                          sentiment: Optional[str] = None, topics: Optional[List[str]] = None,
                          links: Optional[List[str]] = None) -> int:
        """AI応答をデータベースに保存"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ai_responses (ai_name, query_text, response_text, response_sentiment, response_topics, response_links)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (ai_name, query_text, response_text, sentiment, topics, links))
                return cursor.fetchone()[0]

class AICollector:
    """AI APIからデータを収集するクラス"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        # API設定（環境変数から取得）
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        
        # APIクライアント初期化
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        if self.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
    
    def query_chatgpt(self, query: str) -> Optional[str]:
        """ChatGPT APIにクエリを送信"""
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API key not found")
                return None
                
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": query}],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"ChatGPT API error: {e}")
            return None
    
    def query_gemini(self, query: str) -> Optional[str]:
        """Gemini APIにクエリを送信"""
        try:
            if not self.gemini_api_key:
                logger.warning("Gemini API key not found")
                return None
                
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(query)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def query_claude(self, query: str) -> Optional[str]:
        """Claude APIにクエリを送信"""
        try:
            if not self.anthropic_api_key:
                logger.warning("Anthropic API key not found")
                return None
                
            response = self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                messages=[{"role": "user", "content": query}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

class WebScraper:
    """WebインターフェースからAI応答を収集するクラス"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.driver = None
    
    def setup_driver(self):
        """Seleniumドライバーをセットアップ"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def close_driver(self):
        """ドライバーを閉じる"""
        if self.driver:
            self.driver.quit()
    
    def scrape_perplexity(self, query: str) -> Optional[str]:
        """Perplexity AIから応答を取得"""
        try:
            if not self.driver:
                self.setup_driver()
            
            self.driver.get("https://www.perplexity.ai/")
            
            # 検索ボックスを見つけて入力
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea"))
            )
            search_box.send_keys(query)
            
            # 送信ボタンをクリック
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            
            # 応答を待機
            time.sleep(5)
            
            # 応答テキストを取得
            response_elements = self.driver.find_elements(By.CSS_SELECTOR, ".prose")
            if response_elements:
                return response_elements[-1].text
            
            return None
        except Exception as e:
            logger.error(f"Perplexity scraping error: {e}")
            return None

class QueryGenerator:
    """監視用クエリを生成するクラス"""
    
    def __init__(self, brand_keywords: List[str]):
        self.brand_keywords = brand_keywords
    
    def generate_queries(self) -> List[str]:
        """ブランド監視用のクエリを生成"""
        base_queries = [
            "おすすめの{}は何ですか？",
            "{}について教えてください",
            "{}の評判はどうですか？",
            "{}の競合他社を教えてください",
            "{}を使うメリットは何ですか？"
        ]
        
        queries = []
        for keyword in self.brand_keywords:
            for base_query in base_queries:
                queries.append(base_query.format(keyword))
        
        return queries

class MonitoringEngine:
    """メインの監視エンジン"""
    
    def __init__(self, db_config: Dict[str, str], brand_keywords: List[str]):
        self.db_manager = DatabaseManager(db_config)
        self.ai_collector = AICollector(self.db_manager)
        self.web_scraper = WebScraper(self.db_manager)
        self.query_generator = QueryGenerator(brand_keywords)
        
    def run_monitoring_cycle(self):
        """1回の監視サイクルを実行"""
        logger.info("Starting monitoring cycle...")
        
        queries = self.query_generator.generate_queries()
        
        for query in queries[:5]:  # テスト用に最初の5つのクエリのみ実行
            logger.info(f"Processing query: {query}")
            
            # ChatGPT
            chatgpt_response = self.ai_collector.query_chatgpt(query)
            if chatgpt_response:
                self.db_manager.insert_ai_response("ChatGPT", query, chatgpt_response)
                logger.info("ChatGPT response saved")
            
            # Gemini
            gemini_response = self.ai_collector.query_gemini(query)
            if gemini_response:
                self.db_manager.insert_ai_response("Gemini", query, gemini_response)
                logger.info("Gemini response saved")
            
            # Claude
            claude_response = self.ai_collector.query_claude(query)
            if claude_response:
                self.db_manager.insert_ai_response("Claude", query, claude_response)
                logger.info("Claude response saved")
            
            # レート制限を避けるため少し待機
            time.sleep(2)
        
        logger.info("Monitoring cycle completed")

def main():
    """メイン関数"""
    # データベース設定
    db_config = {
        'host': 'localhost',
        'database': 'ai_monitoring',
        'user': 'manus',
        'password': 'manus_password'
    }
    
    # 監視対象のブランドキーワード
    brand_keywords = ["Python", "機械学習", "AI開発"]
    
    # 監視エンジンを初期化
    engine = MonitoringEngine(db_config, brand_keywords)
    
    # スケジューラーを設定
    scheduler = BlockingScheduler()
    
    # 3時間ごとに監視を実行
    scheduler.add_job(
        func=engine.run_monitoring_cycle,
        trigger=IntervalTrigger(hours=3),
        id='monitoring_job',
        name='AI Brand Monitoring',
        replace_existing=True
    )
    
    # 即座に1回実行
    engine.run_monitoring_cycle()
    
    logger.info("Starting scheduler...")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        scheduler.shutdown()

if __name__ == "__main__":
    main()

