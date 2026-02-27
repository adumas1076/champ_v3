-- ============================================
-- CHAMP V3 — Self Mode Runs Table
-- Brick 8: State persistence for autonomous runs
-- ============================================

CREATE TABLE IF NOT EXISTS self_mode_runs (
    id TEXT PRIMARY KEY,
    goal_card JSONB NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    subtasks JSONB DEFAULT '[]'::jsonb,
    result_pack JSONB,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for heartbeat polling (queued runs)
CREATE INDEX IF NOT EXISTS idx_self_mode_runs_status
    ON self_mode_runs(status)
    WHERE status = 'queued';

-- Index for lookups by goal_id inside JSONB
CREATE INDEX IF NOT EXISTS idx_self_mode_runs_goal_id
    ON self_mode_runs((goal_card->>'goal_id'));

-- Auto-update updated_at on every UPDATE
CREATE OR REPLACE FUNCTION update_self_mode_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_self_mode_updated_at ON self_mode_runs;
CREATE TRIGGER trg_self_mode_updated_at
    BEFORE UPDATE ON self_mode_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_self_mode_updated_at();
