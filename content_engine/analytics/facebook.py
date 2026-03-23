"""
Facebook Analytics Module
Pulls page/post performance data via Facebook Graph API (Meta Business).
Feeds metrics into the autoresearch loop for content scoring.

Covers: Facebook Pages, Reels, Stories, Videos, Posts.
Uses same Graph API as Instagram but different endpoints.

Required env vars:
  FACEBOOK_ACCESS_TOKEN    — long-lived page access token (Meta Business)
  FACEBOOK_PAGE_ID         — Facebook Page ID
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def _get_token() -> Optional[str]:
    return os.getenv("FACEBOOK_ACCESS_TOKEN")


def _get_page_id() -> Optional[str]:
    return os.getenv("FACEBOOK_PAGE_ID")


async def _graph_get(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make a GET request to Facebook Graph API."""
    token = _get_token()
    if not token:
        logger.warning("FACEBOOK_ACCESS_TOKEN not set — Facebook analytics unavailable")
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
        logger.error(f"Facebook API error: {e}")
        return None


async def get_page_info() -> Optional[dict]:
    """Get Facebook Page info."""
    page_id = _get_page_id()
    if not page_id:
        return None
    return await _graph_get(page_id, {
        "fields": "id,name,about,fan_count,followers_count,category,link,verification_status",
    })


async def get_recent_posts(limit: int = 25) -> list[dict]:
    """Get recent posts from the Facebook Page with engagement metrics."""
    page_id = _get_page_id()
    if not page_id:
        return []
    data = await _graph_get(f"{page_id}/posts", {
        "fields": "id,message,created_time,type,permalink_url,full_picture,shares,likes.summary(true),comments.summary(true),reactions.summary(true)",
        "limit": limit,
    })
    if not data:
        return []
    return data.get("data", [])


async def get_recent_videos(limit: int = 25) -> list[dict]:
    """Get recent videos (including Reels) from the Facebook Page."""
    page_id = _get_page_id()
    if not page_id:
        return []
    data = await _graph_get(f"{page_id}/videos", {
        "fields": "id,title,description,created_time,length,permalink_url,likes.summary(true),comments.summary(true),views",
        "limit": limit,
    })
    if not data:
        return []
    return data.get("data", [])


async def get_post_insights(post_id: str) -> Optional[dict]:
    """Get detailed insights for a single post.

    Metrics: impressions, reach, engagement, clicks,
    negative feedback, video views (if video).
    """
    data = await _graph_get(f"{post_id}/insights", {
        "metric": "post_impressions,post_impressions_unique,post_engaged_users,post_clicks,post_reactions_by_type_total,post_negative_feedback",
    })
    if not data:
        return None

    insights = {}
    for metric in data.get("data", []):
        name = metric.get("name", "")
        values = metric.get("values", [{}])
        insights[name] = values[0].get("value", 0) if values else 0

    insights["post_id"] = post_id
    insights["pulled_at"] = datetime.utcnow().isoformat()
    return insights


async def get_video_insights(video_id: str) -> Optional[dict]:
    """Get detailed insights for a video/reel.

    Metrics: total views, unique views, average watch time,
    view-to-completion rate, engagement.
    """
    data = await _graph_get(f"{video_id}/video_insights", {
        "metric": "total_video_views,total_video_views_unique,total_video_avg_time_watched,total_video_view_total_time,total_video_complete_views,total_video_10s_views",
    })
    if not data:
        return None

    insights = {}
    for metric in data.get("data", []):
        name = metric.get("name", "")
        values = metric.get("values", [{}])
        insights[name] = values[0].get("value", 0) if values else 0

    insights["video_id"] = video_id
    insights["pulled_at"] = datetime.utcnow().isoformat()
    return insights


