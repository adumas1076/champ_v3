# ============================================
# CHAMP V3 — Function Tools
# Ported from champ_v1/core/tools.py + Brain integration
# Pattern: @function_tool() + RunContext
# ============================================

import logging
import os
from livekit.agents import function_tool, RunContext
import requests
from langchain_community.tools import DuckDuckGoSearchRun

BRAIN_URL = os.getenv("BRAIN_URL", "http://127.0.0.1:8100")


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
) -> str:
    """Get the current weather for a given city."""
    try:
        response = requests.get(f"https://wttr.in/{city}?format=3")
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}."


@function_tool()
async def search_web(
    context: RunContext,
    query: str,
) -> str:
    """Search the web using DuckDuckGo."""
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}'."


@function_tool()
async def ask_brain(
    context: RunContext,
    question: str,
) -> str:
    """Ask the Brain for a deep, thoughtful answer. Use this for complex questions,
    coding help, build plans, architecture advice, or anything that needs more than
    a quick voice response. The Brain uses Claude Sonnet with Champ's full persona."""
    try:
        response = requests.post(
            f"{BRAIN_URL}/v1/chat/completions",
            json={
                "model": "claude-sonnet",
                "messages": [{"role": "user", "content": question}],
                "stream": False,
                "max_tokens": 1000,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logging.info(f"Brain response for '{question[:50]}...': {len(content)} chars")
        return content
    except Exception as e:
        logging.error(f"Brain error for '{question[:50]}...': {e}")
        return f"Brain is offline or errored: {e}"
