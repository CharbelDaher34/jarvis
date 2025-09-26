from __future__ import annotations

import logging
from typing import Optional, Tuple

import helium
from selenium import webdriver

from src.browser_agent.agent import BrowserDeps, run_with_screenshot
from src.browser_agent.config import load_config
from src.browser_agent.user_experience import create_progress_tracker, logger, feedback
from src.browser_agent.error_handling import BrowserConnectionError, safe_execute


class BrowserSession:
    """Manage the lifecycle of the browser with optional keep-open behaviour."""

    def __init__(self, headless: bool) -> None:
        self.headless = headless
        self._active = False
        self._keep_open = False
        self._owns_browser = False
        self._task_handle: Optional[str] = None

    def start(self) -> None:
        _, started_new = _start_browser(self.headless)
        self._active = True
        self._owns_browser = started_new

    def keep_open(self) -> None:
        self._keep_open = True

    def close(self, force: bool = False) -> None:
        should_cleanup = force or not self._keep_open

        if should_cleanup and self._task_handle:
            _close_owned_tab(self._task_handle)
            self._task_handle = None

        if self._active and should_cleanup:
            if self._owns_browser:
                _stop_browser()
            else:
                logger.info("Leaving shared browser session running")
        self._active = False

    def open_task_tab(self) -> None:
        handle = _open_new_tab()
        if handle:
            self._task_handle = handle
        else:
            logger.warning("Unable to open dedicated task tab; continuing in current tab")


def _get_existing_driver() -> Optional[webdriver.Chrome]:
    try:
        driver = helium.get_driver()
    except Exception:
        return None

    if not driver:
        return None

    try:
        # Accessing current_url triggers a WebDriver call that raises if the session is dead
        _ = driver.current_url
        driver.window_handles  # Ensure browser still has open windows
    except Exception:
        return None

    return driver


def _configure_driver(driver: webdriver.Chrome) -> None:
    config = load_config()
    driver.set_page_load_timeout(config.browser.page_load_timeout)
    driver.implicitly_wait(config.browser.implicit_wait)


def _start_browser(headless: bool) -> Tuple[Optional[webdriver.Chrome], bool]:
    """Start Chrome browser with enhanced configuration and error handling."""
    try:
        existing_driver = _get_existing_driver()
        if existing_driver:
            logger.browser_action("Reusing existing Chrome browser session")
            _configure_driver(existing_driver)
            return existing_driver, False

        config = load_config()

        logger.browser_action("Initializing Chrome browser")

        # Configure Chrome options with enhanced settings
        chrome_options = webdriver.ChromeOptions()
        
        # Headless mode configuration
        if headless or config.browser.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            logger.info("Running in headless mode")
        
        # Window configuration
        window_size = f"{config.browser.window_width},{config.browser.window_height}"
        chrome_options.add_argument(f"--window-size={window_size}")
        chrome_options.add_argument("--window-position=0,0")
        chrome_options.add_argument("--force-device-scale-factor=1")
        
        # Performance and reliability options
        chrome_options.add_argument("--disable-pdf-viewer")
        chrome_options.add_argument("--disable-web-security")  # For development
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-extensions")
        
        # Optional: Disable images for faster loading
        if config.browser.disable_images:
            prefs = {"profile.managed_default_content_settings.images": 2}
            chrome_options.add_experimental_option("prefs", prefs)
            logger.info("Images disabled for faster loading")
        
        # Optional: Custom user agent
        if config.browser.user_agent:
            chrome_options.add_argument(f"--user-agent={config.browser.user_agent}")
        
        # Optional: Download directory
        if config.browser.download_directory:
            prefs = {
                "download.default_directory": config.browser.download_directory,
                "download.prompt_for_download": False,
            }
            chrome_options.add_experimental_option("prefs", prefs)
        
        # Start browser with error handling
        def start_chrome():
            helium.start_chrome(headless=headless or config.browser.headless, options=chrome_options)
        
        result, error = safe_execute(start_chrome, error_message="Failed to start Chrome browser")
        
        if error:
            raise BrowserConnectionError(f"Browser initialization failed: {error}")
        
        # Verify browser is working
        try:
            driver = helium.get_driver()
            _configure_driver(driver)
            logger.browser_action("Chrome browser started successfully")
        except Exception as e:
            raise BrowserConnectionError(f"Browser verification failed: {e}")
        
        return driver, True

    except Exception as e:
        logger.error(f"Browser startup failed: {e}")
        raise


