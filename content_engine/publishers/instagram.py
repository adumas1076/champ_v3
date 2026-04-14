"""
Instagram Publisher — Post content via Instagram Graph API (Meta Business).

Pattern harvested from Postiz instagram.provider.ts:
  - Graph API v20.0 container → poll → publish flow
  - Supports: image, video, reel, carousel, story
  - Requires: Facebook Business account linked to IG Business/Creator account
  - Media via URL (not direct upload) — host on our storage first

Required env vars:
  INSTAGRAM_ACCESS_TOKEN     — Long-lived page access token (via Nango or manual)
  INSTAGRAM_BUSINESS_ID      — IG Business Account ID

Rate limits (from 0033):
  - 3 posts/day per face (our limit)
  - Platform max: 25 posts/day
  - 10 min minimum interval between posts
"""

import os
import asyncio
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PublishError, PostPayload,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


def _get_credentials() -> tuple[Optional[str], Optional[str]]:
    """Get Instagram credentials from env."""
    return (
        os.getenv("INSTAGRAM_ACCESS_TOKEN"),
        os.getenv("INSTAGRAM_BUSINESS_ID"),
    )


async def _graph_request(method: str, endpoint: str, token: str, **kwargs) -> dict:
    """Make a request to the Facebook Graph API."""
    import httpx

    url = f"{GRAPH_API_BASE}/{endpoint}"
    params = kwargs.get("params", {})
    params["access_token"] = token
    data = kwargs.get("data", None)

    async with httpx.AsyncClient(timeout=60) as client:
        if method == "GET":
            resp = await client.get(url, params=params)
        elif method == "POST":
            if data:
                resp = await client.post(url, params=params, json=data)
            else:
                resp = await client.post(url, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")

        resp.raise_for_status()
        return resp.json()


async def _wait_for_media(creation_id: str, token: str, max_wait: int = 300) -> bool:
    """Poll media container until ready for publish.

    Instagram processes media async — we must poll until
    status_code != 'IN_PROGRESS'. Harvested from Postiz.
    """
    elapsed = 0
    interval = 10  # seconds between polls

    while elapsed < max_wait:
        try:
            result = await _graph_request(
                "GET", creation_id, token,
                params={"fields": "status_code"},
            )
            status = result.get("status_code", "")
            if status == "FINISHED":
                return True
            if status == "ERROR":
                logger.error(f"[IG] Media processing failed for {creation_id}")
                return False
            # Still IN_PROGRESS — wait and retry
        except Exception as e:
            logger.warning(f"[IG] Poll error for {creation_id}: {e}")

        await asyncio.sleep(interval)
        elapsed += interval

    logger.error(f"[IG] Media processing timed out for {creation_id} after {max_wait}s")
    return False


class InstagramPublisher(BasePublisher):
    """Publish content to Instagram via Graph API."""

    @property
    def platform(self) -> str:
        return "instagram"

    async def _authenticate(self) -> bool:
        token, ig_id = _get_credentials()
        return token is not None and ig_id is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """Instagram doesn't support text-only posts. Return error."""
        return PublishResult(
            success=False,
            error="Instagram requires media — text-only posts not supported",
        )

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post image, video, reel, or carousel to Instagram.

        Flow (from Postiz):
          1. Create media container with URL
          2. Poll until processing complete
          3. Publish container
          4. Get permalink
        """
        token, ig_id = _get_credentials()
        if not token or not ig_id:
            return PublishResult(success=False, error="Instagram credentials not configured")

        try:
            caption = payload.text
            if payload.hashtags:
                tag_str = " ".join(f"#{t}" for t in payload.hashtags[:30])
                caption = f"{caption}\n\n{tag_str}"

            media_list = payload.media
            is_carousel = len(media_list) > 1 and all(m.media_type == "image" for m in media_list)

            is_ai = payload.is_ai_generated

            if is_carousel:
                return await self._post_carousel(ig_id, token, caption, media_list, is_ai=is_ai)
            else:
                media = media_list[0]
                if media.media_type == "video":
                    return await self._post_video(ig_id, token, caption, media, is_ai=is_ai)
                else:
                    return await self._post_image(ig_id, token, caption, media, is_ai=is_ai)

        except Exception as e:
            return PublishResult(success=False, error=f"Instagram error: {e}")

    async def _post_image(
        self, ig_id: str, token: str, caption: str, media, is_ai: bool = True
    ) -> PublishResult:
        """Post single image. Sets AI disclosure (Made with AI) by default."""
        # Step 1: Create container — with AI disclosure for Meta labeling
        params = {"image_url": media.url, "caption": caption}
        if is_ai:
            # Meta AI disclosure — shows "Made with AI" label on the post
            params["alt_text"] = ""  # placeholder so flag takes effect
            params["is_ai_generated"] = "true"
        result = await _graph_request("POST", f"{ig_id}/media", token, params=params)
        creation_id = result.get("id")
        if not creation_id:
            return PublishResult(success=False, error="Failed to create media container")

        # Step 2: Poll until ready
        if not await _wait_for_media(creation_id, token):
            return PublishResult(success=False, error="Media processing failed or timed out")

        # Step 3: Publish
        pub_result = await _graph_request(
            "POST", f"{ig_id}/media_publish", token,
            params={"creation_id": creation_id},
        )
        media_id = pub_result.get("id")

        # Step 4: Get permalink
        permalink = ""
        try:
            meta = await _graph_request(
                "GET", media_id, token, params={"fields": "permalink"},
            )
            permalink = meta.get("permalink", "")
        except Exception:
            pass

        return PublishResult(success=True, post_id=media_id, post_url=permalink)

    async def _post_video(
        self, ig_id: str, token: str, caption: str, media, is_ai: bool = True
    ) -> PublishResult:
        """Post video or reel with AI disclosure."""
        params = {
            "video_url": media.url,
            "caption": caption,
            "media_type": "REELS",  # Default to reel (better reach)
        }
        if is_ai:
            # Meta "Made with AI" label — required for synthetic media in 2026
            params["is_ai_generated"] = "true"
        result = await _graph_request("POST", f"{ig_id}/media", token, params=params)
        creation_id = result.get("id")
        if not creation_id:
            return PublishResult(success=False, error="Failed to create video container")

        # Videos take longer to process
        if not await _wait_for_media(creation_id, token, max_wait=600):
            return PublishResult(success=False, error="Video processing failed or timed out")

        pub_result = await _graph_request(
            "POST", f"{ig_id}/media_publish", token,
            params={"creation_id": creation_id},
        )
        media_id = pub_result.get("id")

        permalink = ""
        try:
            meta = await _graph_request(
                "GET", media_id, token, params={"fields": "permalink"},
            )
            permalink = meta.get("permalink", "")
        except Exception:
            pass

        return PublishResult(success=True, post_id=media_id, post_url=permalink)

    async def _post_carousel(
        self, ig_id: str, token: str, caption: str, media_list, is_ai: bool = True
    ) -> PublishResult:
        """Post carousel (multiple images) with AI disclosure."""
        child_ids = []

        # Step 1: Create each child container (no caption on children)
        for media in media_list[:10]:  # Instagram max 10 carousel items
            params = {"image_url": media.url, "is_carousel_item": "true"}
            if is_ai:
                params["is_ai_generated"] = "true"
            result = await _graph_request("POST", f"{ig_id}/media", token, params=params)
            child_id = result.get("id")
            if child_id:
                child_ids.append(child_id)

        if not child_ids:
            return PublishResult(success=False, error="No carousel items created")

        # Step 2: Wait for all children to process
        for child_id in child_ids:
            await _wait_for_media(child_id, token)

        # Step 3: Create carousel container
        params = {
            "media_type": "CAROUSEL",
            "caption": caption,
            "children": ",".join(child_ids),
        }
        result = await _graph_request("POST", f"{ig_id}/media", token, params=params)
        container_id = result.get("id")
        if not container_id:
            return PublishResult(success=False, error="Failed to create carousel container")

        await _wait_for_media(container_id, token)

        # Step 4: Publish
        pub_result = await _graph_request(
            "POST", f"{ig_id}/media_publish", token,
            params={"creation_id": container_id},
        )
        media_id = pub_result.get("id")

        permalink = ""
        try:
            meta = await _graph_request(
                "GET", media_id, token, params={"fields": "permalink"},
            )
            permalink = meta.get("permalink", "")
        except Exception:
            pass

        return PublishResult(success=True, post_id=media_id, post_url=permalink)
