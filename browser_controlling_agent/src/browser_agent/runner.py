from __future__ import annotations

import contextlib
import os
import logging
from typing import Optional

import helium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from src.browser_agent.agent import BrowserDeps, run_with_screenshot
from src.browser_agent.config import load_config
from src.browser_agent.user_experience import create_progress_tracker, logger, feedback
from src.browser_agent.error_handling import BrowserConnectionError, safe_execute


def _start_browser(headless: bool) -> None:
    """Start Chrome browser with enhanced configuration and error handling."""
    try:
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
            driver.set_page_load_timeout(config.browser.page_load_timeout)
            driver.implicitly_wait(config.browser.implicit_wait)
            logger.browser_action("Chrome browser started successfully")
        except Exception as e:
            raise BrowserConnectionError(f"Browser verification failed: {e}")
            
    except Exception as e:
        logger.error(f"Browser startup failed: {e}")
        raise


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


async def run_task(prompt: str, headless: bool = False) -> str:
    """
    Run a browser automation task with enhanced progress tracking and error handling.
    
    Args:
        prompt: Task description for the agent
        headless: Whether to run in headless mode
        
    Returns:
        Task result output
    """
    # Create progress tracker
    progress = create_progress_tracker("Browser Automation Task")
    
    # Add steps
    progress.add_step("init", "Initialize browser")
    progress.add_step("execute", "Execute automation task")  
    progress.add_step("cleanup", "Clean up resources")
    
    try:
        # Step 1: Initialize browser
        with progress.step("init", "Starting Chrome browser"):
            _start_browser(headless)
        
        # Step 2: Execute task
        with progress.step("execute", f"Running task: {prompt[:50]}..."):
            logger.user_action("Starting automation task", prompt)
            
            # Import helium to ensure it's available
            import helium  # noqa: F401
            
            result = await run_with_screenshot(prompt, deps=BrowserDeps(headless=headless))
            
            if result:
                logger.user_action("Task completed successfully")
                progress.complete_current_step(f"Generated {len(result)} characters of output")
            else:
                logger.warning("Task completed but returned no output")
                progress.complete_current_step("No output generated")
        
        # Step 3: Cleanup
        with progress.step("cleanup", "Cleaning up browser session"):
            # Ask user if they want to keep browser open for inspection
            if not headless:
                keep_open = feedback.confirm_action(
                    "Keep browser open for inspection?", 
                    default=False
                )
                
                if keep_open:
                    logger.info("Browser left open for inspection")
                    progress.skip_current_step("User chose to keep browser open")
                else:
                    _stop_browser()
                    progress.complete_current_step("Browser closed")
            else:
                _stop_browser()
                progress.complete_current_step("Headless browser closed")
        
        progress.finish(success=True)
        
        # Display final result
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
        
        # Emergency cleanup
        try:
            _stop_browser()
        except Exception as cleanup_error:
            logger.error(f"Emergency cleanup failed: {cleanup_error}")
        
        raise
    
    finally:
        # Ensure progress tracking is completed
        if not progress.end_time:
            progress.finish(success=False)
