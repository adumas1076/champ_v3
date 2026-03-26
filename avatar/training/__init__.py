"""
CHAMP Avatar Training — 2-Minute Video Reference Pipeline

Processes user-uploaded video into avatar reference data:
  1. extract_keyframes — video → diverse keyframes (face detection + pose clustering)
  2. avatar_registry — manages stored avatars (metadata, paths, loading)

Future:
  3. prepare_training_data — audio+video alignment for LoRA fine-tuning
  4. train_lora — person-specific LoRA weights for FlashHead
"""
