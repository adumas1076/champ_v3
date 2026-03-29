"""
CHAMP Avatar Studio — Video Templates

Pre-built video configurations for common use cases.
Templates define: script structure, render settings, voice config, and metadata.

Templates are JSON configs, not code — users can create their own.

Built-in templates:
  - product_demo: Product walkthrough with intro/outro
  - sales_pitch: Persuasive sales video
  - explainer: Educational/how-to video
  - social_clip: Short-form social media content
  - greeting: Personal greeting/welcome video
  - testimonial: Customer testimonial style
  - announcement: Company/product announcement

Usage:
    template = get_template("product_demo")
    job = template.create_render_job(
        script="Our new product does X, Y, Z...",
        avatar_id="anthony",
    )
    result = await job.run()
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .render_job import RenderJob, RenderConfig, VoiceInterface

logger = logging.getLogger("champ.avatar.studio.templates")


@dataclass
class VideoTemplate:
    """A pre-configured video template."""
    template_id: str
    name: str
    description: str
    category: str                                # "marketing", "sales", "social", "internal"

    # Script structure
    max_duration_sec: float = 120.0              # Maximum video duration
    suggested_word_count: tuple = (50, 300)      # (min, max) words

    # Render settings
    render_config: dict = field(default_factory=dict)

    # Voice defaults
    voice_config: dict = field(default_factory=lambda: {
        "speed": 1.0,
        "pitch": 1.0,
        "style": "professional",
    })

    # Metadata
    tags: list = field(default_factory=list)

    def create_render_job(
        self,
        script: str,
        avatar_id: str,
        voice: Optional[VoiceInterface] = None,
        output_dir: Optional[str] = None,
        **overrides,
    ) -> RenderJob:
        """Create a RenderJob from this template."""
        # Merge template config with overrides
        rc = RenderConfig(**{**self.render_config, **overrides})
        vc = {**self.voice_config}

        return RenderJob(
            script=script,
            avatar_id=avatar_id,
            voice=voice,
            voice_config=vc,
            render_config=rc,
            output_dir=output_dir,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VideoTemplate":
        return cls(**data)


# ── Built-in Templates ──────────────────────────────────────────────────────

BUILTIN_TEMPLATES = {
    "product_demo": VideoTemplate(
        template_id="product_demo",
        name="Product Demo",
        description="Walk through your product's features with a professional presenter",
        category="marketing",
        max_duration_sec=180,
        suggested_word_count=(100, 400),
        render_config={"upscale": True, "upscale_factor": 2, "crf": 16},
        voice_config={"speed": 0.95, "style": "professional", "energy": "medium"},
        tags=["product", "demo", "features", "walkthrough"],
    ),
    "sales_pitch": VideoTemplate(
        template_id="sales_pitch",
        name="Sales Pitch",
        description="Persuasive video for prospects — energetic and confident delivery",
        category="sales",
        max_duration_sec=90,
        suggested_word_count=(50, 200),
        render_config={"upscale": True, "upscale_factor": 2, "crf": 18},
        voice_config={"speed": 1.05, "style": "persuasive", "energy": "high"},
        tags=["sales", "pitch", "persuasion", "outreach"],
    ),
    "explainer": VideoTemplate(
        template_id="explainer",
        name="Explainer",
        description="Educational content — clear, methodical, easy to follow",
        category="marketing",
        max_duration_sec=300,
        suggested_word_count=(150, 600),
        render_config={"upscale": False, "crf": 20},
        voice_config={"speed": 0.9, "style": "educational", "energy": "calm"},
        tags=["education", "tutorial", "how-to", "explainer"],
    ),
    "social_clip": VideoTemplate(
        template_id="social_clip",
        name="Social Media Clip",
        description="Short, punchy content for social media — under 60 seconds",
        category="social",
        max_duration_sec=60,
        suggested_word_count=(20, 120),
        render_config={"upscale": True, "upscale_factor": 2, "crf": 18},
        voice_config={"speed": 1.1, "style": "energetic", "energy": "high"},
        tags=["social", "short-form", "tiktok", "reels", "shorts"],
    ),
    "greeting": VideoTemplate(
        template_id="greeting",
        name="Personal Greeting",
        description="Warm, personal welcome or thank-you video",
        category="internal",
        max_duration_sec=45,
        suggested_word_count=(20, 80),
        render_config={"upscale": False, "crf": 20},
        voice_config={"speed": 0.95, "style": "warm", "energy": "medium"},
        tags=["greeting", "welcome", "thank-you", "personal"],
    ),
    "testimonial": VideoTemplate(
        template_id="testimonial",
        name="Testimonial",
        description="Customer testimonial style — authentic and conversational",
        category="marketing",
        max_duration_sec=120,
        suggested_word_count=(50, 250),
        render_config={"upscale": True, "upscale_factor": 2, "crf": 18},
        voice_config={"speed": 0.95, "style": "conversational", "energy": "medium"},
        tags=["testimonial", "review", "case-study"],
    ),
    "announcement": VideoTemplate(
        template_id="announcement",
        name="Announcement",
        description="Company or product announcement — clear and authoritative",
        category="internal",
        max_duration_sec=90,
        suggested_word_count=(50, 200),
        render_config={"upscale": True, "upscale_factor": 2, "crf": 16},
        voice_config={"speed": 1.0, "style": "authoritative", "energy": "medium"},
        tags=["announcement", "news", "update", "launch"],
    ),
}


# ── Template API ─────────────────────────────────────────────────────────────

def get_template(template_id: str) -> VideoTemplate:
    """Get a built-in template by ID."""
    if template_id not in BUILTIN_TEMPLATES:
        available = ", ".join(BUILTIN_TEMPLATES.keys())
        raise ValueError(f"Template '{template_id}' not found. Available: {available}")
    return BUILTIN_TEMPLATES[template_id]


def list_templates(category: Optional[str] = None) -> list[VideoTemplate]:
    """List all available templates, optionally filtered by category."""
    templates = list(BUILTIN_TEMPLATES.values())
    if category:
        templates = [t for t in templates if t.category == category]
    return templates


def load_custom_template(path: str) -> VideoTemplate:
    """Load a custom template from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return VideoTemplate.from_dict(data)


def save_custom_template(template: VideoTemplate, path: str):
    """Save a template to a JSON file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(template.to_dict(), f, indent=2)
