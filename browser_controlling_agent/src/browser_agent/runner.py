from __future__ import annotations

import logging
import asyncio
from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime

import helium
from selenium import webdriver

from src.browser_agent.agent import BrowserDeps, run_with_screenshot
from src.browser_agent.config import load_config
from src.browser_agent.error_handling import BrowserConnectionError, safe_execute

# Setup logging
logger = logging.getLogger(__name__)


class BrowserSession:
    """Manage the lifecycle of the browser with optional keep-open behaviour and video recording."""

    def __init__(self, headless: bool, record_video: bool = False, video_dir: Optional[str] = None) -> None:
        self.headless = headless
        self._active = False
        self._keep_open = False
        self._owns_browser = False
        self._task_handle: Optional[str] = None
        self._record_video = record_video
        self._video_dir = video_dir or str(Path.cwd() / "videos")
        self._screenshots_dir: Optional[str] = None
        self._take_screenshots = False

    def enable_screenshots(self, screenshots_dir: str) -> None:
        """Enable screenshot taking and set directory."""
        self._take_screenshots = True
        self._screenshots_dir = screenshots_dir
        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Screenshots enabled in directory: {screenshots_dir}")

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

    def take_screenshot(self, name: str, page_title: Optional[str] = None) -> Optional[str]:
        """Take a screenshot and save it to the screenshots directory."""
        if not self._take_screenshots or not self._screenshots_dir:
            return None
        
        try:
            from datetime import datetime
            driver = helium.get_driver()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = Path(self._screenshots_dir) / filename
            
            driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            
            return str(filepath)
        except Exception as e:
            logger.warning(f"Failed to take screenshot '{name}': {e}")
            return None


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
            logger.info("Reusing existing Chrome browser session")
            _configure_driver(existing_driver)
            return existing_driver, False

        config = load_config()

        logger.info("Initializing Chrome browser")

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
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Hide automation
        
        # Experimental options to make browser less detectable
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
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
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False
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
            
            # Remove webdriver flag to make browser less detectable
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": driver.execute_script("return navigator.userAgent").replace('Headless', '')
            })
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome browser started successfully")
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
    logger.info(f"Opened new tab with handle {handle}")
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
    logger.info("Stopping Chrome browser")
    
    def cleanup_browser():
        try:
            driver = helium.get_driver()
            if driver:
                # Clear cookies and cache
                try:
                    driver.delete_all_cookies()
                except Exception as e:
                    logger.debug(f"Could not delete cookies: {e}")
                
                # Close all windows gracefully
                try:
                    handles = driver.window_handles[:]
                    for handle in handles:
                        try:
                            driver.switch_to.window(handle)
                            driver.close()
                        except Exception as e:
                            logger.debug(f"Could not close window {handle}: {e}")
                except Exception as e:
                    logger.debug(f"Could not close windows: {e}")
                
                # Quit driver
                try:
                    driver.quit()
                except Exception as e:
                    logger.debug(f"Error during driver.quit(): {e}")
        except Exception as e:
            logger.warning(f"Browser cleanup encountered issues: {e}")
    
    result, error = safe_execute(cleanup_browser, error_message="Browser cleanup failed")
    
    if error:
        logger.warning(f"Browser may not have shut down cleanly: {error}")
    else:
        logger.info("Browser stopped successfully")


def _should_keep_browser_open(headless: bool) -> bool:
    """Ask user if they want to keep browser open."""
    if headless:
        return False
    
    try:
        response = input("Keep browser open for inspection? [y/N]: ").strip().lower()
        return response in ["y", "yes"]
    except (EOFError, KeyboardInterrupt):
        return False


async def run_task(
    prompt: str, 
    headless: bool = False,
    record_video: bool = False,
    video_dir: Optional[str] = None,
    screenshots_dir: Optional[str] = None
) -> str:
    """
    Run a browser automation task with enhanced error handling.
    
    Args:
        prompt: Task description for the agent
        headless: Whether to run in headless mode
        record_video: Whether to record video of the session (not implemented)
        video_dir: Directory to save video recordings (not implemented)
        screenshots_dir: Directory to save screenshots
        
    Returns:
        Task result output
    """
    logger.info("="*60)
    logger.info("Starting Browser Automation Task")
    logger.info("="*60)
    
    session = BrowserSession(headless, record_video=record_video, video_dir=video_dir)
    result: Optional[str] = None
    start_time = datetime.now()
    
    # Enable screenshots if directory provided
    if screenshots_dir:
        session.enable_screenshots(screenshots_dir)

    try:
        # Step 1: Initialize browser
        logger.info("🔄 Initializing browser...")
        session.start()
        logger.info("✅ Browser started")
        
        # Step 2: Configure session
        logger.info("🔄 Configuring browser session...")
        session.open_task_tab()
        if screenshots_dir:
            session.take_screenshot("task_start")
        logger.info("✅ Session configured")

        # Step 3: Execute task
        logger.info(f"🔄 Running task: {prompt[:50]}...")
        if screenshots_dir:
            session.take_screenshot("before_execution")
        
        result = await run_with_screenshot(prompt, deps=BrowserDeps(headless=headless))
        
        if screenshots_dir:
            session.take_screenshot("after_execution")

        if result:
            logger.info("✅ Task completed successfully")
        else:
            logger.warning("⚠️  Task completed but returned no output")

        # Step 4: Cleanup
        logger.info("🔄 Cleaning up browser session...")
        if screenshots_dir:
            session.take_screenshot("task_complete")
        
        if _should_keep_browser_open(headless):
            session.keep_open()
            logger.info("✅ Browser left open for inspection")
        else:
            session.close()
            logger.info("✅ Browser closed")

        # Print summary
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("="*60)
        logger.info(f"✅ Task completed in {elapsed:.1f}s")
        logger.info("="*60)

        if result:
            print(f"\n{'='*60}")
            print("🎉 TASK COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}")
            
            if screenshots_dir:
                print(f"\n📸 Screenshots saved to: {screenshots_dir}")

        return result or "Task completed but no output generated"

    except Exception as e:
        logger.error(f"❌ Task execution failed: {e}")
        
        # Take error screenshot
        if screenshots_dir:
            session.take_screenshot("error_state")
        
        session.close(force=True)
        raise

    finally:
        session.close(force=False)


async def run_task_with_context(
    prompt: str,
    starting_url: Optional[str] = None,
    headless: bool = False,
    **kwargs
) -> str:
    """
    Run a browser automation task with an optional starting URL.
    
    Args:
        prompt: Task description for the agent
        starting_url: Initial URL to navigate to before starting task
        headless: Whether to run in headless mode
        **kwargs: Additional arguments passed to run_task
        
    Returns:
        Task result output
    """
    # If starting URL provided, prepend navigation instruction
    if starting_url:
        enhanced_prompt = f"First, navigate to {starting_url}. Then, {prompt}"
        logger.info(f"Enhanced prompt with starting URL: {starting_url}")
        return await run_task(enhanced_prompt, headless=headless, **kwargs)
    else:
        return await run_task(prompt, headless=headless, **kwargs)
