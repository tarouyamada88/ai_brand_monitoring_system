import smtplib
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass

# ログ設定
logger = logging.getLogger(__name__)

@dataclass
class AlertRule:
    """アラートルールの定義"""
    name: str
    condition_type: str  # 'sentiment_threshold', 'mention_count', 'keyword_detection'
    threshold: float
    brand_keywords: List[str]
    ai_sources: List[str]
    email_recipients: List[str]
    is_active: bool = True

@dataclass
class Alert:
    """アラート情報"""
    rule_name: str
    message: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    timestamp: datetime
    data: Dict

class EmailNotifier:
    """メール通知クラス"""
    
    def __init__(self, smtp_config: Dict[str, str]):
        self.smtp_config = smtp_config
    
    def send_alert_email(self, recipients: List[str], alert: Alert):
        """アラートメールを送信"""
        try:
            # メール内容を作成
            subject = f"[AI監視アラート] {alert.rule_name} - {alert.severity.upper()}"
            
            html_body = self._create_email_html(alert)
            text_body = self._create_email_text(alert)
            
            # MIMEメッセージを作成
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = ', '.join(recipients)
            
            # テキストとHTMLパートを追加
            text_part = MIMEText(text_body, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # SMTPサーバーに接続して送信
            with smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port']) as server:
                if self.smtp_config.get('use_tls', True):
                    server.starttls()
                
                if self.smtp_config.get('username') and self.smtp_config.get('password'):
                    server.login(self.smtp_config['username'], self.smtp_config['password'])
                
                server.send_message(msg)
            
            logger.info(f"Alert email sent to {recipients} for rule: {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
    
    def _create_email_html(self, alert: Alert) -> str:
        """HTMLメール本文を作成"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        
        color = severity_colors.get(alert.severity, '#6c757d')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-top: 10px; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .data-table th {{ background-color: #f2f2f2; }}
                .timestamp {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🚨 AI監視アラート</h2>
                <h3>{alert.rule_name}</h3>
                <p class="timestamp">発生時刻: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="content">
                <h4>アラート内容</h4>
                <p>{alert.message}</p>
                
                <h4>重要度</h4>
                <p style="color: {color}; font-weight: bold;">{alert.severity.upper()}</p>
                
                <h4>詳細データ</h4>
                <table class="data-table">
        """
        
        # データテーブルを追加
        for key, value in alert.data.items():
            html += f"<tr><th>{key}</th><td>{value}</td></tr>"
        
        html += """
                </table>
                
                <hr style="margin: 20px 0;">
                <p style="font-size: 0.9em; color: #666;">
                    このアラートは AI Brand Monitoring System により自動生成されました。<br>
                    詳細な分析結果はダッシュボードでご確認ください。
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_email_text(self, alert: Alert) -> str:
        """テキストメール本文を作成"""
        text = f"""
AI監視アラート: {alert.rule_name}

発生時刻: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
重要度: {alert.severity.upper()}

アラート内容:
{alert.message}

詳細データ:
"""
        
        for key, value in alert.data.items():
            text += f"- {key}: {value}\n"
        
        text += """
---
このアラートは AI Brand Monitoring System により自動生成されました。
詳細な分析結果はダッシュボードでご確認ください。
"""
        
        return text

class AlertEngine:
    """アラートエンジンのメインクラス"""
    
    def __init__(self, db_config: Dict[str, str], smtp_config: Dict[str, str]):
        self.db_config = db_config
        self.email_notifier = EmailNotifier(smtp_config)
        self.alert_rules = self._load_default_rules()
    
    def _load_default_rules(self) -> List[AlertRule]:
        """デフォルトのアラートルールを読み込み"""
        return [
            AlertRule(
                name="ネガティブ感情急増",
                condition_type="sentiment_threshold",
                threshold=0.7,  # ネガティブ感情が70%以上
                brand_keywords=["Python", "機械学習", "AI開発"],
                ai_sources=["ChatGPT", "Gemini", "Claude"],
                email_recipients=["admin@example.com"]
            ),
            AlertRule(
                name="ブランド言及数急増",
                condition_type="mention_count",
                threshold=10,  # 1時間で10件以上の言及
                brand_keywords=["Python", "機械学習", "AI開発"],
                ai_sources=["ChatGPT", "Gemini", "Claude"],
                email_recipients=["admin@example.com"]
            ),
            AlertRule(
                name="競合他社言及検出",
                condition_type="keyword_detection",
                threshold=1,  # 1件でもアラート
                brand_keywords=["競合", "ライバル", "代替"],
                ai_sources=["ChatGPT", "Gemini", "Claude"],
                email_recipients=["admin@example.com"]
            )
        ]
    
    def check_sentiment_threshold(self, rule: AlertRule) -> Optional[Alert]:
        """感情閾値チェック"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # 過去1時間のネガティブ感情応答を取得
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_count,
                            SUM(CASE WHEN response_sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                            ai_name
                        FROM ai_responses 
                        WHERE timestamp >= NOW() - INTERVAL '1 hour'
                        AND ai_name = ANY(%s)
                        GROUP BY ai_name
                    """, (rule.ai_sources,))
                    
                    results = cursor.fetchall()
                    
                    for result in results:
                        if result['total_count'] > 0:
                            negative_ratio = result['negative_count'] / result['total_count']
                            
                            if negative_ratio >= rule.threshold:
                                return Alert(
                                    rule_name=rule.name,
                                    message=f"{result['ai_name']}でネガティブ感情の応答が急増しています（{negative_ratio:.1%}）",
                                    severity="high" if negative_ratio >= 0.8 else "medium",
                                    timestamp=datetime.now(),
                                    data={
                                        "AI名": result['ai_name'],
                                        "総応答数": result['total_count'],
                                        "ネガティブ応答数": result['negative_count'],
                                        "ネガティブ比率": f"{negative_ratio:.1%}",
                                        "期間": "過去1時間"
                                    }
                                )
            
            return None
            
        except Exception as e:
            logger.error(f"Sentiment threshold check error: {e}")
            return None
    
    def check_mention_count(self, rule: AlertRule) -> Optional[Alert]:
        """言及数チェック"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # 過去1時間のブランド言及数を取得
                    cursor.execute("""
                        SELECT 
                            bm.brand_name,
                            COUNT(*) as mention_count,
                            ar.ai_name
                        FROM brand_mentions bm
                        JOIN ai_responses ar ON bm.ai_response_id = ar.id
                        WHERE ar.timestamp >= NOW() - INTERVAL '1 hour'
                        AND bm.brand_name = ANY(%s)
                        AND ar.ai_name = ANY(%s)
                        GROUP BY bm.brand_name, ar.ai_name
                    """, (rule.brand_keywords, rule.ai_sources))
                    
                    results = cursor.fetchall()
                    
                    for result in results:
                        if result['mention_count'] >= rule.threshold:
                            return Alert(
                                rule_name=rule.name,
                                message=f"{result['brand_name']}の言及数が急増しています（{result['ai_name']}で{result['mention_count']}件）",
                                severity="medium" if result['mention_count'] < 20 else "high",
                                timestamp=datetime.now(),
                                data={
                                    "ブランド名": result['brand_name'],
                                    "AI名": result['ai_name'],
                                    "言及数": result['mention_count'],
                                    "期間": "過去1時間"
                                }
                            )
            
            return None
            
        except Exception as e:
            logger.error(f"Mention count check error: {e}")
            return None
    
    def check_keyword_detection(self, rule: AlertRule) -> Optional[Alert]:
        """キーワード検出チェック"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # 過去1時間で特定キーワードを含む応答を検索
                    keyword_pattern = '|'.join(rule.brand_keywords)
                    
                    cursor.execute("""
                        SELECT 
                            ar.ai_name,
                            ar.query_text,
                            ar.response_text,
                            ar.timestamp
                        FROM ai_responses ar
                        WHERE ar.timestamp >= NOW() - INTERVAL '1 hour'
                        AND ar.ai_name = ANY(%s)
                        AND (ar.response_text ~* %s OR ar.query_text ~* %s)
                        ORDER BY ar.timestamp DESC
                        LIMIT 5
                    """, (rule.ai_sources, keyword_pattern, keyword_pattern))
                    
                    results = cursor.fetchall()
                    
                    if len(results) >= rule.threshold:
                        return Alert(
                            rule_name=rule.name,
                            message=f"特定キーワード（{', '.join(rule.brand_keywords)}）を含む応答が検出されました",
                            severity="low",
                            timestamp=datetime.now(),
                            data={
                                "検出件数": len(results),
                                "キーワード": ', '.join(rule.brand_keywords),
                                "最新の応答": results[0]['response_text'][:200] + "..." if results else "",
                                "期間": "過去1時間"
                            }
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Keyword detection check error: {e}")
            return None
    
    def run_alert_checks(self):
        """全てのアラートルールをチェック"""
        logger.info("Starting alert checks...")
        
        for rule in self.alert_rules:
            if not rule.is_active:
                continue
            
            alert = None
            
            if rule.condition_type == "sentiment_threshold":
                alert = self.check_sentiment_threshold(rule)
            elif rule.condition_type == "mention_count":
                alert = self.check_mention_count(rule)
            elif rule.condition_type == "keyword_detection":
                alert = self.check_keyword_detection(rule)
            
            if alert:
                logger.info(f"Alert triggered: {alert.rule_name}")
                self.email_notifier.send_alert_email(rule.email_recipients, alert)
                self._log_alert(alert)
        
        logger.info("Alert checks completed")
    
    def _log_alert(self, alert: Alert):
        """アラートをデータベースにログ"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cursor:
                    # アラートログテーブルが存在しない場合は作成
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS alert_logs (
                            id SERIAL PRIMARY KEY,
                            rule_name VARCHAR(255) NOT NULL,
                            message TEXT NOT NULL,
                            severity VARCHAR(50) NOT NULL,
                            data JSONB,
                            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # アラートを挿入
                    cursor.execute("""
                        INSERT INTO alert_logs (rule_name, message, severity, data)
                        VALUES (%s, %s, %s, %s)
                    """, (alert.rule_name, alert.message, alert.severity, json.dumps(alert.data)))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

def main():
    """テスト用メイン関数"""
    # データベース設定
    db_config = {
        'host': 'localhost',
        'database': 'ai_monitoring',
        'user': 'manus',
        'password': 'manus_password'
    }
    
    # SMTP設定（実際の設定に置き換えてください）
    smtp_config = {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'username': 'your_email@gmail.com',
        'password': 'your_app_password',
        'from_email': 'your_email@gmail.com'
    }
    
    # アラートエンジンを初期化
    alert_engine = AlertEngine(db_config, smtp_config)
    
    # アラートチェックを実行
    alert_engine.run_alert_checks()

if __name__ == "__main__":
    main()

