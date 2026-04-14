"""
TikTok Publisher — Post content via TikTok Content Posting API.

Pattern harvested from Postiz tiktok.provider.ts:
  - Open API v2 endpoints
  - Two posting methods: DIRECT_POST (public) and MEDIA_UPLOAD (inbox)
  - Media via URL (PULL_FROM_URL) — host on our storage first
  - Async processing — must poll status until PUBLISH_COMPLETE
  - Supports: video (single), photo carousel (multiple images)

Required env vars:
  TIKTOK_ACCESS_TOKEN    — OAuth bearer token (via Nango or manual)
  TIKTOK_OPEN_ID         — User's TikTok open_id

Rate limits (from 0033):
  - 3 posts/day per face (our limit)
  - Platform safe max: 3-5/day
  - 20 min minimum interval between posts
  - Max 5 pending shares at once
"""

import os
import asyncio
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PostPayload,
)

logger = logging.getLogger(__name__)

API_BASE = "https://open.tiktokapis.com/v2"


def _get_credentials() -> tuple[Optional[str], Optional[str]]:
    """Get TikTok credentials from env."""
    return (
        os.getenv("TIKTOK_ACCESS_TOKEN"),
        os.getenv("TIKTOK_OPEN_ID"),
    )


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }


async def _poll_publish_status(
    token: str, publish_id: str, max_wait: int = 300
) -> Optional[dict]:
    """Poll TikTok until video is published or fails.

    Harvested from Postiz: polls every 10s for PUBLISH_COMPLETE.
    """
    import httpx

    elapsed = 0
    interval = 10

    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < max_wait:
            try:
                resp = await client.post(
                    f"{API_BASE}/post/publish/status/fetch/",
                    headers=_headers(token),
                    json={"publish_id": publish_id},
                )
                data = resp.json().get("data", {})
                status = data.get("status", "")

                if status == "PUBLISH_COMPLETE":
                    return data
                elif status == "FAILED":
                    fail_reason = data.get("fail_reason", "unknown")
                    logger.error(f"[TIKTOK] Publish failed: {fail_reason}")
                    return None
                # PROCESSING_UPLOAD, PROCESSING_DOWNLOAD, SEND_TO_USER_INBOX — keep waiting

            except Exception as e:
                logger.warning(f"[TIKTOK] Poll error: {e}")

            await asyncio.sleep(interval)
            elapsed += interval

    logger.error(f"[TIKTOK] Publish timed out after {max_wait}s for {publish_id}")
    return None


class TikTokPublisher(BasePublisher):
    """Publish content to TikTok via Content Posting API."""

    @property
    def platform(self) -> str:
        return "tiktok"

    async def _authenticate(self) -> bool:
        token, open_id = _get_credentials()
        return token is not None and open_id is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """TikTok doesn't support text-only posts."""
        return PublishResult(
            success=False,
            error="TikTok requires media — text-only posts not supported",
        )

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post video or photo carousel to TikTok.

        TikTok flow (from Postiz):
          1. Init publish with media URL
          2. Poll status until PUBLISH_COMPLETE
          3. Get post ID from response
        """
        token, open_id = _get_credentials()
        if not token or not open_id:
            return PublishResult(success=False, error="TikTok credentials not configured")

        try:
            media_list = payload.media
            has_video = any(m.media_type == "video" for m in media_list)

            if has_video:
                return await self._post_video(token, payload)
            else:
                return await self._post_photos(token, payload)

        except Exception as e:
            return PublishResult(success=False, error=f"TikTok error: {e}")

    async def _post_video(self, token: str, payload: PostPayload) -> PublishResult:
        """Post a single video to TikTok."""
        import httpx

        video = next((m for m in payload.media if m.media_type == "video"), None)
        if not video or not video.url:
            return PublishResult(success=False, error="No video URL provided")

        body = {
            "post_info": {
                "title": payload.title or payload.text[:90],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "is_aigc": payload.is_ai_generated,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video.url,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{API_BASE}/post/publish/video/init/",
                headers=_headers(token),
                json=body,
            )

            if resp.status_code != 200:
                error_data = resp.json().get("error", {})
                return PublishResult(
                    success=False,
                    error=_classify_error(error_data),
                )

            data = resp.json().get("data", {})
            publish_id = data.get("publish_id")

            if not publish_id:
                return PublishResult(success=False, error="No publish_id returned")

        # Poll until published
        result = await _poll_publish_status(token, publish_id)
        if not result:
            return PublishResult(success=False, error="Video publish failed or timed out")

        post_id = result.get("publicaly_available_post_id", "")
        return PublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.tiktok.com/@/video/{post_id}" if post_id else None,
        )

    async def _post_photos(self, token: str, payload: PostPayload) -> PublishResult:
        """Post photo carousel to TikTok."""
        import httpx

        photo_urls = [m.url for m in payload.media if m.url and m.media_type == "image"]
        if not photo_urls:
            return PublishResult(success=False, error="No photo URLs provided")

        body = {
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO",
            "post_info": {
                "title": (payload.title or "")[:90],
                "description": payload.text,
                "privacy_level": "PUBLIC_TO_EVERYONE",
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 0,
                "photo_images": photo_urls,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{API_BASE}/post/publish/content/init/",
                headers=_headers(token),
                json=body,
            )

            if resp.status_code != 200:
                error_data = resp.json().get("error", {})
                return PublishResult(
                    success=False,
                    error=_classify_error(error_data),
                )

            data = resp.json().get("data", {})
            publish_id = data.get("publish_id")

            if not publish_id:
                return PublishResult(success=False, error="No publish_id returned")

        result = await _poll_publish_status(token, publish_id)
        if not result:
            return PublishResult(success=False, error="Photo publish failed or timed out")

        post_id = result.get("publicaly_available_post_id", "")
        return PublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.tiktok.com/@/video/{post_id}" if post_id else None,
        )


def _classify_error(error_data: dict) -> str:
    """Classify TikTok API errors. Harvested from Postiz error handler."""
    code = error_data.get("code", "")
    message = error_data.get("message", str(error_data))

    error_map = {
        "access_token_invalid": "Auth failed — refresh TikTok access token",
        "rate_limit_exceeded": "Rate limit hit — wait before posting",
        "spam_risk_too_many_posts": "Daily post limit reached",
        "spam_risk_too_many_pending_share": "Max 5 pending posts — wait for processing",
        "duration_check_failed": "Video duration invalid",
        "picture_size_check_failed": "Photo must be ≤1080p, video must be ≥720p",
        "file_format_check_failed": "Unsupported file format",
        "video_pull_failed": "Cannot fetch video from URL",
        "photo_pull_failed": "Cannot fetch photo from URL",
        "spam_risk_user_banned_from_posting": "Account banned from posting",
    }

    return error_map.get(code, f"TikTok error ({code}): {message}")
