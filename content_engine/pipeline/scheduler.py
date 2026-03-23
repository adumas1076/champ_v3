"""
Content Scheduler — Queue and auto-post content across platforms.

Two modes (from marketing.yaml):
  approve_first — content queued, user reviews and approves before posting
  auto_post     — content posts automatically on schedule

Integrates with platform APIs for actual publishing.
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class PostStatus(str, Enum):
    QUEUED = "queued"              # In the queue, waiting for its slot
    APPROVED = "approved"          # User approved, ready to post
    PUBLISHING = "publishing"      # Currently being posted
    PUBLISHED = "published"        # Successfully posted
    FAILED = "failed"              # Publishing failed
    REJECTED = "rejected"          # User rejected this piece
    PAUSED = "paused"              # Temporarily paused


@dataclass
class ScheduledPost:
    """A content piece scheduled for publishing."""
    id: str
    content_id: str                    # Reference to ContentPiece
    pillar_id: str                     # Which pillar this came from
    influencer_id: str
    platform: str
    # Scheduling
    scheduled_at: Optional[str] = None  # When to post (ISO datetime)
    posted_at: Optional[str] = None     # When it was actually posted
    status: PostStatus = PostStatus.QUEUED
    # Content
    title: str = ""
    caption: str = ""
    media_url: Optional[str] = None    # URL to media file
    hashtags: list[str] = field(default_factory=list)
    # Approval
    approval_mode: str = "approve_first"  # approve_first | auto_post
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    # Result
    post_url: Optional[str] = None     # URL of the published post
    error: Optional[str] = None
    # Metadata
    funnel_stage: str = "tof"
    content_type: str = "micro"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PublishResult:
    """Result of publishing a post to a platform."""
    success: bool
    post_url: Optional[str] = None
    platform_post_id: Optional[str] = None
    error: Optional[str] = None


class ContentScheduler:
    """Manages the content publishing queue.

    Usage:
        scheduler = ContentScheduler(approval_mode="approve_first")
        scheduler.add_to_queue(post)
        scheduler.approve(post_id)
        results = await scheduler.publish_due()
    """

    def __init__(self, approval_mode: str = "approve_first"):
        self.approval_mode = approval_mode
        self._queue: list[ScheduledPost] = []
        self._publishers: dict = {}  # platform → publisher function

    def add_to_queue(
        self,
        content_id: str,
        pillar_id: str,
        influencer_id: str,
        platform: str,
        title: str = "",
        caption: str = "",
        media_url: Optional[str] = None,
        hashtags: Optional[list[str]] = None,
        scheduled_at: Optional[str] = None,
        funnel_stage: str = "tof",
        content_type: str = "micro",
    ) -> ScheduledPost:
        """Add a content piece to the publishing queue."""
        import uuid
        post = ScheduledPost(
            id=uuid.uuid4().hex[:12],
            content_id=content_id,
            pillar_id=pillar_id,
            influencer_id=influencer_id,
            platform=platform,
            title=title,
            caption=caption,
            media_url=media_url,
            hashtags=hashtags or [],
            scheduled_at=scheduled_at or self._next_slot(platform),
            funnel_stage=funnel_stage,
            content_type=content_type,
            approval_mode=self.approval_mode,
        )

        # In auto_post mode, auto-approve
        if self.approval_mode == "auto_post":
            post.status = PostStatus.APPROVED

        self._queue.append(post)
        logger.info(f"[SCHEDULER] Queued {content_id} for {platform} at {post.scheduled_at}")
        return post

    def approve(self, post_id: str, approved_by: str = "user") -> bool:
        """Approve a queued post for publishing."""
        post = self._find(post_id)
        if not post:
            return False
        if post.status != PostStatus.QUEUED:
            logger.warning(f"[SCHEDULER] Cannot approve post {post_id} — status is {post.status}")
            return False
        post.status = PostStatus.APPROVED
        post.approved_by = approved_by
        logger.info(f"[SCHEDULER] Approved {post_id} by {approved_by}")
        return True

    def reject(self, post_id: str, reason: str = "") -> bool:
        """Reject a queued post."""
        post = self._find(post_id)
        if not post:
            return False
        post.status = PostStatus.REJECTED
        post.rejection_reason = reason
        logger.info(f"[SCHEDULER] Rejected {post_id}: {reason}")
        return True

    def pause(self, post_id: str) -> bool:
        """Pause a scheduled post."""
        post = self._find(post_id)
        if not post:
            return False
        post.status = PostStatus.PAUSED
        return True

    def resume(self, post_id: str) -> bool:
        """Resume a paused post."""
        post = self._find(post_id)
        if not post or post.status != PostStatus.PAUSED:
            return False
        post.status = PostStatus.APPROVED
        return True

    def get_queue(
        self,
        platform: Optional[str] = None,
        status: Optional[PostStatus] = None,
        influencer_id: Optional[str] = None,
    ) -> list[ScheduledPost]:
        """Get posts in the queue, optionally filtered."""
        results = self._queue
        if platform:
            results = [p for p in results if p.platform == platform]
        if status:
            results = [p for p in results if p.status == status]
        if influencer_id:
            results = [p for p in results if p.influencer_id == influencer_id]
        return sorted(results, key=lambda p: p.scheduled_at or "")

    def get_due_posts(self) -> list[ScheduledPost]:
        """Get posts that are approved and due for publishing."""
        now = datetime.utcnow().isoformat()
        return [
            p for p in self._queue
            if p.status == PostStatus.APPROVED
            and p.scheduled_at
            and p.scheduled_at <= now
        ]

    async def publish_due(self) -> list[PublishResult]:
        """Publish all due posts. Returns results."""
        due = self.get_due_posts()
        results = []
        for post in due:
            result = await self._publish(post)
            results.append(result)
        return results

    async def _publish(self, post: ScheduledPost) -> PublishResult:
        """Publish a single post to its platform."""
        post.status = PostStatus.PUBLISHING
        publisher = self._publishers.get(post.platform)

        if not publisher:
            logger.warning(f"[SCHEDULER] No publisher registered for {post.platform} — marking as published (dry run)")
            post.status = PostStatus.PUBLISHED
            post.posted_at = datetime.utcnow().isoformat()
            return PublishResult(success=True, post_url=None)

        try:
            result = await publisher(post)
            if result.success:
                post.status = PostStatus.PUBLISHED
                post.posted_at = datetime.utcnow().isoformat()
                post.post_url = result.post_url
            else:
                post.status = PostStatus.FAILED
                post.error = result.error
            return result
        except Exception as e:
            post.status = PostStatus.FAILED
            post.error = str(e)
            logger.error(f"[SCHEDULER] Failed to publish {post.id}: {e}")
            return PublishResult(success=False, error=str(e))

    def register_publisher(self, platform: str, publisher_fn):
        """Register a platform-specific publishing function.

        Publisher fn signature: async def publish(post: ScheduledPost) -> PublishResult
        """
        self._publishers[platform] = publisher_fn
        logger.info(f"[SCHEDULER] Registered publisher for {platform}")

    def _find(self, post_id: str) -> Optional[ScheduledPost]:
        for p in self._queue:
            if p.id == post_id:
                return p
        return None

    def _next_slot(self, platform: str) -> str:
        """Calculate next available posting slot for a platform.

        Spreads posts throughout the day to avoid flooding.
        """
        # Find latest scheduled post for this platform
        platform_posts = [p for p in self._queue if p.platform == platform and p.scheduled_at]
        if platform_posts:
            latest = max(p.scheduled_at for p in platform_posts)
            # Schedule 3 hours after the latest post
            latest_dt = datetime.fromisoformat(latest)
            next_dt = latest_dt + timedelta(hours=3)
        else:
            # First post — schedule for next hour
            next_dt = datetime.utcnow() + timedelta(hours=1)
        return next_dt.isoformat()

    def get_summary(self) -> str:
        """Human-readable summary of the queue."""
        status_counts = {}
        platform_counts = {}
        for p in self._queue:
            status_counts[p.status.value] = status_counts.get(p.status.value, 0) + 1
            platform_counts[p.platform] = platform_counts.get(p.platform, 0) + 1

        lines = [
            f"# Content Queue — {len(self._queue)} total posts",
            f"Mode: {self.approval_mode}",
            "",
            "## By Status:",
        ]
        for s, c in status_counts.items():
            lines.append(f"  {s}: {c}")
        lines.append("")
        lines.append("## By Platform:")
        for p, c in platform_counts.items():
            lines.append(f"  {p}: {c}")
        return "\n".join(lines)
