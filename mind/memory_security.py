# ============================================
# CHAMP V3 — Memory Security Layer
# Harvested from: Hermes Agent (NousResearch)
#
# Two protections:
#   1. Atomic File Writes — temp file + os.replace()
#      prevents race conditions and partial writes
#      when multiple operators write concurrently
#
#   2. Threat Scanning — regex patterns detect
#      prompt injection, credential exfiltration,
#      and other attacks in memory content
#
# Every memory write in the system should go
# through scan_content() before persisting.
# ============================================

import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# ---- Threat Patterns ----
# Harvested from Hermes Agent's memory_tool.py
# Extended with CHAMP-specific patterns

THREAT_PATTERNS = [
    # Prompt injection
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "prompt_injection"),
    (r"you\s+are\s+now\s+a", "prompt_injection"),
    (r"new\s+instructions?\s*:", "prompt_injection"),
    (r"system\s*:\s*you", "prompt_injection"),
    (r"forget\s+(everything|all|previous)", "prompt_injection"),
    (r"disregard\s+(all|previous|prior)", "prompt_injection"),

    # Credential exfiltration
    (r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD)", "exfiltration"),
    (r"wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD)", "exfiltration"),
    (r"fetch\s*\([^\)]*\$\{?\w*(KEY|TOKEN|SECRET)", "exfiltration"),
    (r"(OPENAI|ANTHROPIC|SUPABASE|LIVEKIT)_(API_)?KEY\s*=", "credential_leak"),

    # SSH/system backdoors
    (r"authorized_keys", "backdoor"),
    (r"\.ssh/", "backdoor"),
    (r"chmod\s+[0-7]*7[0-7]*", "backdoor"),
    (r"crontab\s+-[er]", "backdoor"),
    (r"/etc/(passwd|shadow|sudoers)", "system_access"),

    # Data exfiltration
    (r"base64\s+(encode|decode|--decode|-d)", "data_exfil"),
    (r"nc\s+-[a-z]*l", "data_exfil"),  # netcat listener
    (r"ngrok\s+http", "data_exfil"),

    # Operator manipulation
    (r"change\s+your\s+(persona|personality|identity)", "operator_manipulation"),
    (r"pretend\s+to\s+be\s+a\s+different", "operator_manipulation"),
    (r"override\s+(safety|rules|boundaries)", "operator_manipulation"),
]

# Compile patterns once
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), threat_type)
    for pattern, threat_type in THREAT_PATTERNS
]


def scan_content(content: str) -> list[dict]:
    """
    Scan content for potential threats before storing in memory.

    Returns list of detected threats:
    [{"pattern": "...", "threat_type": "...", "match": "..."}]

    Empty list = safe to store.
    """
    if not content:
        return []

    threats = []
    for compiled, threat_type in _COMPILED_PATTERNS:
        match = compiled.search(content)
        if match:
            threats.append({
                "pattern": compiled.pattern,
                "threat_type": threat_type,
                "match": match.group(0)[:100],
            })

    if threats:
        logger.warning(
            f"[SECURITY] {len(threats)} threat(s) detected in content: "
            f"{[t['threat_type'] for t in threats]}"
        )

    return threats


def is_safe(content: str) -> bool:
    """Quick check — returns True if content passes threat scan."""
    return len(scan_content(content)) == 0


def sanitize(content: str) -> str:
    """
    Remove detected threat patterns from content.
    Use when you want to store a cleaned version rather than reject entirely.
    """
    sanitized = content
    for compiled, threat_type in _COMPILED_PATTERNS:
        sanitized = compiled.sub(f"[REDACTED:{threat_type}]", sanitized)
    return sanitized


# ---- Atomic File Writes ----

def atomic_write(filepath: str, content: str) -> bool:
    """
    Write content to a file atomically using temp file + os.replace().

    This prevents:
    - Partial writes (crash mid-write → corrupted file)
    - Race conditions (two operators writing same file)
    - Empty file windows (file exists but is truncated)

    Pattern from Hermes: write to temp → atomic rename.
    """
    try:
        directory = os.path.dirname(filepath)
        os.makedirs(directory, exist_ok=True)

        # Write to temp file in same directory (same filesystem = atomic rename)
        fd, tmp_path = tempfile.mkstemp(
            dir=directory,
            suffix=".tmp",
            prefix=".champ_",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force to disk

            # Atomic rename — this is the critical moment
            os.replace(tmp_path, filepath)

            logger.debug(f"[SECURITY] Atomic write: {filepath} ({len(content)} chars)")
            return True

        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    except Exception as e:
        logger.error(f"[SECURITY] Atomic write failed for {filepath}: {e}")
        return False


def atomic_read(filepath: str) -> Optional[str]:
    """
    Read a file safely, handling potential corruption.
    Returns None if file doesn't exist or is corrupted.
    """
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"[SECURITY] Read failed for {filepath}: {e}")
        return None


# ---- Secure Memory Write (combines scan + atomic write) ----

def secure_write(
    filepath: str,
    content: str,
    allow_threats: bool = False,
) -> dict:
    """
    Scan content for threats, then write atomically.

    Returns:
    {
        "success": bool,
        "threats": list[dict],
        "action": "written" | "blocked" | "sanitized" | "error"
    }
    """
    threats = scan_content(content)

    if threats and not allow_threats:
        logger.warning(
            f"[SECURITY] Write blocked for {filepath}: "
            f"{len(threats)} threats detected"
        )
        return {
            "success": False,
            "threats": threats,
            "action": "blocked",
        }

    if threats and allow_threats:
        # Write but log the threats
        content = sanitize(content)
        ok = atomic_write(filepath, content)
        return {
            "success": ok,
            "threats": threats,
            "action": "sanitized" if ok else "error",
        }

    ok = atomic_write(filepath, content)
    return {
        "success": ok,
        "threats": [],
        "action": "written" if ok else "error",
    }
