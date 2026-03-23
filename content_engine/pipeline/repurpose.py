"""
Content Repurposing Pipeline — Gary Vee Reverse Pyramid
1 pillar piece → 64+ micro pieces across all platforms.

Architecture:
  Pillar Content (1 long-form piece, 15-30 min)
      ↓
  Round 1: Long-form distribution
  (YouTube, Podcast, Blog = 5 pieces)
      ↓
  Round 2: Micro clips (2-4 min)
  (8-10 clips × 2 platforms = 16-20 pieces)
      ↓
  Round 3: Micro-micro content (<60s, images, quotes, memes)
  (15-20 clips × 3 platforms + 10-18 statics = 55-78 pieces)
      ↓
  TOTAL: 64-100+ pieces from 1 pillar
"""

import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    PILLAR = "pillar"              # Original long-form (15-30 min)
    LONG_FORM = "long_form"        # Full-length distributions
    MICRO = "micro"                # 2-4 min clips
    MICRO_MICRO = "micro_micro"    # <60s clips
    STATIC = "static"              # Images, quotes, carousels, memes


class FunnelStage(str, Enum):
    TOF = "tof"      # Top of funnel — awareness (50%)
    MOF = "mof"      # Middle of funnel — consideration (30%)
    BOF = "bof"      # Bottom of funnel — conversion (20%)


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    PODCAST = "podcast"
    BLOG = "blog"
    EMAIL = "email"


@dataclass
class ContentPiece:
    """A single content piece in the pipeline."""
    id: str
    pillar_id: str                    # Which pillar this was derived from
    content_type: ContentType
    platform: Platform
    funnel_stage: FunnelStage
    influencer_id: str
    # Content details
    title: str = ""
    description: str = ""
    script: str = ""                  # Text content / script
    duration_sec: Optional[int] = None
    # Source segment (which part of the pillar)
    source_start_sec: Optional[int] = None
    source_end_sec: Optional[int] = None
    # Production requirements
    needs_subtitles: bool = True      # 70%+ watch with sound off
    needs_headline_overlay: bool = True
    needs_timer: bool = False         # Only for time-based content
    needs_captions_varied: bool = True  # Lamar: vary caption styles
    # Pipeline status
    status: str = "planned"           # planned | scripted | produced | scored | approved | published | rejected
    eval_score: Optional[float] = None
    eval_verdict: Optional[str] = None
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    published_at: Optional[str] = None
    tags: list[str] = field(default_factory=list)


@dataclass
class PillarContent:
    """A pillar content piece — the raw material for everything else."""
    id: str
    influencer_id: str
    title: str
    description: str
    duration_min: int                  # Target: 15-30 min
    source_type: str                   # video | podcast | call | meeting | livestream | blog
    funnel_stage: FunnelStage = FunnelStage.TOF
    # File references
    source_file: Optional[str] = None
    transcript: Optional[str] = None
    # Derived pieces
    pieces: list[ContentPiece] = field(default_factory=list)
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "created"            # created | transcribed | repurposed | distributed

    @property
    def total_pieces(self) -> int:
        return len(self.pieces)

    @property
    def pieces_by_type(self) -> dict:
        counts = {}
        for p in self.pieces:
            counts[p.content_type.value] = counts.get(p.content_type.value, 0) + 1
        return counts

    @property
    def pieces_by_platform(self) -> dict:
        counts = {}
        for p in self.pieces:
            counts[p.platform.value] = counts.get(p.platform.value, 0) + 1
        return counts


# ============================================
# Repurposing Engine
# ============================================

