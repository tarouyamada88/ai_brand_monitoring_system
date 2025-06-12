# AI Brand Monitoring System - 設定ファイル

# データベース設定
DATABASE_CONFIG = {
    'host': 'localhost',
    'database': 'ai_monitoring',
    'user': 'manus',
    'password': 'manus_password'
}

# 監視対象のブランドキーワード
BRAND_KEYWORDS = [
   "みずほ銀行",
"三菱UFJ銀行",
"三井住友銀行",
"りそな銀行",
"ゆうちょ銀行"
]
# API設定（環境変数で設定）
# export OPENAI_API_KEY="your_openai_api_key"
# export GEMINI_API_KEY="your_gemini_api_key"
# export ANTHROPIC_API_KEY="your_anthropic_api_key"

# 監視間隔（時間）
MONITORING_INTERVAL_HOURS = 3

# ログレベル
LOG_LEVEL = "INFO"

