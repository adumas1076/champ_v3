"""
CHAMP Avatar — Body Motion System

Extends the face-only avatar to include upper body, hands, and gestures.

Composite approach:
  1. FlashHead renders the face region (512x512)
  2. GesturePredictor maps audio prosody to gesture classes
  3. BodyCompositor merges face onto body template with gestures

This is the foundation — body templates and gesture prediction
are modular and can be upgraded independently.
"""
