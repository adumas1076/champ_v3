# ============================================
# CHAMP V3 — FTS5 Session Search
# Harvested from: Hermes Agent (NousResearch)
#
# SQLite FTS5 full-text search across ALL past
# sessions. When an operator needs to recall
# "what did we discuss 3 weeks ago about X?",
# this finds it.
#
# Flow:
#   1. Every session's messages are indexed into
#      a local SQLite FTS5 table
#   2. Search queries hit FTS5 for fast text matching
#   3. Top results are grouped by session
#   4. A cheap LLM summarizes the relevant passages
#   5. Summaries returned to the operator
#
# This is the LONG-TERM recall tier:
#   - Snapshot (in-prompt): ~1,300 tokens, always loaded
#   - Session Search: unlimited, on-demand, LLM cost per query
# ============================================

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import requests

from brain.config import Settings

logger = logging.getLogger(__name__)

# Default DB path
DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"), ".champ", "session_index.db"
)


class SessionSearch:
    """
    Full-text search across past operator sessions.

    Architecture:
    - Local SQLite DB with FTS5 virtual table
    - Indexed on: session_id, role, content, operator_name, timestamp
    - Search returns ranked results grouped by session
    - LLM summarization for human-readable recall

    Why local SQLite and not Supabase?
    - FTS5 is faster for full-text search than PostgreSQL FTS
    - No network latency for search queries
    - Works offline
    - Supabase stores the canonical data; this is a search index
    """

    def __init__(self, settings: Settings, db_path: str = ""):
        self.settings = settings
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self.llm_url = f"{settings.litellm_base_url}/chat/completions"
        self.llm_api_key = settings.litellm_api_key

    def connect(self) -> bool:
        """Initialize SQLite DB and create FTS5 tables if needed."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info(f"[SESSION_SEARCH] Connected: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"[SESSION_SEARCH] Failed to connect: {e}")
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        """Create the FTS5 virtual table and metadata table."""
        self._conn.executescript("""
            -- Metadata table for session info
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id TEXT PRIMARY KEY,
                operator_name TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                started_at TEXT DEFAULT '',
                ended_at TEXT DEFAULT '',
                message_count INTEGER DEFAULT 0
            );

            -- FTS5 virtual table for full-text search
            CREATE VIRTUAL TABLE IF NOT EXISTS session_messages_fts USING fts5(
                session_id,
                role,
                content,
                operator_name,
                timestamp,
                tokenize='porter unicode61'
            );

            -- Message dedup tracking
            CREATE TABLE IF NOT EXISTS indexed_messages (
                session_id TEXT,
                message_index INTEGER,
                PRIMARY KEY (session_id, message_index)
            );
        """)
        self._conn.commit()

    # ---- Indexing (called at session end) ----

    def index_session(
        self,
        session_id: str,
        messages: list[dict],
        operator_name: str = "",
        user_id: str = "",
    ) -> int:
        """
        Index a session's messages into the FTS5 table.
        Returns number of messages indexed.

        Called at session end after transcript is persisted.
        Idempotent — skips already-indexed messages.
        """
        if not self._conn:
            return 0

        try:
            # Upsert session metadata
            self._conn.execute("""
                INSERT OR REPLACE INTO session_meta
                (session_id, operator_name, user_id, started_at, message_count)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id, operator_name, user_id,
                datetime.now(timezone.utc).isoformat(),
                len(messages),
            ))

            indexed = 0
            for i, msg in enumerate(messages):
                # Skip already-indexed messages
                exists = self._conn.execute(
                    "SELECT 1 FROM indexed_messages WHERE session_id=? AND message_index=?",
                    (session_id, i),
                ).fetchone()

                if exists:
                    continue

                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                timestamp = msg.get("created_at", msg.get("timestamp", ""))

                if not content.strip():
                    continue

                self._conn.execute("""
                    INSERT INTO session_messages_fts
                    (session_id, role, content, operator_name, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, role, content, operator_name, timestamp))

                self._conn.execute(
                    "INSERT INTO indexed_messages (session_id, message_index) VALUES (?, ?)",
                    (session_id, i),
                )
                indexed += 1

            self._conn.commit()
            logger.info(
                f"[SESSION_SEARCH] Indexed {indexed} messages from {session_id}"
            )
            return indexed

        except Exception as e:
            logger.error(f"[SESSION_SEARCH] Indexing failed: {e}")
            return 0

    # ---- Search ----

    def search(
        self,
        query: str,
        operator_name: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """
        Search past sessions using FTS5 full-text search.

        Returns list of matches:
        [{"session_id", "role", "content", "operator_name", "timestamp", "rank"}]
        """
        if not self._conn or not query.strip():
            return []

        try:
            # Escape FTS5 special characters
            safe_query = self._sanitize_fts_query(query)

            if operator_name:
                rows = self._conn.execute("""
                    SELECT session_id, role, content, operator_name, timestamp,
                           rank
                    FROM session_messages_fts
                    WHERE session_messages_fts MATCH ?
                    AND operator_name = ?
                    ORDER BY rank
                    LIMIT ?
                """, (safe_query, operator_name, limit)).fetchall()
            else:
                rows = self._conn.execute("""
                    SELECT session_id, role, content, operator_name, timestamp,
                           rank
                    FROM session_messages_fts
                    WHERE session_messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (safe_query, limit)).fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"[SESSION_SEARCH] Search failed: {e}")
            return []

    async def search_with_summary(
        self,
        query: str,
        operator_name: str = "",
        max_sessions: int = 3,
    ) -> str:
        """
        Search + LLM summarization for human-readable recall.

        Flow:
        1. FTS5 search finds matching messages
        2. Group by session, take top N sessions
        3. Send grouped context to cheap LLM for summarization
        4. Return per-session summaries
        """
        matches = self.search(query, operator_name, limit=30)

        if not matches:
            return ""

        # Group by session
        sessions: dict[str, list[dict]] = {}
        for match in matches:
            sid = match["session_id"]
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(match)

        # Take top N sessions (most matches = most relevant)
        top_sessions = sorted(
            sessions.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:max_sessions]

        # Build context for LLM
        context_parts = []
        for sid, msgs in top_sessions:
            meta = self._get_session_meta(sid)
            header = f"Session {sid[:8]}..."
            if meta:
                header += f" (operator: {meta.get('operator_name', '?')})"

            lines = [header]
            for msg in msgs[:10]:  # Max 10 messages per session
                role = msg["role"].upper()
                content = msg["content"][:300]
                lines.append(f"  {role}: {content}")

            context_parts.append("\n".join(lines))

        context = "\n\n---\n\n".join(context_parts)

        # Summarize with cheap LLM
        summary_prompt = f"""\
The user is asking about: "{query}"

Here are relevant excerpts from past conversations:

{context[:8000]}

Write a brief summary (2-4 sentences per session) of what was discussed
that's relevant to the query. Focus on decisions made, outcomes, and
key facts. Be specific — include names, dates, and details."""

        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": "gemini-flash",
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
                headers={"Authorization": f"Bearer {self.llm_api_key}"},
                timeout=20,
            )
            response.raise_for_status()

            summary = response.json()["choices"][0]["message"]["content"].strip()
            return f"[SESSION RECALL]\n{summary}"

        except Exception as e:
            logger.error(f"[SESSION_SEARCH] Summarization failed: {e}")
            # Fallback: return raw excerpts
            return f"[SESSION RECALL (raw)]\n{context[:1000]}"

    def _get_session_meta(self, session_id: str) -> Optional[dict]:
        if not self._conn:
            return None
        try:
            row = self._conn.execute(
                "SELECT * FROM session_meta WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def _sanitize_fts_query(self, query: str) -> str:
        """
        Sanitize a user query for FTS5.
        Removes special characters that would break the query.
        """
        # Remove FTS5 operators that could cause errors
        for char in ['"', "'", "(", ")", "*", ":", "^", "{", "}", "~"]:
            query = query.replace(char, " ")
        # Collapse whitespace
        query = " ".join(query.split())
        return query

    def get_stats(self) -> dict:
        """Get search index statistics."""
        if not self._conn:
            return {"sessions": 0, "messages": 0}

        try:
            sessions = self._conn.execute(
                "SELECT COUNT(*) FROM session_meta"
            ).fetchone()[0]
            messages = self._conn.execute(
                "SELECT COUNT(*) FROM indexed_messages"
            ).fetchone()[0]
            return {"sessions": sessions, "messages": messages}
        except Exception:
            return {"sessions": 0, "messages": 0}
