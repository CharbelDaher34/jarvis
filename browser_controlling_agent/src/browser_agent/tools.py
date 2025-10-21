from __future__ import annotations

import logging
from time import sleep
from typing import Optional, List, Tuple
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
from src.browser_agent.utils import (
    configure_logger,
    format_error_message,
    sanitize_selector,
    truncate_text,
    format_time_elapsed
)

# Setup logging
configure_logger()
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
        #sleep(1)
        
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
            #sleep(0.5)  # Brief pause between attempts
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
                        #sleep(0.3)
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
                        #sleep(0.3)
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
        #sleep(1.0)
        
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
    Enhanced with better element detection and interaction patterns.
    
    Args:
        text_or_selector: Text content or CSS selector
        timeout: Maximum time to wait for element
        
    Returns:
        Description of click action taken
        
    Raises:
        ElementNotFoundError: If element cannot be found or clicked
    """
    import time
    start_time = time.time()
    
    try:
        driver = get_driver()
        wait = WebDriverWait(driver, timeout)
        element = None
        strategy_used = ""
        
        # Strategy 1: Try as CSS selector
        if any(char in text_or_selector for char in ['.', '#', '[', ']', '>']):
            try:
                sanitized = sanitize_selector(text_or_selector)
                element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sanitized)))
                strategy_used = f"CSS selector '{truncate_text(text_or_selector, 50)}'"
                logger.debug(f"Found element using CSS selector: {text_or_selector}")
            except TimeoutException:
                pass
        
        # Strategy 2: Try exact text match
        if not element:
            try:
                xpath = f"//*[normalize-space(text())='{text_or_selector}']"
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                strategy_used = f"exact text '{truncate_text(text_or_selector, 50)}'"
                logger.debug(f"Found element using exact text: {text_or_selector}")
            except TimeoutException:
                pass
        
        # Strategy 3: Try partial text match
        if not element:
            try:
                xpath = f"//*[contains(text(), '{text_or_selector}')]"
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                strategy_used = f"partial text '{truncate_text(text_or_selector, 50)}'"
                logger.debug(f"Found element using partial text: {text_or_selector}")
            except TimeoutException:
                pass
        
        # Strategy 4: Try as link text
        if not element:
            try:
                element = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, text_or_selector)))
                strategy_used = f"link text '{truncate_text(text_or_selector, 50)}'"
                logger.debug(f"Found element using link text: {text_or_selector}")
            except TimeoutException:
                pass
        
        # Strategy 5: Try attributes (aria-label, title, etc.)
        if not element:
            for attr in ['aria-label', 'title', 'alt', 'placeholder']:
                try:
                    xpath = f"//*[@{attr}='{text_or_selector}']"
                    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    strategy_used = f"{attr} attribute '{truncate_text(text_or_selector, 50)}'"
                    logger.debug(f"Found element using {attr}: {text_or_selector}")
                    break
                except TimeoutException:
                    continue
        
        if not element:
            raise ElementNotFoundError(
                f"Could not find clickable element with text or selector: '{text_or_selector}'"
            )
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        sleep(0.3)
        
        # Try multiple click methods
        click_successful = False
        
        # Method 1: Standard click
        try:
            element.click()
            click_successful = True
        except Exception:
            pass
        
        # Method 2: JavaScript click
        if not click_successful:
            try:
                driver.execute_script("arguments[0].click();", element)
                click_successful = True
            except Exception:
                pass
        
        # Method 3: Actions click
        if not click_successful:
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).move_to_element(element).click().perform()
                click_successful = True
            except Exception:
                pass
        
        if not click_successful:
            raise ElementNotFoundError(f"Found element but could not click it: '{text_or_selector}'")
        
        elapsed = time.time() - start_time
        elapsed_str = format_time_elapsed(elapsed)
        
        result = f"Successfully clicked element using {strategy_used} ({elapsed_str})"
        logger.info(result)
        return result
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        error_msg = format_error_message(e, f"clicking on '{text_or_selector}'")
        logger.error(error_msg)
        raise ElementNotFoundError(error_msg)
        driver = get_driver()
        wait = WebDriverWait(driver, timeout)
        
        element = None
        strategy_used = None
        
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
            strategy_used = "CSS selector"
        except Exception as e:
            logger.debug(f"CSS selector click failed: {e}")
        
        # Strategy 3: Try as XPath with text content
        if not element:
            try:
                xpath = f"//*[contains(text(), '{text_or_selector}')]"
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                strategy_used = "XPath text match"
            except Exception as e:
                logger.debug(f"XPath text click failed: {e}")
        
        # Strategy 4: Try partial text match (case-insensitive)
        if not element:
            try:
                xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_or_selector.lower()}')]"
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                strategy_used = "Partial text match"
            except Exception as e:
                logger.debug(f"Partial text match click failed: {e}")
        
        if not element:
            raise ElementNotFoundError(f"Could not find element: '{text_or_selector}'")
        
        # Scroll element into view before clicking
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            sleep(0.3)
        except Exception as e:
            logger.debug(f"Could not scroll to element: {e}")
        
        # Try standard click first
        try:
            element.click()
            return f"Clicked {strategy_used}: '{text_or_selector}'"
        except Exception as click_error:
            logger.debug(f"Standard click failed: {click_error}, trying JavaScript click")
            
            # Fallback to JavaScript click
            try:
                driver.execute_script("arguments[0].click();", element)
                return f"Clicked {strategy_used} (JavaScript): '{text_or_selector}'"
            except Exception as js_error:
                logger.error(f"JavaScript click also failed: {js_error}")
                raise ElementNotFoundError(f"Could not click element: '{text_or_selector}'")
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        raise BrowserConnectionError(f"Click operation failed: {str(e)}")


def enter_text(selector: str, text: str, clear_first: bool = True, use_keyboard: bool = False) -> str:
    """
    Enter text into an element identified by selector.
    Enhanced with multiple input strategies.
    
    Args:
        selector: CSS selector for the target element
        text: Text to enter
        clear_first: Whether to clear existing text first
        use_keyboard: Whether to simulate keyboard typing
        
    Returns:
        Description of the action taken
        
    Raises:
        ElementNotFoundError: If element cannot be found
        BrowserConnectionError: If text entry fails
    """
    try:
        driver = get_driver()
        wait = WebDriverWait(driver, 10)
        
        # Wait for element to be present and interactable
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        
        # Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        sleep(0.2)
        
        # Clear existing text if requested
        if clear_first:
            try:
                element.clear()
            except Exception as e:
                logger.debug(f"Could not clear element using .clear(): {e}, trying selection + delete")
                try:
                    element.click()
                    element.send_keys(Keys.CONTROL + "a")
                    element.send_keys(Keys.BACKSPACE)
                except Exception as clear_error:
                    logger.warning(f"Could not clear existing text: {clear_error}")
        
        # Focus on the element
        element.click()
        sleep(0.1)
        
        # Enter text based on strategy
        if use_keyboard:
            # Simulate keyboard typing with delay
            for char in text:
                element.send_keys(char)
                sleep(0.01)  # Small delay between characters for realism
        else:
            # Standard send_keys
            element.send_keys(text)
        
        # Get element info for response
        tag_name = element.tag_name
        element_id = element.get_attribute('id') or 'no id'
        
        logger.info(f"Successfully entered text '{text}' into {tag_name} element with selector '{selector}'")
        return f"Success: Entered text '{text}' into {tag_name} element (id: {element_id})"
        
    except TimeoutException:
        raise ElementNotFoundError(f"Element with selector '{selector}' not found within timeout")
    except Exception as e:
        raise BrowserConnectionError(f"Failed to enter text: {str(e)}")


def enter_text_and_click(
    text_selector: str, 
    text: str, 
    click_selector: Optional[str] = None,
    wait_before_click: float = 0.5
) -> str:
    """
    Enter text into an element and then click another element (or press Enter).
    
    Args:
        text_selector: CSS selector for text input element
        text: Text to enter
        click_selector: CSS selector for element to click (if None, presses Enter)
        wait_before_click: Wait time in seconds before clicking
        
    Returns:
        Description of actions taken
        
    Raises:
        ElementNotFoundError: If elements cannot be found
        BrowserConnectionError: If operation fails
    """
    try:
        # Enter the text
        enter_result = enter_text(text_selector, text, clear_first=True)
        
        # Wait before click if specified
        if wait_before_click > 0:
            sleep(wait_before_click)
        
        # If no click selector, just press Enter on the text field
        if click_selector is None or click_selector == text_selector:
            driver = get_driver()
            element = driver.find_element(By.CSS_SELECTOR, text_selector)
            element.send_keys(Keys.RETURN)
            return f"{enter_result}. Then pressed Enter."
        
        # Otherwise, click the specified element
        click_result = smart_click(click_selector)
        return f"{enter_result}. {click_result}"
        
    except Exception as e:
        raise BrowserConnectionError(f"Enter text and click operation failed: {str(e)}")


def press_key_combination(key_combination: str) -> str:
    """
    Press a key combination (e.g., 'Control+C', 'Alt+Tab').
    
    Args:
        key_combination: Key combination string (keys separated by '+')
        
    Returns:
        Description of the action taken
        
    Raises:
        BrowserConnectionError: If key press fails
    """
    try:
        driver = get_driver()
        
        # Map common key names to Selenium Keys
        key_map = {
            'control': Keys.CONTROL,
            'ctrl': Keys.CONTROL,
            'alt': Keys.ALT,
            'shift': Keys.SHIFT,
            'enter': Keys.RETURN,
            'return': Keys.RETURN,
            'tab': Keys.TAB,
            'escape': Keys.ESCAPE,
            'esc': Keys.ESCAPE,
            'pagedown': Keys.PAGE_DOWN,
            'pageup': Keys.PAGE_UP,
            'home': Keys.HOME,
            'end': Keys.END,
            'delete': Keys.DELETE,
            'backspace': Keys.BACK_SPACE,
        }
        
        # Split the combination
        keys = [k.strip().lower() for k in key_combination.split('+')]
        
        # Get the active element or body
        try:
            active_element = driver.switch_to.active_element
        except Exception:
            active_element = driver.find_element(By.TAG_NAME, 'body')
        
        # Build the key combination
        selenium_keys = []
        for key in keys:
            if key in key_map:
                selenium_keys.append(key_map[key])
            else:
                # For regular characters
                selenium_keys.append(key)
        
        # Press the combination
        if len(selenium_keys) == 1:
            active_element.send_keys(selenium_keys[0])
        else:
            # For combinations, use ActionChains
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            
            # Hold down modifier keys
            for key in selenium_keys[:-1]:
                actions = actions.key_down(key)
            
            # Press the final key
            actions = actions.send_keys(selenium_keys[-1])
            
            # Release modifier keys
            for key in selenium_keys[:-1]:
                actions = actions.key_up(key)
            
            actions.perform()
        
        logger.info(f"Successfully pressed key combination: {key_combination}")
        return f"Pressed key combination: {key_combination}"
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to press key combination '{key_combination}': {str(e)}")


def get_page_text(include_alt_text: bool = True) -> str:
    """
    Get all visible text content from the current page.
    
    Args:
        include_alt_text: Whether to include alt text from images
        
    Returns:
        Text content of the page
        
    Raises:
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        
        # Get body text
        try:
            body_text = driver.find_element(By.TAG_NAME, 'body').text
        except Exception:
            body_text = ""
        
        # Get alt text from images if requested
        alt_texts = []
        if include_alt_text:
            try:
                images = driver.find_elements(By.TAG_NAME, 'img')
                alt_texts = [img.get_attribute('alt') for img in images if img.get_attribute('alt')]
            except Exception as e:
                logger.debug(f"Could not extract alt texts: {e}")
        
        result = body_text
        if alt_texts:
            result += "\n\nImage Alt Texts: " + " | ".join(alt_texts)
        
        logger.info(f"Extracted {len(body_text)} characters of text from page")
        return result
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get page text: {str(e)}")


