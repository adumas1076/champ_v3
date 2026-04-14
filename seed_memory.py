"""Seed all memory tables from champ_memory_extract.json"""

import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
client = create_client(url, key)

with open("../reference/champ_memory_extract.json", "r", encoding="utf-8") as f:
    data = json.load(f)

USER_ID = "00000000-0000-0000-0000-000000000001"

# 1. SEED MEM_PROFILE — user facts
profiles = [
    {"user_id": USER_ID, "category": "bio", "key": "name", "value": "Anthony", "confidence": "explicit", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "meta", "key": "total_sessions", "value": str(data["stats"]["total_conversations"]), "confidence": "explicit", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "meta", "key": "total_messages", "value": str(data["stats"]["total_messages"]), "confidence": "explicit", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "meta", "key": "relationship_start", "value": data["stats"]["date_range"]["earliest"], "confidence": "explicit", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "communication", "key": "avg_response_words", "value": str(data["speech_patterns"]["avg_response_words"]), "confidence": "high", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "communication", "key": "dash_rate", "value": str(data["speech_patterns"]["style_markers"]["dash_rate"]), "confidence": "high", "scope": "user", "tier": "hot"},
    {"user_id": USER_ID, "category": "communication", "key": "exclamation_rate", "value": str(data["speech_patterns"]["style_markers"]["exclamation_rate"]), "confidence": "high", "scope": "user", "tier": "hot"},
]

for p in profiles:
    client.table("mem_profile").insert(p).execute()
print(f"Seeded {len(profiles)} profile entries")

# 2. SEED MEM_OPERATOR — Champ's speech patterns (openers)
openers = data["speech_patterns"]["top_openers"][:15]
opener_count = 0
for phrase, count in openers:
    if "{" in phrase or "```" in phrase or "[" in phrase:
        continue
    client.table("mem_operator").insert({
        "operator_name": "champ",
        "memory_type": "pattern",
        "title": f"Opener: {phrase[:50]}",
        "content": phrase,
        "confidence": min(count / 50.0, 1.0),
        "source": "chatgpt_export",
        "tier": "hot",
        "times_seen": count,
    }).execute()
    opener_count += 1
print(f"Seeded {opener_count} opener patterns")

# 3. SEED MEM_OPERATOR — top phrases
phrases = data["speech_patterns"]["top_phrases"][:20]
phrase_count = 0
for phrase, count in phrases:
    if "{" in phrase or "```" in phrase or "|" in phrase or "---" in phrase:
        continue
    client.table("mem_operator").insert({
        "operator_name": "champ",
        "memory_type": "pattern",
        "title": f"Phrase: {phrase[:50]}",
        "content": phrase,
        "confidence": min(count / 1000.0, 1.0),
        "source": "chatgpt_export",
        "tier": "hot",
        "times_seen": count,
    }).execute()
    phrase_count += 1
print(f"Seeded {phrase_count} phrase patterns")

# 4. SEED MEM_LESSONS — signature exchanges
for i, ex in enumerate(data["signature_exchanges"][:15]):
    user_text = ex["user"][:200].replace("'", "")
    champ_text = ex["champ"][:300].replace("'", "")
    client.table("mem_lessons").insert({
        "user_id": USER_ID,
        "operator_name": "champ",
        "lesson": f"Exchange from: {ex['conversation']}\nUSER: {user_text}\nCHAMP: {champ_text}",
        "tags": ["conversation", "signature_exchange"],
        "status": "standard",
        "times_seen": 1,
        "tier": "hot",
    }).execute()
print(f"Seeded 15 signature exchange lessons")

# 5. SEED MEM_ENTITIES — key entities
entities = [
    {"entity_type": "person", "name": "Anthony", "description": "Founder of Abundant Creators, builder, creative partner", "operator_name": "champ"},
    {"entity_type": "company", "name": "Abundant Creators", "description": "Online school for entrepreneurs and creatives", "operator_name": "champ"},
    {"entity_type": "company", "name": "Skipper Financial", "description": "Credit repair business with AI-powered client journeys", "operator_name": "champ"},
    {"entity_type": "project", "name": "Cocreatiq OS", "description": "Voice-based AI operating system for operators", "operator_name": "champ"},
    {"entity_type": "project", "name": "CHAMP", "description": "Personal AI creative partner — first operator on the OS", "operator_name": "champ"},
    {"entity_type": "operator", "name": "Genesis", "description": "AI credit guide for Skipper — sales and onboarding", "operator_name": "champ"},
    {"entity_type": "operator", "name": "Billy", "description": "Billing agent for Line Skippers", "operator_name": "champ"},
    {"entity_type": "operator", "name": "Sadie", "description": "Executive assistant operator", "operator_name": "champ"},
    {"entity_type": "tool", "name": "LiveKit", "description": "WebRTC transport layer for voice agents", "operator_name": "champ"},
    {"entity_type": "tool", "name": "Supabase", "description": "Database backbone — sessions, memory, transcripts", "operator_name": "champ"},
    {"entity_type": "tool", "name": "Claude Code", "description": "Primary build partner — CC", "operator_name": "champ"},
    {"entity_type": "concept", "name": "Dr. Frankenstein", "description": "Build philosophy — stitch from proven parts, never start from scratch", "operator_name": "champ"},
    {"entity_type": "concept", "name": "ISF", "description": "Issues and Solutions Formula — first-principles debugging skill", "operator_name": "champ"},
    {"entity_type": "concept", "name": "AST", "description": "Agentic Solution Thinking — master methodology, Create + Fix modes", "operator_name": "champ"},
]

for e in entities:
    client.table("mem_entities").insert(e).execute()
print(f"Seeded {len(entities)} entities")

# 6. SEED MEM_DAILY_LOGS — deepest sessions
for session in data["key_conversations"]["deepest_sessions"][:10]:
    first_msg = session["first_user_msg"][:200].replace("'", "")
    client.table("mem_daily_logs").insert({
        "operator_name": "champ",
        "user_id": USER_ID,
        "log_date": session["date"],
        "content": f"{session['title']} — {session['message_count']} messages. First: {first_msg}",
        "log_type": "note",
        "distilled": False,
    }).execute()
print(f"Seeded 10 deepest session logs")

print("\nDONE — All memory tables seeded from 628 conversations")