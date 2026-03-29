"""
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
