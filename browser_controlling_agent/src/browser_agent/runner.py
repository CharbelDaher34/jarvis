from __future__ import annotations

import logging
import asyncio
from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime

import helium
from selenium import webdriver
## Go into the directory browser_controlling_agent/ path


from src.browser_agent.config import load_config
from src.browser_agent.error_handling import BrowserConnectionError, safe_execute
from src.browser_agent.utils import (
    configure_logger, 
    NotificationManager, 
    MessageType, 
    TaskStatus,
    format_time_elapsed
)

# Setup logging with enhanced configuration
configure_logger()
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
        self._screenshots_dir: Optional[str] = None
        self._take_screenshots = False
        self._status = TaskStatus.PENDING
        
        # Initialize notification manager
        self.notification_manager = NotificationManager()
        
        # Set video directory with proper path handling and creation
        self.set_video_dir(video_dir)
    
    def set_video_dir(self, video_dir: Optional[str] = None) -> None:
        """Set video directory, creating it if it doesn't exist."""
        if not video_dir:
            video_dir = str(Path.cwd() / "videos")
        
        # Ensure the path is absolute
        video_dir = str(Path(video_dir).resolve())
        
        # Create directory if it doesn't exist
        Path(video_dir).mkdir(parents=True, exist_ok=True)
        
        self._video_dir = video_dir
        logger.debug(f"Video directory set to: {video_dir}")
    
    def get_video_dir(self) -> str:
        """Get the video directory path."""
        return self._video_dir
    
    def set_video_recording(self, record_video: bool) -> None:
        """Enable or disable video recording."""
        self._record_video = record_video
        logger.debug(f"Video recording {'enabled' if record_video else 'disabled'}")
    
    def get_video_recording(self) -> bool:
        """Check if video recording is enabled."""
        return self._record_video

    def set_screenshots_dir(self, screenshots_dir: str) -> None:
        """
        Set the directory for saving screenshots, creating it if it doesn't exist.
        
        Args:
            screenshots_dir (str): Path to the screenshots directory
        """
        if not screenshots_dir:
            # If no directory specified, create a 'screenshots' directory in current working directory
            screenshots_dir = str(Path.cwd() / "screenshots")
        
        # Ensure the path is absolute
        screenshots_dir = str(Path(screenshots_dir).resolve())
        
        # Create the directory if it doesn't exist
        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
        
        self._screenshots_dir = screenshots_dir
        logger.debug(f"Screenshots directory set to: {screenshots_dir}")
    
    def get_screenshots_dir(self) -> Optional[str]:
        """Get the screenshots directory path."""
        return self._screenshots_dir
    
    def set_take_screenshots(self, take_screenshots: bool) -> None:
        """Enable or disable screenshot taking."""
        self._take_screenshots = take_screenshots
        logger.debug(f"Screenshot taking {'enabled' if take_screenshots else 'disabled'}")
    
    def get_take_screenshots(self) -> bool:
        """Check if screenshot taking is enabled."""
        return self._take_screenshots
    
    def enable_screenshots(self, screenshots_dir: str) -> None:
        """Enable screenshot taking and set directory."""
        self.set_take_screenshots(True)
        self.set_screenshots_dir(screenshots_dir)
        logger.info(f"Screenshots enabled in directory: {screenshots_dir}")

    def start(self) -> None:
        """Start the browser session."""
        self._status = TaskStatus.RUNNING
        self.notification_manager.notify("Starting browser session", MessageType.INFO.value)
        _, started_new = _start_browser(self.headless)
        self._active = True
        self._owns_browser = started_new
        self.notification_manager.notify("Browser session started", MessageType.SUCCESS.value)

    def keep_open(self) -> None:
        self._keep_open = True

    def close(self, force: bool = False) -> None:
        """
        Close browser session with proper cleanup.
        
        Args:
            force: Force close even if keep_open flag is set
        """
        should_cleanup = force or not self._keep_open

        if should_cleanup and self._task_handle:
            _close_owned_tab(self._task_handle)
            self._task_handle = None

        if self._active and should_cleanup:
            if self._owns_browser:
                self.notification_manager.notify("Closing browser", MessageType.INFO.value)
                _stop_browser()
            else:
                logger.info("Leaving shared browser session running")
        self._active = False
        
    def get_current_url(self) -> Optional[str]:
        """
        Get the current URL of the active browser page.
        
        Returns:
            Current URL or None if unable to access
        """
        try:
            driver = helium.get_driver()
            if driver:
                return driver.current_url
        except Exception as e:
            logger.debug(f"Unable to get current URL: {e}")
        return None

    def open_task_tab(self) -> None:
        handle = _open_new_tab()
        if handle:
            self._task_handle = handle
        else:
            logger.warning("Unable to open dedicated task tab; continuing in current tab")

    def take_screenshot(self, name: str, page_title: Optional[str] = None, include_timestamp: bool = True) -> Optional[str]:
        """
        Take a screenshot and save it to the screenshots directory.
        
        Args:
            name: Base name for the screenshot file
            page_title: Optional page title (not used in Selenium implementation)
            include_timestamp: Whether to include timestamp in filename
            
        Returns:
            Path to saved screenshot or None if screenshots disabled
        """
        if not self._take_screenshots or not self._screenshots_dir:
            return None
        
        try:
            driver = helium.get_driver()
            
            # Build filename with optional timestamp
            screenshot_name = name
            if include_timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_name = f"{timestamp}_{screenshot_name}"
            screenshot_name += ".png"
            
            # Use Path for proper path handling
            filepath = Path(self._screenshots_dir) / screenshot_name
            
            driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to take screenshot '{name}': {e}")
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
    """
    Start Chrome browser with enhanced configuration and error handling.
    
    Returns:
        Tuple of (driver, started_new_browser)
    """
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
        chrome_options.add_argument("--disable-session-crashed-bubble")  # Disable restore session bubble
        chrome_options.add_argument("--disable-infobars")  # Disable informational popups
        
        # Experimental options to make browser less detectable
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Optional: Disable images for faster loading
        if hasattr(config.browser, 'disable_images') and config.browser.disable_images:
            prefs = {"profile.managed_default_content_settings.images": 2}
            chrome_options.add_experimental_option("prefs", prefs)
            logger.info("Images disabled for faster loading")
        
        # Optional: Custom user agent
        if hasattr(config.browser, 'user_agent') and config.browser.user_agent:
            chrome_options.add_argument(f"--user-agent={config.browser.user_agent}")
        
        # Optional: Download directory
        if hasattr(config.browser, 'download_directory') and config.browser.download_directory:
            prefs = {
                "download.default_directory": config.browser.download_directory,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False
            }
            chrome_options.add_experimental_option("prefs", prefs)
            logger.info(f"Download directory set to: {config.browser.download_directory}")
        
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
            try:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": driver.execute_script("return navigator.userAgent").replace('Headless', '')
                })
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception as e:
                logger.debug(f"Could not apply stealth settings: {e}")
            
            # Navigate to Google as the default homepage
            try:
                driver.get("https://www.google.com")
                logger.info("Browser opened at https://www.google.com")
            except Exception as e:
                logger.warning(f"Could not navigate to Google homepage: {e}")
            
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
    """
    Close a specific browser tab by handle.
    
    Args:
        handle: Window handle of the tab to close
    """
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
            logger.debug(f"Closed tab with handle {handle}")
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
    record_video: bool = True,
    video_dir: Optional[str] = "videos",
    screenshots_dir: Optional[str] = "screenshots",
    starting_url: Optional[str] = None,
    notification_callback: Optional[callable] = None,
    use_multi_agent: bool = False,
    max_iterations: int = 20
) -> str:
    """
    Run a browser automation task with enhanced error handling.
    
    Args:
        prompt: Task description for the agent
        headless: Whether to run in headless mode
        record_video: Whether to record video of the session (not implemented)
        video_dir: Directory to save video recordings (not implemented)
        screenshots_dir: Directory to save screenshots
        starting_url: Optional initial URL to navigate to before starting task
        notification_callback: Optional callback for task progress notifications
        use_multi_agent: Whether to use multi-agent system (Planner->Browser->Critique) or single browser agent
        max_iterations: Maximum iterations for multi-agent mode (only used if use_multi_agent=True)
        
    Returns:
        Task result output
    """
    logger.info("="*60)
    logger.info("Starting Browser Automation Task")
    logger.info("="*60)
    
    # Log execution mode
    if use_multi_agent:
        logger.info("🎭 Using Multi-Agent System (Planner->Browser->Critique)")
    else:
        logger.info("🤖 Using Single Browser Agent")
    
    # Import orchestrator
    from src.browser_agent.orchestrator import run_with_orchestrator
    
    # Enhance prompt with starting URL if provided
    if starting_url:
        prompt = f"First, navigate to {starting_url}. Then, {prompt}"
        logger.info(f"Task will start at URL: {starting_url}")
    
    # Start browser session
    session = BrowserSession(headless, record_video=record_video, video_dir=video_dir)
    
    # Register notification callback if provided
    if notification_callback:
        session.notification_manager.register_listener(notification_callback)
    
    result: Optional[str] = None
    start_time = datetime.now()
    
    # Enable screenshots if directory provided
    if screenshots_dir:
        session.enable_screenshots(screenshots_dir)

    try:
        # Step 1: Initialize browser
        logger.info("🔄 Initializing browser...")
        session.notification_manager.notify("Initializing browser...", MessageType.STEP.value)
        session.start()
        logger.info("✅ Browser started")
        
        # Step 2: Configure session
        logger.info("🔄 Configuring browser session...")
        session.notification_manager.notify("Configuring browser session...", MessageType.STEP.value)
        session.open_task_tab()
        screenshot_path = session.take_screenshot("task_start")
        if screenshot_path:
            logger.debug(f"Task start screenshot: {screenshot_path}")
        logger.info("✅ Session configured")

        # Step 3: Execute task via orchestrator
        logger.info(f"🔄 Running task: {prompt[:100]}...")
        session.notification_manager.notify(f"Executing task: {prompt[:50]}...", MessageType.STEP.value)
        session.take_screenshot("before_execution")
        
        # Always use orchestrator - it decides between multi-agent or single agent
        result = await run_with_orchestrator(
            prompt=prompt,
            headless=headless,
            max_iterations=max_iterations,
            use_multi_agent=use_multi_agent,
            notification_callback=notification_callback
        )
        
        session.take_screenshot("after_execution")

        if result:
            logger.info("✅ Task completed successfully")
            session.notification_manager.notify("Task completed successfully", MessageType.SUCCESS.value)
        else:
            logger.warning("⚠️  Task completed but returned no output")
            session.notification_manager.notify("Task completed with no output", MessageType.WARNING.value)

        # Step 4: Cleanup
        logger.info("🔄 Cleaning up browser session...")
        session.take_screenshot("task_complete")
        
        # Log final URL
        final_url = session.get_current_url()
        if final_url:
            logger.info(f"Final URL: {final_url}")
        
        if _should_keep_browser_open(headless):
            session.keep_open()
            logger.info("✅ Browser left open for inspection")
        else:
            session.close()
            logger.info("✅ Browser closed")

        # Print summary
        elapsed = (datetime.now() - start_time).total_seconds()
        elapsed_str = format_time_elapsed(elapsed)
        logger.info("="*60)
        logger.info(f"✅ Task completed in {elapsed_str}")
        logger.info("="*60)

        if result:
            print(f"\n{'='*60}")
            print("🎉 TASK COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}")
            print(f"⏱️  Duration: {elapsed_str}")
            
            if screenshots_dir:
                print(f"📸 Screenshots saved to: {screenshots_dir}")
            if final_url:
                print(f"🌐 Final URL: {final_url}")
        
        session.notification_manager.notify(
            f"Task completed in {elapsed_str}", 
            MessageType.DONE.value
        )

        return result or "Task completed but no output generated"

    except KeyboardInterrupt:
        logger.warning("⚠️  Task interrupted by user")
        session.notification_manager.notify("Task interrupted by user", MessageType.WARNING.value)
        session.take_screenshot("interrupted")
        session.close(force=True)
        raise
    except Exception as e:
        logger.error(f"❌ Task execution failed: {e}")
        session.notification_manager.notify(f"Task failed: {str(e)}", MessageType.ERROR.value)
        
        # Take error screenshot
        session.take_screenshot("error_state")
        
        session.close(force=True)
        raise

    finally:
        # Ensure cleanup happens
        if session._active:
            session.close(force=False)


