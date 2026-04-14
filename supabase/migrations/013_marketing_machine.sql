-- ============================================
-- Migration 013 — Marketing Machine V1 Tables
-- Creates: waitlist + assessment_responses
-- Both tables backing capture/waitlist.py and capture/assessment.py
-- Run this against the Supabase project before launch.
-- ============================================

-- ========== WAITLIST ==========
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    -- Source attribution (which content drove them)
    source_platform TEXT,          -- twitter / instagram / linkedin / tiktok / youtube / facebook / direct
    source_influencer TEXT,        -- anthony / influencer_1 / influencer_2 / influencer_3
    source_campaign TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_content TEXT,              -- content_piece_id or keyword
    -- Status
    status TEXT DEFAULT 'active',  -- active / unsubscribed / bounced
    welcome_sent BOOLEAN DEFAULT FALSE,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist(email);
CREATE INDEX IF NOT EXISTS idx_waitlist_source ON waitlist(source_platform, source_influencer);
CREATE INDEX IF NOT EXISTS idx_waitlist_status ON waitlist(status);
CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON waitlist(created_at DESC);

-- RLS — keep leads locked down, only service role can query
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;


-- ========== ASSESSMENT RESPONSES ==========
CREATE TABLE IF NOT EXISTS assessment_responses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id TEXT NOT NULL,   -- ai_readiness / ai_stack_readiness / scale_readiness / brand_readiness
    respondent_email TEXT NOT NULL,
    respondent_name TEXT,
    -- Source attribution
    source_platform TEXT,
    source_influencer TEXT,
    source_campaign TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_content TEXT,
    -- The response data
    answers JSONB,                 -- question_id → answer
    segmentation_data JSONB,       -- open-text responses for personalization
    -- Scoring
    raw_score FLOAT,
    max_score FLOAT,
    percentage FLOAT,
    tier TEXT,                     -- cold / warm / hot / buyer
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessment_id ON assessment_responses(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_email ON assessment_responses(respondent_email);
CREATE INDEX IF NOT EXISTS idx_assessment_tier ON assessment_responses(tier);
CREATE INDEX IF NOT EXISTS idx_assessment_created_at ON assessment_responses(created_at DESC);

ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;


-- ========== UPDATED_AT TRIGGER ==========
-- Auto-update waitlist.updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_waitlist_updated_at ON waitlist;
CREATE TRIGGER update_waitlist_updated_at
    BEFORE UPDATE ON waitlist
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ========== SANITY CHECK VIEW ==========
-- Quick daily summary view for Anthony's dashboard
CREATE OR REPLACE VIEW waitlist_summary AS
SELECT
    source_platform,
    source_influencer,
    COUNT(*) as total_leads,
    COUNT(*) FILTER (WHERE welcome_sent = TRUE) as welcome_delivered,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as leads_24h,
    MAX(created_at) as latest_signup
FROM waitlist
WHERE status = 'active'
GROUP BY source_platform, source_influencer;

CREATE OR REPLACE VIEW assessment_summary AS
SELECT
    assessment_id,
    tier,
    COUNT(*) as total,
    ROUND(AVG(percentage)::numeric, 1) as avg_score,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as responses_24h
FROM assessment_responses
GROUP BY assessment_id, tier
ORDER BY assessment_id,
    CASE tier
        WHEN 'buyer' THEN 1
        WHEN 'hot' THEN 2
        WHEN 'warm' THEN 3
        WHEN 'cold' THEN 4
        ELSE 5
    END;

-- ============================================
-- Migration complete
-- ============================================