def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def generate_round_1_long_form(pillar: PillarContent) -> list[ContentPiece]:
    """Round 1: Long-form distribution.

    Distribute the raw pillar across long-form platforms:
    YouTube (full video), Podcast (audio rip), Blog (transcription),
    IGTV, Facebook.

    Target: ~5 pieces
    """
    pieces = []

    # YouTube — full video
    pieces.append(ContentPiece(
        id=_gen_id(),
        pillar_id=pillar.id,
        content_type=ContentType.LONG_FORM,
        platform=Platform.YOUTUBE,
        funnel_stage=pillar.funnel_stage,
        influencer_id=pillar.influencer_id,
        title=pillar.title,
        description=pillar.description,
        duration_sec=pillar.duration_min * 60,
        needs_subtitles=True,
        tags=["long_form", "round_1", "youtube"],
    ))

    # Podcast — audio rip
    pieces.append(ContentPiece(
        id=_gen_id(),
        pillar_id=pillar.id,
        content_type=ContentType.LONG_FORM,
        platform=Platform.PODCAST,
        funnel_stage=pillar.funnel_stage,
        influencer_id=pillar.influencer_id,
        title=pillar.title,
        description=pillar.description,
        duration_sec=pillar.duration_min * 60,
        needs_subtitles=False,  # Audio only
        tags=["long_form", "round_1", "podcast", "audio_rip"],
    ))

    # Blog — transcription
    pieces.append(ContentPiece(
        id=_gen_id(),
        pillar_id=pillar.id,
        content_type=ContentType.LONG_FORM,
        platform=Platform.BLOG,
        funnel_stage=pillar.funnel_stage,
        influencer_id=pillar.influencer_id,
        title=pillar.title,
        description=pillar.description,
        script=pillar.transcript or "",
        needs_subtitles=False,  # Text
        tags=["long_form", "round_1", "blog", "transcription"],
    ))

    # LinkedIn article
    pieces.append(ContentPiece(
        id=_gen_id(),
        pillar_id=pillar.id,
        content_type=ContentType.LONG_FORM,
        platform=Platform.LINKEDIN,
        funnel_stage=pillar.funnel_stage,
        influencer_id=pillar.influencer_id,
        title=pillar.title,
        description="LinkedIn article version — professional framing",
        tags=["long_form", "round_1", "linkedin"],
    ))

    # Email newsletter
    pieces.append(ContentPiece(
        id=_gen_id(),
        pillar_id=pillar.id,
        content_type=ContentType.LONG_FORM,
        platform=Platform.EMAIL,
        funnel_stage=pillar.funnel_stage,
        influencer_id=pillar.influencer_id,
        title=f"Newsletter: {pillar.title}",
        description="Email newsletter version — key takeaways + link to full content",
        tags=["long_form", "round_1", "email"],
    ))

    return pieces


