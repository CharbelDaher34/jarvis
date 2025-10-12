"""
User Interaction Tools

Functions for clicking, entering text, and interacting with page elements.
"""

from __future__ import annotations
import logging
import time
from time import sleep
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import (
    ElementNotFoundError, BrowserConnectionError, safe_execute
)
from src.browser_agent.utils import (
    configure_logger, sanitize_selector, truncate_text, format_time_elapsed,
    format_error_message
)

configure_logger()
logger = logging.getLogger(__name__)


def _escape_xpath_string(text: str) -> str:
    """
    Escape a string for use in XPath expressions.
    Handles strings containing both single and double quotes.
    
    Args:
        text: The text to escape
        
    Returns:
        Escaped XPath string expression
    """
    if "'" not in text:
        return f"'{text}'"
    elif '"' not in text:
        return f'"{text}"'
    else:
        # String contains both ' and ", use concat()
        parts = text.split("'")
        return "concat('" + "', \"'\", '".join(parts) + "')"


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
                escaped_text = _escape_xpath_string(text_or_selector)
                xpath = f"//*[normalize-space(text())={escaped_text}]"
                element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                strategy_used = f"exact text '{truncate_text(text_or_selector, 50)}'"
                logger.debug(f"Found element using exact text: {text_or_selector}")
            except TimeoutException:
                pass
        
        # Strategy 3: Try partial text match
        if not element:
            try:
                escaped_text = _escape_xpath_string(text_or_selector)
                xpath = f"//*[contains(text(), {escaped_text})]"
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
                    escaped_text = _escape_xpath_string(text_or_selector)
                    xpath = f"//*[@{attr}={escaped_text}]"
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


def type_in_element(target: str, text: str, press_enter: bool = False) -> str:
    """
    Type text into an element identified by text, selector, or description.
    Simpler interface than enter_text - automatically finds and types in the element.
    
    Args:
        target: Element identifier (text, CSS selector, placeholder, or description)
        text: Text to type
        press_enter: Whether to press Enter after typing
        
    Returns:
        Description of the action taken
        
    Raises:
        ElementNotFoundError: If element cannot be found
        BrowserConnectionError: If typing fails
    """
    try:
        driver = get_driver()
        wait = WebDriverWait(driver, 10)
        element = None
        strategy_used = ""
        
        # Strategy 1: Try as CSS selector
        if any(char in target for char in ['.', '#', '[', ']', '>']):
            try:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, target)))
                strategy_used = f"CSS selector '{truncate_text(target, 50)}'"
                logger.debug(f"Found input using CSS selector: {target}")
            except TimeoutException:
                pass
        
        # Strategy 2: Try by placeholder text
        if not element:
            try:
                escaped_text = _escape_xpath_string(target)
                xpath = f"//input[@placeholder={escaped_text}] | //textarea[@placeholder={escaped_text}]"
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                strategy_used = f"placeholder '{truncate_text(target, 50)}'"
                logger.debug(f"Found input using placeholder: {target}")
            except TimeoutException:
                pass
        
        # Strategy 3: Try by name attribute
        if not element:
            try:
                xpath = f"//input[@name='{target}'] | //textarea[@name='{target}']"
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                strategy_used = f"name attribute '{truncate_text(target, 50)}'"
                logger.debug(f"Found input using name: {target}")
            except TimeoutException:
                pass
        
        # Strategy 4: Try by ID
        if not element:
            try:
                element = wait.until(EC.presence_of_element_located((By.ID, target)))
                strategy_used = f"ID '{truncate_text(target, 50)}'"
                logger.debug(f"Found input using ID: {target}")
            except TimeoutException:
                pass
        
        # Strategy 5: Try finding by label text
        if not element:
            try:
                escaped_text = _escape_xpath_string(target)
                xpath = f"//label[contains(text(), {escaped_text})]/@for"
                label_for = driver.find_element(By.XPATH, xpath).get_attribute('for')
                if label_for:
                    element = wait.until(EC.presence_of_element_located((By.ID, label_for)))
                    strategy_used = f"label text '{truncate_text(target, 50)}'"
                    logger.debug(f"Found input using label: {target}")
            except Exception:
                pass
        
        # Strategy 6: Try aria-label
        if not element:
            try:
                escaped_text = _escape_xpath_string(target)
                xpath = f"//input[@aria-label={escaped_text}] | //textarea[@aria-label={escaped_text}]"
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                strategy_used = f"aria-label '{truncate_text(target, 50)}'"
                logger.debug(f"Found input using aria-label: {target}")
            except TimeoutException:
                pass
        
        if not element:
            raise ElementNotFoundError(
                f"Could not find input element with target: '{target}'"
            )
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        sleep(0.2)
        
        # Clear existing text
        try:
            element.clear()
        except Exception:
            try:
                element.click()
                element.send_keys(Keys.CONTROL + "a")
                element.send_keys(Keys.BACKSPACE)
            except Exception as e:
                logger.warning(f"Could not clear existing text: {e}")
        
        # Focus and type
        element.click()
        sleep(0.1)
        element.send_keys(text)
        
        # Press Enter if requested
        if press_enter:
            element.send_keys(Keys.RETURN)
            action_desc = "typed and pressed Enter"
        else:
            action_desc = "typed"
        
        elapsed_str = format_time_elapsed(time.time())
        result = f"Successfully {action_desc} '{text}' in element using {strategy_used}"
        logger.info(result)
        return result
        
    except ElementNotFoundError:
        raise
    except Exception as e:
        error_msg = format_error_message(e, f"typing in element '{target}'")
        logger.error(error_msg)
        raise BrowserConnectionError(error_msg)
