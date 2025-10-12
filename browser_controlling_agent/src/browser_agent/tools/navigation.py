"""
Navigation Tools

Functions for browser navigation (URLs, back button, page loads).
"""

from __future__ import annotations
import logging
from typing import Optional
from urllib.parse import urlparse

from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import (
    NavigationError, PageLoadError, validate_url, with_retry, RetryConfig
)
from src.browser_agent.config import load_config
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


@with_retry(RetryConfig(max_attempts=2, base_delay=1.0), (Exception,), logger)
def go_back() -> str:
    """
    Goes back to the previous page in browser history.
    
    Returns:
        Success message with current URL
        
    Raises:
        NavigationError: If navigation fails
    """
    try:
        driver = get_driver()
        
        # Store current URL for comparison
        current_url = driver.current_url
        
        driver.back()
        
        # Check if we actually went back
        new_url = driver.current_url
        if new_url == current_url:
            logger.warning("Browser back operation may not have changed page")
        
        return f"Went back from {current_url} to {new_url}"
        
    except Exception as e:
        raise NavigationError(f"Failed to go back: {str(e)}")


def navigate_to_url(url: str, wait_for_load: bool = True, timeout: int = 30) -> str:
    """
    Navigate to a specified URL with optional wait for page load.
    
    Args:
        url: The URL to navigate to (protocol is auto-added if missing)
        wait_for_load: Whether to wait for page to fully load
        timeout: Maximum time to wait for page load in seconds
        
    Returns:
        Description of navigation result with page title
        
    Raises:
        NavigationError: If navigation fails
        PageLoadError: If page fails to load within timeout
    """
    try:
        driver = get_driver()
        
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            logger.info(f"Added https:// protocol to URL: {url}")
        
        # Validate URL
        is_valid, error = validate_url(url)
        if not is_valid:
            raise NavigationError(f"Invalid URL: {error}")
        
        # Check security config
        config = load_config()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        if any(blocked in domain for blocked in config.security.blocked_domains):
            raise NavigationError(f"Domain {domain} is blocked by security policy")
        
        # Navigate to URL
        logger.info(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for page load if requested
        if wait_for_load:
            try:
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                logger.warning(f"Page load timeout after {timeout}s, continuing anyway")
        
        # Get page info
        current_url = driver.current_url
        title = driver.title
        
        result = f"Navigated to {current_url}"
        if title:
            result += f" - Title: {title}"
        
        logger.info(result)
        return result
        
    except NavigationError:
        raise
    except Exception as e:
        raise NavigationError(f"Failed to navigate to {url}: {str(e)}")


def wait_for_page_load(timeout: int = 30) -> bool:
    """
    Wait for the page to finish loading.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if page loaded successfully, False if timeout
    """
    try:
        driver = get_driver()
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.info("Page loaded successfully")
        return True
    except TimeoutException:
        logger.warning(f"Page load timeout after {timeout}s")
        return False
    except Exception as e:
        logger.error(f"Error waiting for page load: {e}")
        return False
