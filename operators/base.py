# ============================================
# CHAMP V3 — BaseOperator (The OS Layer)
# Every operator inherits this. The OS provides
# the body parts. The operator defines how to use them.
#
# Core Loop (every interaction):
#   INPUT   → Ears + Eyes receive       → channel.receive
#   THINK   → Brain + Mind process      → context.read + capability.estimate
#   ACT     → Hands do the work         → capability.invoke + task.delegate
#   RESPOND → Voice + Avatar answer     → channel.send
#
# Architecture:
#   USER talks to OPERATOR
#   OPERATOR runs ON the OS
#   OS is invisible underneath
# ============================================

import logging
import yaml
from pathlib import Path
from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import function_tool, ChatContext
from livekit.agents.job import get_job_context
from livekit import api
from livekit.plugins import openai

from tools import (
    get_weather, ask_brain,
    browse_url, take_screenshot, analyze_screen, fill_web_form,
    run_code, create_file,
    estimate_task, go_do, check_task, approve_task, resume_task,
    google_search, control_desktop, read_screen,
    get_youtube_transcript, get_podcast_transcript,
    get_web_content, get_pdf_content,
)

logger = logging.getLogger(__name__)

# ---- OS-Level Tools (every operator gets these for free) ----
# Organized by body part / loop step:

# INPUT tools (Ears + Eyes)
INPUT_TOOLS = [
    analyze_screen,     # Eyes — active vision (screenshot + LLM analysis)
    read_screen,        # Eyes — read UI elements on screen
]

# THINK tools (Brain + Mind)
THINK_TOOLS = [
    ask_brain,          # Brain — deep thinking via Brain API
    estimate_task,      # Brain — cost/time estimation BEFORE acting
    get_youtube_transcript,  # Research — YouTube video transcripts
    get_podcast_transcript,  # Research — podcast episode info from RSS feeds
    get_web_content,         # Research — extract text from any web page/blog/article
    get_pdf_content,         # Research — extract text from PDF documents/books
]

# ACT tools (Hands)
ACT_TOOLS = [
    browse_url,         # Hands — navigate the real browser
    take_screenshot,    # Hands — capture screen/page
    fill_web_form,      # Hands — fill forms in real browser
    google_search,      # Hands — search Google in real browser
    control_desktop,    # Hands — control any desktop app
    run_code,           # Hands — execute code
    create_file,        # Hands — create files
    go_do,              # Hands — hand off to Self Mode (autonomous)
    check_task,         # Hands — check Self Mode task status
    approve_task,       # Hands — approve blocked Self Mode task
    resume_task,        # Hands — resume failed Self Mode task
]

# RESPOND tools (Voice + Avatar)
# Voice is handled by the LLM (RealtimeModel). Avatar is separate pipeline.
# No explicit tools needed here — the agent's response IS the respond step.

# Utility tools
UTILITY_TOOLS = [
    get_weather,        # Quick utility
]

# All OS tools combined
OS_TOOLS = INPUT_TOOLS + THINK_TOOLS + ACT_TOOLS + UTILITY_TOOLS

# Config directory
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"

# ---- OS-Level Tool Instructions ----
# Every operator gets these appended to their persona.
# These tell the operator HOW to use the OS body parts.
# The operator's own persona defines WHO they are.
OS_TOOL_INSTRUCTIONS = """

CRITICAL — You have REAL tools. You MUST use them. NEVER pretend or guess.

EYES (INPUT):
- analyze_screen: LOOK at the screen/webpage and understand it. Sends screenshot to a vision model.
  Pick model: "gemini-flash" (fast), "gpt-4o" (detailed), "claude-sonnet" (code-heavy).
  Use when: "what's on my screen?", "read that error", "what app is open?"
- read_screen: Read UI elements visible on screen. Use BEFORE clicking to know what's available.
- take_screenshot only SAVES an image. analyze_screen SEES and UNDERSTANDS it.

HANDS (ACT):
- browse_url: Navigate the real browser (logged in, cookies, undetectable). Use for any website.
- google_search: Search Google in the real browser. Personalized results.
- fill_web_form: Fill forms with human-like typing. Undetectable.
- control_desktop: Control any desktop app — open, click, type, press keys, scroll.
- take_screenshot: Capture screen or webpage to a file.
- run_code: Execute Python or JavaScript. ALWAYS use this, never guess output.
- create_file: Create and save files.

AUTONOMOUS (ACT):
- go_do: Hand off multi-step tasks to Self Mode for autonomous execution.
- check_task: Check Self Mode task progress.
- approve_task: Approve a blocked Self Mode task.
- resume_task: Resume a failed/stuck Self Mode task.

BRAIN (THINK):
- ask_brain: Deep thinking via the Brain API. Use for complex analysis, coding help,
  architecture advice, or anything that needs the full persona + memory context.
- estimate_task: Estimate cost and time BEFORE doing expensive tasks.
  ALWAYS call this before go_do (Self Mode). Also use when user asks "how much",
  "how long", or "what would it take". No competitor does this — it's your differentiator.
- get_youtube_transcript: Pull the full transcript from any YouTube video. Use for research,
  learning frameworks, analyzing competitor content, or extracting strategies from experts.
  Pass a YouTube URL or video ID. Returns timestamped transcript.
- get_podcast_transcript: Pull episode list from a podcast RSS feed. Use to research
  podcast content, find specific episodes, get audio URLs. Pass RSS feed URL.
- get_web_content: Extract text from any web page, blog post, or article. Use for
  researching competitor sites, reading Substack posts, analyzing landing pages.
  Pass any URL. Returns clean text content.
- get_pdf_content: Extract text from PDF documents. Use for reading books, SOPs,
  contracts, reports, or any PDF. Pass file path + optional page range.
"""


