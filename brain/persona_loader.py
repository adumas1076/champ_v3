# ============================================
# CHAMP V3 — Persona V1.6.1 Loader
# Loads Champ's persona and injects as system
# prompt into every LiteLLM request.
# ============================================
# "Built to build. Born to create."

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
    Loads the Champ persona from disk and serves it as the system prompt.

    Features:
    - Loads from persona directory on startup
    - Falls back to hardcoded persona if file missing
    - Hot-reload without restart via reload()
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._persona_text: str = ""
        self._persona_path: Path | None = None

    async def load(self) -> None:
        """Load persona from file on startup."""
        persona_dir = self.settings.persona_dir
        persona_file = persona_dir / self.settings.default_persona

        if persona_file.exists():
            self._persona_path = persona_file
            self._persona_text = persona_file.read_text(encoding="utf-8")
            logger.info(
                f"Persona loaded: {persona_file.name} "
                f"({len(self._persona_text)} chars)"
            )
        else:
            self._persona_text = FALLBACK_PERSONA
            logger.warning(
                f"Persona file not found at {persona_file}, "
                f"using fallback persona"
            )

    def get_persona(self) -> str:
        """Return the current persona text."""
        return self._persona_text

    async def reload(self) -> None:
        """Hot-reload persona from disk without restart."""
        await self.load()
        logger.info("Persona reloaded")