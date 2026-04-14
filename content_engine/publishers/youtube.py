"""
YouTube Publisher — Upload and publish videos via YouTube Data API v3.

Pattern harvested from Postiz youtube.provider.ts:
  - google-api-python-client for upload (same as our analytics adapter)
  - Resumable upload via MediaFileUpload
  - Metadata: title, description, tags, privacy, thumbnail
  - Shorts vs long-form: same API, YouTube auto-detects from dimensions/duration
  - Thumbnail uploaded separately after video

Required env vars:
  YOUTUBE_CLIENT_ID       — OAuth client ID
  YOUTUBE_CLIENT_SECRET   — OAuth client secret
  YOUTUBE_REFRESH_TOKEN   — Refresh token (per channel, via Nango or manual)

Rate limits (from 0033):
  - 2 uploads/day (our limit — YouTube rewards quality over volume)
  - 1 hour minimum interval between uploads
  - Shorts auto-generated from pillar clips (not standalone)

Mirrors: content_engine/analytics/youtube.py (same auth pattern, write instead of read)
"""

import os
import logging
from typing import Optional

from content_engine.publishers.base import (
    BasePublisher, PublishResult, PostPayload,
)

logger = logging.getLogger(__name__)

_youtube_client = None


def _get_authenticated_client():
    """Get authenticated YouTube Data API v3 client for uploads.

    Same auth pattern as analytics/youtube.py but with upload scope.
    """
    global _youtube_client
    if _youtube_client:
        return _youtube_client

    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            logger.warning("YouTube OAuth credentials not set — publisher unavailable")
            return None

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/youtube.force-ssl",
            ],
        )
        _youtube_client = build("youtube", "v3", credentials=creds)
        return _youtube_client

    except ImportError:
        logger.warning(
            "google-api-python-client / google-auth not installed — "
            "run: pip install google-api-python-client google-auth"
        )
        return None


class YouTubePublisher(BasePublisher):
    """Publish videos to YouTube via Data API v3."""

    @property
    def platform(self) -> str:
        return "youtube"

    async def _authenticate(self) -> bool:
        return _get_authenticated_client() is not None

    async def _post_text(self, payload: PostPayload) -> PublishResult:
        """YouTube doesn't support text-only posts."""
        return PublishResult(
            success=False,
            error="YouTube requires video — text-only posts not supported. Use community posts for text.",
        )

    async def _post_media(self, payload: PostPayload) -> PublishResult:
        """Upload and publish a video to YouTube.

        Flow (from Postiz):
          1. Build metadata (title, description, tags, privacy)
          2. Upload video via resumable upload
          3. Optionally upload custom thumbnail
          4. Return video ID + URL
        """
        client = _get_authenticated_client()
        if not client:
            return PublishResult(success=False, error="YouTube client not configured")

        video_media = next((m for m in payload.media if m.media_type == "video"), None)
        if not video_media:
            return PublishResult(success=False, error="No video file provided")

        if not video_media.file_path:
            return PublishResult(
                success=False,
                error="YouTube requires local file upload — URL-based not supported. "
                      "Download the video first.",
            )

        try:
            return await self._upload_video(client, payload, video_media)
        except Exception as e:
            return PublishResult(
                success=False,
                error=_classify_error(str(e)),
            )

    async def _upload_video(self, client, payload: PostPayload, video_media) -> PublishResult:
        """Execute the YouTube video upload."""
        from googleapiclient.http import MediaFileUpload

        # Build metadata
        title = payload.title or payload.text[:100]
        description = payload.text
        if payload.hashtags:
            tag_str = " ".join(f"#{t}" for t in payload.hashtags)
            description = f"{description}\n\n{tag_str}"

        tags = payload.hashtags[:500] if payload.hashtags else []

        # Determine privacy — default to unlisted for safety, switch to public when ready
        privacy = "unlisted"  # Safe default. Change to "public" in production.

        body = {
            "snippet": {
                "title": title[:100],         # YouTube max: 100 chars
                "description": description[:5000],  # YouTube max: 5000 chars
                "tags": tags,
                "categoryId": "28",           # Science & Technology (default for our niche)
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                # YouTube 2026 synthetic content disclosure — required for AI-generated realistic video
                "containsSyntheticMedia": payload.is_ai_generated,
            },
        }

        # Upload video (resumable)
        media = MediaFileUpload(
            video_media.file_path,
            mimetype=video_media.mime_type or "video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = client.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=True,
        )

        # Execute resumable upload
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"[YOUTUBE] Upload progress: {progress}%")

        video_id = response.get("id")
        if not video_id:
            return PublishResult(success=False, error="Upload succeeded but no video ID returned")

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"[YOUTUBE] Uploaded: {video_url} — '{title}'")

        # Upload thumbnail if we have an image in the media list
        thumbnail = next(
            (m for m in payload.media if m.media_type == "image" and m.file_path),
            None,
        )
        if thumbnail:
            try:
                thumb_media = MediaFileUpload(
                    thumbnail.file_path,
                    mimetype=thumbnail.mime_type or "image/jpeg",
                )
                client.thumbnails().set(
                    videoId=video_id,
                    media_body=thumb_media,
                ).execute()
                logger.info(f"[YOUTUBE] Custom thumbnail set for {video_id}")
            except Exception as e:
                # Thumbnail failure is non-fatal — video is still published
                logger.warning(f"[YOUTUBE] Thumbnail upload failed (non-fatal): {e}")

        return PublishResult(
            success=True,
            post_id=video_id,
            post_url=video_url,
        )


def _classify_error(error: str) -> str:
    """Classify YouTube API errors. Harvested from Postiz error handler."""
    error_lower = error.lower()
    if "uploadlimitexceeded" in error_lower:
        return "Daily upload limit reached — try again tomorrow"
    if "invalidtitle" in error_lower or "title" in error_lower and "long" in error_lower:
        return "Title too long — max 100 characters"
    if "unauthorized" in error_lower or "unauthenticated" in error_lower:
        return "Auth failed — refresh YouTube OAuth token"
    if "invalid_grant" in error_lower:
        return "Token expired — re-authenticate via Nango"
    if "failedprecondition" in error_lower and "thumbnail" in error_lower:
        return "Thumbnail too large — max 2MB"
    if "youtubesignuprequired" in error_lower:
        return "YouTube account not linked to Google account"
    if "quota" in error_lower:
        return "API quota exceeded — wait or request higher quota"
    if "forbidden" in error_lower:
        return "Forbidden — channel may lack upload permission"
    return f"YouTube API error: {error}"
