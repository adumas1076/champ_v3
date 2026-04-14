"""
LinkedIn Publisher — Post content via LinkedIn REST API.

Pattern harvested from Postiz linkedin.provider.ts:
  - REST API with LinkedIn-Version header
  - 3-step media upload: init → chunked PUT (2MB) → finalize
  - Post types: text, image, video, carousel (multi-image)
  - Auth: OAuth 2.0 with refresh token

Required env vars:
  LINKEDIN_ACCESS_TOKEN   — OAuth bearer token (via Nango or manual)
  LINKEDIN_PERSON_ID      — LinkedIn person URN ID (or org ID)
  LINKEDIN_IS_ORG         — "true" if posting as organization

Rate limits (from 0033):
  - 2 posts/day per face (our limit — LinkedIn is sensitive)
  - 20 min minimum interval between posts
"""

import os
import asyncio
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PostPayload,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.linkedin.com"
API_VERSION = "202601"


def _get_credentials() -> tuple[Optional[str], Optional[str], bool]:
    """Get LinkedIn credentials from env."""
    return (
        os.getenv("LINKEDIN_ACCESS_TOKEN"),
        os.getenv("LINKEDIN_PERSON_ID"),
        os.getenv("LINKEDIN_IS_ORG", "").lower() == "true",
    )


def _get_author_urn(person_id: str, is_org: bool) -> str:
    """Build the author URN string."""
    if is_org:
        return f"urn:li:organization:{person_id}"
    return f"urn:li:person:{person_id}"


def _headers(token: str) -> dict:
    """Standard LinkedIn API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


async def _upload_media(
    token: str, person_id: str, file_path: str, media_type: str = "image"
) -> Optional[str]:
    """Upload media to LinkedIn via 3-step flow.

    1. Initialize upload → get upload URL + media URN
    2. PUT file in 2MB chunks
    3. Finalize (videos only)

    Returns media URN for use in post creation.
    """
    import httpx

    is_video = media_type == "video"
    endpoint = "videos" if is_video else "images"

    # Step 1: Initialize upload
    init_body = {
        "initializeUploadRequest": {
            "owner": _get_author_urn(person_id, False),
        }
    }
    if is_video:
        import os as _os
        file_size = _os.path.getsize(file_path)
        init_body["initializeUploadRequest"]["fileSizeBytes"] = file_size
        init_body["initializeUploadRequest"]["uploadCaptions"] = False
        init_body["initializeUploadRequest"]["uploadThumbnail"] = False

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{API_BASE}/rest/{endpoint}?action=initializeUpload",
            headers=_headers(token),
            json=init_body,
        )
        resp.raise_for_status()
        init_data = resp.json().get("value", {})

        upload_url = init_data.get("uploadUrl")
        media_urn = init_data.get("image") or init_data.get("video")

        if not upload_url:
            # Videos may have uploadInstructions array
            instructions = init_data.get("uploadInstructions", [])
            if instructions:
                upload_url = instructions[0].get("uploadUrl")
                media_urn = init_data.get("video")

        if not upload_url or not media_urn:
            logger.error(f"[LINKEDIN] Upload init failed — no upload URL returned")
            return None

        # Step 2: Upload in 2MB chunks
        chunk_size = 2 * 1024 * 1024  # 2MB
        etags = []

        with open(file_path, "rb") as f:
            chunk_index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                content_type = "application/octet-stream"
                put_resp = await client.put(
                    upload_url if not is_video else init_data.get("uploadInstructions", [{}])[chunk_index].get("uploadUrl", upload_url),
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": content_type,
                    },
                )
                put_resp.raise_for_status()
                etag = put_resp.headers.get("etag")
                if etag:
                    etags.append(etag)
                chunk_index += 1

        # Step 3: Finalize (videos only)
        if is_video and etags:
            finalize_body = {
                "finalizeUploadRequest": {
                    "video": media_urn,
                    "uploadToken": "",
                    "uploadedPartIds": etags,
                }
            }
            fin_resp = await client.post(
                f"{API_BASE}/rest/videos?action=finalizeUpload",
                headers=_headers(token),
                json=finalize_body,
            )
            fin_resp.raise_for_status()

    return media_urn


class LinkedInPublisher(BasePublisher):
    """Publish content to LinkedIn via REST API."""

    @property
    def platform(self) -> str:
        return "linkedin"

    async def _authenticate(self) -> bool:
        token, person_id, _ = _get_credentials()
        return token is not None and person_id is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """Post text-only update to LinkedIn."""
        token, person_id, is_org = _get_credentials()
        if not token or not person_id:
            return PublishResult(success=False, error="LinkedIn credentials not configured")

        try:
            return await self._create_post(token, person_id, is_org, payload.text)
        except Exception as e:
            return PublishResult(success=False, error=f"LinkedIn error: {e}")

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Post with media (image, video, or carousel)."""
        token, person_id, is_org = _get_credentials()
        if not token or not person_id:
            return PublishResult(success=False, error="LinkedIn credentials not configured")

        try:
            media_list = payload.media
            media_urns = []

            for media in media_list:
                if media.file_path:
                    urn = await _upload_media(token, person_id, media.file_path, media.media_type)
                    if urn:
                        media_urns.append(urn)

            if not media_urns:
                # Fall back to text-only if upload failed
                return await self._create_post(token, person_id, is_org, payload.text)

            return await self._create_post(
                token, person_id, is_org, payload.text,
                media_urns=media_urns,
                is_carousel=len(media_urns) > 1,
            )
        except Exception as e:
            return PublishResult(success=False, error=f"LinkedIn error: {e}")

    async def _create_post(
        self,
        token: str,
        person_id: str,
        is_org: bool,
        text: str,
        media_urns: Optional[list[str]] = None,
        is_carousel: bool = False,
    ) -> PublishResult:
        """Create a LinkedIn post."""
        import httpx

        body = {
            "author": _get_author_urn(person_id, is_org),
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        if media_urns:
            if is_carousel:
                body["content"] = {
                    "multiImage": {
                        "images": [{"id": urn} for urn in media_urns]
                    }
                }
            else:
                body["content"] = {
                    "media": {"id": media_urns[0]}
                }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{API_BASE}/rest/posts",
                headers=_headers(token),
                json=body,
            )

            if resp.status_code in (200, 201):
                # LinkedIn returns post URN in x-restli-id header
                post_urn = resp.headers.get("x-restli-id", "")
                post_id = post_urn.split(":")[-1] if post_urn else ""
                return PublishResult(
                    success=True,
                    post_id=post_id,
                    post_url=f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None,
                )
            else:
                return PublishResult(
                    success=False,
                    error=f"LinkedIn API {resp.status_code}: {resp.text[:200]}",
                )
