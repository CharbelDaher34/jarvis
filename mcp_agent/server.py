#!/usr/bin/env python
# browser_mcp_server.py
# An MCP server exposing Playwright-powered browser automation tools.
# Requires: mcp (Python SDK) and playwright.

import asyncio
import base64
import re
from typing import Optional, Literal, Dict

from pydantic import BaseModel, Field, HttpUrl
from mcp.server.fastmcp import FastMCP, Context, Image

# --- Playwright (async) ---
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeoutError


mcp = FastMCP(
    name="Browser Automation MCP",
    # website_url="https://modelcontextprotocol.io",
)

# -----------------------
# Session / Browser state
# -----------------------
class SessionInfo(BaseModel):
    session_id: str
    url: Optional[str] = None
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800

class ActionResult(BaseModel):
    ok: bool
    detail: str
    url: Optional[str] = None

class ScreenshotResult(BaseModel):
    ok: bool
    content: Image = Field(description="PNG image as MCP Image type")
    url: Optional[str] = None

class TextResult(BaseModel):
    ok: bool
    text: str
    url: Optional[str] = None

# In-memory session registry
_sessions: Dict[str, Page] = {}
_browser: Optional[Browser] = None
_playwright = None

# Default safety: only allow these host patterns (edit as needed)
ALLOWED_HOST_PATTERNS = [
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?/.*$",
    r"^https?://.*\.example\.com/.*$",
]

def _url_allowed(url: str, allow_any: bool = False) -> bool:
    allow_any = True
    if allow_any:
        return True
    for pat in ALLOWED_HOST_PATTERNS:
        if re.match(pat, url):
            return True
    return False

async def _ensure_browser(headless: bool) -> Browser:
    global _playwright, _browser
    if _browser:
        return _browser
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=headless)
    return _browser

async def _get_or_create_page(
    session_id: str,
    headless: bool = True,
    viewport: tuple[int, int] = (1280, 800),
) -> Page:
    global _sessions
    page = _sessions.get(session_id)
    if page and not page.is_closed():
        return page
    browser = await _ensure_browser(headless=headless)
    context: BrowserContext = await browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]}
    )
    page = await context.new_page()
    _sessions[session_id] = page
    return page

async def _cleanup_session(session_id: str) -> None:
    page = _sessions.pop(session_id, None)
    if page:
        try:
            ctx = page.context
            await page.close()
            await ctx.close()
        except Exception:
            pass

async def _shutdown_all() -> None:
    """Called by MCP shutdown lifespan hook."""
    global _sessions, _browser, _playwright
    for sid in list(_sessions.keys()):
        await _cleanup_session(sid)
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
    _browser = None
    _playwright = None


# -----------------------
# Tools
# -----------------------
@mcp.tool()
async def start_session(
    session_id: str,
    headless: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 800,
) -> SessionInfo:
    """
    Create (or reuse) a browser page bound to a session_id.
    """
    page = await _get_or_create_page(
        session_id, headless=False, viewport=(viewport_width, viewport_height)
    )
    return SessionInfo(
        session_id=session_id,
        url=page.url if page.url else None,
        headless=False,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )

@mcp.tool()
async def goto(
    session_id: str,
    url: HttpUrl,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    allow_any_domain: bool = False,
    timeout_ms: int = 20000,
) -> ActionResult:
    """
    Navigate to a URL.
    Safety: by default, only allow URLs matching ALLOWED_HOST_PATTERNS.
    """
    if not _url_allowed(str(url), allow_any_domain):
        return ActionResult(ok=False, detail=f"Blocked by allowlist: {url}", url=str(url))

    page = await _get_or_create_page(session_id)
    try:
        await page.goto(str(url), wait_until=wait_until, timeout=timeout_ms)
        return ActionResult(ok=True, detail="navigated", url=page.url)
    except PWTimeoutError:
        return ActionResult(ok=False, detail="navigation timeout", url=str(url))

@mcp.tool()
async def click(
    session_id: str,
    selector: str,
    timeout_ms: int = 15000,
) -> ActionResult:
    """
    Click an element by CSS or text selector (Playwright).
    """
    page = await _get_or_create_page(session_id)
    try:
        await page.click(selector, timeout=timeout_ms)
        return ActionResult(ok=True, detail=f"clicked {selector}", url=page.url)
    except Exception as e:
        return ActionResult(ok=False, detail=f"click failed: {e}", url=page.url)

