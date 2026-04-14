"""
Facebook Publisher — Post content via Facebook Graph API v20.0.

Pattern harvested from Postiz facebook.provider.ts:
  - Graph API v20.0 endpoints
  - Videos: POST /{pageId}/videos with file_url (creates reel)
  - Photos: POST /{pageId}/photos (unpublished) → POST /{pageId}/feed with attached_media
  - Text: POST /{pageId}/feed with message only
  - All media is URL-based (no binary upload)
  - Auth: Page access token (not user token)

Required env vars:
  FACEBOOK_PAGE_ACCESS_TOKEN  — Long-lived page token (via Nango or manual)
  FACEBOOK_PAGE_ID            — Facebook Page ID

Rate limits (from 0033):
  - 3 posts/day per face (our limit)
  - Platform max: ~25/day before throttling
  - 10 min minimum interval between posts
"""

import os
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PostPayload,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


def _get_credentials() -> tuple[Optional[str], Optional[str]]:
    """Get Facebook Page credentials from env."""
    return (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN"),
        os.getenv("FACEBOOK_PAGE_ID"),
    )


async def _graph_post(endpoint: str, token: str, params: dict) -> dict:
    """POST to Facebook Graph API."""
    import httpx

    url = f"{GRAPH_API_BASE}/{endpoint}"
    params["access_token"] = token

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, data=params)
        data = resp.json()

        if "error" in data:
            error = data["error"]
            raise Exception(
                f"FB error {error.get('code', '?')}: {error.get('message', str(error))}"
            )

        return data


class FacebookPublisher(BasePublisher):
    """Publish content to Facebook Page via Graph API."""

    @property
    def platform(self) -> str:
        return "facebook"

    async def _authenticate(self) -> bool:
        token, page_id = _get_credentials()
        return token is not None and page_id is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """Post text-only to Facebook Page feed."""
        token, page_id = _get_credentials()
        if not token or not page_id:
            return PublishResult(success=False, error="Facebook credentials not configured")

        try:
            result = await _graph_post(f"{page_id}/feed", token, {
                "message": payload.text,
                "published": "true",
            })

            post_id = result.get("id", "")
            return PublishResult(
                success=True,
                post_id=post_id,
                post_url=f"https://www.facebook.com/{post_id}" if post_id else None,
            )
        except Exception as e:
            return PublishResult(success=False, error=_classify_error(str(e)))

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post media to Facebook Page.

        Flow (from Postiz):
          - Video (mp4): POST /{pageId}/videos → creates reel
          - Photos: Upload each unpublished → POST /{pageId}/feed with attached_media
        """
        token, page_id = _get_credentials()
        if not token or not page_id:
            return PublishResult(success=False, error="Facebook credentials not configured")

        try:
            has_video = any(m.media_type == "video" for m in payload.media)

            if has_video:
                return await self._post_video(token, page_id, payload)
            else:
                return await self._post_photos(token, page_id, payload)

        except Exception as e:
            return PublishResult(success=False, error=_classify_error(str(e)))

    async def _post_video(
        self, token: str, page_id: str, payload: PostPayload
    ) -> PublishResult:
        """Post video as a reel with AI disclosure."""
        video = next((m for m in payload.media if m.media_type == "video"), None)
        if not video or not video.url:
            return PublishResult(success=False, error="No video URL provided for Facebook")

        params = {
            "file_url": video.url,
            "description": payload.text,
            "published": "true",
        }
        if payload.is_ai_generated:
            # Meta "Made with AI" disclosure — required for synthetic video
            params["is_ai_generated"] = "true"
        result = await _graph_post(f"{page_id}/videos", token, params)

        video_id = result.get("id", "")
        return PublishResult(
            success=True,
            post_id=video_id,
            post_url=f"https://www.facebook.com/reel/{video_id}" if video_id else None,
        )

    async def _post_photos(
        self, token: str, page_id: str, payload: PostPayload
    ) -> PublishResult:
        """Post one or more photos to feed.

        Postiz pattern: upload each photo unpublished, then attach all to feed post.
        """
        images = [m for m in payload.media if m.media_type == "image" and m.url]
        if not images:
            # No images with URLs — fall back to text post
            return await self._post_text(payload)

        # Step 1: Upload each photo unpublished (with AI disclosure per Meta 2026 policy)
        photo_ids = []
        photo_params = {"published": "false"}
        if payload.is_ai_generated:
            photo_params["is_ai_generated"] = "true"
        for img in images[:10]:  # FB carousel max ~10
            result = await _graph_post(f"{page_id}/photos", token, {
                "url": img.url,
                **photo_params,
            })
            photo_id = result.get("id")
            if photo_id:
                photo_ids.append(photo_id)

        if not photo_ids:
            return PublishResult(success=False, error="Failed to upload photos to Facebook")

        # Step 2: Create feed post with attached photos
        params = {
            "message": payload.text,
            "published": "true",
        }
        for i, pid in enumerate(photo_ids):
            params[f"attached_media[{i}]"] = f'{{"media_fbid":"{pid}"}}'

        result = await _graph_post(f"{page_id}/feed", token, params)

        post_id = result.get("id", "")
        return PublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.facebook.com/{post_id}" if post_id else None,
        )


def _classify_error(error: str) -> str:
    """Classify Facebook API errors. Harvested from Postiz error handler."""
    if "validating access token" in error or "490" in error:
        return "Auth failed — Facebook page token expired, refresh via Nango"
    if "1390008" in error:
        return "Rate limited — posting too fast, wait before retrying"
    if "1366046" in error:
        return "Photo too large or wrong format — max 4MB, JPG/PNG only"
    if "1346003" in error or "1404102" in error:
        return "Content flagged — violates community standards"
    if "1609008" in error:
        return "Facebook.com links not allowed in posts"
    if "2061006" in error:
        return "Invalid URL format in post"
    if "REVOKED_ACCESS_TOKEN" in error:
        return "Access token revoked — re-authenticate via Nango"
    if "1404078" in error:
        return "Insufficient permissions — check page token scopes"
    return f"Facebook error: {error}"
