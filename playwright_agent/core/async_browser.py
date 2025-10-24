"""
Async Browser Manager using Playwright.
Replaces synchronous Selenium/Helium approach.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout
)

from ..config import load_config
from ..error_handling import (
    BrowserConnectionError,
    NavigationError,
    PageLoadError
)

logger = logging.getLogger(__name__)


class AsyncBrowserSession:
    """
    Manages async browser lifecycle with Playwright.
    
    Advantages over Selenium:
    - Non-blocking async/await
    - Built-in auto-waiting (no explicit sleeps)
    - Better reliability
    - Native network interception
    - Multi-browser support (Chromium, Firefox, WebKit)
    """
    
    def __init__(
        self,
        headless: bool = False,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        record_video: bool = False,
        screenshots_dir: Optional[str] = None
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.record_video = record_video
        self.screenshots_dir = screenshots_dir
        
        # Playwright components
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Session state
        self._active = False
        self.action_history: List[Dict[str, Any]] = []
        self.visited_urls: set[str] = set()
        
        # Performance tracking
        self.total_actions = 0
        self.failed_actions = 0
    
    # async def start(self) -> None:
    #     """Initialize browser with optimal settings."""
    #     if self._active:
    #         logger.warning("Browser already active")
    #         return
        
    #     config = load_config()
        
    #     try:
    #         # Start Playwright
    #         self._playwright = await async_playwright().start()
            
    #         # Launch browser
    #         self._browser = await self._playwright.chromium.launch(
    #             headless=self.headless,
    #             args=[
    #                 "--disable-blink-features=AutomationControlled",
    #                 "--disable-dev-shm-usage",
    #                 f"--window-size={self.viewport_width},{self.viewport_height}",
    #             ],
    #             # Keep sandbox enabled for security
    #         )
            
    #         # Create context (isolated session)
    #         context_options = {
    #             "viewport": {
    #                 "width": self.viewport_width,
    #                 "height": self.viewport_height
    #             },
    #             "user_agent": (
    #                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    #                 "AppleWebKit/537.36 (KHTML, like Gecko) "
    #                 "Chrome/120.0.0.0 Safari/537.36"
    #             ),
    #             "locale": "en-US",
    #             "timezone_id": "America/New_York",
    #         }
            
    #         # Add video recording if enabled
    #         if self.record_video:
    #             context_options["record_video_dir"] = "videos/"
    #             context_options["record_video_size"] = {
    #                 "width": self.viewport_width,
    #                 "height": self.viewport_height
    #             }
            
    #         self._context = await self._browser.new_context(**context_options)
            
    #         # Inject stealth scripts to avoid detection
    #         await self._context.add_init_script("""
    #             // Remove webdriver flag
    #             Object.defineProperty(navigator, 'webdriver', {
    #                 get: () => undefined
    #             });
                
    #             // Mock plugins
    #             Object.defineProperty(navigator, 'plugins', {
    #                 get: () => [1, 2, 3, 4, 5]
    #             });
                
    #             // Mock languages
    #             Object.defineProperty(navigator, 'languages', {
    #                 get: () => ['en-US', 'en']
    #             });
    #         """)
            
    #         # Create initial page
    #         self._page = await self._context.new_page()
            
    #         # Set default timeout
    #         self._page.set_default_timeout(config.browser.page_load_timeout * 1000)
            
    #         # Enable request interception for performance
    #         await self._setup_request_interception()
            
    #         self._active = True
    #         logger.info("✅ Async browser session started")
            
    #     except Exception as e:
    #         await self.close()
    #         raise BrowserConnectionError(f"Failed to start browser: {e}")
    
    async def start(self) -> None:
        """Initialize browser (Google Chrome) with optimal settings and English locale."""
        if self._active:
            logger.warning("Browser already active")
            return

        config = load_config()

        try:
            # Start Playwright
            self._playwright = await async_playwright().start()

            # Launch Google Chrome
            self._browser = await self._playwright.chromium.launch(
                # channel="chrome",  # Ensures Google Chrome instead of bundled Chromium
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    f"--window-size={self.viewport_width},{self.viewport_height}",
                ],
                # Keeping sandbox enabled for security
            )

            # Define context options (English locale & timezone)
            context_options = {
                "viewport": {"width": self.viewport_width, "height": self.viewport_height},
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "extra_http_headers": {
                    "Accept-Language": "en-US,en;q=0.9"
                }
            }
            

            # Add video recording if enabled
            if self.record_video:
                context_options["record_video_dir"] = "videos/"
                context_options["record_video_size"] = {
                    "width": self.viewport_width,
                    "height": self.viewport_height
                }

            # Create new context
            self._context = await self._browser.new_context(**context_options)

            # Inject stealth scripts to reduce detection
            await self._context.add_init_script("""
                // Remove webdriver flag
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)

            # Create first page
            self._page = await self._context.new_page()

            # Set default timeout (convert seconds to ms)
            self._page.set_default_timeout(config.browser.page_load_timeout * 1000)

            # Enable request interception for optimization
            await self._setup_request_interception()

            self._active = True
            logger.info("✅ Async Chrome browser session started with English locale")

        except Exception as e:
            await self.close()
            raise BrowserConnectionError(f"Failed to start browser: {e}")
    async def _setup_request_interception(self):
        """Intercept and block unnecessary resources for performance."""
        config = load_config()
        
        async def handle_route(route, request):
            # Block images, fonts, and other heavy resources if configured
            if config.browser.disable_images:
                if request.resource_type in ["image", "stylesheet", "font", "media"]:
                    await route.abort()
                    return
            
            await route.continue_()
        
        await self._page.route("**/*", handle_route)
    
    async def navigate(self, url: str, wait_until: str = "commit") -> Dict[str, Any]:
        """
        Navigate to URL in a new tab with automatic waiting.
        
        Args:
            url: Target URL
            wait_until: When to consider navigation complete
                       ('domcontentloaded', 'load', 'networkidle')
        
        Returns:
            Dict with navigation details
        """
        if not self._context:
            raise BrowserConnectionError("Browser not started")
        
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        start_time = datetime.now()
        
        try:
            # Create new page (tab)
            new_page = await self._context.new_page()
            
            # Set default timeout for new page
            config = load_config()
            new_page.set_default_timeout(config.browser.page_load_timeout * 1000)
            
            # Set up request interception for the new page
            async def handle_route(route, request):
                if config.browser.disable_images:
                    if request.resource_type in ["image", "stylesheet", "font", "media"]:
                        await route.abort()
                        return
                await route.continue_()
            
            await new_page.route("**/*", handle_route)
            
            # Switch to the new page
            self._page = new_page
            
            # Navigate with auto-wait
            response = await self._page.goto(url, wait_until=wait_until)
            
            # Record action
            elapsed = (datetime.now() - start_time).total_seconds()
            self.visited_urls.add(url)
            self.total_actions += 1
            
            action_record = {
                "action": "navigate",
                "url": url,
                "timestamp": start_time,
                "elapsed_seconds": elapsed,
                "status": response.status if response else None,
                "success": True
            }
            self.action_history.append(action_record)
            
            logger.info(f"✅ Navigated to {url} in {elapsed:.2f}s")
            
            return {
                "url": url,
                "title": await self._page.title(),
                "status": response.status if response else None,
                "elapsed": elapsed
            }
            
        except PlaywrightTimeout:
            self.failed_actions += 1
            raise PageLoadError(f"Page load timeout for {url}")
        except Exception as e:
            self.failed_actions += 1
            raise NavigationError(f"Navigation failed for {url}: {e}")
    
    async def click(self, selector: str, timeout: Optional[int] = None) -> str:
        """
        Click element with automatic waiting and retry.
        
        Args:
            selector: CSS selector, text content, or natural language description
            timeout: Optional custom timeout in milliseconds
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        # Determine if this looks like a CSS selector or natural text
        is_likely_selector = any(char in selector for char in ['.', '#', '[', '>', '~', '+']) or \
                           selector.startswith(('input', 'button', 'a', 'div', 'span', 'text='))
        
        if is_likely_selector:
            # Try as CSS selector first
            try:
                await self._page.click(selector, timeout=timeout or 3000)  # Reduced from 5000ms
                self.total_actions += 1
                logger.info(f"✅ Clicked: {selector}")
                return f"Clicked element: {selector}"
            except Exception as e:
                logger.debug(f"CSS selector failed: {e}, trying alternative strategies")
        
        # Use smart fallback for natural language or if CSS failed
        return await self._smart_click_fallback(selector, timeout)
    
    async def _smart_click_fallback(self, target: str, timeout: Optional[int] = None) -> str:
        """Try multiple strategies to click element."""
        timeout_ms = timeout or 2000  # Reduced from 5000ms for faster retries
        
        strategies = [
            # Strategy 1: Try as exact text content
            ("exact text", lambda: self._page.get_by_text(target, exact=True).click(timeout=timeout_ms)),
            
            # Strategy 2: Try partial text
            ("partial text", lambda: self._page.get_by_text(target, exact=False).first.click(timeout=timeout_ms)),
            
            # Strategy 3: Try as button role with name
            ("button role", lambda: self._page.get_by_role("button", name=target).click(timeout=timeout_ms)),
            
            # Strategy 4: Try as link role with name
            ("link role", lambda: self._page.get_by_role("link", name=target).click(timeout=timeout_ms)),
            
            # Strategy 5: Try case-insensitive text match
            ("case-insensitive", lambda: self._page.locator(f"text=/{target}/i").first.click(timeout=timeout_ms)),
            
            # Strategy 6: Try XPath with contains
            ("xpath contains", lambda: self._page.locator(f"xpath=//*[contains(text(), '{target}')]").first.click(timeout=timeout_ms)),
            
            # Strategy 7: Try aria-label
            ("aria-label", lambda: self._page.locator(f"[aria-label*='{target}' i]").first.click(timeout=timeout_ms)),
            
            # Strategy 8: Try title attribute
            ("title", lambda: self._page.locator(f"[title*='{target}' i]").first.click(timeout=timeout_ms)),
        ]
        
        for i, (strategy_name, strategy_func) in enumerate(strategies, 1):
            try:
                await strategy_func()
                self.total_actions += 1
                logger.info(f"✅ Clicked using strategy {i} ({strategy_name}): {target}")
                return f"Clicked '{target}' using {strategy_name} strategy"
            except Exception as e:
                logger.debug(f"Strategy {i} ({strategy_name}) failed: {e}")
                continue
        
        self.failed_actions += 1
        raise Exception(f"All {len(strategies)} click strategies failed for: '{target}'")
    
    async def type_text(self, selector: str, text: str, delay: int = 0) -> str:
        """
        Type text into element with minimal delay for speed.
        
        Args:
            selector: CSS selector, placeholder text, or field description
            text: Text to type
            delay: Delay between keystrokes in ms (0 for instant)
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        # Determine if this looks like a CSS selector
        is_likely_selector = any(char in selector for char in ['.', '#', '[', '>', '~']) or \
                           selector.startswith(('input', 'textarea', 'select'))
        
        if is_likely_selector:
            # Try as CSS selector first
            try:
                await self._page.fill(selector, text)
                self.total_actions += 1
                logger.info(f"✅ Typed text into: {selector}")
                return f"Entered text into {selector}"
            except Exception as e:
                logger.debug(f"CSS selector failed: {e}, trying alternative strategies")
        
        # Try alternative strategies for natural language
        strategies = [
            # Strategy 1: Try as placeholder
            ("placeholder", lambda: self._page.get_by_placeholder(selector).fill(text)),
            
            # Strategy 2: Try as label
            ("label", lambda: self._page.get_by_label(selector).fill(text)),
            
            # Strategy 3: Try role with name
            ("textbox role", lambda: self._page.get_by_role("textbox", name=selector).fill(text)),
            
            # Strategy 4: Try partial placeholder match
            ("partial placeholder", lambda: self._page.locator(f"input[placeholder*='{selector}' i]").first.fill(text)),
            
            # Strategy 5: Try name attribute
            ("name attribute", lambda: self._page.locator(f"input[name*='{selector}' i]").first.fill(text)),
            
            # Strategy 6: Try aria-label
            ("aria-label", lambda: self._page.locator(f"input[aria-label*='{selector}' i]").first.fill(text)),
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                await strategy_func()
                self.total_actions += 1
                logger.info(f"✅ Typed text using {strategy_name}: {selector}")
                return f"Entered '{text}' into '{selector}' using {strategy_name} strategy"
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
                continue
        
        self.failed_actions += 1
        raise Exception(f"All strategies failed to type into: '{selector}'")
    
    async def get_page_content(self) -> Dict[str, Any]:
        """
        Get comprehensive page content including DOM and text.
        
        Returns:
            Dict with page content, structure, and metadata
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        try:
            # Get page metadata
            url = self._page.url
            title = await self._page.title()
            
            # Get text content
            text_content = await self._page.inner_text("body")
            
            # Get interactive elements
            elements = await self._page.evaluate("""
                () => {
                    const elements = Array.from(
                        document.querySelectorAll('a, button, input, select, textarea')
                    );
                    
                    return elements
                        .filter(el => el.offsetParent !== null)  // Only visible
                        .map(el => ({
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim().substring(0, 100),
                            type: el.type || null,
                            id: el.id || null,
                            class: el.className || null,
                            href: el.href || null,
                            visible: true
                        }));
                }
            """)
            
            return {
                "url": url,
                "title": title,
                "text_content": text_content[:5000],  # Truncate if too long
                "interactive_elements": elements,
                "element_count": len(elements)
            }
            
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            raise
    
    async def screenshot(self, path: Optional[str] = None) -> bytes:
        """
        Take screenshot of current page.
        
        Args:
            path: Optional path to save screenshot
        
        Returns:
            Screenshot as bytes
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        try:
            screenshot_bytes = await self._page.screenshot(
                full_page=False,
                path=path
            )
            
            if path:
                logger.info(f"📸 Screenshot saved: {path}")
            
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise
    
    async def scroll(self, direction: str = "down", amount: Optional[int] = None) -> str:
        """
        Scroll page in specified direction.
        
        Args:
            direction: 'up', 'down', 'top', 'bottom'
            amount: Pixels to scroll (if not specified, uses viewport height)
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        if direction == "top":
            await self._page.evaluate("window.scrollTo(0, 0)")
            return "Scrolled to top"
        elif direction == "bottom":
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return "Scrolled to bottom"
        else:
            if amount is None:
                amount = self.viewport_height
            
            delta = amount if direction == "down" else -amount
            await self._page.evaluate(f"window.scrollBy(0, {delta})")
            return f"Scrolled {direction} {amount}px"
    
    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: int = 30000
    ) -> bool:
        """
        Wait for element to reach specified state.
        
        Args:
            selector: CSS selector
            state: 'attached', 'visible', 'hidden', 'detached'
            timeout: Timeout in milliseconds
        """
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        try:
            await self._page.wait_for_selector(selector, state=state, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False
    
    async def get_all_pages(self) -> List[Page]:
        """Get all open pages (tabs)."""
        if not self._context:
            raise BrowserConnectionError("Browser not started")
        return self._context.pages
    
    async def close_current_tab(self) -> None:
        """Close the current tab and switch to the previous one."""
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        pages = await self.get_all_pages()
        if len(pages) <= 1:
            logger.warning("Cannot close the last tab")
            return
        
        # Close current page
        await self._page.close()
        
        # Switch to the last remaining page
        pages = await self.get_all_pages()
        if pages:
            self._page = pages[-1]
            logger.info(f"Switched to tab: {await self._page.title()}")
    
    async def switch_to_tab(self, index: int) -> None:
        """Switch to a specific tab by index (0-based)."""
        if not self._context:
            raise BrowserConnectionError("Browser not started")
        
        pages = await self.get_all_pages()
        if 0 <= index < len(pages):
            self._page = pages[index]
            logger.info(f"Switched to tab {index}: {await self._page.title()}")
        else:
            raise ValueError(f"Tab index {index} out of range (0-{len(pages)-1})")
    
    async def close_all_tabs_except_current(self) -> None:
        """Close all tabs except the current one."""
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        
        current_page = self._page
        pages = await self.get_all_pages()
        
        for page in pages:
            if page != current_page:
                await page.close()
        
        logger.info("Closed all tabs except current")
    
    @property
    def page(self) -> Page:
        """Get current page for direct Playwright API access."""
        if not self._page:
            raise BrowserConnectionError("Browser not started")
        return self._page
    
    @property
    def is_active(self) -> bool:
        """Check if browser session is active."""
        return self._active
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get session performance metrics."""
        success_rate = (
            (self.total_actions - self.failed_actions) / self.total_actions * 100
            if self.total_actions > 0 else 0
        )
        
        # Get number of open tabs
        open_tabs = len(self._context.pages) if self._context else 0
        
        return {
            "total_actions": self.total_actions,
            "failed_actions": self.failed_actions,
            "success_rate": f"{success_rate:.1f}%",
            "unique_urls_visited": len(self.visited_urls),
            "action_history_count": len(self.action_history),
            "open_tabs": open_tabs
        }
    
    async def close(self) -> None:
        """Close browser with proper cleanup."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            self._active = False
            logger.info("✅ Browser session closed")
            
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()


# Example usage
async def example_usage():
    """Demonstrate async browser usage."""
    async with AsyncBrowserSession(headless=False) as browser:
        # Navigate
        await browser.navigate("https://www.python.org")
        
        # Get page content
        content = await browser.get_page_content()
        print(f"Title: {content['title']}")
        print(f"Found {content['element_count']} interactive elements")
        
        # Click element
        await browser.click("text=Downloads")
        
        # Take screenshot
        await browser.screenshot("python_downloads.png")
        
        # Get metrics
        metrics = browser.get_metrics()
        print(f"Metrics: {metrics}")


if __name__ == "__main__":
    asyncio.run(example_usage())

