# ============================================
# CHAMP V3 — Stealth Browser (Full Hands Upgrade)
# Uses nodriver to control the user's REAL browser
# Undetectable — no bot fingerprint
# ============================================

import asyncio
import base64
import logging
import tempfile
from pathlib import Path

import nodriver as uc

logger = logging.getLogger(__name__)

# Singleton browser instance — reuses the user's real browser
_browser = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    """Get or create a persistent browser instance using the user's real Chrome."""
    global _browser
    async with _browser_lock:
        if _browser is None:
            logger.info("[STEALTH] Launching real browser via nodriver...")
            config = uc.Config()
            config.headless = False  # Real browser — visible on screen
            config.sandbox = False
            _browser = await uc.start(config=config)
            logger.info("[STEALTH] Browser launched successfully")
        return _browser


async def close_browser():
    """Shut down the stealth browser instance."""
    global _browser
    async with _browser_lock:
        if _browser is not None:
            try:
                _browser.stop()
            except Exception:
                pass
            _browser = None
            logger.info("[STEALTH] Browser closed")


async def browse(url: str, timeout: float = 30.0) -> dict:
    """Navigate to URL in the real browser, return page text and metadata."""
    try:
        browser = await _get_browser()
        tab = await browser.get(url)
        await tab.sleep(2)  # Let page render

        title = await tab.evaluate("document.title") or "No title"
        text = await tab.evaluate(
            "document.body ? document.body.innerText.substring(0, 3000) : ''"
        ) or ""
        current_url = await tab.evaluate("window.location.href") or url

        logger.info(f"[STEALTH] Browsed {url} -> {title}")
        return {
            "ok": True,
            "title": title,
            "text": text,
            "url": current_url,
        }
    except Exception as e:
        logger.error(f"[STEALTH] Browse error: {e}")
        return {"ok": False, "error": str(e)}


async def take_screenshot(url: str = None, timeout: float = 30.0) -> dict:
    """Take screenshot of current page or navigate to URL first."""
    try:
        browser = await _get_browser()

        if url:
            tab = await browser.get(url)
            await tab.sleep(2)
        else:
            tab = browser.main_tab

        # Save screenshot
        output_dir = Path(__file__).resolve().parent.parent / "output"
        output_dir.mkdir(exist_ok=True)

        filepath = output_dir / f"screenshot_{id(tab)}.png"
        await tab.save_screenshot(str(filepath))

        title = await tab.evaluate("document.title") or "No title"

        logger.info(f"[STEALTH] Screenshot saved: {filepath}")
        return {
            "ok": True,
            "path": str(filepath),
            "title": title,
        }
    except Exception as e:
        logger.error(f"[STEALTH] Screenshot error: {e}")
        return {"ok": False, "error": str(e)}


async def click_element(selector: str) -> dict:
    """Click an element on the current page using CSS selector."""
    try:
        browser = await _get_browser()
        tab = browser.main_tab

        element = await tab.query_selector(selector)
        if not element:
            return {"ok": False, "error": f"Element not found: {selector}"}

        await element.click()
        await tab.sleep(0.5)

        logger.info(f"[STEALTH] Clicked: {selector}")
        return {"ok": True, "clicked": selector}
    except Exception as e:
        logger.error(f"[STEALTH] Click error: {e}")
        return {"ok": False, "error": str(e)}


async def type_text(selector: str, text: str, human_like: bool = True) -> dict:
    """Type text into an element with human-like timing."""
    try:
        browser = await _get_browser()
        tab = browser.main_tab

        element = await tab.query_selector(selector)
        if not element:
            return {"ok": False, "error": f"Element not found: {selector}"}

        await element.click()
        await tab.sleep(0.3)

        if human_like:
            await element.send_keys(text)
        else:
            await tab.evaluate(
                f"document.querySelector('{selector}').value = '{text}'"
            )

        logger.info(f"[STEALTH] Typed into {selector}: {text[:30]}...")
        return {"ok": True, "typed": text[:50], "selector": selector}
    except Exception as e:
        logger.error(f"[STEALTH] Type error: {e}")
        return {"ok": False, "error": str(e)}


async def fill_form(url: str, fields: list, submit_selector: str = None) -> dict:
    """Navigate to URL and fill form fields with human-like typing.
    fields: [{"selector": "input[name='email']", "value": "test@example.com"}, ...]
    """
    try:
        browser = await _get_browser()
        tab = await browser.get(url)
        await tab.sleep(2)

        filled = []
        for field in fields:
            selector = field.get("selector", "")
            value = field.get("value", "")
            if not selector:
                continue

            element = await tab.query_selector(selector)
            if element:
                await element.click()
                await tab.sleep(0.2)
                await element.send_keys(value)
                await tab.sleep(0.3)
                filled.append(selector)

        if submit_selector:
            submit = await tab.query_selector(submit_selector)
            if submit:
                await submit.click()
                await tab.sleep(1)

        title = await tab.evaluate("document.title") or "No title"

        logger.info(f"[STEALTH] Filled form on {url}: {len(filled)} fields")
        return {
            "ok": True,
            "title": title,
            "fields_filled": filled,
            "url": url,
        }
    except Exception as e:
        logger.error(f"[STEALTH] Form fill error: {e}")
        return {"ok": False, "error": str(e)}


async def get_page_content() -> dict:
    """Get the current page's title, URL, and visible text."""
    try:
        browser = await _get_browser()
        tab = browser.main_tab

        title = await tab.evaluate("document.title") or ""
        url = await tab.evaluate("window.location.href") or ""
        text = await tab.evaluate(
            "document.body ? document.body.innerText.substring(0, 3000) : ''"
        ) or ""

        return {"ok": True, "title": title, "url": url, "text": text}
    except Exception as e:
        logger.error(f"[STEALTH] Get content error: {e}")
        return {"ok": False, "error": str(e)}


async def execute_js(script: str) -> dict:
    """Execute JavaScript on the current page."""
    try:
        browser = await _get_browser()
        tab = browser.main_tab

        result = await tab.evaluate(script)

        logger.info(f"[STEALTH] JS executed: {script[:60]}...")
        return {"ok": True, "result": str(result) if result else ""}
    except Exception as e:
        logger.error(f"[STEALTH] JS error: {e}")
        return {"ok": False, "error": str(e)}


async def google_search(query: str) -> dict:
    """Search Google using the user's real browser (logged-in Google account)."""
    try:
        browser = await _get_browser()
        tab = await browser.get(f"https://www.google.com/search?q={query}")
        await tab.sleep(2)

        # Extract search results
        results = await tab.evaluate("""
            (() => {
                const items = document.querySelectorAll('div.g');
                return Array.from(items).slice(0, 5).map(item => {
                    const title = item.querySelector('h3');
                    const link = item.querySelector('a');
                    const snippet = item.querySelector('.VwiC3b');
                    return {
                        title: title ? title.innerText : '',
                        url: link ? link.href : '',
                        snippet: snippet ? snippet.innerText : ''
                    };
                });
            })()
        """)

        logger.info(f"[STEALTH] Google search: {query} -> {len(results or [])} results")
        return {
            "ok": True,
            "query": query,
            "results": results or [],
        }
    except Exception as e:
        logger.error(f"[STEALTH] Google search error: {e}")
        return {"ok": False, "error": str(e)}
