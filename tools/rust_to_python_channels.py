"""
Rust-to-Python Channel Adapter Converter
=========================================
Dr. Frankenstein tool: reads OpenFang Rust channel adapters,
converts them to Python using Claude API, outputs ready-to-use
Python channel adapters that conform to Cocreatiq's AIOSP Channel spec.

NOT a generic Rust-to-Python converter. Specifically designed for
converting ChannelAdapter trait implementations to Python classes.

Usage:
    python rust_to_python_channels.py --all          # Convert all 47 adapters
    python rust_to_python_channels.py --only telegram discord slack  # Convert specific ones
    python rust_to_python_channels.py --list          # List available adapters

Requires: ANTHROPIC_API_KEY in environment
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Paths
OPENFANG_CHANNELS = Path(__file__).resolve().parent.parent.parent / "reference" / "openfang" / "crates" / "openfang-channels" / "src"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "channels" / "adapters"
TYPES_FILE = OPENFANG_CHANNELS / "types.rs"

# Files to skip (not adapters)
SKIP_FILES = {"lib.rs", "types.rs", "bridge.rs", "router.rs", "formatter.rs"}

# Python base class template that all adapters inherit from
BASE_CLASS_TEMPLATE = '''"""
Cocreatiq OS — Channel Adapter Base Class
==========================================
All channel adapters inherit from this.
Maps to AIOSP Channel primitive (channel.open, channel.send, channel.receive, channel.close).
Auto-generated base from OpenFang types.rs patterns.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Supported channel types."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    DISCORD = "discord"
    SIGNAL = "signal"
    MATRIX = "matrix"
    EMAIL = "email"
    TEAMS = "teams"
    MATTERMOST = "mattermost"
    WEBCHAT = "webchat"
    CLI = "cli"
    MQTT = "mqtt"
    BLUESKY = "bluesky"
    MASTODON = "mastodon"
    REDDIT = "reddit"
    LINKEDIN = "linkedin"
    TWITCH = "twitch"
    IRC = "irc"
    WEBHOOK = "webhook"
    SMS = "sms"
    VOICE = "voice"
    VIDEO = "video"


@dataclass
class ChannelUser:
    """A user on a messaging platform."""
    platform_id: str
    display_name: str
    cocreatiq_user: Optional[str] = None


@dataclass
class ChannelContent:
    """Content received from or sent to a channel."""
    type: str  # "text", "image", "file", "voice", "location", "command"
    body: str  # Text content, URL, or base64 data
    caption: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ChannelMessage:
    """A unified message from any channel. Maps to AIOSP channel.receive."""
    channel: ChannelType
    platform_message_id: str
    sender: ChannelUser
    content: ChannelContent
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_group: bool = False
    thread_id: Optional[str] = None
    target_operator: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ChannelAdapter(ABC):
    """
    Base class for all channel adapters.

    Maps to AIOSP Channel primitive:
        channel.open   → connect()
        channel.send   → send_message()
        channel.receive → receive_messages() (async iterator)
        channel.close  → disconnect()

    Every adapter must implement these 4 methods.
    """

    channel_type: ChannelType

    @abstractmethod
    async def connect(self) -> bool:
        """Initialize connection to the platform. Returns True if successful."""
        ...

    @abstractmethod
    async def send_message(
        self,
        recipient_id: str,
        content: ChannelContent,
        thread_id: Optional[str] = None,
    ) -> bool:
        """Send a message to a recipient. Returns True if successful."""
        ...

    @abstractmethod
    async def receive_messages(self) -> AsyncIterator[ChannelMessage]:
        """Yield incoming messages as they arrive."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection and resources."""
        ...

    async def send_typing_indicator(self, recipient_id: str) -> None:
        """Optional: show typing indicator. Override if platform supports it."""
        pass

    async def send_reaction(self, message_id: str, emoji: str) -> None:
        """Optional: react to a message. Override if platform supports it."""
        pass
