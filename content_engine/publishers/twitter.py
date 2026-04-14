"""
Twitter/X Publisher — Post content via Twitter API v2.

Pattern harvested from Postiz x.provider.ts:
  - Uses tweepy (Python equivalent of twitter-api-v2 Node SDK)
  - Media upload via chunked upload for videos, simple for images
  - Threads via reply_to tweet ID
  - Token format: OAuth 1.0a user context (consumer + access tokens)

Required env vars:
  X_API_KEY            — Consumer/App API key
  X_API_SECRET         — Consumer/App API secret
  X_ACCESS_TOKEN       — User access token (per influencer, or via Nango)
  X_ACCESS_SECRET      — User access secret

Rate limits (from 0033):
  - 3 posts/day per face (our conservative limit)
  - Platform max: 300 tweets per 3 hours
  - 2 min minimum interval between posts
"""

import os
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PublishError, PostPayload, MediaFile,
)

logger = logging.getLogger(__name__)

_client = None


def _get_client(access_token: Optional[str] = None, access_secret: Optional[str] = None):
    """Get authenticated tweepy Client (lazy-loaded)."""
    global _client
    if _client and not access_token:
        return _client
    try:
        import tweepy

        api_key = os.getenv("X_API_KEY")
        api_secret = os.getenv("X_API_SECRET")
        token = access_token or os.getenv("X_ACCESS_TOKEN")
        secret = access_secret or os.getenv("X_ACCESS_SECRET")

        if not all([api_key, api_secret, token, secret]):
            logger.warning("X/Twitter credentials not set — publisher unavailable")
            return None

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=token,
            access_token_secret=secret,
        )
        if not access_token:
            _client = client
        return client
    except ImportError:
        logger.warning("tweepy not installed — run: pip install tweepy")
        return None


def _get_api_v1(access_token: Optional[str] = None, access_secret: Optional[str] = None):
    """Get tweepy API v1.1 for media uploads (v2 client doesn't handle uploads)."""
    try:
        import tweepy

        api_key = os.getenv("X_API_KEY")
        api_secret = os.getenv("X_API_SECRET")
        token = access_token or os.getenv("X_ACCESS_TOKEN")
        secret = access_secret or os.getenv("X_ACCESS_SECRET")

        auth = tweepy.OAuth1UserHandler(api_key, api_secret, token, secret)
        return tweepy.API(auth)
    except ImportError:
        return None


class TwitterPublisher(BasePublisher):
    """Publish content to Twitter/X via API v2."""

    @property
    def platform(self) -> str:
        return "twitter"

    async def _authenticate(self) -> bool:
        return _get_client() is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """Post a text tweet."""
        client = _get_client()
        if not client:
            return PublishResult(success=False, error="Twitter client not configured")

        try:
            text = payload.text
            if payload.hashtags:
                tag_str = " ".join(f"#{t}" for t in payload.hashtags[:5])
                if len(text) + len(tag_str) + 1 <= 280:
                    text = f"{text}\n{tag_str}"

            kwargs = {"text": text}
            if payload.reply_to:
                kwargs["in_reply_to_tweet_id"] = payload.reply_to

            response = client.create_tweet(**kwargs)
            tweet_id = response.data["id"]

            return PublishResult(
                success=True,
                post_id=str(tweet_id),
                post_url=f"https://x.com/i/status/{tweet_id}",
            )
        except Exception as e:
            error_str = str(e)
            return PublishResult(
                success=False,
                error=_classify_error(error_str),
            )

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post a tweet with media (image or video)."""
        client = _get_client()
        api_v1 = _get_api_v1()
        if not client or not api_v1:
            return PublishResult(success=False, error="Twitter client not configured")

        try:
            media_ids = []
            for media in payload.media[:4]:  # Twitter max: 4 images or 1 video
                if media.file_path:
                    if media.media_type == "video":
                        upload = api_v1.media_upload(
                            media.file_path,
                            media_category="tweet_video",
                        )
                    else:
                        upload = api_v1.media_upload(media.file_path)
                    media_ids.append(str(upload.media_id))

            text = payload.text
            if payload.hashtags:
                tag_str = " ".join(f"#{t}" for t in payload.hashtags[:5])
                if len(text) + len(tag_str) + 1 <= 280:
                    text = f"{text}\n{tag_str}"

            kwargs = {"text": text}
            if media_ids:
                kwargs["media_ids"] = media_ids
            if payload.reply_to:
                kwargs["in_reply_to_tweet_id"] = payload.reply_to

            response = client.create_tweet(**kwargs)
            tweet_id = response.data["id"]

            return PublishResult(
                success=True,
                post_id=str(tweet_id),
                post_url=f"https://x.com/i/status/{tweet_id}",
            )
        except Exception as e:
            return PublishResult(
                success=False,
                error=_classify_error(str(e)),
            )


def _classify_error(error: str) -> str:
    """Classify Twitter API errors into actionable messages."""
    error_lower = error.lower()
    if "unauthorized" in error_lower or "authentication" in error_lower:
        return "Auth failed — check X_ACCESS_TOKEN and X_ACCESS_SECRET"
    if "duplicate" in error_lower:
        return "Duplicate tweet detected — Twitter blocks identical content"
    if "rate limit" in error_lower or "too many" in error_lower:
        return "Rate limit hit — wait before posting again"
    if "forbidden" in error_lower:
        return "Forbidden — account may lack write permissions"
    return f"Twitter API error: {error}"