async def get_page_insights(period: str = "day") -> Optional[dict]:
    """Get page-level insights (reach, impressions, engagement, follower growth).

    Args:
        period: "day" | "week" | "days_28"
    """
    page_id = _get_page_id()
    if not page_id:
        return None
    data = await _graph_get(f"{page_id}/insights", {
        "metric": "page_impressions,page_impressions_unique,page_engaged_users,page_post_engagements,page_fans,page_fan_adds,page_fan_removes,page_views_total",
        "period": period,
    })
    if not data:
        return None

    insights = {}
    for metric in data.get("data", []):
        name = metric.get("name", "")
        values = metric.get("values", [])
        insights[name] = values

    insights["pulled_at"] = datetime.utcnow().isoformat()
    return insights


async def get_reels(limit: int = 25) -> list[dict]:
    """Get recent Reels from the Facebook Page."""
    page_id = _get_page_id()
    if not page_id:
        return []
    # Reels are accessed via the video endpoint with a type filter
    data = await _graph_get(f"{page_id}/video_reels", {
        "fields": "id,description,created_time,length,permalink_url,likes.summary(true),comments.summary(true),views",
        "limit": limit,
    })
    if not data:
        # Fallback: try regular videos endpoint
        return await get_recent_videos(limit=limit)
    return data.get("data", [])


async def pull_content_performance(max_posts: int = 25) -> dict:
    """Pull comprehensive performance data for recent Facebook content.

    Main entry point for the autoresearch loop.
    Pulls both regular posts AND videos/reels, deduplicates, and returns
    unified performance data.
    """
    # Pull posts and videos separately
    posts = await get_recent_posts(limit=max_posts)
    videos = await get_recent_videos(limit=max_posts)

    # Deduplicate — video posts appear in both endpoints
    seen_ids = set()
    all_items = []
    for item in posts + videos:
        item_id = item.get("id", "")
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            all_items.append(item)

    results = []
    total_impressions = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_views = 0

    for item in all_items[:max_posts]:
        item_id = item.get("id", "")
        item_type = item.get("type", "")

        # Determine if video
        is_video = "length" in item or "views" in item or item_type in ("video", "reel")

        # Extract engagement from summary fields
        likes_data = item.get("likes", {})
        comments_data = item.get("comments", {})
        reactions_data = item.get("reactions", {})
        shares_data = item.get("shares", {})

        likes = likes_data.get("summary", {}).get("total_count", 0) if isinstance(likes_data, dict) else 0
        comments = comments_data.get("summary", {}).get("total_count", 0) if isinstance(comments_data, dict) else 0
        reactions = reactions_data.get("summary", {}).get("total_count", 0) if isinstance(reactions_data, dict) else 0
        shares = shares_data.get("count", 0) if isinstance(shares_data, dict) else 0
        views = item.get("views", 0) or 0

        # Use reactions if higher than likes (reactions include all types)
        likes = max(likes, reactions)

        # Get detailed insights
        impressions = 0
        if is_video:
            video_insights = await get_video_insights(item_id)
            if video_insights:
                views = max(views, video_insights.get("total_video_views", 0))

        post_insights = await get_post_insights(item_id)
        if post_insights:
            impressions = post_insights.get("post_impressions", 0)

        engagement = likes + comments + shares
        engagement_rate = (engagement / max(1, impressions)) * 100 if impressions else 0

        entry = {
            "post_id": item_id,
            "message": (item.get("message") or item.get("title") or item.get("description") or "")[:200],
            "type": "video" if is_video else item_type or "status",
            "created_at": item.get("created_time", ""),
            "permalink": item.get("permalink_url", ""),
            "is_video": is_video,
            "duration_sec": item.get("length", 0),
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "impressions": impressions,
            "engagement_rate": engagement_rate,
        }
        results.append(entry)
        total_impressions += impressions
        total_likes += likes
        total_comments += comments
        total_shares += shares
        total_views += views

    total_engagement = total_likes + total_comments + total_shares
    engagement_rate = (total_engagement / max(1, total_impressions)) * 100

    return {
        "platform": "facebook",
        "posts_analyzed": len(results),
        "total_impressions": total_impressions,
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "engagement_rate": engagement_rate,
        "posts": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
