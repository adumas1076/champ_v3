-- ============================================
-- CHAMP V3 — Migration 012: Hermes Harvest
-- New tables for patterns harvested from
-- NousResearch/hermes-agent:
--   1. operator_skills — skill creation + self-improvement
--   2. user_model_observations — dual-peer observations
--   3. user_model_representations — synthesized peer models
-- ============================================

-- ---- Operator Skills (Hermes Pattern #4) ----
-- Reusable procedures learned from experience.
-- Skills are per-operator, self-improving, and promotable.

CREATE TABLE IF NOT EXISTS operator_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps JSONB DEFAULT '[]'::jsonb,
    trigger_patterns JSONB DEFAULT '[]'::jsonb,
    operator_name TEXT NOT NULL DEFAULT 'champ',
    times_used INTEGER DEFAULT 0,
    times_improved INTEGER DEFAULT 0,
    effectiveness REAL DEFAULT 0.5,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'proven', 'archived')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_operator ON operator_skills(operator_name);
CREATE INDEX IF NOT EXISTS idx_skills_status ON operator_skills(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_name_operator ON operator_skills(name, operator_name);

-- RLS
ALTER TABLE operator_skills ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on operator_skills"
    ON operator_skills FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ---- User Model Observations (Hermes Pattern #3) ----
-- Individual observations from dual-peer analysis.
-- Each conversation turn may produce 0-4 observations.

CREATE TABLE IF NOT EXISTS user_model_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'anthony',
    operator_name TEXT NOT NULL DEFAULT 'champ',
    peer_type TEXT NOT NULL CHECK (peer_type IN ('user', 'ai')),
    observation TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    category TEXT DEFAULT 'pattern' CHECK (category IN ('fact', 'preference', 'pattern', 'identity', 'style')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_observations_user ON user_model_observations(user_id);
CREATE INDEX IF NOT EXISTS idx_observations_peer ON user_model_observations(peer_type);
CREATE INDEX IF NOT EXISTS idx_observations_created ON user_model_observations(created_at DESC);

-- RLS
ALTER TABLE user_model_observations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on user_model_observations"
    ON user_model_observations FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ---- User Model Representations (Hermes Pattern #3) ----
-- Synthesized compact representations from observations.
-- One row per (user_id, operator_name, peer_type) combo.

CREATE TABLE IF NOT EXISTS user_model_representations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'anthony',
    operator_name TEXT NOT NULL DEFAULT 'champ',
    peer_type TEXT NOT NULL CHECK (peer_type IN ('user', 'ai')),
    representation TEXT DEFAULT '',
    observation_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, operator_name, peer_type)
);

CREATE INDEX IF NOT EXISTS idx_representations_user ON user_model_representations(user_id);

-- RLS
ALTER TABLE user_model_representations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on user_model_representations"
    ON user_model_representations FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
