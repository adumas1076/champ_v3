"""
Platform Adapters — Format content for each platform's requirements.
Each adapter takes a ContentPiece and returns platform-specific formatting.

Platforms: YouTube, Instagram, TikTok, LinkedIn, Twitter, Podcast, Blog, Email

Key rule: "Context is king, not content" — Gary Vee
Same message, different packaging per platform.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FormattedContent:
    """Content formatted for a specific platform."""
    content_id: str
    platform: str
    # Text fields
    title: str = ""
    caption: str = ""
    hashtags: list[str] = None
    alt_text: str = ""
    # Media specs
    aspect_ratio: str = ""         # 16:9, 9:16, 1:1, 4:5
    max_duration_sec: Optional[int] = None
    min_duration_sec: Optional[int] = None
    resolution: str = ""
    # Production notes
    needs_subtitles: bool = True
    needs_headline_overlay: bool = True
    needs_timer: bool = False
    caption_style: str = ""        # slide_in | fade | enlarge | bold
    # Platform-specific
    cta: str = ""                  # Call to action
    link: str = ""                 # Link in bio / swipe up / etc
    schedule_note: str = ""        # Best time to post

    def __post_init__(self):
        if self.hashtags is None:
            self.hashtags = []


# ============================================
# Platform Specs
# ============================================

PLATFORM_SPECS = {
    "youtube": {
        "name": "YouTube",
        "long_form": {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "max_duration_sec": 7200,     # 2 hours
            "min_duration_sec": 480,      # 8 min for mid-roll ads
            "title_max_chars": 100,
            "description_max_chars": 5000,
            "hashtags_max": 15,
            "best_times": ["9am-11am", "2pm-4pm"],
        },
        "shorts": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 60,
            "min_duration_sec": 15,
            "title_max_chars": 100,
        },
    },
    "instagram": {
        "name": "Instagram",
        "reels": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 90,
            "min_duration_sec": 15,
            "caption_max_chars": 2200,
            "hashtags_max": 30,
            "best_times": ["11am-1pm", "7pm-9pm"],
        },
        "feed": {
            "aspect_ratio": "4:5",
            "resolution": "1080x1350",
            "caption_max_chars": 2200,
            "hashtags_max": 30,
        },
        "stories": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 15,
        },
        "carousel": {
            "aspect_ratio": "1:1",
            "resolution": "1080x1080",
            "slides_min": 2,
            "slides_max": 10,
            "caption_max_chars": 2200,
        },
    },
    "facebook": {
        "name": "Facebook",
        "post": {
            "caption_max_chars": 63206,
            "hashtags_max": 10,
            "best_times": ["9am-11am", "1pm-3pm"],
        },
        "video": {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "max_duration_sec": 14400,     # 4 hours
            "min_duration_sec": 3,
            "best_times": ["1pm-4pm"],
        },
        "reels": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 90,
            "min_duration_sec": 3,
            "caption_max_chars": 2200,
            "best_times": ["9am-12pm", "7pm-9pm"],
        },
        "stories": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 20,
        },
    },
    "tiktok": {
        "name": "TikTok",
        "video": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 180,
            "min_duration_sec": 15,
            "caption_max_chars": 2200,
            "hashtags_max": 5,           # TikTok prefers fewer hashtags
            "best_times": ["7pm-11pm"],
        },
    },
    "linkedin": {
        "name": "LinkedIn",
        "post": {
            "caption_max_chars": 3000,
            "hashtags_max": 5,
            "best_times": ["8am-10am", "12pm"],
        },
        "article": {
            "body_max_chars": 125000,
            "best_times": ["8am-10am"],
        },
        "video": {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "max_duration_sec": 600,
            "min_duration_sec": 30,
        },
        "carousel": {
            "slides_max": 300,           # PDF pages
            "aspect_ratio": "4:5",
        },
    },
    "twitter": {
        "name": "Twitter/X",
        "tweet": {
            "max_chars": 280,
            "hashtags_max": 2,
            "best_times": ["9am-11am", "1pm-3pm"],
        },
        "thread": {
            "max_tweets": 25,
            "max_chars_per_tweet": 280,
        },
        "video": {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "max_duration_sec": 140,
        },
    },
    "podcast": {
        "name": "Podcast",
        "episode": {
            "format": "audio",
            "bitrate": "128kbps",
            "sample_rate": "44100",
        },
    },
    "blog": {
        "name": "Blog",
        "post": {
            "format": "markdown",
            "min_words": 500,
            "max_words": 5000,
        },
    },
    "email": {
        "name": "Email Newsletter",
        "newsletter": {
            "format": "html",
            "subject_max_chars": 60,
            "preview_max_chars": 90,
            "best_times": ["6am-8am", "10am"],
        },
    },
}


# ============================================
# Formatting Functions
# ============================================

def format_for_platform(
    content_id: str,
    platform: str,
    content_type: str,
    title: str = "",
    caption: str = "",
    hashtags: Optional[list[str]] = None,
    funnel_stage: str = "tof",
    influencer_niche: str = "",
) -> FormattedContent:
    """Format a content piece for a specific platform.

    Applies platform-specific constraints and adds production notes.
    """
    specs = PLATFORM_SPECS.get(platform, {})
    hashtags = hashtags or []

    # Determine format key based on content type
    format_key = _get_format_key(platform, content_type)
    format_specs = specs.get(format_key, {})

    formatted = FormattedContent(
        content_id=content_id,
        platform=platform,
        title=_truncate(title, format_specs.get("title_max_chars", 100)),
        caption=_truncate(caption, format_specs.get("caption_max_chars", 2200)),
        hashtags=hashtags[:format_specs.get("hashtags_max", 10)],
        aspect_ratio=format_specs.get("aspect_ratio", "16:9"),
        max_duration_sec=format_specs.get("max_duration_sec"),
        min_duration_sec=format_specs.get("min_duration_sec"),
        resolution=format_specs.get("resolution", ""),
        needs_subtitles=platform in ("instagram", "tiktok", "twitter", "linkedin", "facebook"),  # 70%+ sound off
        needs_headline_overlay=platform in ("instagram", "tiktok", "facebook"),
        cta=_get_cta(platform, funnel_stage),
        schedule_note=_get_best_time(format_specs),
    )

    # Vary caption style (Lamar Every-5 Rule)
    caption_styles = ["slide_in", "fade", "enlarge", "bold"]
    formatted.caption_style = caption_styles[hash(content_id) % len(caption_styles)]

    return formatted


def _get_format_key(platform: str, content_type: str) -> str:
    """Map content type to platform-specific format."""
    mappings = {
        ("youtube", "pillar"): "long_form",
        ("youtube", "long_form"): "long_form",
        ("youtube", "micro"): "shorts",
        ("youtube", "micro_micro"): "shorts",
        ("facebook", "pillar"): "video",
        ("facebook", "long_form"): "video",
        ("facebook", "micro"): "reels",
        ("facebook", "micro_micro"): "reels",
        ("facebook", "static"): "post",
        ("instagram", "micro"): "reels",
        ("instagram", "micro_micro"): "reels",
        ("instagram", "static"): "feed",
        ("tiktok", "micro"): "video",
        ("tiktok", "micro_micro"): "video",
        ("linkedin", "long_form"): "article",
        ("linkedin", "micro"): "video",
        ("linkedin", "static"): "carousel",
        ("twitter", "micro"): "video",
        ("twitter", "micro_micro"): "video",
        ("twitter", "static"): "tweet",
        ("podcast", "long_form"): "episode",
        ("blog", "long_form"): "post",
        ("email", "long_form"): "newsletter",
    }
    return mappings.get((platform, content_type), "post")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def _get_cta(platform: str, funnel_stage: str) -> str:
    """Generate CTA based on funnel stage and platform."""
    ctas = {
        "tof": {
            "default": "Follow for more",
            "youtube": "Subscribe for weekly builds",
            "twitter": "RT if this hits",
        },
        "mof": {
            "default": "Link in bio for the full breakdown",
            "youtube": "Watch the full version — link in description",
            "linkedin": "What's your experience with this?",
        },
        "bof": {
            "default": "DM 'START' to get early access",
            "youtube": "Join the waitlist — link in description",
            "twitter": "Early access open → link in bio",
        },
    }
    stage_ctas = ctas.get(funnel_stage, ctas["tof"])
    return stage_ctas.get(platform, stage_ctas["default"])


def _get_best_time(specs: dict) -> str:
    times = specs.get("best_times", [])
    return f"Best posting times: {', '.join(times)}" if times else ""


def get_platform_specs(platform: str) -> dict:
    """Get full specs for a platform."""
    return PLATFORM_SPECS.get(platform, {})


def get_all_platforms() -> list[str]:
    """Get list of all supported platforms."""
    return list(PLATFORM_SPECS.keys())
