# ============================================
# CHAMP V3 — Mode Detector Unit Tests
# Run: python -m pytest tests/test_mode_detector.py -v
# ============================================

import sys
from pathlib import Path

# Add parent dir so brain module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.mode_detector import ModeDetector
from brain.models import OutputMode


detector = ModeDetector()


# --- VIBE MODE ---
def test_vibe_explicit_quick():
    assert detector.detect("Quick question about APIs") == OutputMode.VIBE

def test_vibe_explicit_thoughts():
    assert detector.detect("What you think about this idea?") == OutputMode.VIBE

def test_vibe_explicit_yes_or_no():
    assert detector.detect("Yes or no, should we use Redis?") == OutputMode.VIBE

def test_vibe_default_casual():
    assert detector.detect("Hey what's good") == OutputMode.VIBE

def test_vibe_default_empty():
    assert detector.detect("") == OutputMode.VIBE


# --- BUILD MODE ---
def test_build_explicit_lets_build():
    assert detector.detect("Let's build a voice agent") == OutputMode.BUILD

def test_build_explicit_step_by_step():
    assert detector.detect("Walk me through the deployment step by step") == OutputMode.BUILD

def test_build_explicit_help_me_build():
    assert detector.detect("Help me build a landing page") == OutputMode.BUILD

def test_build_explicit_lets_make():
    assert detector.detect("Let's make a new API endpoint") == OutputMode.BUILD

def test_build_inferred_how_do_we():
    assert detector.detect("How do we set up the database?") == OutputMode.BUILD

def test_build_inferred_architecture():
    assert detector.detect("I need to architect the backend") == OutputMode.BUILD


# --- SPEC MODE ---
def test_spec_explicit_give_me_the_code():
    assert detector.detect("Give me the code for the auth middleware") == OutputMode.SPEC

def test_spec_explicit_ship_it():
    assert detector.detect("This looks good, ship it") == OutputMode.SPEC

def test_spec_explicit_json():
    assert detector.detect("I need the JSON schema for the API") == OutputMode.SPEC

def test_spec_explicit_template():
    assert detector.detect("Give me a template for the email") == OutputMode.SPEC

def test_spec_explicit_i_need_exact():
    assert detector.detect("I need exact specifications for the API") == OutputMode.SPEC

def test_spec_explicit_specific():
    assert detector.detect("Be specific about the implementation") == OutputMode.SPEC

def test_spec_inferred_write_code():
    assert detector.detect("Write me a Python function for parsing CSV") == OutputMode.SPEC


# --- PRIORITY: SPEC > BUILD > VIBE ---
def test_priority_spec_over_build():
    # "give me the code" is SPEC — SPEC wins over BUILD
    assert detector.detect("Give me the code, let's build it") == OutputMode.SPEC

def test_priority_build_over_vibe():
    # "step by step" is BUILD — BUILD wins over VIBE's "quick"
    assert detector.detect("Walk me through this step by step, quick overview first") == OutputMode.BUILD


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])