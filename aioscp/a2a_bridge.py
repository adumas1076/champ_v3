# ============================================
# AIOSCP ↔ A2A Bridge
#
# Generates A2A Agent Cards from AIOSCP
# OperatorManifests so external systems can
# discover and interact with our operators.
#
# A2A spec: https://a2a-protocol.org
# Agent Card path: /.well-known/agent-card.json
# ============================================

import json
import logging
from typing import Optional

from aioscp.types import OperatorManifest, Capability

logger = logging.getLogger("aioscp.a2a")


def capability_to_skill(cap: Capability, operator_id: str) -> dict:
    """Convert an AIOSCP Capability to an A2A AgentSkill."""
    return {
        "id": f"{operator_id}.{cap.id}",
        "name": cap.name,
        "description": cap.description,
        "inputModes": ["text"],
        "outputModes": ["text"],
        "examples": [],
        "tags": cap.metadata.side_effects if cap.metadata.side_effects else [],
    }


def manifest_to_agent_card(
    manifest: OperatorManifest,
    base_url: str = "https://api.cocreatiq.com",
    provider_name: str = "Cocreatiq",
    provider_url: str = "https://cocreatiq.com",
    version: str = "1.0.0",
) -> dict:
    """
    Convert an AIOSCP OperatorManifest to an A2A Agent Card.

    The Agent Card is a JSON document that external systems use to
    discover what this operator can do and how to talk to it.

    Follows the A2A spec:
    https://a2a-protocol.org/latest/specification/#5-agent-discovery-the-agent-card
    """
    skills = [
        capability_to_skill(cap, manifest.id)
        for cap in manifest.capabilities
    ]

    return {
        "name": manifest.name,
        "description": manifest.description,
        "url": f"{base_url}/a2a/{manifest.id}",
        "version": version,
        "provider": {
            "organization": provider_name,
            "url": provider_url,
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "authentication": {
            "schemes": ["Bearer"],
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": skills,
        # AIOSCP extensions (non-standard, prefixed)
        "x-aioscp": {
            "protocol": "aioscp",
            "protocolVersion": "1.0",
            "operatorId": manifest.id,
            "trustLevel": manifest.trust_level,
            "persona": {
                "role": manifest.persona.role,
                "voice": manifest.persona.voice,
            },
            "modelPreference": manifest.model_preference,
        },
    }


def generate_agent_cards(
    manifests: list[OperatorManifest],
    base_url: str = "https://api.cocreatiq.com",
) -> dict:
    """
    Generate the full /.well-known/agent-card.json response
    for all operators on this host.

    Returns a dict with all agent cards keyed by operator ID.
    """
    cards = {}
    for manifest in manifests:
        cards[manifest.id] = manifest_to_agent_card(manifest, base_url)
        logger.info(
            f"[A2A] Agent Card generated: {manifest.name} "
            f"({len(manifest.capabilities)} skills)"
        )

    return {
        "agents": cards,
        "host": {
            "name": "Cocreatiq OS",
            "version": "3.0",
            "protocol": "aioscp",
            "protocolVersion": "1.0",
            "a2aVersion": "1.0",
            "totalAgents": len(cards),
        },
    }


def agent_cards_to_json(
    manifests: list[OperatorManifest],
    base_url: str = "https://api.cocreatiq.com",
    indent: int = 2,
) -> str:
    """Generate Agent Cards as a JSON string, ready to serve."""
    cards = generate_agent_cards(manifests, base_url)
    return json.dumps(cards, indent=indent, default=str)