"""
Scrolling Tools

Functions for scrolling the page and scrolling to elements.
"""

from __future__ import annotations
import logging
from typing import Optional

from src.browser_agent.tools.driver import get_driver
from src.browser_agent.error_handling import BrowserConnectionError
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


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
