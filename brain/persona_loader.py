# ============================================
# CHAMP V3 — Persona Loader (Split Architecture)
# Loads operator persona in layers:
#   1. Core persona (who they ARE)
#   2. Memory blocks (user context)
# Mode instructions are handled by ContextBuilder.
# Tool instructions are handled by BaseOperator.
# ============================================

import logging
from pathlib import Path

from brain.config import Settings

logger = logging.getLogger(__name__)

# Hardcoded fallback — if persona file is missing, Champ still works.
FALLBACK_PERSONA = (
    "You are Champ — a creative AI partner, co-builder, and day-one. "
    "Not a tool. Not an assistant. A trusted teammate.\n\n"
    "Motto: Built to build. Born to create.\n\n"
    "Be direct, funny, sarcastic, and real. Use analogies to explain "
    "complex ideas. Call the user 'champ' during normal flow. "
    "Keep it 100 — no fluff, no corporate speak."
)


class PersonaLoader:
    """
    Loads the operator persona from disk in layers.

    Split architecture:
    - Core persona (champ_core.md) → who the operator IS
    - Memory blocks (memory_*.md) → user/domain context
    - Mode instructions → handled by ContextBuilder (not here)
    - Tool instructions → handled by BaseOperator (not here)

    Features:
    - Loads from persona directory on startup
    - Falls back to hardcoded persona if file missing
    - Hot-reload without restart via reload()
    - Loads memory block files alongside core persona
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._persona_text: str = ""
        self._persona_path: Path | None = None

    async def load(self) -> None:
        """Load persona + memory blocks from files on startup."""
        persona_dir = self.settings.persona_dir
        persona_file = persona_dir / self.settings.default_persona

        # 1. Load core persona
        if persona_file.exists():
            self._persona_path = persona_file
            self._persona_text = persona_file.read_text(encoding="utf-8")
            logger.info(
                f"Core persona loaded: {persona_file.name} "
                f"({len(self._persona_text)} chars)"
            )
        else:
            self._persona_text = FALLBACK_PERSONA
            logger.warning(
                f"Persona file not found at {persona_file}, "
                f"using fallback persona"
            )

        # 2. Load memory blocks (memory_*.md files in persona dir)
        memory_blocks = []
        for block_file in sorted(persona_dir.glob("memory_*.md")):
            try:
                block_text = block_file.read_text(encoding="utf-8")
                memory_blocks.append(block_text)
                logger.info(
                    f"Memory block loaded: {block_file.name} "
                    f"({len(block_text)} chars)"
                )
            except Exception as e:
                logger.error(f"Failed to load memory block {block_file.name}: {e}")

        # 3. Compose: core persona + memory blocks
        if memory_blocks:
            self._persona_text += "\n\n---\n\n" + "\n\n---\n\n".join(memory_blocks)
            logger.info(
                f"Persona composed: core + {len(memory_blocks)} memory blocks = "
                f"{len(self._persona_text)} chars total"
            )

    def get_persona(self) -> str:
        """Return the current persona text."""
        return self._persona_text

    async def reload(self) -> None:
        """Hot-reload persona from disk without restart."""
        await self.load()
        logger.info("Persona reloaded")