def generate_round_2_micro(
    pillar: PillarContent,
    num_clips: int = 10,
) -> list[ContentPiece]:
    """Round 2: Micro clips (2-4 min).

    Cut the best segments based on engagement data.
    Each clip must follow Hook → Lead → Meat → Payoff structure.
    Distribute to Instagram + Facebook + TikTok.

    Target: 8-10 clips × 2-3 platforms = 16-30 pieces
    """
    pieces = []
    duration_sec = pillar.duration_min * 60
    segment_duration = min(240, max(120, duration_sec // num_clips))  # 2-4 min each

    for i in range(num_clips):
        start = i * (duration_sec // num_clips)
        end = start + segment_duration
        clip_id = _gen_id()

        # Each clip goes to multiple platforms
        for platform in [Platform.INSTAGRAM, Platform.TIKTOK]:
            pieces.append(ContentPiece(
                id=f"{clip_id}_{platform.value}",
                pillar_id=pillar.id,
                content_type=ContentType.MICRO,
                platform=platform,
                funnel_stage=pillar.funnel_stage,
                influencer_id=pillar.influencer_id,
                title=f"{pillar.title} — Clip {i + 1}",
                description=f"Micro clip {i + 1}/{num_clips} from pillar",
                duration_sec=segment_duration,
                source_start_sec=start,
                source_end_sec=end,
                needs_subtitles=True,
                needs_headline_overlay=True,
                needs_captions_varied=True,
                tags=["micro", "round_2", platform.value, f"clip_{i + 1}"],
            ))

    return pieces


def generate_round_3_micro_micro(
    pillar: PillarContent,
    num_video_clips: int = 15,
    num_statics: int = 10,
) -> list[ContentPiece]:
    """Round 3: Micro-micro content — maximum volume.

    Video: 60s, 30s, <30s clips
    Static: quote graphics, memes, carousels, screenshot tweets
    Distribute EVERYWHERE.

    Target: 15-20 clips × 3 platforms + 10-18 statics = 55-78 pieces
    """
    pieces = []

    # Video clips — varying lengths
    durations = [60, 30, 15]  # seconds
    clips_per_duration = num_video_clips // len(durations)

    for dur in durations:
        for i in range(clips_per_duration):
            clip_id = _gen_id()
            for platform in [Platform.INSTAGRAM, Platform.TIKTOK, Platform.TWITTER]:
                pieces.append(ContentPiece(
                    id=f"{clip_id}_{platform.value}",
                    pillar_id=pillar.id,
                    content_type=ContentType.MICRO_MICRO,
                    platform=platform,
                    funnel_stage=pillar.funnel_stage,
                    influencer_id=pillar.influencer_id,
                    title=f"{pillar.title} — {dur}s #{i + 1}",
                    duration_sec=dur,
                    needs_subtitles=True,
                    needs_headline_overlay=True,
                    tags=["micro_micro", "round_3", platform.value, f"{dur}s"],
                ))

    # Static content
    static_types = [
        ("quote_graphic", "Key quote from pillar — bold typography on brand background"),
        ("carousel", "5-10 slide carousel summarizing key takeaways"),
        ("meme", "Relatable meme using pillar's core message"),
        ("screenshot_tweet", "Screenshot of tweet about pillar topic → Instagram post"),
        ("screenshot_notes", "Screenshot of notepad thoughts → Instagram story"),
    ]

    statics_per_type = max(1, num_statics // len(static_types))
    for static_type, desc in static_types:
        for i in range(statics_per_type):
            static_id = _gen_id()
            for platform in [Platform.INSTAGRAM, Platform.TWITTER, Platform.LINKEDIN]:
                pieces.append(ContentPiece(
                    id=f"{static_id}_{platform.value}",
                    pillar_id=pillar.id,
                    content_type=ContentType.STATIC,
                    platform=platform,
                    funnel_stage=pillar.funnel_stage,
                    influencer_id=pillar.influencer_id,
                    title=f"{pillar.title} — {static_type} #{i + 1}",
                    description=desc,
                    needs_subtitles=False,
                    tags=["static", "round_3", platform.value, static_type],
                ))

    return pieces


def repurpose_pillar(
    pillar: PillarContent,
    micro_clips: int = 10,
    micro_micro_clips: int = 15,
    statics: int = 10,
) -> PillarContent:
    """Full repurposing pipeline: 1 pillar → 64+ pieces.

    Runs all 3 rounds of the Gary Vee reverse pyramid.
    Returns the pillar with all derived pieces attached.
    """
    logger.info(f"[REPURPOSE] Starting repurposing for pillar: {pillar.title}")

    # Round 1: Long-form distribution (~5 pieces)
    round_1 = generate_round_1_long_form(pillar)
    pillar.pieces.extend(round_1)
    logger.info(f"[REPURPOSE] Round 1: {len(round_1)} long-form pieces")

    # Round 2: Micro clips (~16-30 pieces)
    round_2 = generate_round_2_micro(pillar, num_clips=micro_clips)
    pillar.pieces.extend(round_2)
    logger.info(f"[REPURPOSE] Round 2: {len(round_2)} micro pieces")

    # Round 3: Micro-micro + statics (~55-78 pieces)
    round_3 = generate_round_3_micro_micro(pillar, num_video_clips=micro_micro_clips, num_statics=statics)
    pillar.pieces.extend(round_3)
    logger.info(f"[REPURPOSE] Round 3: {len(round_3)} micro-micro + static pieces")

    pillar.status = "repurposed"

    logger.info(
        f"[REPURPOSE] Complete: {pillar.total_pieces} total pieces | "
        f"By type: {pillar.pieces_by_type} | "
        f"By platform: {pillar.pieces_by_platform}"
    )

    return pillar


def get_pipeline_summary(pillar: PillarContent) -> str:
    """Human-readable summary of the repurposing pipeline."""
    lines = [
        f"# Pillar: {pillar.title}",
        f"Status: {pillar.status} | Total pieces: {pillar.total_pieces}",
        "",
        "## By Type:",
    ]
    for t, count in pillar.pieces_by_type.items():
        lines.append(f"  {t}: {count}")
    lines.append("")
    lines.append("## By Platform:")
    for p, count in pillar.pieces_by_platform.items():
        lines.append(f"  {p}: {count}")

    # Status breakdown
    status_counts = {}
    for piece in pillar.pieces:
        status_counts[piece.status] = status_counts.get(piece.status, 0) + 1
    lines.append("")
    lines.append("## By Status:")
    for s, count in status_counts.items():
        lines.append(f"  {s}: {count}")

    return "\n".join(lines)
