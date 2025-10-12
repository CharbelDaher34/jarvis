"""
Browser Automation Tools

Organized collection of browser automation tools split into logical modules:
- driver: Browser driver management
- navigation: URL navigation and page loads
- interactions: Clicking, typing, and user interactions
- page_content: Reading and extracting page content
- scrolling: Page scrolling operations
- search: Search functionality (Google, page search)
- utilities: Screenshots, popups, frames, JavaScript

This package maintains backward compatibility with the original tools.py interface.
"""

# Driver management
from src.browser_agent.tools.driver import (
    get_driver,
)

# Navigation tools
from src.browser_agent.tools.navigation import (
    go_back,
    navigate_to_url,
    wait_for_page_load,
)

# Interaction tools
from src.browser_agent.tools.interactions import (
    smart_click,
    enter_text,
    enter_text_and_click,
    press_key_combination,
)

# Page content tools
from src.browser_agent.tools.page_content import (
    get_page_text,
    get_page_info,
    get_interactive_elements,
    get_element_attribute,
)

# Scrolling tools
from src.browser_agent.tools.scrolling import (
    scroll_page,
)

# Search tools
from src.browser_agent.tools.search import (
    google_search,
    search_item_ctrl_f,
)

# Utility tools
from src.browser_agent.tools.utilities import (
    close_popups,
    capture_screenshot,
    highlight_element,
    execute_javascript,
    switch_to_frame,
    switch_to_default_content,
    wait_for_element,
)

# Export all tools for backward compatibility
__all__ = [
    # Driver
    'get_driver',
    
    # Navigation
    'go_back',
    'navigate_to_url',
    'wait_for_page_load',
    
    # Interactions
    'smart_click',
    'enter_text',
    'enter_text_and_click',
    'press_key_combination',
    
    # Page Content
    'get_page_text',
    'get_page_info',
    'get_interactive_elements',
    'get_element_attribute',
    
    # Scrolling
    'scroll_page',
    
    # Search
    'google_search',
    'search_item_ctrl_f',
    
    # Utilities
    'close_popups',
    'capture_screenshot',
    'highlight_element',
    'execute_javascript',
    'switch_to_frame',
    'switch_to_default_content',
    'wait_for_element',
]
