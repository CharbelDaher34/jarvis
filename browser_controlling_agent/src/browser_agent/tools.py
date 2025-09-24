from __future__ import annotations

import logging
from time import sleep
from typing import Optional, List
from urllib.parse import urlparse

import helium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

from src.browser_agent.error_handling import (
    BrowserConnectionError, PageLoadError, ElementNotFoundError, 
    SearchError, NavigationError, validate_url, with_retry, 
    RetryConfig, safe_execute, TimeoutManager
)
from src.browser_agent.config import load_config

# Setup logging
logger = logging.getLogger(__name__)


@with_retry(RetryConfig(max_attempts=3, base_delay=2.0), (Exception,), logger)
def google_search(query: str, num_results: int = 5) -> List[str]:
    """
    Performs a Google search for the input query and returns a list of URLs.
    
    Args:
        query: The search query string
        num_results: Number of results to return (default: 5)
        
    Returns:
        List of URLs from the search results
        
    Raises:
        SearchError: If search fails after retries
    """
    if not query or not query.strip():
        raise SearchError("Search query cannot be empty")
    
    config = load_config()
    
    try:
        with TimeoutManager(config.search.search_timeout, "Google search"):
            from googlesearch import search
            
            urls = []
            # Limit results to prevent excessive API calls
            max_results = min(num_results, config.search.max_results_per_search)
            
            for url in search(query, num_results=max_results, stop=max_results, unique=True):
                # Validate each URL before adding
                is_valid, error = validate_url(url)
                if is_valid:
                    # Check against security config
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.lower()
                    
                    # Check blocked domains
                    if any(blocked in domain for blocked in config.security.blocked_domains):
                        logger.warning(f"Skipping blocked domain: {domain}")
                        continue
                    
                    # Check allowed domains (if configured)
                    if config.security.allowed_domains:
                        if not any(allowed in domain for allowed in config.security.allowed_domains):
                            logger.warning(f"Skipping non-allowed domain: {domain}")
                            continue
                    
                    urls.append(url)
                else:
                    logger.warning(f"Skipping invalid URL: {url} ({error})")
            
            logger.info(f"Google search for '{query}' returned {len(urls)} valid results.")
            return urls
            
    except ImportError:
        raise SearchError("googlesearch-python package not installed")
    except Exception as e:
        raise SearchError(f"Google search failed: {str(e)}")

def get_driver() -> webdriver.Chrome:
    """
    Get the current browser driver instance.
    
    Returns:
        Chrome WebDriver instance
        
    Raises:
        BrowserConnectionError: If driver is not available
    """
    try:
        driver = helium.get_driver()
        if not driver:
            raise BrowserConnectionError("Browser driver is not initialized")
        return driver
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get browser driver: {str(e)}")


