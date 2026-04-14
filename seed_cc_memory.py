"""Seed memory tables from Claude Code session memories (52 files)"""

import os
import re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
client = create_client(url, key)

MEMORY_DIR = "C:/Users/libby/.claude/projects/c--Users-libby-OneDrive-Desktop-tool-shed-CHAMP/memory"
USER_ID = "00000000-0000-0000-0000-000000000001"

count = 0
skipped = 0

for filename in os.listdir(MEMORY_DIR):
    if not filename.endswith(".md") or filename == "MEMORY.md":
        continue

    filepath = os.path.join(MEMORY_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse frontmatter
    name = filename.replace(".md", "")
    mem_type = "project"
    description = ""

    # Extract frontmatter fields
    fm_match = re.search(r"---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        name_match = re.search(r"name:\s*(.+)", fm)
        desc_match = re.search(r"description:\s*(.+)", fm)
        type_match = re.search(r"type:\s*(.+)", fm)
        if name_match:
            name = name_match.group(1).strip()
        if desc_match:
            description = desc_match.group(1).strip()
        if type_match:
            mem_type = type_match.group(1).strip()

    # Remove frontmatter from content
    body = re.sub(r"---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL).strip()
    if not body:
        skipped += 1
        continue

    # Map type to table
    if mem_type in ("feedback",):
        # Feedback goes to mem_lessons
        client.table("mem_lessons").insert({
            "user_id": USER_ID,
            "operator_name": "champ",
            "lesson": f"{name}: {description}\n\n{body[:500]}",
            "tags": ["cc_session", mem_type],
            "status": "standard",
            "times_seen": 1,
            "tier": "hot",
        }).execute()
    elif mem_type in ("reference",):
        # References go to mem_operator
        client.table("mem_operator").insert({
            "operator_name": "champ",
            "memory_type": "context",
            "title": name,
            "content": f"{description}\n\n{body[:500]}",
            "confidence": 0.9,
            "source": "cc_session",
            "tier": "warm",
            "times_seen": 1,
        }).execute()
    elif mem_type in ("user",):
        # User info goes to mem_profile
        client.table("mem_profile").insert({
            "user_id": USER_ID,
            "category": "general",
            "key": name[:50],
            "value": f"{description}\n\n{body[:300]}",
            "confidence": "high",
            "scope": "user",
            "tier": "hot",
        }).execute()
    else:
        # Project/other goes to mem_operator as context
        client.table("mem_operator").insert({
            "operator_name": "champ",
            "memory_type": "context",
            "title": name,
            "content": f"{description}\n\n{body[:500]}",
            "confidence": 0.8,
            "source": "cc_session",
            "tier": "hot",
            "times_seen": 1,
        }).execute()

    count += 1

print(f"Seeded {count} Claude Code session memories ({skipped} skipped)")
print("DONE")