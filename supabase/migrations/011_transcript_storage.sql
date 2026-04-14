-- ============================================
-- CHAMP V3 Migration 011: Transcript Storage
-- Harvested from Genesis/Skipper V5 call_transcripts system
-- Adds full transcript logging + evaluation scoring
-- ============================================

-- 1. Call Transcripts — stores full conversation transcripts
CREATE TABLE IF NOT EXISTS call_transcripts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT NOT NULL,
    transcript_text TEXT,                           -- full raw transcript as plain text
    transcript_json JSONB,                          -- [{timestamp, seconds, speaker, text, type}]
    message_count   INTEGER DEFAULT 0,
    user_message_count   INTEGER DEFAULT 0,
    agent_message_count  INTEGER DEFAULT 0,
    tool_call_count      INTEGER DEFAULT 0,
    duration_seconds     INTEGER,
    audio_url       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 2. Call Evaluations — scores and feedback per transcript
CREATE TABLE IF NOT EXISTS call_evaluations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT NOT NULL,
    transcript_id   UUID REFERENCES call_transcripts(id),
    overall_score   NUMERIC(3,1),
    category_scores JSONB,
    strengths       JSONB,
    weaknesses      JSONB,
    corrections     JSONB,
    section_scores  JSONB,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 3. Link transcripts to existing conversations table
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS transcript_id UUID REFERENCES call_transcripts(id);

-- 4. Indexes
CREATE INDEX IF NOT EXISTS idx_call_transcripts_session_id
    ON call_transcripts(session_id);

CREATE INDEX IF NOT EXISTS idx_call_transcripts_created_at
    ON call_transcripts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_call_evaluations_session_id
    ON call_evaluations(session_id);

CREATE INDEX IF NOT EXISTS idx_call_evaluations_transcript_id
    ON call_evaluations(transcript_id);

CREATE INDEX IF NOT EXISTS idx_conversations_transcript_id
    ON conversations(transcript_id);

-- 5. RLS — enable row-level security
ALTER TABLE call_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_evaluations ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (Brain uses service key)
CREATE POLICY "service_role_all_transcripts"
    ON call_transcripts FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "service_role_all_evaluations"
    ON call_evaluations FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
