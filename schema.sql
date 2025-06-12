CREATE TABLE IF NOT EXISTS ai_responses (
    id SERIAL PRIMARY KEY,
    ai_name VARCHAR(255) NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_sentiment VARCHAR(50),
    response_topics TEXT[],
    response_links TEXT[],
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS brand_mentions (
    id SERIAL PRIMARY KEY,
    ai_response_id INTEGER REFERENCES ai_responses(id) ON DELETE CASCADE,
    brand_name VARCHAR(255) NOT NULL,
    mention_type VARCHAR(50),
    sentiment VARCHAR(50),
    context TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


