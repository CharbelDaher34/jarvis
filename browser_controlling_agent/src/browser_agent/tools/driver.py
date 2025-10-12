"""
Browser Driver Management

Functions for managing the browser driver instance.
"""

from __future__ import annotations
import logging
from selenium import webdriver

from src.browser_agent.error_handling import BrowserConnectionError
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


def get_driver() -> webdriver.Chrome:
    """
    Get the current browser driver instance.
    
    Returns:
        Chrome WebDriver instance
        
    Raises:
        BrowserConnectionError: If driver is not available
    """
    try:
        import helium
        driver = helium.get_driver()
        if not driver:
            raise BrowserConnectionError("Browser driver is not initialized")
        return driver
    except Exception as e:
        raise BrowserConnectionError(f"Failed to get browser driver: {str(e)}")
