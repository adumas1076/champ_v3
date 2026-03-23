"""
LinkedIn Analytics Module
Pulls post performance data via LinkedIn Marketing API / Community Management API.
Feeds metrics into the autoresearch loop for content scoring.

Required env vars:
  LINKEDIN_ACCESS_TOKEN    — OAuth 2.0 access token (3-legged)
  LINKEDIN_PERSON_URN      — LinkedIn person URN (urn:li:person:XXXXX)
  LINKEDIN_ORG_URN         — LinkedIn organization URN (optional, for company pages)
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"


def _get_token() -> Optional[str]:
    return os.getenv("LINKEDIN_ACCESS_TOKEN")


def _get_person_urn() -> Optional[str]:
    return os.getenv("LINKEDIN_PERSON_URN")


def _get_org_urn() -> Optional[str]:
    return os.getenv("LINKEDIN_ORG_URN")


async def _linkedin_get(endpoint: str, params: Optional[dict] = None, use_rest: bool = False) -> Optional[dict]:
    """Make authenticated GET request to LinkedIn API."""
    token = _get_token()
    if not token:
        logger.warning("LINKEDIN_ACCESS_TOKEN not set — LinkedIn analytics unavailable")
        return None
    try:
        import httpx
        base = LINKEDIN_REST_BASE if use_rest else LINKEDIN_API_BASE
        headers = {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": "202401",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base}/{endpoint}", params=params or {}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.error(f"LinkedIn API error: {e}")
        return None


async def get_profile() -> Optional[dict]:
    """Get LinkedIn profile info."""
    return await _linkedin_get("me")


async def get_recent_posts(count: int = 20) -> list[dict]:
    """Get recent posts/shares from the authenticated user."""
    person_urn = _get_person_urn()
    if not person_urn:
        logger.warning("LINKEDIN_PERSON_URN not set")
        return []

    data = await _linkedin_get("ugcPosts", {
        "q": "authors",
        "authors": f"List({person_urn})",
        "count": count,
        "sortBy": "LAST_MODIFIED",
    })
    if not data:
        return []
    return data.get("elements", [])


async def get_post_stats(post_urn: str) -> Optional[dict]:
    """Get engagement stats for a specific post.

    Returns: likes, comments, shares, impressions, clicks, engagement rate.
    """
    data = await _linkedin_get("organizationalEntityShareStatistics", {
        "q": "organizationalEntity",
        "shares": f"List({post_urn})",
    })
    if not data:
        # Try socialActions endpoint for personal posts
        actions_data = await _linkedin_get(f"socialActions/{post_urn}")
        if actions_data:
            return {
                "post_urn": post_urn,
                "likes": actions_data.get("likesSummary", {}).get("totalLikes", 0),
                "comments": actions_data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                "pulled_at": datetime.utcnow().isoformat(),
            }
        return None

    elements = data.get("elements", [])
    if not elements:
        return None

    stats = elements[0].get("totalShareStatistics", {})
    return {
        "post_urn": post_urn,
        "impressions": stats.get("impressionCount", 0),
        "clicks": stats.get("clickCount", 0),
        "likes": stats.get("likeCount", 0),
        "comments": stats.get("commentCount", 0),
        "shares": stats.get("shareCount", 0),
        "engagement": stats.get("engagement", 0),
        "unique_impressions": stats.get("uniqueImpressionsCount", 0),
        "pulled_at": datetime.utcnow().isoformat(),
    }


async def get_follower_stats() -> Optional[dict]:
    """Get follower count and growth stats."""
    org_urn = _get_org_urn()
    if not org_urn:
        # Personal profile — get from /me
        profile = await get_profile()
        if profile:
            return {
                "type": "personal",
                "follower_count": profile.get("followersCount", 0),
                "pulled_at": datetime.utcnow().isoformat(),
            }
        return None

    data = await _linkedin_get("organizationalEntityFollowerStatistics", {
        "q": "organizationalEntity",
        "organizationalEntity": org_urn,
    })
    if not data:
        return None
    elements = data.get("elements", [])
    if not elements:
        return None
    return {
        "type": "organization",
        "org_urn": org_urn,
        "total_followers": elements[0].get("followerCounts", {}).get("organicFollowerCount", 0),
        "pulled_at": datetime.utcnow().isoformat(),
    }


async def pull_content_performance(max_posts: int = 20) -> dict:
    """Pull comprehensive performance data for recent LinkedIn content.

    Main entry point for the autoresearch loop.
    """
    posts = await get_recent_posts(count=max_posts)
    results = []
    total_impressions = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_clicks = 0

    for post in posts:
        post_urn = post.get("id", "")
        specific_content = post.get("specificContent", {}).get("com.linkedin.ugc.ShareContent", {})
        text = specific_content.get("shareCommentary", {}).get("text", "")
        media = specific_content.get("media", [])
        media_type = media[0].get("mediaCategory", "NONE") if media else "NONE"

        stats = await get_post_stats(post_urn)

        entry = {
            "post_urn": post_urn,
            "text": text[:200] if text else "",
            "media_type": media_type,
            "created_at": post.get("created", {}).get("time", ""),
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "impressions": 0,
            "clicks": 0,
            "engagement_rate": 0,
        }

        if stats:
            entry["likes"] = stats.get("likes", 0)
            entry["comments"] = stats.get("comments", 0)
            entry["shares"] = stats.get("shares", 0)
            entry["impressions"] = stats.get("impressions", 0)
            entry["clicks"] = stats.get("clicks", 0)
            if entry["impressions"] > 0:
                entry["engagement_rate"] = (
                    (entry["likes"] + entry["comments"] + entry["shares"] + entry["clicks"])
                    / entry["impressions"] * 100
                )

        results.append(entry)
        total_impressions += entry["impressions"]
        total_likes += entry["likes"]
        total_comments += entry["comments"]
        total_shares += entry["shares"]
        total_clicks += entry["clicks"]

    total_engagement = total_likes + total_comments + total_shares + total_clicks
    engagement_rate = (total_engagement / max(1, total_impressions)) * 100

    return {
        "platform": "linkedin",
        "posts_analyzed": len(results),
        "total_impressions": total_impressions,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_clicks": total_clicks,
        "engagement_rate": engagement_rate,
        "posts": results,
        "pulled_at": datetime.utcnow().isoformat(),
    }
