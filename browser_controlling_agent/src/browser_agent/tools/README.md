# Tools Module Quick Reference

## Import Examples

### Old way (still works):
```python
from src.browser_agent.tools import (
    get_driver,
    smart_click,
    navigate_to_url,
    capture_screenshot
)
```

### New way (also works):
```python
# Import from specific modules
from src.browser_agent.tools.driver import get_driver
from src.browser_agent.tools.interactions import smart_click
from src.browser_agent.tools.navigation import navigate_to_url
from src.browser_agent.tools.utilities import capture_screenshot
```

## Tools by Category

| Module | Functions |
|--------|-----------|
| **driver** | `get_driver()` |
| **navigation** | `go_back()`, `navigate_to_url()`, `wait_for_page_load()` |
| **interactions** | `smart_click()`, `enter_text()`, `enter_text_and_click()`, `press_key_combination()` |
| **page_content** | `get_page_text()`, `get_page_info()`, `get_interactive_elements()`, `get_element_attribute()` |
| **scrolling** | `scroll_page()` |
| **search** | `google_search()`, `search_item_ctrl_f()` |
| **utilities** | `close_popups()`, `capture_screenshot()`, `highlight_element()`, `execute_javascript()`, `switch_to_frame()`, `switch_to_default_content()`, `wait_for_element()` |

## File Structure

```
tools/
├── __init__.py          # All exports (use this for backward compatibility)
├── driver.py            # Browser driver
├── navigation.py        # URL navigation
├── interactions.py      # User interactions
├── page_content.py      # Content extraction
├── scrolling.py         # Scrolling
├── search.py            # Search tools
└── utilities.py         # Misc utilities
```