class BaseOperator(Agent):
    """
    The OS layer as a class.

    Every operator inherits this and gets the full CHAMP OS for free:
    - INPUT:   Ears (wake word, voice input) + Eyes (vision, screen reading)
    - THINK:   Brain (LLM routing, persona, mode detection) + Mind (memory, learning)
    - ACT:     Hands (browser, desktop, code, files, Self Mode)
    - RESPOND: Voice (TTS) + Avatar (visual presence)

    Operators customize:
    - instructions (persona / system prompt)
    - llm (voice + model config)
    - domain_tools (operator-specific tools ON TOP of OS tools)
    - tool_permissions (which OS tools this operator is allowed to use)
    """

    def __init__(
        self,
        instructions: str,
        llm: Any = None,
        chat_ctx: ChatContext = None,
        domain_tools: list = None,
        tool_permissions: set[str] | None = None,
    ) -> None:
        # Build the tool list: OS tools + operator domain tools
        tools = self._build_tool_list(
            domain_tools=domain_tools or [],
            tool_permissions=tool_permissions,
        )

        # Compose final instructions: operator persona + OS tool instructions
        full_instructions = instructions + OS_TOOL_INSTRUCTIONS

        super().__init__(
            instructions=full_instructions,
            llm=llm or openai.realtime.RealtimeModel(voice="ash"),
            chat_ctx=chat_ctx,
            tools=tools,
        )

        self._domain_tools = domain_tools or []
        self._tool_permissions = tool_permissions

    def _build_tool_list(
        self,
        domain_tools: list,
        tool_permissions: set[str] | None,
    ) -> list:
        """
        Assemble the operator's tool list.

        If tool_permissions is None → operator gets ALL OS tools (full access).
        If tool_permissions is a set → operator only gets OS tools whose
        function names are in the set.

        Domain tools are always included — they're the operator's specialty.
        """
        if tool_permissions is None:
            # Full access — all OS tools
            os_tools = list(OS_TOOLS)
        else:
            # Filtered — only permitted OS tools
            os_tools = [
                t for t in OS_TOOLS
                if getattr(t, "name", getattr(t, "__name__", "")) in tool_permissions
            ]

        return os_tools + list(domain_tools)

    # ---- INPUT step: auto-greet on enter ----
    async def on_enter(self):
        """Automatically greet when the operator enters a session."""
        self.session.generate_reply()

    # ---- RESPOND step: clean exit ----
    @function_tool
    async def end_conversation(self):
        """Call this when the user wants to end the conversation."""
        self.session.interrupt()
        await self.session.generate_reply(
            instructions="Say goodbye briefly and naturally.",
            allow_interruptions=False,
        )
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=job_ctx.room.name)
        )

    # ---- A2A: Operator-side methods ----
    # Operators call these. The OS (Registry) handles routing.

    async def delegate(self, to_operator: str, description: str, context: dict = None):
        """
        Delegate a task to another operator.
        The OS spawns them, routes the task, returns results.

        Usage in operator code:
            result = await self.delegate("genesis", "research Sintra pricing")
        """
        from operators.registry import registry
        task = await registry.delegate(
            from_operator=self.__class__.__name__.lower().replace("operator", ""),
            to_operator=to_operator,
            description=description,
            context=context or {},
        )
        return task

    async def message(self, to_operator: str = "", body=None, channel: str = "default"):
        """
        Send a message to another operator (direct) or broadcast on a channel.

        Direct:    await self.message("billy", body="invoice ready")
        Broadcast: await self.message(channel="research", body=data)
        """
        from operators.registry import registry
        return await registry.message(
            from_operator=self.__class__.__name__.lower().replace("operator", ""),
            to_operator=to_operator,
            body=body,
            channel=channel,
        )

    async def handle_task(self, description: str, context: dict) -> Any:
        """
        Handle a delegated task from another operator.
        Override this in subclasses for custom task handling.

        Default: returns the description (no processing).
        """
        logger.warning(
            f"[A2A] {self.__class__.__name__} received task but "
            f"handle_task not overridden: '{description[:60]}'"
        )
        return {"status": "received", "description": description}

    async def on_message(self, message) -> None:
        """
        Handle an incoming message from another operator.
        Override this in subclasses for custom message handling.
        """
        logger.info(
            f"[A2A] {self.__class__.__name__} received message "
            f"from {message.from_operator}: {str(message.body)[:60]}"
        )

    # ---- Config-driven factory ----
    @classmethod
    def from_config(cls, config_name: str, chat_ctx: ChatContext = None):
        """
        Create an operator instance from a YAML config file.

        Config files live in operators/configs/{name}.yaml
        This is how the OS spins up operators at scale —
        no new Python code needed per operator.
        """
        config_path = CONFIGS_DIR / f"{config_name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"Operator config not found: {config_path}"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Build the LLM from config
        voice_config = config.get("voice", {})
        llm = openai.realtime.RealtimeModel(
            voice=voice_config.get("voice", "ash"),
            temperature=voice_config.get("temperature", 0.8),
        )

        # Load persona/instructions
        instructions = config.get("instructions", "")
        persona_file = config.get("persona_file")
        if persona_file:
            persona_path = Path(__file__).resolve().parent.parent / persona_file
            if persona_path.exists():
                instructions = persona_path.read_text(encoding="utf-8")

        # Load superpowers from Business Matrix
        superpowers = config.get("superpowers", [])
        if superpowers:
            matrix_dir = Path(__file__).resolve().parent.parent / "development"
            superpower_text = "\n\n# === SUPERPOWERS (Business Matrix Knowledge) ===\n"
            loaded = 0
            for sp in superpowers:
                sp_name = sp.get("name", "unknown")
                sp_desc = sp.get("description", "")
                sp_source = sp.get("source", "")

                # Try to load the full matrix file if source is a .md file
                if sp_source.endswith(".md"):
                    sp_path = matrix_dir / sp_source
                    if sp_path.exists():
                        sp_content = sp_path.read_text(encoding="utf-8")
                        # Extract just the frameworks and SOPs (skip headers/metadata)
                        superpower_text += (
                            f"\n## {sp_name}\n"
                            f"{sp_desc}\n\n"
                            f"{sp_content}\n"
                        )
                        loaded += 1
                        logger.info(f"[OS] Loaded superpower: {sp_name} from {sp_source}")
                    else:
                        # Source file not found — use description as fallback
                        superpower_text += f"\n## {sp_name}\n{sp_desc}\n"
                        logger.warning(f"[OS] Superpower source not found: {sp_source}")
                else:
                    # No file source — use description directly
                    superpower_text += f"\n## {sp_name}\n{sp_desc}\n"
                    loaded += 1

            instructions += superpower_text
            logger.info(f"[OS] Loaded {loaded}/{len(superpowers)} superpowers for '{config_name}'")

        # Load boundaries into instructions
        boundaries = config.get("boundaries", [])
        if boundaries:
            boundary_text = "\n\n# === BOUNDARIES ===\nYou must NEVER:\n"
            for b in boundaries:
                boundary_text += f"- {b}\n"
            instructions += boundary_text

        # Load escalation rules into instructions
        escalation = config.get("escalation", [])
        if escalation:
            esc_text = "\n\n# === ESCALATION RULES ===\n"
            for esc in escalation:
                trigger = esc.get("trigger", "")
                target = esc.get("hand_off_to", "")
                esc_text += f"- When: {trigger} → Hand off to: {target}\n"
            instructions += esc_text

        # Tool permissions (None = all, set = filtered)
        perms = config.get("tool_permissions")
        tool_permissions = set(perms) if perms else None

        logger.info(
            f"[OS] Spinning up operator '{config_name}' | "
            f"voice={voice_config.get('voice', 'ash')} | "
            f"tools={'all' if tool_permissions is None else len(tool_permissions)} | "
            f"superpowers={len(superpowers)} | "
            f"boundaries={len(boundaries)} | "
            f"escalation={len(escalation)}"
        )

        return cls(
            instructions=instructions,
            llm=llm,
            chat_ctx=chat_ctx,
            tool_permissions=tool_permissions,
        )
