"""
Instagram Analytics Module
Pulls post/reel performance data via Instagram Graph API (Meta Business).
Feeds metrics into the autoresearch loop for content scoring.

Required env vars:
  INSTAGRAM_ACCESS_TOKEN   — long-lived user access token (Meta Business)
  INSTAGRAM_BUSINESS_ID    — Instagram Business/Creator account ID
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Base URL for Instagram Graph API
GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def _get_token() -> Optional[str]:
    return os.getenv("INSTAGRAM_ACCESS_TOKEN")


def _get_business_id() -> Optional[str]:
    return os.getenv("INSTAGRAM_BUSINESS_ID")


async def _graph_get(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make a GET request to Instagram Graph API."""
    token = _get_token()
    if not token:
        logger.warning("INSTAGRAM_ACCESS_TOKEN not set — Instagram analytics unavailable")
        return None
    try:
        import httpx
        params = params or {}
        params["access_token"] = token
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GRAPH_API_BASE}/{endpoint}", params=params)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.error(f"Instagram API error: {e}")
        return None


async def get_account_info() -> Optional[dict]:
    """Get Instagram business account info."""
    biz_id = _get_business_id()
    if not biz_id:
        return None
    return await _graph_get(biz_id, {
        "fields": "id,username,name,biography,followers_count,follows_count,media_count",
    })


async def get_recent_media(limit: int = 20) -> list[dict]:
    """Get recent media (posts, reels, carousels) with basic metrics."""
    biz_id = _get_business_id()
    if not biz_id:
        return []
    data = await _graph_get(f"{biz_id}/media", {
        "fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
        "limit": limit,
    })
    if not data:
        return []
    return data.get("data", [])


async def get_media_insights(media_id: str) -> Optional[dict]:
    """Get detailed insights for a single media item.

    Metrics vary by media type:
    - IMAGE/CAROUSEL: impressions, reach, engagement, saved
    - VIDEO/REEL: impressions, reach, engagement, saved, video_views, plays
    """
    # Try reel metrics first, fall back to image metrics
    reel_metrics = "impressions,reach,likes,comments,shares,saved,plays,total_interactions"
    image_metrics = "impressions,reach,likes,comments,saved,total_interactions"

    data = await _graph_get(f"{media_id}/insights", {
        "metric": reel_metrics,
    })
    if not data or "error" in data:
        # Fallback for non-reel content
        data = await _graph_get(f"{media_id}/insights", {
            "metric": image_metrics,
        })
    if not data:
        return None

    # Flatten insights into a simple dict
    insights = {}
    for metric in data.get("data", []):
        name = metric.get("name")
        values = metric.get("values", [{}])
        insights[name] = values[0].get("value", 0) if values else 0

    insights["media_id"] = media_id
    insights["pulled_at"] = datetime.utcnow().isoformat()
    return insights


async def get_account_insights(period: str = "day", days: int = 28) -> Optional[dict]:
    """Get account-level insights (follower growth, reach, impressions).

    Args:
        period: "day" | "week" | "days_28"
        days: number of days to look back
    """
    biz_id = _get_business_id()
    if not biz_id:
        return None
    data = await _graph_get(f"{biz_id}/insights", {
        "metric": "impressions,reach,follower_count,profile_views",
        "period": period,
    })
    if not data:
        return None

    insights = {}
    for metric in data.get("data", []):
        name = metric.get("name")
        values = metric.get("values", [])
        insights[name] = values

    insights["pulled_at"] = datetime.utcnow().isoformat()
    return insights


async def pull_content_performance(limit: int = 20) -> dict:
    """Pull comprehensive performance data for recent content.

    This is the main entry point for the autoresearch loop.
    Returns performance data for each post plus aggregate stats.
    """
    media_items = await get_recent_media(limit=limit)
    results = []
    total_likes = 0
    total_comments = 0
    total_impressions = 0

    for item in media_items:
        insights = await get_media_insights(item["id"])
        entry = {
            "media_id": item["id"],
            "caption": (item.get("caption") or "")[:200],
            "media_type": item.get("media_type"),
            "timestamp": item.get("timestamp"),
            "permalink": item.get("permalink"),
            "likes": item.get("like_count", 0),
            "comments": item.get("comments_count", 0),
            "insights": insights,
        }
        results.append(entry)
        total_likes += entry["likes"]
        total_comments += entry["comments"]
        if insights:
            total_impressions += insights.get("impressions", 0)

    avg_likes = total_likes / max(1, len(results))
    avg_comments = total_comments / max(1, len(results))
    engagement_rate = (total_likes + total_comments) / max(1, total_impressions) * 100 if total_impressions else 0

    return {
        "platform": "instagram",
        "posts_analyzed": len(results),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_impressions": total_impressions,
        "avg_likes_per_post": avg_likes,
        "avg_comments_per_post": avg_comments,
        "engagement_rate": engagement_rate,
        "posts": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