'''

# Conversion prompt template
CONVERSION_PROMPT = """You are converting a Rust channel adapter from OpenFang to a Python channel adapter for Cocreatiq OS.

Here is the Rust source code:

```rust
{rust_code}
```

Here is the Python base class that the adapter must inherit from:

```python
{base_class}
```

Convert this Rust adapter to Python following these rules:

1. The class must inherit from `ChannelAdapter`
2. Implement all 4 required methods: `connect()`, `send_message()`, `receive_messages()`, `disconnect()`
3. Use `httpx` for HTTP requests (async)
4. Use `asyncio` for async patterns
5. Keep the same logic and error handling patterns from Rust
6. Use environment variables for tokens/credentials (same var names as Rust)
7. Include docstrings explaining what each method does
8. Add graceful error handling (log errors, don't crash)
9. Keep the allowed_users filtering if present
10. Use Python dataclasses and typing throughout

Return ONLY the Python code. No explanation. No markdown fences. Just the code.
"""


def list_adapters() -> list[str]:
    """List all available Rust adapter files."""
    adapters = []
    for f in sorted(OPENFANG_CHANNELS.glob("*.rs")):
        if f.name not in SKIP_FILES:
            adapters.append(f.stem)
    return adapters


def read_rust_file(name: str) -> str:
    """Read a Rust adapter file."""
    path = OPENFANG_CHANNELS / f"{name}.rs"
    if not path.exists():
        raise FileNotFoundError(f"No adapter found: {path}")
    return path.read_text(encoding="utf-8")


def convert_with_claude(rust_code: str, api_key: str) -> str:
    """Send Rust code to Claude API for conversion to Python."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": CONVERSION_PROMPT.format(
                rust_code=rust_code,
                base_class=BASE_CLASS_TEMPLATE,
            ),
        }],
    )

    return message.content[0].text


def save_adapter(name: str, python_code: str) -> Path:
    """Save converted Python adapter."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.py"
    path.write_text(python_code, encoding="utf-8")
    return path


def save_base_class() -> Path:
    """Save the base class file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "base.py"
    path.write_text(BASE_CLASS_TEMPLATE, encoding="utf-8")

    # Also create __init__.py
    init_path = OUTPUT_DIR / "__init__.py"
    if not init_path.exists():
        init_path.write_text("# Cocreatiq OS — Channel Adapters\n", encoding="utf-8")

    return path


def main():
    parser = argparse.ArgumentParser(description="Convert OpenFang Rust channel adapters to Python")
    parser.add_argument("--all", action="store_true", help="Convert all adapters")
    parser.add_argument("--only", nargs="+", help="Convert specific adapters by name")
    parser.add_argument("--list", action="store_true", help="List available adapters")
    parser.add_argument("--base-only", action="store_true", help="Only generate the base class")
    args = parser.parse_args()

    if args.list:
        adapters = list_adapters()
        print(f"\n{len(adapters)} adapters available:\n")
        for a in adapters:
            print(f"  - {a}")
        return

    # Always save base class first
    base_path = save_base_class()
    logger.info(f"Base class saved: {base_path}")

    if args.base_only:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set. Cannot convert without Claude API.")
        sys.exit(1)

    # Determine which adapters to convert
    if args.all:
        targets = list_adapters()
    elif args.only:
        targets = args.only
    else:
        parser.print_help()
        return

    logger.info(f"Converting {len(targets)} adapters...")

    success = 0
    failed = 0

    for name in targets:
        try:
            logger.info(f"Converting: {name}")
            rust_code = read_rust_file(name)
            python_code = convert_with_claude(rust_code, api_key)
            path = save_adapter(name, python_code)
            logger.info(f"  ✓ Saved: {path}")
            success += 1
        except Exception as e:
            logger.error(f"  ✗ Failed: {name} — {e}")
            failed += 1

    logger.info(f"\nDone: {success} converted, {failed} failed out of {len(targets)} total")


if __name__ == "__main__":
    main()
