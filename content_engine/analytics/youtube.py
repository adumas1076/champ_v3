"""
YouTube Analytics Module
Pulls video performance data via YouTube Data API v3 + YouTube Analytics API.
Feeds metrics into the autoresearch loop for content scoring.

Required env vars:
  YOUTUBE_API_KEY          — for public data (video stats)
  YOUTUBE_CLIENT_ID        — for authenticated data (analytics, channel)
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports — only load google API client when actually used
_youtube_data = None
_youtube_analytics = None


def _get_api_key() -> Optional[str]:
    return os.getenv("YOUTUBE_API_KEY")


def _get_data_client():
    """Get YouTube Data API v3 client (public data — video stats)."""
    global _youtube_data
    if _youtube_data:
        return _youtube_data
    try:
        from googleapiclient.discovery import build
        api_key = _get_api_key()
        if not api_key:
            logger.warning("YOUTUBE_API_KEY not set — YouTube analytics unavailable")
            return None
        _youtube_data = build("youtube", "v3", developerKey=api_key)
        return _youtube_data
    except ImportError:
        logger.warning("google-api-python-client not installed — run: pip install google-api-python-client")
        return None


def _get_analytics_client():
    """Get YouTube Analytics API client (authenticated — channel analytics)."""
    global _youtube_analytics
    if _youtube_analytics:
        return _youtube_analytics
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            logger.warning("YouTube OAuth credentials not set — analytics unavailable")
            return None

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        _youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
        return _youtube_analytics
    except ImportError:
        logger.warning("google-api-python-client / google-auth not installed")
        return None


async def get_video_stats(video_id: str) -> Optional[dict]:
    """Get public stats for a single video (views, likes, comments, duration)."""
    client = _get_data_client()
    if not client:
        return None
    try:
        response = client.videos().list(
            part="statistics,contentDetails,snippet",
            id=video_id,
        ).execute()
        items = response.get("items", [])
        if not items:
            return None
        item = items[0]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        return {
            "video_id": video_id,
            "title": snippet.get("title"),
            "published_at": snippet.get("publishedAt"),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration": item.get("contentDetails", {}).get("duration"),
            "pulled_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get video stats for {video_id}: {e}")
        return None


async def get_channel_videos(channel_id: str, max_results: int = 20) -> list[dict]:
    """Get recent videos from a channel."""
    client = _get_data_client()
    if not client:
        return []
    try:
        response = client.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            maxResults=max_results,
            type="video",
        ).execute()
        videos = []
        for item in response.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
            })
        return videos
    except Exception as e:
        logger.error(f"Failed to get channel videos for {channel_id}: {e}")
        return []


async def get_video_analytics(
    video_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[dict]:
    """Get detailed analytics for a video (requires OAuth).

    Returns: watch time, avg view duration, avg percentage viewed,
    retention data, traffic sources, demographics.
    """
    client = _get_analytics_client()
    if not client:
        return None

    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if not rows:
            return None
        row = rows[0]
        headers = [h["name"] for h in response.get("columnHeaders", [])]
        data = dict(zip(headers, row))
        data["video_id"] = video_id
        data["pulled_at"] = datetime.utcnow().isoformat()
        return data
    except Exception as e:
        logger.error(f"Failed to get analytics for {video_id}: {e}")
        return None


async def get_retention_data(video_id: str) -> Optional[dict]:
    """Get audience retention curve for a video (requires OAuth).

    This is the KEY metric for the autoresearch loop —
    maps directly to Lamar's retention graph levels:
    - Level 1 (Drop-Off): immediate drop to zero
    - Level 2 (Early Plateau): stays through hook, drops mid-video
    - Level 3 (Even Scale): consistent start to near-end (TARGET)
    """
    client = _get_analytics_client()
    if not client:
        return None

    try:
        response = client.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=datetime.utcnow().strftime("%Y-%m-%d"),
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=f"video=={video_id}",
        ).execute()
        rows = response.get("rows", [])
        if not rows:
            return None

        # Build retention curve
        curve = [{"time_ratio": row[0], "watch_ratio": row[1]} for row in rows]

        # Classify retention level (Lamar framework)
        if len(curve) < 3:
            level = "unknown"
        else:
            avg_mid = sum(p["watch_ratio"] for p in curve[len(curve) // 4: 3 * len(curve) // 4]) / max(1, len(curve) // 2)
            avg_end = sum(p["watch_ratio"] for p in curve[3 * len(curve) // 4:]) / max(1, len(curve) // 4)

            if avg_mid < 0.2:
                level = "drop_off"       # Level 1: Hook bad, everything bad
            elif avg_end < 0.15:
                level = "early_plateau"  # Level 2: Hook good, but loses them
            else:
                level = "even_scale"     # Level 3: TARGET — consistent retention

        return {
            "video_id": video_id,
            "retention_curve": curve,
            "retention_level": level,
            "pulled_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get retention data for {video_id}: {e}")
        return None


async def pull_channel_analytics(
    channel_id: str,
    days: int = 28,
    max_videos: int = 20,
) -> dict:
    """Pull comprehensive analytics for a channel's recent videos.

    This is the main entry point for the autoresearch loop.
    Returns performance data for each video plus aggregate stats.
    """
    videos = await get_channel_videos(channel_id, max_results=max_videos)
    results = []
    for v in videos:
        stats = await get_video_stats(v["video_id"])
        analytics = await get_video_analytics(v["video_id"])
        retention = await get_retention_data(v["video_id"])
        results.append({
            **v,
            "stats": stats,
            "analytics": analytics,
            "retention": retention,
        })

    # Aggregate stats
    total_views = sum(r["stats"]["views"] for r in results if r.get("stats"))
    total_likes = sum(r["stats"]["likes"] for r in results if r.get("stats"))
    avg_views = total_views / max(1, len(results))

    return {
        "channel_id": channel_id,
        "period_days": days,
        "videos_analyzed": len(results),
        "total_views": total_views,
        "total_likes": total_likes,
        "avg_views_per_video": avg_views,
        "videos": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
