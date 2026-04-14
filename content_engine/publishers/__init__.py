# Content Engine — Platform Publishers
# Actual API posting to social platforms.
# Every publisher inherits BasePublisher and implements platform-specific logic.
#
# Architecture (from 0034_click_to_client_technical_wiring.md):
#   base.py        — Abstract publisher with retry, rate limit, compliance
#   compliance.py  — Rate limits, disclosure rules, ban prevention
#   twitter.py     — Twitter API v2
#   linkedin.py    — LinkedIn REST API
#   instagram.py   — Instagram Graph API (via Meta Business)
#   tiktok.py      — TikTok Content Posting API
#
# OAuth tokens: env vars now, Nango integration planned
# Posting patterns: harvested from Postiz (reference/postiz/)

import logging
from content_engine.publishers.base import BasePublisher, PublishResult, PublishError, PostPayload
from content_engine.publishers.compliance import ComplianceChecker, PLATFORM_LIMITS

logger = logging.getLogger(__name__)

# Global compliance checker — shared across all publishers
_compliance = ComplianceChecker()


def get_compliance() -> ComplianceChecker:
    """Get the global compliance checker instance."""
    return _compliance


def register_all_publishers(scheduler) -> dict:
    """Register all available platform publishers with the content scheduler.

    Call this at startup to wire publishers into scheduler.py's
    register_publisher() framework. Each publisher is wrapped with
    compliance checking before posting.

    Usage:
        from content_engine.pipeline.scheduler import ContentScheduler
        from content_engine.publishers import register_all_publishers

        scheduler = ContentScheduler(approval_mode="auto_post")
        publishers = register_all_publishers(scheduler)
    """
    from content_engine.publishers.twitter import TwitterPublisher
    from content_engine.publishers.instagram import InstagramPublisher
    from content_engine.publishers.linkedin import LinkedInPublisher
    from content_engine.publishers.tiktok import TikTokPublisher
    from content_engine.publishers.youtube import YouTubePublisher
    from content_engine.publishers.facebook import FacebookPublisher

    publishers = {}
    publisher_classes = {
        "twitter": TwitterPublisher,
        "instagram": InstagramPublisher,
        "linkedin": LinkedInPublisher,
        "tiktok": TikTokPublisher,
        "youtube": YouTubePublisher,
        "facebook": FacebookPublisher,
    }

    for platform, cls in publisher_classes.items():
        pub = cls()
        publishers[platform] = pub

        # Create a compliance-wrapped publish function for the scheduler
        # Uses default arg binding to capture current pub/platform in closure
        async def _publish_fn(scheduled_post, publisher=pub, plat=platform):
            # Check compliance before posting
            if not _compliance.can_post(plat, scheduled_post.influencer_id):
                status = _compliance.get_status(plat, scheduled_post.influencer_id)
                return PublishResult(
                    success=False,
                    platform=plat,
                    error=f"Compliance block: {status.posts_today}/{status.posts_limit} posts today. "
                          f"Next safe time: {status.next_post_at or 'tomorrow'}",
                )

            # Build payload from ScheduledPost
            payload = PostPayload(
                text=scheduled_post.caption or scheduled_post.title,
                influencer_id=scheduled_post.influencer_id,
                content_id=scheduled_post.content_id,
                funnel_stage=scheduled_post.funnel_stage,
                content_type=scheduled_post.content_type,
                hashtags=scheduled_post.hashtags,
                title=scheduled_post.title,
            )

            # Add media if present
            if scheduled_post.media_url:
                from content_engine.publishers.base import MediaFile
                is_video = any(
                    ext in (scheduled_post.media_url or "")
                    for ext in [".mp4", ".mov", ".avi", ".webm"]
                )
                payload.media = [MediaFile(
                    url=scheduled_post.media_url,
                    file_path=None,
                    media_type="video" if is_video else "image",
                )]

            # Post
            result = await publisher.post(payload)

            # Record action for compliance tracking
            if result.success:
                _compliance.record_action(plat, scheduled_post.influencer_id, "post", result.post_id)

            # Write publish_result to MarketingGraph (non-blocking)
            try:
                from content_engine import graph_writer
                graph_writer.record_publish_result(
                    piece_id=scheduled_post.content_id,
                    platform=plat,
                    success=result.success,
                    post_id=result.post_id or "",
                    post_url=result.post_url or "",
                    error=result.error or "",
                )
            except Exception:
                pass  # Graph write is non-fatal

            return result

        scheduler.register_publisher(platform, _publish_fn)
        logger.info(f"[PUBLISHERS] Registered {platform} publisher with scheduler")

    return publishers
