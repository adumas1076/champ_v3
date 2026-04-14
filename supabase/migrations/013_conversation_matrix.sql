-- ============================================
-- Conversation Matrix Graph — 5 new tables
-- Migration: 013_conversation_matrix.sql
-- Date: 2026-04-13
-- ============================================

-- 1. Callback-worthy moments
CREATE TABLE IF NOT EXISTS conv_callbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    callback_type TEXT NOT NULL,
    trigger_text TEXT NOT NULL,
    user_reaction TEXT,
    context_summary TEXT,
    engagement_score REAL DEFAULT 0.5,
    times_called_back INTEGER DEFAULT 0,
    last_called_back TIMESTAMPTZ,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_callbacks_user ON conv_callbacks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_callbacks_score ON conv_callbacks(engagement_score DESC);

-- 2. Emotional arcs per session
CREATE TABLE IF NOT EXISTS conv_emotional_arcs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    arc_data JSONB NOT NULL,
    dominant_emotion TEXT,
    arc_shape TEXT,
    peak_moment TEXT,
    valley_moment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arcs_user ON conv_emotional_arcs(user_id);

-- 3. Per-law effectiveness scores
CREATE TABLE IF NOT EXISTS conv_law_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    law_id INTEGER NOT NULL,
    law_name TEXT NOT NULL,
    avg_score REAL DEFAULT 0.5,
    times_scored INTEGER DEFAULT 0,
    times_positive INTEGER DEFAULT 0,
    times_negative INTEGER DEFAULT 0,
    recommended_dial REAL,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, operator_name, law_id)
);
CREATE INDEX IF NOT EXISTS idx_law_scores_user ON conv_law_scores(user_id, operator_name);

-- 4. Relationship stage tracking
CREATE TABLE IF NOT EXISTS conv_relationship_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    stage TEXT DEFAULT 'new',
    session_count INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    stage_history JSONB DEFAULT '[]',
    roast_modifier INTEGER DEFAULT 0,
    formality_level TEXT DEFAULT 'warm but measured',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, operator_name)
);

-- 5. Unresolved conversation threads
CREATE TABLE IF NOT EXISTS conv_unresolved_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    operator_name TEXT DEFAULT 'champ',
    topic TEXT NOT NULL,
    user_position TEXT,
    operator_position TEXT,
    context_snippet TEXT,
    status TEXT DEFAULT 'open',
    revisit_count INTEGER DEFAULT 0,
    last_revisited TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_unresolved_user ON conv_unresolved_threads(user_id, status);

-- Upsert function for law scores (rolling average)
CREATE OR REPLACE FUNCTION upsert_law_score(
    p_user_id TEXT,
    p_operator_name TEXT,
    p_law_id INTEGER,
    p_law_name TEXT,
    p_new_score REAL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO conv_law_scores (user_id, operator_name, law_id, law_name, avg_score, times_scored, updated_at)
    VALUES (p_user_id, p_operator_name, p_law_id, p_law_name, p_new_score, 1, now())
    ON CONFLICT (user_id, operator_name, law_id) DO UPDATE SET
        avg_score = (conv_law_scores.avg_score * conv_law_scores.times_scored + p_new_score)
                    / (conv_law_scores.times_scored + 1),
        times_scored = conv_law_scores.times_scored + 1,
        updated_at = now();
END;
$$ LANGUAGE plpgsql;