def _open_new_tab() -> Optional[str]:
    try:
        driver = helium.get_driver()
    except Exception as exc:
        logger.warning(f"Unable to access driver when opening new tab: {exc}")
        return None

    if not driver:
        logger.warning("No active driver available to open a new tab")
        return None

    try:
        driver.switch_to.new_window("tab")
    except Exception:
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

    handle = driver.current_window_handle
    logger.browser_action(f"Opened new tab with handle {handle}")
    return handle


def _close_owned_tab(handle: str) -> None:
    try:
        driver = helium.get_driver()
    except Exception as exc:
        logger.warning(f"Unable to access driver when closing tab {handle}: {exc}")
        return

    if not driver:
        return

    try:
        if handle in driver.window_handles:
            driver.switch_to.window(handle)
            driver.close()
            remaining = driver.window_handles
            if remaining:
                driver.switch_to.window(remaining[0])
    except Exception as exc:
        logger.warning(f"Unable to close task tab {handle}: {exc}")


def _stop_browser() -> None:
    """Stop browser with proper cleanup and error handling."""
    logger.browser_action("Stopping Chrome browser")
    
    def cleanup_browser():
        try:
            driver = helium.get_driver()
            if driver:
                # Clear cookies and cache
                driver.delete_all_cookies()
                # Close all windows
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.close()
                # Quit driver
                driver.quit()
        except Exception as e:
            logger.warning(f"Browser cleanup encountered issues: {e}")
    
    result, error = safe_execute(cleanup_browser, error_message="Browser cleanup failed")
    
    if error:
        logger.warning(f"Browser may not have shut down cleanly: {error}")
    else:
        logger.info("Browser stopped successfully")


def _should_keep_browser_open(headless: bool) -> bool:
    if headless:
        return False
    return feedback.confirm_action("Keep browser open for inspection?", default=False)


async def run_task(prompt: str, headless: bool = False) -> str:
    """
    Run a browser automation task with enhanced progress tracking and error handling.
    
    Args:
        prompt: Task description for the agent
        headless: Whether to run in headless mode
        
    Returns:
        Task result output
    """
    progress = create_progress_tracker("Browser Automation Task")
    progress.add_step("init", "Initialize browser")
    progress.add_step("execute", "Execute automation task")
    progress.add_step("cleanup", "Clean up resources")

    session = BrowserSession(headless)
    result: Optional[str] = None

    try:
        with progress.step("init", "Starting Chrome browser"):
            session.start()
            session.open_task_tab()
            progress.complete_current_step("Browser ready")

        with progress.step("execute", f"Running task: {prompt[:50]}..."):
            logger.user_action("Starting automation task", prompt)
            result = await run_with_screenshot(prompt, deps=BrowserDeps(headless=headless))

            if result:
                logger.user_action("Task completed successfully")
                progress.complete_current_step(f"Generated {len(result)} characters of output")
            else:
                logger.warning("Task completed but returned no output")
                progress.complete_current_step("No output generated")

        with progress.step("cleanup", "Cleaning up browser session"):
            if _should_keep_browser_open(headless):
                session.keep_open()
                logger.info("Browser left open for inspection")
                progress.skip_current_step("User chose to keep browser open")
            else:
                session.close()
                progress.complete_current_step("Browser closed")

        progress.finish(success=True)

        if result:
            print(f"\n{'='*60}")
            print("🎉 TASK COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}")

        return result or "Task completed but no output generated"

    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        progress.fail_current_step(str(e))
        progress.finish(success=False)
        session.close(force=True)
        raise

    finally:
        session.close(force=False)
        if not progress.end_time:
            progress.finish(success=False)
