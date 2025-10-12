"""
Page Content Tools

Functions for reading and extracting content from pages.
"""

from __future__ import annotations
import logging
from typing import List, Optional

from selenium.webdriver.common.by import By

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import BrowserConnectionError
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


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
        from src.browser_agent.error_handling import ElementNotFoundError
        
        driver = get_driver()
        element = driver.find_element(By.CSS_SELECTOR, selector)
        
        if not element:
            raise ElementNotFoundError(f"Element with selector '{selector}' not found")
        
        value = element.get_attribute(attribute)
        logger.info(f"Got attribute '{attribute}' from element '{selector}': {value}")
        return value
        
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get element attribute: {str(e)}")