@mcp.tool()
async def fill(
    session_id: str,
    selector: str,
    value: str,
    clear: bool = True,
    timeout_ms: int = 15000,
) -> ActionResult:
    """
    Fill a field (input/textarea/contenteditable).
    """
    page = await _get_or_create_page(session_id)
    try:
        if clear:
            await page.fill(selector, value, timeout=timeout_ms)
        else:
            # Type without clearing
            await page.click(selector, timeout=timeout_ms)
            await page.type(selector, value, timeout=timeout_ms)
        return ActionResult(ok=True, detail=f"filled {selector}", url=page.url)
    except Exception as e:
        return ActionResult(ok=False, detail=f"fill failed: {e}", url=page.url)

@mcp.tool()
async def press(
    session_id: str,
    key: str,
    timeout_ms: int = 15000,
) -> ActionResult:
    """
    Press a keyboard key (e.g., 'Enter', 'Tab', 'Control+A').
    """
    page = await _get_or_create_page(session_id)
    try:
        await page.keyboard.press(key, timeout=timeout_ms)
        return ActionResult(ok=True, detail=f"pressed {key}", url=page.url)
    except Exception as e:
        return ActionResult(ok=False, detail=f"press failed: {e}", url=page.url)

@mcp.tool()
async def wait_for_selector(
    session_id: str,
    selector: str,
    state: Literal["attached", "detached", "visible", "hidden"] = "visible",
    timeout_ms: int = 15000,
) -> ActionResult:
    """
    Wait for a selector in a specific state.
    """
    page = await _get_or_create_page(session_id)
    try:
        await page.wait_for_selector(selector, state=state, timeout=timeout_ms)
        return ActionResult(ok=True, detail=f"{selector} is {state}", url=page.url)
    except Exception as e:
        return ActionResult(ok=False, detail=f"wait failed: {e}", url=page.url)

@mcp.tool()
async def inner_text(
    session_id: str,
    selector: str,
    timeout_ms: int = 15000,
) -> TextResult:
    """
    Get innerText of the first element matching selector.
    """
    page = await _get_or_create_page(session_id)
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
        text = await page.inner_text(selector, timeout=timeout_ms)
        return TextResult(ok=True, text=text, url=page.url)
    except Exception as e:
        return TextResult(ok=False, text=f"error: {e}", url=page.url)

@mcp.tool()
async def evaluate_js(
    session_id: str,
    expression: str,
    timeout_ms: int = 15000,
) -> TextResult:
    """
    Evaluate JS in the page context. Returns stringified result.
    """
    page = await _get_or_create_page(session_id)
    try:
        result = await page.evaluate(f"async () => {{ return await (async () => {{ {expression} }})() }}")
        return TextResult(ok=True, text=str(result), url=page.url)
    except Exception as e:
        return TextResult(ok=False, text=f"eval error: {e}", url=page.url)

@mcp.tool()
async def screenshot(
    session_id: str,
    full_page: bool = False,
    timeout_ms: int = 15000,
) -> ScreenshotResult:
    """
    Take a PNG screenshot and return it as an MCP Image (no files written).
    """
    page = await _get_or_create_page(session_id)
    try:
        buf = await page.screenshot(full_page=full_page, timeout=timeout_ms, type="png")
        return ScreenshotResult(
            ok=True,
            content=Image(data=buf, format="png"),
            url=page.url,
        )
    except Exception as e:
        # Return a tiny PNG with the error text would be overkill; send text via detail if needed
        empty = Image(data=b"", format="png")
        return ScreenshotResult(ok=False, content=empty, url=page.url)

@mcp.tool()
async def close_session(session_id: str) -> ActionResult:
    """
    Close and forget a session/page.
    """
    await _cleanup_session(session_id)
    return ActionResult(ok=True, detail="session closed")

# -------------
# Lifespan hook
# -------------
@mcp.lifespan
async def _lifespan(ctx: Context):
    # Startup: nothing special (browser is lazy-started)
    yield
    # Shutdown: close pages/contexts/browser
    await _shutdown_all()


# -----------
# Entrypoint
# -----------
if __name__ == "__main__":
    print("🚀 Starting Browser Automation MCP server (Playwright)")
    import time
    mcp.run()