def get_page_info() -> dict:
    """
    Get comprehensive information about the current page.
    
    Returns:
        Dictionary containing page URL, title, and other metadata
        
    Raises:
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        
        info = {
            'url': driver.current_url,
            'title': driver.title,
            'ready_state': driver.execute_script("return document.readyState"),
        }
        
        # Try to get additional info
        try:
            info['viewport_width'] = driver.execute_script("return window.innerWidth")
            info['viewport_height'] = driver.execute_script("return window.innerHeight")
            info['scroll_height'] = driver.execute_script("return document.body.scrollHeight")
            info['scroll_position'] = driver.execute_script("return window.pageYOffset")
        except Exception as e:
            logger.debug(f"Could not get full page info: {e}")
        
        return info
        
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get page info: {str(e)}")


def scroll_page(direction: str = "down", amount: Optional[int] = None) -> str:
    """
    Scroll the page in the specified direction.
    
    Args:
        direction: 'down', 'up', 'top', or 'bottom'
        amount: Number of pixels to scroll (None for viewport height)
        
    Returns:
        Description of scroll action
        
    Raises:
        BrowserConnectionError: If scroll fails
    """
    try:
        driver = get_driver()
        
        if direction.lower() == 'top':
            driver.execute_script("window.scrollTo(0, 0);")
            return "Scrolled to top of page"
        elif direction.lower() == 'bottom':
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            return "Scrolled to bottom of page"
        else:
            # Get viewport height if amount not specified
            if amount is None:
                amount = driver.execute_script("return window.innerHeight")
            
            if direction.lower() == 'down':
                driver.execute_script(f"window.scrollBy(0, {amount});")
                return f"Scrolled down {amount}px"
            elif direction.lower() == 'up':
                driver.execute_script(f"window.scrollBy(0, -{amount});")
                return f"Scrolled up {amount}px"
            else:
                raise ValueError(f"Invalid direction: {direction}")
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to scroll page: {str(e)}")


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


def get_interactive_elements() -> List[dict]:
    """
    Get all interactive elements on the current page (buttons, links, inputs, etc.).
    
    Returns:
        List of dictionaries containing element information
        
    Raises:
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        
        # Interactive element selectors
        selectors = [
            'button',
            'a[href]',
            'input',
            'textarea',
            'select',
            '[role="button"]',
            '[onclick]',
            '[tabindex]'
        ]
        
        elements = []
        for selector in selectors:
            try:
                found_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in found_elements:
                    if elem.is_displayed():
                        element_info = {
                            'tag': elem.tag_name,
                            'text': elem.text[:100] if elem.text else '',
                            'id': elem.get_attribute('id') or '',
                            'class': elem.get_attribute('class') or '',
                            'type': elem.get_attribute('type') or '',
                            'href': elem.get_attribute('href') or '',
                            'visible': elem.is_displayed(),
                            'enabled': elem.is_enabled()
                        }
                        elements.append(element_info)
            except Exception as e:
                logger.debug(f"Could not process selector {selector}: {e}")
        
        logger.info(f"Found {len(elements)} interactive elements")
        return elements
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get interactive elements: {str(e)}")


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


def get_element_attribute(selector: str, attribute: str) -> Optional[str]:
    """
    Get a specific attribute value from an element.
    
    Args:
        selector: CSS selector for the element
        attribute: Attribute name to retrieve
        
    Returns:
        Attribute value or None if not found
        
    Raises:
        ElementNotFoundError: If element not found
        BrowserConnectionError: If operation fails
    """
    try:
        driver = get_driver()
        element = driver.find_element(By.CSS_SELECTOR, selector)
        
        if not element:
            raise ElementNotFoundError(f"Element with selector '{selector}' not found")
        
        value = element.get_attribute(attribute)
        logger.info(f"Got attribute '{attribute}' from element '{selector}': {value}")
        return value
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get element attribute: {str(e)}")


