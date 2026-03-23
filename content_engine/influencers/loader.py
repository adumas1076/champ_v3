"""
Influencer Profile Loader
Loads influencer configs from YAML, validates clone readiness,
and provides profile data to the content pipeline.
"""

from pathlib import Path
from typing import Optional
import yaml


INFLUENCER_DIR = Path(__file__).parent


def load_influencer(influencer_id: str) -> dict:
    """Load a single influencer profile by ID."""
    for f in INFLUENCER_DIR.glob("*.yaml"):
        with open(f) as fh:
            profile = yaml.safe_load(fh)
        if profile and profile.get("id") == influencer_id:
            return profile
    raise ValueError(f"Influencer '{influencer_id}' not found")


def load_all_influencers() -> list[dict]:
    """Load all influencer profiles."""
    profiles = []
    for f in sorted(INFLUENCER_DIR.glob("*.yaml")):
        with open(f) as fh:
            profile = yaml.safe_load(fh)
        if profile and "id" in profile:
            profiles.append(profile)
    return profiles


def get_clone_status(influencer_id: str) -> dict:
    """Check clone readiness for an influencer."""
    profile = load_influencer(influencer_id)
    clone = profile.get("clone", {})
    face_status = clone.get("face", {}).get("status", "pending")
    voice_status = clone.get("voice", {}).get("status", "pending")
    return {
        "influencer_id": influencer_id,
        "face_ready": face_status == "trained",
        "face_status": face_status,
        "voice_ready": voice_status == "cloned",
        "voice_status": voice_status,
        "clone_ready": face_status == "trained" and voice_status == "cloned",
    }


def get_brand_voice(influencer_id: str) -> dict:
    """Get brand voice rules for content generation."""
    profile = load_influencer(influencer_id)
    return profile.get("brand_voice", {})


def get_platform_rules(influencer_id: str, platform: Optional[str] = None) -> dict:
    """Get platform-specific rules for an influencer."""
    profile = load_influencer(influencer_id)
    rules = profile.get("platform_rules", {})
    if platform:
        return rules.get(platform, {})
    return rules


def get_funnel_targets(influencer_id: str) -> dict:
    """Get content funnel distribution targets."""
    profile = load_influencer(influencer_id)
    return profile.get("funnel", {"top_of_funnel": 50, "middle_of_funnel": 30, "bottom_of_funnel": 20})
