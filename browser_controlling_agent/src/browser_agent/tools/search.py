"""
Search Tools

Functions for searching (Google search, page search, etc.).
"""

from __future__ import annotations
import logging
from typing import List
from time import sleep
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import (
    SearchError, ElementNotFoundError, BrowserConnectionError,
    validate_url, with_retry, RetryConfig, TimeoutManager, safe_execute
)
from src.browser_agent.config import load_config
from src.browser_agent.utils import configure_logger

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
        
        # Escape text for XPath
        escaped_text = _escape_xpath_string(text)
        escaped_text_lower = _escape_xpath_string(text.lower())
        
        # Try multiple XPath strategies for better element detection
        xpath_strategies = [
            f"//*[contains(text(), {escaped_text})]",
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {escaped_text_lower})]",
            f"//*[@*[contains(., {escaped_text})]]"
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