def search_item_ctrl_f(text: str, nth_result: int = 1) -> str:
    """
    Searches for text on the current page and jumps to the nth occurrence.
    
    Args:
        text: The text to search for
        nth_result: Which occurrence to jump to (default: 1)
        
    Returns:
        Description of search results and focused element
        
    Raises:
        ElementNotFoundError: If no matches found
        BrowserConnectionError: If driver is not available
    """
    if not text or not text.strip():
        raise ElementNotFoundError("Search text cannot be empty")
    
    logger.info(f"Searching for '{text}', occurrence {nth_result}...")
    
    try:
        driver = get_driver()
        
        # Use WebDriverWait for better reliability
        wait = WebDriverWait(driver, 10)
        
        # Try multiple XPath strategies for better element detection
        xpath_strategies = [
            f"//*[contains(text(), '{text}')]",
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
            f"//*[@*[contains(., '{text}')]]"
        ]
        
        elements = []
        for xpath in xpath_strategies:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                if elements:
                    break
            except Exception as e:
                logger.debug(f"XPath strategy failed: {xpath} - {e}")
        
        if not elements:
            raise ElementNotFoundError(f"No matches found for '{text}' on current page")
        
        # Validate nth_result
        if nth_result < 1:
            nth_result = 1
        elif nth_result > len(elements):
            logger.warning(f"Requested occurrence {nth_result} exceeds found matches {len(elements)}, using last match")
            nth_result = len(elements)
        
        # Get the target element
        target_element = elements[nth_result - 1]
        
        # Scroll element into view with error handling
        result, error = safe_execute(
            lambda: driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target_element),
            error_message="Failed to scroll element into view"
        )
        
        if error:
            logger.warning(f"Could not scroll to element: {error}")
        
        # Highlight the element briefly for better user feedback
        try:
            driver.execute_script(
                "arguments[0].style.border='3px solid red';"
                "setTimeout(function() { arguments[0].style.border=''; }, 2000);", 
                target_element
            )
        except Exception as e:
            logger.debug(f"Could not highlight element: {e}")
        
        # Build detailed response
        result_text = f"Found {len(elements)} matches for '{text}'. Focused on element {nth_result} of {len(elements)}"
        
        # Get element context
        element_text = target_element.text.strip()
        if element_text:
            # Truncate long text for readability
            if len(element_text) > 100:
                element_text = element_text[:97] + "..."
            result_text += f". Element text: '{element_text}'"
        
        # Add element type and attributes for context
        tag_name = target_element.tag_name
        result_text += f". Element type: {tag_name}"
        
        # Get useful attributes
        useful_attrs = ['id', 'class', 'href', 'title', 'alt']
        attrs = []
        for attr in useful_attrs:
            value = target_element.get_attribute(attr)
            if value:
                attrs.append(f"{attr}='{value}'")
        
        if attrs:
            result_text += f". Attributes: {', '.join(attrs)}"
        
        return result_text
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        raise BrowserConnectionError(f"Search operation failed: {str(e)}")

@with_retry(RetryConfig(max_attempts=2, base_delay=1.0), (WebDriverException,), logger)
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
        
        # Wait briefly for navigation
        sleep(1)
        
        # Check if we actually went back
        new_url = driver.current_url
        if new_url == current_url:
            logger.warning("Browser back operation may not have changed page")
        
        return f"Went back from {current_url} to {new_url}"
        
    except Exception as e:
        raise NavigationError(f"Failed to go back: {str(e)}")


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
            sleep(0.5)  # Brief pause between attempts
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
                        sleep(0.3)
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
                        sleep(0.3)
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
        
        # Brief pause for dynamic content
        sleep(1.0)
        
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


def smart_click(text_or_selector: str, timeout: int = 10) -> str:
    """
    Intelligent click function that tries multiple strategies.
    
    Args:
        text_or_selector: Text content or CSS selector
        timeout: Maximum time to wait for element
        
    Returns:
        Description of click action taken
        
    Raises:
        ElementNotFoundError: If element cannot be found or clicked
    """
    try:
        driver = get_driver()
        wait = WebDriverWait(driver, timeout)
        
        # Strategy 1: Try as helium text-based click
        try:
            import helium
            if helium.Text(text_or_selector).exists():
                helium.click(text_or_selector)
                return f"Clicked text element: '{text_or_selector}'"
        except Exception as e:
            logger.debug(f"Helium text click failed: {e}")
        
        # Strategy 2: Try as CSS selector
        try:
            element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, text_or_selector)))
            element.click()
            return f"Clicked CSS selector: '{text_or_selector}'"
        except Exception as e:
            logger.debug(f"CSS selector click failed: {e}")
        
        # Strategy 3: Try as XPath with text content
        try:
            xpath = f"//*[contains(text(), '{text_or_selector}')]"
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            element.click()
            return f"Clicked XPath text match: '{text_or_selector}'"
        except Exception as e:
            logger.debug(f"XPath text click failed: {e}")
        
        # Strategy 4: Try partial text match
        try:
            xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_or_selector.lower()}')]"
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            element.click()
            return f"Clicked partial text match: '{text_or_selector}'"
        except Exception as e:
            logger.debug(f"Partial text match click failed: {e}")
        
        raise ElementNotFoundError(f"Could not find or click element: '{text_or_selector}'")
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        raise BrowserConnectionError(f"Click operation failed: {str(e)}")

