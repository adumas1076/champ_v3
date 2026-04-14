"""
Base Publisher — Abstract interface for all platform publishers.

Every publisher inherits BasePublisher and implements platform-specific logic.
Provides: retry with exponential backoff, compliance integration, error handling.

Pattern matches our analytics adapters (content_engine/analytics/*.py):
  - Lazy-loaded clients
  - Env-based credentials
  - Async methods
  - Graceful error handling with logging

Posting patterns harvested from Postiz (reference/postiz/):
  - Twitter: SDK-based, media upload via buffer
  - Instagram: Graph API container → poll → publish
  - LinkedIn: REST init upload → chunked PUT → create post
  - TikTok: Open API init → poll status

Spec: 0034_click_to_client_technical_wiring.md — Component 1
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass
class PublishResult:
    """Result of publishing a post to a platform."""
    success: bool
    platform: str = ""
    post_id: Optional[str] = None       # Platform's post ID
    post_url: Optional[str] = None      # Live URL on platform
    error: Optional[str] = None
    retry_count: int = 0
    published_at: Optional[str] = None

    def __post_init__(self):
        if self.success and not self.published_at:
            self.published_at = datetime.utcnow().isoformat()


@dataclass
class PublishError(Exception):
    """Structured publishing error."""
    platform: str
    error_type: str       # "auth" | "rate_limit" | "media" | "validation" | "server" | "unknown"
    message: str
    retryable: bool = True
    raw_error: Optional[str] = None


@dataclass
class MediaFile:
    """Media to upload with a post."""
    file_path: Optional[str] = None     # Local file path
    url: Optional[str] = None           # Remote URL (for platforms that accept URLs)
    mime_type: Optional[str] = None     # image/jpeg, video/mp4, etc.
    media_type: str = "image"           # "image" | "video" | "carousel"


@dataclass
class PostPayload:
    """Platform-agnostic post payload. Publishers adapt this to their API."""
    text: str
    media: list[MediaFile] = field(default_factory=list)
    # Metadata
    influencer_id: str = ""
    content_id: str = ""
    funnel_stage: str = "tof"
    content_type: str = "micro"
    # Platform-specific overrides
    title: Optional[str] = None         # YouTube, TikTok
    hashtags: list[str] = field(default_factory=list)
    reply_to: Optional[str] = None      # For threads/replies
    # Scheduling
    scheduled_at: Optional[str] = None
    # Flags
    is_ai_generated: bool = True        # For platform disclosure
    is_thread: bool = False


# ============================================
# Base Publisher
# ============================================

class BasePublisher(ABC):
    """Abstract base class for all platform publishers.

    Subclasses implement:
      - platform (property)
      - _authenticate()
      - _post_text()
      - _post_media()
      - _upload_media()

    Base class provides:
      - Retry with exponential backoff (3 attempts)
      - Error classification
      - Logging
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2  # seconds: 2, 4, 8

    @property
    @abstractmethod
    def platform(self) -> str:
        """Platform identifier: 'twitter', 'instagram', etc."""
        ...

    @abstractmethod
    async def _authenticate(self) -> bool:
        """Authenticate with the platform. Return True if successful."""
        ...

    @abstractmethod
    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """Post text-only content. Platform-specific implementation."""
        ...

    @abstractmethod
    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post content with media (image/video). Platform-specific implementation."""
        ...

    async def post(self, payload: PostPayload) -> PublishResult:
        """Post content with retry logic. Main entry point.

        Determines post type (text vs media) and delegates to
        platform-specific implementation with exponential backoff retry.

        Platform-specific AI disclosure (2026 requirement):
          - Instagram/Facebook: is_ai_generated flag in API call (wired in publisher)
          - TikTok: is_aigc in post_info (wired in publisher)
          - YouTube: containsSyntheticMedia in status (wired in publisher)
          - X/Twitter + LinkedIn: no API field — use profile bio + post text
            disclosure (e.g., "🤖 AI-generated content | Cocreatiq operator")
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                if payload.media:
                    result = await self._post_media(payload)
                else:
                    result = await self._post_text(payload)

                result.platform = self.platform
                result.retry_count = attempt - 1

                if result.success:
                    logger.info(
                        f"[PUBLISHER:{self.platform.upper()}] Posted {payload.content_id} "
                        f"→ {result.post_url or result.post_id} "
                        f"(attempt {attempt})"
                    )
                    return result

                # Non-retryable failure
                if result.error and not self._is_retryable(result.error):
                    logger.error(
                        f"[PUBLISHER:{self.platform.upper()}] Non-retryable error: {result.error}"
                    )
                    return result

            except PublishError as e:
                if not e.retryable or attempt == self.MAX_RETRIES:
                    logger.error(
                        f"[PUBLISHER:{self.platform.upper()}] Failed after {attempt} attempts: {e.message}"
                    )
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error=e.message,
                        retry_count=attempt,
                    )
            except Exception as e:
                if attempt == self.MAX_RETRIES:
                    logger.error(
                        f"[PUBLISHER:{self.platform.upper()}] Unexpected error after {attempt} attempts: {e}"
                    )
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error=str(e),
                        retry_count=attempt,
                    )

            # Exponential backoff before retry
            backoff = self.RETRY_BACKOFF_BASE ** attempt
            logger.info(
                f"[PUBLISHER:{self.platform.upper()}] Retry {attempt}/{self.MAX_RETRIES} "
                f"in {backoff}s..."
            )
            await asyncio.sleep(backoff)

        return PublishResult(
            success=False,
            platform=self.platform,
            error="Max retries exceeded",
            retry_count=self.MAX_RETRIES,
        )

    async def post_reply(self, payload: PostPayload, parent_post_id: str) -> PublishResult:
        """Post a reply/comment to an existing post (for threads).

        Default implementation sets reply_to and calls post().
        Override in platform-specific publishers if needed.
        """
        payload.reply_to = parent_post_id
        return await self.post(payload)

    def _is_retryable(self, error: str) -> bool:
        """Determine if an error is retryable.

        Non-retryable: auth failures, validation errors, ban/spam detection
        Retryable: rate limits, server errors, timeouts
        """
        non_retryable_keywords = [
            "unauthorized", "forbidden", "invalid token",
            "spam", "banned", "duplicate",
            "caption too long", "media too large",
            "unsupported format",
        ]
        error_lower = error.lower()
        return not any(kw in error_lower for kw in non_retryable_keywords)
