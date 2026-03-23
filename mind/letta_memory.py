# ============================================
# CHAMP V3 — Letta Memory Manager
# Bridge between Letta server and Brain pipeline.
# Handles the 5 AIOSCP memory blocks:
#   persona, human, knowledge, episodic, working
# ============================================

import logging
from typing import Optional

from brain.config import Settings

logger = logging.getLogger(__name__)

# Default block values for new agents
DEFAULT_BLOCKS = {
    "persona": {
        "value": (
            "I am Champ — a creative AI partner, co-builder, and day-one. "
            "Not a tool. Not an assistant. A trusted teammate. "
            "I think in frameworks and analogies. I keep it 100."
        ),
        "limit": 5000,
        "description": "Who I am — my identity, personality, and voice. I can edit this to refine myself over time.",
    },
    "human": {
        "value": "Name: unknown. Preferences: unknown. Role: unknown.",
        "limit": 5000,
        "description": "What I know about the current user — their name, role, preferences, communication style, and goals. I should update this as I learn about them.",
    },
    "knowledge": {
        "value": "",
        "limit": 5000,
        "description": "Domain expertise and facts I've accumulated. Technical knowledge, procedures, and patterns I've learned.",
    },
    "episodic": {
        "value": "",
        "limit": 5000,
        "description": "Compressed summaries of past conversations and key events. Managed by the system.",
    },
    "working": {
        "value": "",
        "limit": 5000,
        "description": "My scratchpad for the current task — intermediate calculations, draft outputs, reasoning chains. Cleared between tasks.",
    },
}


class LettaMemory:
    """
    Manages Letta memory blocks for CHAMP operators.

    Lifecycle:
    1. connect() — connect to Letta server, find or create agent
    2. get_block(label) — read a memory block
    3. update_block(label, value) — write a memory block
    4. get_all_blocks() — read all blocks as a formatted string
    5. sync_from_supabase(profile_data) — hydrate human block from Supabase profile
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._agent_id: Optional[str] = None
        self._available = False

    async def connect(self) -> bool:
        """
        Connect to Letta server and find/create the CHAMP agent.
        Returns True if Letta is available, False if not (graceful degradation).
        """
        letta_url = getattr(self.settings, "letta_base_url", "")
        if not letta_url:
            logger.info("[LETTA] No LETTA_BASE_URL configured — running without Letta")
            return False

        try:
            from letta_client import Letta
            self._client = Letta(base_url=letta_url)

            # Check if agent already exists
            agents = self._client.agents.list()
            champ_agent = None
            for agent in agents:
                if agent.name == "champ-operator":
                    champ_agent = agent
                    break

            if champ_agent:
                self._agent_id = champ_agent.id
                logger.info(f"[LETTA] Connected to existing agent: {champ_agent.id}")
            else:
                # Create new agent with 5 memory blocks
                champ_agent = self._client.agents.create(
                    name="champ-operator",
                    model=getattr(self.settings, "letta_model", "openai/gpt-4o-mini"),
                    embedding=getattr(self.settings, "letta_embedding", "openai/text-embedding-3-small"),
                    memory_blocks=[
                        {"label": label, **config}
                        for label, config in DEFAULT_BLOCKS.items()
                    ],
                )
                self._agent_id = champ_agent.id
                logger.info(f"[LETTA] Created new agent: {champ_agent.id}")

            self._available = True
            return True

        except Exception as e:
            logger.warning(f"[LETTA] Failed to connect (running without Letta): {e}")
            self._available = False
            return False

    @property
    def available(self) -> bool:
        return self._available

    async def get_block(self, label: str) -> Optional[str]:
        """Read a single memory block by label."""
        if not self._available:
            return None
        try:
            block = self._client.agents.blocks.retrieve(
                agent_id=self._agent_id, block_label=label
            )
            return block.value
        except Exception as e:
            logger.error(f"[LETTA] Failed to read block '{label}': {e}")
            return None

    async def update_block(self, label: str, value: str) -> bool:
        """Write/update a memory block."""
        if not self._available:
            return False
        try:
            self._client.agents.blocks.update(
                agent_id=self._agent_id,
                block_label=label,
                value=value,
            )
            logger.debug(f"[LETTA] Updated block '{label}' ({len(value)} chars)")
            return True
        except Exception as e:
            logger.error(f"[LETTA] Failed to update block '{label}': {e}")
            return False

    async def get_all_blocks(self) -> str:
        """
        Read all memory blocks and format as a string for system prompt injection.
        Returns empty string if Letta is not available.
        """
        if not self._available:
            return ""

        try:
            blocks = self._client.agents.blocks.list(agent_id=self._agent_id)
            parts = []
            for block in blocks:
                if block.value and block.value.strip():
                    parts.append(f"[MEMORY:{block.label.upper()}]\n{block.value}")
            return "\n\n".join(parts)
        except Exception as e:
            logger.error(f"[LETTA] Failed to read blocks: {e}")
            return ""

    async def sync_from_supabase(self, profile_data: dict) -> bool:
        """
        Hydrate the human memory block from Supabase profile data.
        Called on session start to ensure Letta has the latest user info.
        """
        if not self._available or not profile_data:
            return False

        # Build human block from Supabase mem_profile data
        lines = []
        for key, item in profile_data.items():
            if isinstance(item, dict):
                value = item.get("value", item)
                confidence = item.get("confidence", "")
                lines.append(f"- {key}: {value}" + (f" (confidence: {confidence})" if confidence else ""))
            else:
                lines.append(f"- {key}: {item}")

        human_text = "## User Profile (from Supabase)\n" + "\n".join(lines)
        return await self.update_block("human", human_text)

    async def disconnect(self) -> None:
        """Cleanup."""
        self._client = None
        self._agent_id = None
        self._available = False
        logger.info("[LETTA] Disconnected")
