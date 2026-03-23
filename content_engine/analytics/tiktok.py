"""
TikTok Analytics Module
Pulls video performance data via TikTok Content Posting API / Research API.
Feeds metrics into the autoresearch loop for content scoring.

Required env vars:
  TIKTOK_ACCESS_TOKEN      — OAuth access token
  TIKTOK_OPEN_ID           — TikTok user open_id
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


def _get_token() -> Optional[str]:
    return os.getenv("TIKTOK_ACCESS_TOKEN")


def _get_open_id() -> Optional[str]:
    return os.getenv("TIKTOK_OPEN_ID")


async def _tiktok_get(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make authenticated GET request to TikTok API."""
    token = _get_token()
    if not token:
        logger.warning("TIKTOK_ACCESS_TOKEN not set — TikTok analytics unavailable")
        return None
    try:
        import httpx
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{TIKTOK_API_BASE}/{endpoint}", params=params or {}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.error(f"TikTok API error: {e}")
        return None


async def _tiktok_post(endpoint: str, body: Optional[dict] = None) -> Optional[dict]:
    """Make authenticated POST request to TikTok API."""
    token = _get_token()
    if not token:
        logger.warning("TIKTOK_ACCESS_TOKEN not set — TikTok analytics unavailable")
        return None
    try:
        import httpx
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{TIKTOK_API_BASE}/{endpoint}", json=body or {}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.error(f"TikTok API error: {e}")
        return None


async def get_user_info() -> Optional[dict]:
    """Get TikTok user profile info."""
    data = await _tiktok_get("user/info/", {
        "fields": "open_id,union_id,avatar_url,display_name,bio_description,profile_deep_link,is_verified,follower_count,following_count,likes_count,video_count",
    })
    if not data:
        return None
    return data.get("data", {}).get("user", {})


async def get_recent_videos(max_count: int = 20) -> list[dict]:
    """Get list of recent videos with basic info."""
    body = {
        "max_count": min(max_count, 20),  # TikTok API max per request
    }
    data = await _tiktok_post("video/list/", body)
    if not data:
        return []
    videos = data.get("data", {}).get("videos", [])
    return videos


async def get_video_insights(video_ids: list[str]) -> list[dict]:
    """Get detailed metrics for specific videos.

    Returns: views, likes, comments, shares, play count,
    average watch time, full video watched rate.
    """
    if not video_ids:
        return []
    body = {
        "filters": {
            "video_ids": video_ids[:20],  # Max 20 per request
        },
        "fields": "id,title,create_time,cover_image_url,share_url,video_description,duration,like_count,comment_count,share_count,view_count",
    }
    data = await _tiktok_post("video/query/", body)
    if not data:
        return []
    return data.get("data", {}).get("videos", [])


async def pull_content_performance(max_videos: int = 20) -> dict:
    """Pull comprehensive performance data for recent TikTok content.

    Main entry point for the autoresearch loop.
    Returns performance data for each video plus aggregate stats.
    """
    videos = await get_recent_videos(max_count=max_videos)
    if not videos:
        # Fallback: try query endpoint
        return {
            "platform": "tiktok",
            "posts_analyzed": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "avg_views_per_video": 0,
            "engagement_rate": 0,
            "posts": [],
            "pulled_at": datetime.utcnow().isoformat(),
        }

    results = []
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0

    for video in videos:
        views = video.get("view_count", 0) or video.get("play_count", 0) or 0
        likes = video.get("like_count", 0) or 0
        comments = video.get("comment_count", 0) or 0
        shares = video.get("share_count", 0) or 0

        entry = {
            "video_id": video.get("id", ""),
            "title": video.get("title", "") or video.get("video_description", ""),
            "duration_sec": video.get("duration", 0),
            "create_time": video.get("create_time", ""),
            "share_url": video.get("share_url", ""),
            "cover_image": video.get("cover_image_url", ""),
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "engagement_rate": ((likes + comments + shares) / max(1, views)) * 100 if views else 0,
        }
        results.append(entry)
        total_views += views
        total_likes += likes
        total_comments += comments
        total_shares += shares

    total_engagement = total_likes + total_comments + total_shares
    avg_views = total_views / max(1, len(results))
    engagement_rate = (total_engagement / max(1, total_views)) * 100

    return {
        "platform": "tiktok",
        "posts_analyzed": len(results),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "avg_views_per_video": avg_views,
        "engagement_rate": engagement_rate,
        "posts": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
