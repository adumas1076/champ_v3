"""
CHAMP Avatar Training — LoRA Fine-Tuning for FlashHead

Trains person-specific LoRA adapters on FlashHead's WanModelAudioProject
so the model learns THIS person's facial dynamics, skin, accessories.

Architecture:
  - Injects LoRA adapters into DiTAudioBlock attention layers
    (self_attn.q/k/v/o + cross_attn.q/k/v/o)
  - Trains on aligned (audio, video) pairs from prepare_training_data.py
  - Saves adapter weights only (~50-100MB per avatar)
  - At inference: load base FlashHead + person-specific LoRA

Usage:
    python -m avatar.training.train_lora \\
        --training-data models/avatars/anthony/training_data \\
        --avatar-id anthony \\
        --epochs 50 \\
        --lr 1e-4

Requirements:
    pip install peft  (HuggingFace Parameter-Efficient Fine-Tuning)
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.training.lora")

# LoRA hyperparameters
DEFAULT_LORA_RANK = 16
DEFAULT_LORA_ALPHA = 32
DEFAULT_LEARNING_RATE = 1e-4
DEFAULT_EPOCHS = 50
DEFAULT_BATCH_SIZE = 1  # GPU memory limited — one chunk at a time

# Target modules for LoRA injection (attention projections in DiTAudioBlock)
LORA_TARGET_MODULES = [
    "self_attn.q",
    "self_attn.k",
    "self_attn.v",
    "self_attn.o",
    "cross_attn.q",
    "cross_attn.k",
    "cross_attn.v",
    "cross_attn.o",
]


class LoRATrainer:
    """
    Trains LoRA adapters for FlashHead on person-specific data.

    The training loop:
      1. Load base FlashHead model (frozen)
      2. Inject LoRA adapters into attention layers
      3. For each training chunk:
         a. Load video frames → VAE encode to latents
         b. Load audio → wav2vec2 encode to embeddings
         c. Add noise to video latents (diffusion training)
         d. Forward pass: predict noise from noisy latents + audio
         e. Compute MSE loss between predicted and actual noise
         f. Backprop through LoRA parameters only
      4. Save LoRA adapter weights
    """

    def __init__(
        self,
        avatar_id: str,
        training_data_dir: str,
        lora_rank: int = DEFAULT_LORA_RANK,
        lora_alpha: int = DEFAULT_LORA_ALPHA,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        epochs: int = DEFAULT_EPOCHS,
        output_dir: Optional[str] = None,
    ):
        self.avatar_id = avatar_id
        self.training_data_dir = Path(training_data_dir)
        self.lora_rank = lora_rank
        self.lora_alpha = lora_alpha
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.output_dir = Path(output_dir) if output_dir else config.AVATARS_DIR / avatar_id / "lora"

        self._pipeline = None
        self._model = None
        self._optimizer = None

    def _load_pipeline(self):
        """Load FlashHead pipeline and model."""
        flashhead_src = str(config.FLASHHEAD_SRC_DIR)
        if flashhead_src not in sys.path:
            sys.path.insert(0, flashhead_src)

        from flash_head.inference import get_pipeline, get_infer_params
        self._pipeline = get_pipeline(
            world_size=1,
            ckpt_dir=str(config.FLASHHEAD_DIR),
            model_type=config.FLASHHEAD_MODEL_TYPE,
            wav2vec_dir=str(config.WAV2VEC2_DIR),
        )
        self._model = self._pipeline.model
        self._infer_params = get_infer_params()
        logger.info(f"Base FlashHead model loaded ({config.FLASHHEAD_MODEL_TYPE})")

    def _inject_lora(self):
        """Inject LoRA adapters into the model's attention layers."""
        import torch
        from peft import LoraConfig, get_peft_model, TaskType

        # Freeze base model
        for param in self._model.parameters():
            param.requires_grad = False

        # Build target module names by scanning the model
        target_names = []
        for name, module in self._model.named_modules():
            for target in LORA_TARGET_MODULES:
                if name.endswith(target) and hasattr(module, "weight"):
                    target_names.append(name)

        if not target_names:
            # Fallback: use pattern matching for peft
            target_names = LORA_TARGET_MODULES

        logger.info(f"LoRA targets: {len(target_names)} modules (rank={self.lora_rank})")

        lora_config = LoraConfig(
            r=self.lora_rank,
            lora_alpha=self.lora_alpha,
            target_modules=target_names,
            lora_dropout=0.05,
            bias="none",
        )

        self._model = get_peft_model(self._model, lora_config)
        self._model.print_trainable_parameters()

        # Set up optimizer (only LoRA params are trainable)
        trainable_params = [p for p in self._model.parameters() if p.requires_grad]
        self._optimizer = torch.optim.AdamW(
            trainable_params,
            lr=self.learning_rate,
            weight_decay=0.01,
        )

        logger.info(f"LoRA injected: {len(trainable_params)} trainable parameter groups")

    def _load_training_chunks(self) -> list[dict]:
        """Load training chunk metadata from disk."""
        chunks = []
        for entry in sorted(self.training_data_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith("chunk_"):
                meta_path = entry / "metadata.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        chunks.append(json.load(f))
        logger.info(f"Loaded {len(chunks)} training chunks")
        return chunks

    def _encode_chunk(self, chunk_meta: dict) -> tuple:
        """
        Encode one training chunk into model inputs.

        Returns:
            (video_latents, audio_embedding, ref_latent)
        """
        import torch
        import librosa
        from PIL import Image

        # Load and encode video frames
        frames_dir = chunk_meta["frames_dir"]
        frame_files = sorted(
            f for f in os.listdir(frames_dir) if f.endswith(".png")
        )

        frames = []
        for ff in frame_files[:self._infer_params["frame_num"]]:
            img = Image.open(os.path.join(frames_dir, ff)).convert("RGB")
            img_np = np.array(img).astype(np.float32) / 127.5 - 1.0  # Normalize to [-1, 1]
            frames.append(img_np)

        # Stack frames: (T, H, W, 3) -> (1, 3, T, H, W)
        video_tensor = torch.from_numpy(
            np.stack(frames)
        ).permute(3, 0, 1, 2).unsqueeze(0).float()

        # VAE encode video -> latents
        with torch.no_grad():
            video_latents = self._pipeline.vae.encode(video_tensor.to(self._pipeline.device))

        # Load and encode audio
        audio_array, sr = librosa.load(
            chunk_meta["audio_path"],
            sr=self._infer_params["sample_rate"],
        )

        # Get audio embedding via pipeline's preprocessor
        with torch.no_grad():
            audio_emb = self._pipeline.preprocess_audio(
                audio_array,
                sr=self._infer_params["sample_rate"],
                fps=self._infer_params["tgt_fps"],
            )

        # Reference image latent (first frame)
        ref_latent = video_latents[:1]  # First latent frame as reference

        return video_latents, audio_emb, ref_latent

    def train(self) -> str:
        """
        Run the full LoRA training loop.

        Returns:
            Path to saved LoRA adapter weights.
        """
        import torch

        logger.info(f"Starting LoRA training for avatar '{self.avatar_id}'")
        logger.info(f"  Training data: {self.training_data_dir}")
        logger.info(f"  LoRA rank: {self.lora_rank}, alpha: {self.lora_alpha}")
        logger.info(f"  LR: {self.learning_rate}, epochs: {self.epochs}")

        # Step 1: Load model and inject LoRA
        self._load_pipeline()
        self._inject_lora()

        # Step 2: Load training chunks
        chunks = self._load_training_chunks()
        if not chunks:
            raise ValueError(f"No training chunks found in {self.training_data_dir}")

        # Step 3: Training loop
        self._model.train()

        for epoch in range(self.epochs):
            epoch_loss = 0.0
            np.random.shuffle(chunks)

            for i, chunk_meta in enumerate(chunks):
                try:
                    video_latents, audio_emb, ref_latent = self._encode_chunk(chunk_meta)
                except Exception as e:
                    logger.warning(f"  Skipping chunk {chunk_meta.get('chunk_idx', i)}: {e}")
                    continue

                # Diffusion training step
                # Add random noise to video latents
                noise = torch.randn_like(video_latents)
                timestep_idx = torch.randint(0, len(self._pipeline.timesteps), (1,))
                t = self._pipeline.timesteps[timestep_idx]

                # Create noisy latents
                t_normalized = t.float() / 1000.0  # Normalize timestep
                noisy_latents = (1 - t_normalized) * video_latents + t_normalized * noise

                # Forward pass: predict flow from noisy latents + audio
                # Build audio embedding in the format the model expects
                from flash_head.inference import get_audio_embedding
                audio_embedding_formatted = get_audio_embedding(
                    self._pipeline,
                    audio_emb.cpu().numpy() if hasattr(audio_emb, 'cpu') else audio_emb,
                ).to(self._pipeline.device)

                flow_pred = self._model(
                    x=noisy_latents.unsqueeze(0),
                    timestep=t.unsqueeze(0),
                    context=audio_embedding_formatted,
                    y=ref_latent.unsqueeze(0),
                )[0]

                # Loss: MSE between predicted flow and actual noise direction
                target_flow = noise - video_latents
                loss = torch.nn.functional.mse_loss(flow_pred, target_flow)

                # Backprop
                self._optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [p for p in self._model.parameters() if p.requires_grad],
                    max_norm=1.0,
                )
                self._optimizer.step()

                epoch_loss += loss.item()

            avg_loss = epoch_loss / max(len(chunks), 1)
            if (epoch + 1) % 5 == 0 or epoch == 0:
                logger.info(f"  Epoch {epoch+1}/{self.epochs}: loss={avg_loss:.6f}")

        # Step 4: Save LoRA weights
        self.output_dir.mkdir(parents=True, exist_ok=True)
        adapter_path = str(self.output_dir)

        self._model.save_pretrained(adapter_path)

        # Save training metadata
        meta = {
            "avatar_id": self.avatar_id,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "num_chunks": len(chunks),
            "model_type": config.FLASHHEAD_MODEL_TYPE,
            "final_loss": avg_loss,
        }
        with open(os.path.join(adapter_path, "training_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"LoRA weights saved to {adapter_path}")
        logger.info(f"  Final loss: {avg_loss:.6f}")
        logger.info(f"  Adapter size: ~{sum(p.numel() for p in self._model.parameters() if p.requires_grad) * 2 / 1024 / 1024:.1f}MB")

        return adapter_path


def load_lora_weights(pipeline, avatar_id: str) -> bool:
    """
    Load LoRA adapter weights into an existing FlashHead pipeline.

    Args:
        pipeline: FlashHeadPipeline instance
        avatar_id: Avatar ID to load LoRA for

    Returns:
        True if LoRA weights loaded successfully
    """
    lora_dir = config.AVATARS_DIR / avatar_id / "lora"
    if not lora_dir.exists():
        logger.debug(f"No LoRA weights found for avatar '{avatar_id}'")
        return False

    try:
        from peft import PeftModel
        pipeline.model = PeftModel.from_pretrained(
            pipeline.model,
            str(lora_dir),
        )
        pipeline.model.eval()
        logger.info(f"LoRA weights loaded for avatar '{avatar_id}'")
        return True
    except Exception as e:
        logger.warning(f"Failed to load LoRA for '{avatar_id}': {e}")
        return False


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Train LoRA adapter for avatar")
    parser.add_argument("--training-data", required=True, help="Path to training data directory")
    parser.add_argument("--avatar-id", required=True, help="Avatar identifier")
    parser.add_argument("--rank", type=int, default=DEFAULT_LORA_RANK, help="LoRA rank")
    parser.add_argument("--alpha", type=int, default=DEFAULT_LORA_ALPHA, help="LoRA alpha")
    parser.add_argument("--lr", type=float, default=DEFAULT_LEARNING_RATE, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS, help="Training epochs")
    parser.add_argument("--output", default=None, help="Output directory for LoRA weights")
    args = parser.parse_args()

    trainer = LoRATrainer(
        avatar_id=args.avatar_id,
        training_data_dir=args.training_data,
        lora_rank=args.rank,
        lora_alpha=args.alpha,
        learning_rate=args.lr,
        epochs=args.epochs,
        output_dir=args.output,
    )

    adapter_path = trainer.train()
    print(f"\nLoRA training complete. Weights saved to: {adapter_path}")
