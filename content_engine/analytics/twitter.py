"""
Twitter/X Analytics Module
Pulls tweet performance data via Twitter API v2.
Feeds metrics into the autoresearch loop for content scoring.

Required env vars:
  TWITTER_BEARER_TOKEN     — App-level bearer token (read-only)
  TWITTER_API_KEY          — OAuth 1.0a consumer key (for posting)
  TWITTER_API_SECRET       — OAuth 1.0a consumer secret
  TWITTER_ACCESS_TOKEN     — User-level access token
  TWITTER_ACCESS_SECRET    — User-level access secret
  TWITTER_USER_ID          — Numeric user ID
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

TWITTER_API_BASE = "https://api.twitter.com/2"


def _get_bearer() -> Optional[str]:
    return os.getenv("TWITTER_BEARER_TOKEN")


def _get_user_id() -> Optional[str]:
    return os.getenv("TWITTER_USER_ID")


async def _twitter_get(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make authenticated GET request to Twitter API v2."""
    bearer = _get_bearer()
    if not bearer:
        logger.warning("TWITTER_BEARER_TOKEN not set — Twitter analytics unavailable")
        return None
    try:
        import httpx
        headers = {"Authorization": f"Bearer {bearer}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{TWITTER_API_BASE}/{endpoint}", params=params or {}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.error(f"Twitter API error: {e}")
        return None


async def get_user_info(user_id: Optional[str] = None) -> Optional[dict]:
    """Get Twitter user profile info."""
    uid = user_id or _get_user_id()
    if not uid:
        return None
    data = await _twitter_get(f"users/{uid}", {
        "user.fields": "public_metrics,description,profile_image_url,verified,created_at",
    })
    if not data:
        return None
    return data.get("data", {})


async def get_recent_tweets(
    user_id: Optional[str] = None,
    max_results: int = 20,
    days_back: int = 7,
) -> list[dict]:
    """Get recent tweets with engagement metrics."""
    uid = user_id or _get_user_id()
    if not uid:
        return []

    start_time = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = await _twitter_get(f"users/{uid}/tweets", {
        "max_results": min(max_results, 100),
        "start_time": start_time,
        "tweet.fields": "public_metrics,created_at,conversation_id,referenced_tweets,attachments",
        "expansions": "attachments.media_keys",
        "media.fields": "type,duration_ms,public_metrics,preview_image_url",
    })
    if not data:
        return []
    return data.get("data", [])


async def get_tweet_metrics(tweet_id: str) -> Optional[dict]:
    """Get detailed metrics for a single tweet.

    Note: Non-public metrics (impressions, profile clicks, url clicks)
    require user-context auth (OAuth 1.0a), not just bearer token.
    """
    data = await _twitter_get(f"tweets/{tweet_id}", {
        "tweet.fields": "public_metrics,non_public_metrics,organic_metrics,created_at",
    })
    if not data:
        return None
    tweet = data.get("data", {})
    public = tweet.get("public_metrics", {})
    non_public = tweet.get("non_public_metrics", {})
    organic = tweet.get("organic_metrics", {})

    return {
        "tweet_id": tweet_id,
        "likes": public.get("like_count", 0),
        "retweets": public.get("retweet_count", 0),
        "replies": public.get("reply_count", 0),
        "quotes": public.get("quote_count", 0),
        "bookmarks": public.get("bookmark_count", 0),
        "impressions": non_public.get("impression_count", 0) or organic.get("impression_count", 0),
        "url_clicks": non_public.get("url_link_clicks", 0) or organic.get("url_link_clicks", 0),
        "profile_clicks": non_public.get("user_profile_clicks", 0),
        "created_at": tweet.get("created_at", ""),
        "pulled_at": datetime.utcnow().isoformat(),
    }


async def get_mentions(
    user_id: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """Get recent mentions of the user."""
    uid = user_id or _get_user_id()
    if not uid:
        return []
    data = await _twitter_get(f"users/{uid}/mentions", {
        "max_results": min(max_results, 100),
        "tweet.fields": "public_metrics,created_at,author_id",
    })
    if not data:
        return []
    return data.get("data", [])


async def pull_content_performance(
    user_id: Optional[str] = None,
    max_tweets: int = 20,
    days_back: int = 7,
) -> dict:
    """Pull comprehensive performance data for recent Twitter content.

    Main entry point for the autoresearch loop.
    """
    uid = user_id or _get_user_id()
    tweets = await get_recent_tweets(user_id=uid, max_results=max_tweets, days_back=days_back)
    results = []
    total_impressions = 0
    total_likes = 0
    total_retweets = 0
    total_replies = 0
    total_quotes = 0
    total_bookmarks = 0

    for tweet in tweets:
        public = tweet.get("public_metrics", {})
        likes = public.get("like_count", 0)
        retweets = public.get("retweet_count", 0)
        replies = public.get("reply_count", 0)
        quotes = public.get("quote_count", 0)
        bookmarks = public.get("bookmark_count", 0)

        # Determine if this is a thread (has referenced tweets)
        refs = tweet.get("referenced_tweets", [])
        is_reply = any(r.get("type") == "replied_to" for r in refs) if refs else False
        is_retweet = any(r.get("type") == "retweeted" for r in refs) if refs else False
        is_quote = any(r.get("type") == "quoted" for r in refs) if refs else False

        # Check for media
        has_media = bool(tweet.get("attachments", {}).get("media_keys"))

        # Try to get impressions (requires elevated access)
        detailed = await get_tweet_metrics(tweet.get("id", ""))
        impressions = detailed.get("impressions", 0) if detailed else 0

        engagement = likes + retweets + replies + quotes + bookmarks
        engagement_rate = (engagement / max(1, impressions)) * 100 if impressions else 0

        entry = {
            "tweet_id": tweet.get("id", ""),
            "text": tweet.get("text", "")[:200],
            "created_at": tweet.get("created_at", ""),
            "is_reply": is_reply,
            "is_retweet": is_retweet,
            "is_quote": is_quote,
            "has_media": has_media,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
            "quotes": quotes,
            "bookmarks": bookmarks,
            "impressions": impressions,
            "engagement_rate": engagement_rate,
        }
        results.append(entry)
        total_impressions += impressions
        total_likes += likes
        total_retweets += retweets
        total_replies += replies
        total_quotes += quotes
        total_bookmarks += bookmarks

    # Filter out retweets for organic performance
    organic = [r for r in results if not r["is_retweet"]]
    total_engagement = total_likes + total_retweets + total_replies + total_quotes + total_bookmarks
    engagement_rate = (total_engagement / max(1, total_impressions)) * 100

    return {
        "platform": "twitter",
        "posts_analyzed": len(results),
        "organic_posts": len(organic),
        "total_impressions": total_impressions,
        "total_likes": total_likes,
        "total_retweets": total_retweets,
        "total_replies": total_replies,
        "total_quotes": total_quotes,
        "total_bookmarks": total_bookmarks,
        "engagement_rate": engagement_rate,
        "posts": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
