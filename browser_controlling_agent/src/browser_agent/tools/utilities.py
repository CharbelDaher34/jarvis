"""
Utility Tools

Helper functions for screenshots, popups, frames, and JavaScript execution.
"""

from __future__ import annotations
import logging
from time import sleep
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import (
    BrowserConnectionError, ElementNotFoundError, TimeoutManager
)
from src.browser_agent.config import load_config
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


def close_popups() -> str:
    """
    Attempts to close visible modals or pop-ups using multiple strategies.
    
    Returns:
        Description of actions taken
    """
    try:
        driver = get_driver()
        actions_taken = []
        
        # Strategy 1: Send ESC key
        try:
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            actions_taken.append("Sent ESC key")
        except Exception as e:
            logger.debug(f"ESC key strategy failed: {e}")
        
        # Strategy 2: Look for common close button selectors
        close_selectors = [
            "button[aria-label*='close' i]",
            "button[title*='close' i]", 
            ".close",
            ".modal-close",
            "[role='button'][aria-label*='close' i]",
            "button:contains('✕')",
            "button:contains('×')",
            "button:contains('Close')"
        ]
        
        for selector in close_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        actions_taken.append(f"Clicked close button: {selector}")
                        break
            except Exception as e:
                logger.debug(f"Close button selector '{selector}' failed: {e}")
        
        # Strategy 3: Click outside modal areas (overlay click)
        try:
            overlay_selectors = [".modal-overlay", ".overlay", ".backdrop"]
            for selector in overlay_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        element.click()
                        actions_taken.append(f"Clicked overlay: {selector}")
                        break
        except Exception as e:
            logger.debug(f"Overlay click strategy failed: {e}")
        
        if not actions_taken:
            actions_taken.append("No popups detected or no action needed")
        
        result = "Popup close attempts: " + ", ".join(actions_taken)
        logger.info(result)
        return result
        
    except Exception as e:
        error_msg = f"Failed to close popups: {str(e)}"
        logger.error(error_msg)
        return error_msg


def capture_screenshot() -> Optional[bytes]:
    """
    Capture a screenshot as PNG bytes with enhanced error handling.
    
    Returns:
        PNG bytes of screenshot, or None if capture fails
    """
    config = load_config()
    
    if not config.enable_screenshots:
        logger.debug("Screenshots disabled in configuration")
        return None
    
    try:
        driver = get_driver()
        
        # Ensure page is fully loaded
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Capture screenshot with timeout
        with TimeoutManager(10.0, "Screenshot capture"):
            png_bytes = driver.get_screenshot_as_png()
            
        if png_bytes and len(png_bytes) > 0:
            logger.debug(f"Screenshot captured successfully ({len(png_bytes)} bytes)")
            return png_bytes
        else:
            logger.warning("Screenshot capture returned empty data")
            return None
            
    except TimeoutException:
        logger.error("Screenshot capture timed out")
        return None
    except Exception as e:
        logger.error(f"Screenshot capture failed: {str(e)}")
        return None


def highlight_element(selector: str, duration: float = 2.0, color: str = 'red') -> str:
    """
    Temporarily highlight an element on the page for visual feedback.
    
    Args:
        selector: CSS selector for the element to highlight
        duration: How long to highlight in seconds
        color: Border color for highlight
        
    Returns:
        Description of the action
        
    Raises:
        ElementNotFoundError: If element not found
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        element = driver.find_element(By.CSS_SELECTOR, selector)
        
        if not element:
            raise ElementNotFoundError(f"Element with selector '{selector}' not found")
        
        # Save original style
        original_style = element.get_attribute('style')
        
        # Apply highlight
        driver.execute_script(
            f"arguments[0].style.border='3px solid {color}';",
            element
        )
        
        # Wait for specified duration
        sleep(duration)
        
        # Restore original style
        if original_style:
            driver.execute_script(
                f"arguments[0].style = '{original_style}';",
                element
            )
        else:
            driver.execute_script(
                "arguments[0].style.border='';",
                element
            )
        
        logger.info(f"Highlighted element with selector: {selector}")
        return f"Highlighted element: {selector}"
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        raise BrowserConnectionError(f"Failed to highlight element: {str(e)}")


def execute_javascript(script: str, *args) -> any:
    """
    Execute arbitrary JavaScript in the current page context.
    
    Args:
        script: JavaScript code to execute
        *args: Arguments to pass to the script
        
    Returns:
        Result of the JavaScript execution
        
    Raises:
        BrowserConnectionError: If execution fails
    """
    try:
        driver = get_driver()
        result = driver.execute_script(script, *args)
        logger.debug(f"Executed JavaScript: {script[:100]}...")
        return result
    except Exception as e:
        raise BrowserConnectionError(f"Failed to execute JavaScript: {str(e)}")


def switch_to_frame(frame_reference: str | int) -> str:
    """
    Switch to an iframe on the page.
    
    Args:
        frame_reference: Frame name, ID, or index number
        
    Returns:
        Description of the action
        
    Raises:
        ElementNotFoundError: If frame not found
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        
        if isinstance(frame_reference, int):
            driver.switch_to.frame(frame_reference)
        else:
            # Try as name/ID first
            try:
                driver.switch_to.frame(frame_reference)
            except Exception:
                # Try as selector
                frame = driver.find_element(By.CSS_SELECTOR, frame_reference)
                driver.switch_to.frame(frame)
        
        logger.info(f"Switched to frame: {frame_reference}")
        return f"Switched to frame: {frame_reference}"
        
    except NoSuchElementException:
        raise ElementNotFoundError(f"Frame not found: {frame_reference}")
    except Exception as e:
        raise BrowserConnectionError(f"Failed to switch to frame: {str(e)}")


def switch_to_default_content() -> str:
    """
    Switch back to the main page content from an iframe.
    
    Returns:
        Description of the action
        
    Raises:
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        driver.switch_to.default_content()
        logger.info("Switched to default content")
        return "Switched to default content"
    except Exception as e:
        raise BrowserConnectionError(f"Failed to switch to default content: {str(e)}")


def wait_for_element(
    locator: tuple[str, str], 
    timeout: int = 10, 
    condition: str = "presence"
) -> bool:
    """
    Wait for an element to meet certain conditions.
    
    Args:
        locator: Tuple of (By type, locator string)
        timeout: Maximum time to wait in seconds
        condition: Condition to wait for ('presence', 'visible', 'clickable')
        
    Returns:
        True if condition met, False if timeout
    """
    try:
        from selenium.webdriver.support import expected_conditions as EC
        
        driver = get_driver()
        wait = WebDriverWait(driver, timeout)
        
        if condition == "presence":
            wait.until(EC.presence_of_element_located(locator))
        elif condition == "visible":
            wait.until(EC.visibility_of_element_located(locator))
        elif condition == "clickable":
            wait.until(EC.element_to_be_clickable(locator))
        else:
            raise ValueError(f"Unknown condition: {condition}")
        
        return True
        
    except TimeoutException:
        logger.warning(f"Element {locator} did not meet condition '{condition}' within {timeout}s")
        return False
    except Exception as e:
        logger.error(f"Error waiting for element {locator}: {str(e)}")
        return False
