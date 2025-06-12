import re
import json
import logging
from typing import List, Dict, Optional, Tuple
import nltk
import spacy
from transformers import pipeline, AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np
import chromadb
from chromadb.config import Settings
import psycopg2
from psycopg2.extras import RealDictCursor

# ログ設定
logger = logging.getLogger(__name__)

class TextAnalyzer:
    """テキスト解析を行うクラス"""
    
    def __init__(self):
        # NLTKデータのダウンロード
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        try:
            nltk.data.find('vader_lexicon')
        except LookupError:
            nltk.download('vader_lexicon')
        
        # spaCyモデルの初期化（日本語対応）
        try:
            self.nlp = spacy.load("ja_core_news_sm")
        except OSError:
            logger.warning("Japanese spaCy model not found, using English model")
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("English spaCy model not found, using basic tokenizer")
                self.nlp = None
        
        # 感情分析パイプライン
        try:
            self.sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                return_all_scores=True
            )
        except Exception as e:
            logger.warning(f"Could not load sentiment analyzer: {e}")
            self.sentiment_analyzer = None
        
        # 文埋め込みモデル
        try:
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Could not load sentence transformer: {e}")
            self.sentence_model = None
    
    def preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        # HTMLタグの除去
        text = re.sub(r'<[^>]+>', '', text)
        
        # URLの除去
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # 特殊文字の正規化
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """固有表現抽出"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })
        
        return entities
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """感情分析"""
        if not self.sentiment_analyzer:
            return {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
        
        try:
            results = self.sentiment_analyzer(text[:512])  # トークン制限
            sentiment_scores = {}
            
            for result in results[0]:
                label = result['label'].lower()
                score = result['score']
                
                if 'pos' in label:
                    sentiment_scores['positive'] = score
                elif 'neg' in label:
                    sentiment_scores['negative'] = score
                else:
                    sentiment_scores['neutral'] = score
            
            return sentiment_scores
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
    
    def extract_topics(self, texts: List[str], n_topics: int = 5) -> List[List[str]]:
        """トピック抽出（TF-IDFベース）"""
        try:
            # 前処理
            processed_texts = [self.preprocess_text(text) for text in texts]
            
            # TF-IDFベクトル化
            vectorizer = TfidfVectorizer(
                max_features=100,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            tfidf_matrix = vectorizer.fit_transform(processed_texts)
            feature_names = vectorizer.get_feature_names_out()
            
            # クラスタリング
            kmeans = KMeans(n_clusters=min(n_topics, len(texts)), random_state=42)
            clusters = kmeans.fit_predict(tfidf_matrix)
            
            # 各クラスタの代表的な単語を抽出
            topics = []
            for i in range(n_topics):
                cluster_center = kmeans.cluster_centers_[i]
                top_indices = cluster_center.argsort()[-10:][::-1]
                topic_words = [feature_names[idx] for idx in top_indices]
                topics.append(topic_words)
            
            return topics
        except Exception as e:
            logger.error(f"Topic extraction error: {e}")
            return []
    
    def get_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """テキストの埋め込みベクトルを取得"""
        if not self.sentence_model:
            return None
        
        try:
            embedding = self.sentence_model.encode(text)
            return embedding
        except Exception as e:
            logger.error(f"Text embedding error: {e}")
            return None

class BrandMentionDetector:
    """ブランド言及検出クラス"""
    
    def __init__(self, brand_keywords: List[str]):
        self.brand_keywords = [keyword.lower() for keyword in brand_keywords]
        self.text_analyzer = TextAnalyzer()
    
    def detect_mentions(self, text: str) -> List[Dict[str, any]]:
        """テキスト内のブランド言及を検出"""
        mentions = []
        text_lower = text.lower()
        
        for keyword in self.brand_keywords:
            if keyword in text_lower:
                # 言及の種類を判定
                mention_type = self._classify_mention_type(text, keyword)
                
                # 感情分析
                sentiment_scores = self.text_analyzer.analyze_sentiment(text)
                sentiment = max(sentiment_scores, key=sentiment_scores.get)
                
                # コンテキスト抽出
                context = self._extract_context(text, keyword)
                
                mentions.append({
                    'brand_name': keyword,
                    'mention_type': mention_type,
                    'sentiment': sentiment,
                    'sentiment_scores': sentiment_scores,
                    'context': context
                })
        
        return mentions
    
    def _classify_mention_type(self, text: str, keyword: str) -> str:
        """言及の種類を分類"""
        text_lower = text.lower()
        
        # URLが含まれている場合
        if 'http' in text_lower and keyword in text_lower:
            return 'link'
        
        # 直接的な言及
        if keyword in text_lower:
            return 'direct'
        
        return 'implied'
    
    def _extract_context(self, text: str, keyword: str, window_size: int = 100) -> str:
        """キーワード周辺のコンテキストを抽出"""
        text_lower = text.lower()
        keyword_pos = text_lower.find(keyword)
        
        if keyword_pos == -1:
            return text[:200]  # キーワードが見つからない場合は先頭200文字
        
        start = max(0, keyword_pos - window_size)
        end = min(len(text), keyword_pos + len(keyword) + window_size)
        
        return text[start:end]

class VectorDatabase:
    """ベクトルデータベース管理クラス"""
    
    def __init__(self, db_path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="ai_responses",
            metadata={"hnsw:space": "cosine"}
        )
        self.text_analyzer = TextAnalyzer()
    
    def add_response(self, response_id: str, text: str, metadata: Dict[str, any]):
        """AI応答をベクトルデータベースに追加"""
        try:
            embedding = self.text_analyzer.get_text_embedding(text)
            if embedding is not None:
                self.collection.add(
                    embeddings=[embedding.tolist()],
                    documents=[text],
                    metadatas=[metadata],
                    ids=[response_id]
                )
                logger.info(f"Added response {response_id} to vector database")
        except Exception as e:
            logger.error(f"Error adding to vector database: {e}")
    
    def search_similar(self, query_text: str, n_results: int = 5) -> List[Dict[str, any]]:
        """類似した応答を検索"""
        try:
            query_embedding = self.text_analyzer.get_text_embedding(query_text)
            if query_embedding is None:
                return []
            
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n_results
            )
            
            return results
        except Exception as e:
            logger.error(f"Error searching vector database: {e}")
            return []

class DataProcessor:
    """データ処理パイプラインのメインクラス"""
    
    def __init__(self, db_config: Dict[str, str], brand_keywords: List[str]):
        self.db_config = db_config
        self.text_analyzer = TextAnalyzer()
        self.brand_detector = BrandMentionDetector(brand_keywords)
        self.vector_db = VectorDatabase()
    
    def process_ai_response(self, response_id: int, ai_name: str, query_text: str, response_text: str):
        """AI応答を処理して分析結果をデータベースに保存"""
        try:
            # テキスト前処理
            processed_text = self.text_analyzer.preprocess_text(response_text)
            
            # 感情分析
            sentiment_scores = self.text_analyzer.analyze_sentiment(processed_text)
            sentiment = max(sentiment_scores, key=sentiment_scores.get)
            
            # 固有表現抽出
            entities = self.text_analyzer.extract_entities(processed_text)
            
            # ブランド言及検出
            brand_mentions = self.brand_detector.detect_mentions(processed_text)
            
            # URLリンク抽出
            links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', response_text)
            
            # データベースを更新
            self._update_database(response_id, sentiment, entities, links, brand_mentions)
            
            # ベクトルデータベースに追加
            metadata = {
                'ai_name': ai_name,
                'query_text': query_text,
                'sentiment': sentiment,
                'timestamp': str(response_id)
            }
            self.vector_db.add_response(str(response_id), processed_text, metadata)
            
            logger.info(f"Processed response {response_id} from {ai_name}")
            
        except Exception as e:
            logger.error(f"Error processing response {response_id}: {e}")
    
    def _update_database(self, response_id: int, sentiment: str, entities: List[Dict], 
                        links: List[str], brand_mentions: List[Dict]):
        """データベースを更新"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    # ai_responsesテーブルを更新
                    cursor.execute("""
                        UPDATE ai_responses 
                        SET response_sentiment = %s, response_links = %s
                        WHERE id = %s
                    """, (sentiment, links, response_id))
                    
                    # brand_mentionsテーブルに挿入
                    for mention in brand_mentions:
                        cursor.execute("""
                            INSERT INTO brand_mentions 
                            (ai_response_id, brand_name, mention_type, sentiment, context)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            response_id,
                            mention['brand_name'],
                            mention['mention_type'],
                            mention['sentiment'],
                            mention['context']
                        ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Database update error: {e}")
    
    def batch_process_unprocessed_responses(self):
        """未処理の応答をバッチ処理"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # 未処理の応答を取得
                    cursor.execute("""
                        SELECT id, ai_name, query_text, response_text
                        FROM ai_responses
                        WHERE response_sentiment IS NULL
                        ORDER BY timestamp DESC
                        LIMIT 100
                    """)
                    
                    responses = cursor.fetchall()
                    
                    for response in responses:
                        self.process_ai_response(
                            response['id'],
                            response['ai_name'],
                            response['query_text'],
                            response['response_text']
                        )
                        
            logger.info(f"Batch processed {len(responses)} responses")
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")

def main():
    """テスト用メイン関数"""
    # データベース設定
    db_config = {
        'host': 'localhost',
        'database': 'ai_monitoring',
        'user': 'manus',
        'password': 'manus_password'
    }
    
    # ブランドキーワード
    brand_keywords = ["Python", "機械学習", "AI開発"]
    
    # データ処理エンジンを初期化
    processor = DataProcessor(db_config, brand_keywords)
    
    # バッチ処理を実行
    processor.batch_process_unprocessed_responses()

if __name__ == "__main__":
    main()

