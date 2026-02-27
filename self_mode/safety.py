# ============================================
# CHAMP V3 — Self Mode Safety Rails
# Brick 8: Prevents unauthorized actions during
# autonomous execution. No payments, no emails,
# no deploys without explicit approval.
# ============================================

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Domains allowed for browsing in Self Mode
ALLOWED_DOMAINS = [
    "github.com",
    "stackoverflow.com",
    "docs.python.org",
    "pypi.org",
    "npmjs.com",
    "developer.mozilla.org",
    "open-meteo.com",
    "api.open-meteo.com",
    "httpbin.org",
    "jsonplaceholder.typicode.com",
]

# Commands that are NEVER allowed in Self Mode
BLOCKED_COMMANDS = [
    re.compile(r"\brm\s+(-rf?|--recursive)\s+/", re.IGNORECASE),
    re.compile(r"\bformat\b.*\b[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[sfq]", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r"\bcurl\b.*\b-X\s*(POST|PUT|DELETE)\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+publish\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bgit\s+commit\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+(?:push|rm|stop|kill)\b", re.IGNORECASE),
    re.compile(r"\bsendmail\b|\bmail\s+-s\b", re.IGNORECASE),
    re.compile(r"\bssh\b", re.IGNORECASE),
    re.compile(r"\bscp\b", re.IGNORECASE),
]

PAYMENT_KEYWORDS = [
    "payment", "charge", "invoice", "billing", "stripe",
    "paypal", "credit card", "debit", "purchase",
]

EMAIL_KEYWORDS = [
    "send email", "smtp", "sendgrid", "mailgun",
    "slack message", "discord message",
]

DEPLOY_KEYWORDS = [
    "deploy", "publish", "release", "push to prod",
    "production", "heroku", "vercel", "netlify",
]


class SafetyRails:
    """
    Enforces safety constraints during Self Mode execution.

    Rules:
    - No payments/emails/deploys without explicit approval
    - No destructive commands
    - Browser actions limited to allowed domains
    """

    def check_subtask(self, subtask, goal_card) -> Optional[str]:
        """
        Check a subtask against safety rails.
        Returns violation description or None if safe.
        """
        params = subtask.params
        action = subtask.action
        description = subtask.description.lower()

        # Check for payment actions
        if self._contains_keywords(description, PAYMENT_KEYWORDS):
            if not self._approval_allows(goal_card, "payment"):
                return "Payment action requires explicit approval in Goal Card"

        # Check for email actions
        if self._contains_keywords(description, EMAIL_KEYWORDS):
            if not self._approval_allows(goal_card, "email"):
                return "Email/messaging action requires explicit approval in Goal Card"

        # Check for deploy actions
        if self._contains_keywords(description, DEPLOY_KEYWORDS):
            if not self._approval_allows(goal_card, "deploy"):
                return "Deployment action requires explicit approval in Goal Card"

        # Check commands
        if action == "command_run":
            command = params.get("command", "")
            violation = self.check_command(command)
            if violation:
                return violation

        # Check browser domains
        if action == "browser_action":
            url = params.get("url", "")
            if url and not self._is_allowed_domain(url):
                return f"Domain not in allowlist: {url}"

        return None

    def check_command(self, command: str) -> Optional[str]:
        """Check a command against blocked patterns. Returns violation or None."""
        for pattern in BLOCKED_COMMANDS:
            if pattern.search(command):
                return f"Blocked command pattern: {pattern.pattern}"
        return None

    def _contains_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if text contains any of the keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _approval_allows(self, goal_card, action_type: str) -> bool:
        """Check if the Goal Card's approval field explicitly allows this action type.
        Rejects negated mentions like 'no payment' or 'not email'."""
        approval = goal_card.approval.lower()
        # Must contain the keyword AND not be preceded by a negation
        pattern = rf"(?<!\bno\s)(?<!\bnot\s)(?<!\bwithout\s)\b{re.escape(action_type)}\b"
        return bool(re.search(pattern, approval))

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL hostname exactly matches an allowed domain."""
        from urllib.parse import urlparse
        try:
            hostname = urlparse(url).hostname or ""
        except Exception:
            return False
        hostname = hostname.lower()
        return any(
            hostname == domain or hostname.endswith("." + domain)
            for domain in ALLOWED_DOMAINS
        )
