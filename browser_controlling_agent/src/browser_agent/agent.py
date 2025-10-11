from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os
import logging

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings

from src.browser_agent.tools import (
    go_back,
    close_popups,
    capture_screenshot,
    get_driver,
    smart_click,
    navigate_to_url,
    enter_text_and_click,
    scroll_page,
    get_page_text,
    get_page_info,
    get_interactive_elements,
    press_key_combination,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from src.browser_agent.config import load_config
from src.browser_agent.utils import (
    configure_logger,
    beautify_plan_message,
    truncate_text,
    format_time_elapsed
)

# Setup logging
configure_logger()
logger = logging.getLogger(__name__)


@dataclass
class BrowserDeps:
    """Dependencies for browser agent tasks."""
    prompt: str = ""
    headless: bool = False
    # --- Tool definitions ----------------------------------------------------



def _build_openai_model(settings: dict) -> OpenAIChatModel:
    api_key = settings.get("api_key")
    if api_key:
        import os
        os.environ["OPENAI_API_KEY"] = api_key
    return OpenAIChatModel(
        model_name=settings["model"],
        # api_key=api_key,
        settings={"parallel_tool_calls": True, "max_tokens": 1024},
    )


def _build_gemini_model(settings: dict) -> GoogleModel:
    import os

    api_key = settings.get("api_key")
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    return GoogleModel(
        settings["model"],
        settings=GoogleModelSettings(google_thinking_config={'include_thoughts': False})
    )


def _build_ollama_model(settings: dict) -> OpenAIChatModel:
    return OpenAIChatModel(
        model_name=settings["model"],
        provider=OllamaProvider(base_url=settings["base_url"]),
    )


MODEL_FACTORIES = {
    "openai": _build_openai_model,
    "gemini": _build_gemini_model,
    "ollama": _build_ollama_model,
}


def create_model():
    """Create and configure the AI model based on available API keys."""
    config = load_config()
    model_type, model_config = config.get_available_model()

    try:
        builder = MODEL_FACTORIES[model_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported model type: {model_type}") from exc

    model = builder(model_config)
    logger.info("Using %s model '%s'", model_type, model_config.get("model"))
    return model


model = create_model()

AGENT_INSTRUCTIONS = (
    "You are a web browsing assistant with advanced tools for navigating and interacting with web pages.\n\n"
    "KEY CAPABILITIES:\n"
    "1. Navigation: Use tool_go_to(url) for reliable page loading\n"
    "2. Clicking: Use tool_smart_click(target) which tries multiple strategies to find elements\n"
    "3. Search: Use tool_enter_text_and_click for search boxes - provide input selector and button selector\n"
    "4. Forms: Use tool_fill_form(field_name, value) to fill form fields\n"
    "5. Discovery: Use tool_get_interactive_elements() to see all clickable elements on a page\n"
    "6. Text Analysis: Use tool_get_page_text() to understand page content\n\n"
    "SEARCH BOX STRATEGY:\n"
    "When you need to use a search box:\n"
    "1. First use tool_get_interactive_elements() to find available inputs and buttons\n"
    "2. Look for search input selectors like: input[type='search'], input[name='q'], #search\n"
    "3. Use tool_enter_text_and_click(input_selector, search_query, button_selector)\n"
    "4. If no button selector is provided, it will press Enter automatically\n\n"
    "ELEMENT FINDING:\n"
    "- CSS selectors are most reliable: 'input[type=\"search\"]', '#search-box', '.search-button'\n"
    "- You can also use visible text: 'Search', 'Submit', 'Sign in'\n"
    "- If unsure, use tool_get_interactive_elements() first to see what's available\n\n"
    "BEST PRACTICES:\n"
    "- Use tool_close_popups() immediately when you see popups or modals\n"
    "- Use tool_handle_cookies('accept') for cookie consent banners\n"
    "- Never attempt to log in to websites\n"
    "- Take one action at a time and observe results\n"
    "- For web searches, use tool_enhanced_search(query) to find URLs, then navigate to them\n"
)

browser_agent = Agent[BrowserDeps, str](
    model,
    deps_type=BrowserDeps,
    output_type=str,
    instructions=AGENT_INSTRUCTIONS,
)


# @browser_agent.tool
# async def tool_execute_python(ctx: RunContext[BrowserDeps], code: str) -> str:
#     """Execute Python code for web automation. Helium is available."""
#     # Disabled in favor of more reliable dedicated tools
#     return "tool_execute_python is disabled. Please use dedicated tools like tool_click, tool_enter_text_and_click, etc."


@browser_agent.tool
async def tool_go_to(ctx: RunContext[BrowserDeps], url: str) -> str:
    """Navigate to a specific URL in a new tab with proper page load handling."""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Opening new tab and navigating to {truncate_text(url, 80)}")
        
        # Open a new tab first
        driver = get_driver()
        if driver:
            # Open new tab
            driver.execute_script("window.open('about:blank', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            logger.debug("Opened new tab for navigation")
        
        # Then navigate to the URL
        result = navigate_to_url(url, wait_for_load=True, timeout=30)
        
        elapsed = time.time() - start_time
        elapsed_str = format_time_elapsed(elapsed)
        logger.info(f"Navigation to new tab completed in {elapsed_str}")
        
        return f"Opened new tab and navigated to {url} ({elapsed_str})"
    except Exception as e:
        error_msg = f"Failed to navigate to {url} in new tab: {str(e)}"
        logger.error(error_msg)
        return error_msg


@browser_agent.tool
async def tool_click(ctx: RunContext[BrowserDeps], text: str) -> str:
    """Click on an element with the given text using intelligent detection."""
    try:
        logger.info("Attempting to click on '%s'", text)
        result = smart_click(text, timeout=10)
        return result
    except Exception as e:
        return f"Failed to click on '{text}': {str(e)}"


@browser_agent.tool
async def tool_scroll_down(ctx: RunContext[BrowserDeps], num_pixels: int = 1200) -> str:
    """Scroll down by the specified number of pixels."""
    try:
        result = scroll_page(direction="down", amount=num_pixels)
        return result
    except Exception as e:
        return f"Failed to scroll down: {str(e)}"


@browser_agent.tool
async def tool_get_page_text(ctx: RunContext[BrowserDeps]) -> str:
    """Get the visible text content of the current page."""
    try:
        text = get_page_text()
        truncated = truncate_text(text, 500)
        logger.info(f"Retrieved page text ({len(text)} characters): {truncated}")
        return text
    except Exception as e:
        error_msg = f"Failed to get page text: {str(e)}"
        logger.error(error_msg)
        return error_msg
        body_text = get_page_text(include_alt_text=True)
        # Truncate if too long to avoid overwhelming the model
        if len(body_text) > 5000:
            body_text = body_text[:5000] + "... (content truncated)"
        return f"Page text content:\n{body_text}"
    except Exception as e:
        return f"Error getting page text: {str(e)}"


@browser_agent.tool
async def tool_enhanced_search(
    ctx: RunContext[BrowserDeps], 
    query: str, 
    num_results: int = 5,
    engine: str = "auto",
    site_filter: Optional[str] = None,
    filetype_filter: Optional[str] = None,
    time_filter: Optional[str] = None
) -> str:
    """
    Perform an enhanced search with multiple engines and filtering options.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)
        engine: Search engine to use ('auto', 'google', 'duckduckgo', 'bing')
        site_filter: Restrict results to specific site (e.g., 'wikipedia.org')
        filetype_filter: Filter by file type (e.g., 'pdf', 'doc')
        time_filter: Filter by time ('day', 'week', 'month', 'year')
    """
    try:
        from src.browser_agent.search_engines import EnhancedSearchManager, SearchQuery
        
        # Create search manager
        search_manager = EnhancedSearchManager()
        
        # Build search query
        search_query = SearchQuery(
            query=query,
            max_results=num_results,
            site_filter=site_filter,
            filetype_filter=filetype_filter,
            time_filter=time_filter
        )
        
        # Perform search
        engine_name = None if engine == "auto" else engine
        results = search_manager.search(search_query, engine_name)
        
        if not results:
            available_engines = search_manager.get_available_engines()
            return f"No search results found for query: '{query}'. Available engines: {', '.join(available_engines)}"
        
        # Format results
        result_text = f"Found {len(results)} search results for '{query}'"
        if engine_name:
            result_text += f" (using {results[0].source_engine})"
        result_text += ":\n\n"
        
        for result in results:
            result_text += f"{result.rank}. **{result.title}**\n"
            result_text += f"   URL: {result.url}\n"
            if result.description:
                description = result.description[:150] + "..." if len(result.description) > 150 else result.description
                result_text += f"   Description: {description}\n"
            result_text += f"   Domain: {result.domain}\n\n"
        
        return result_text
        
    except Exception as e:
        return f"Search failed: {str(e)}. Try using tool_go_to with a specific URL instead."


@browser_agent.tool
async def tool_multi_engine_search(ctx: RunContext[BrowserDeps], query: str, num_results: int = 3) -> str:
    """
    Search across multiple engines and compare results.
    
    Args:
        query: Search query string
        num_results: Number of results per engine (default: 3)
    """
    try:
        from src.browser_agent.search_engines import EnhancedSearchManager, SearchQuery
        
        search_manager = EnhancedSearchManager()
        search_query = SearchQuery(query=query, max_results=num_results)
        
        # Get results from all available engines
        all_results = search_manager.multi_engine_search(search_query)
        
        if not any(all_results.values()):
            return f"No search results found across any search engines for query: '{query}'"
        
        # Format results by engine
        result_text = f"Multi-engine search results for '{query}':\n\n"
        
        for engine_name, results in all_results.items():
            result_text += f"**{engine_name.upper()} RESULTS:**\n"
            if results:
                for result in results:
                    result_text += f"  {result.rank}. {result.title}\n"
                    result_text += f"     {result.url}\n"
                    if result.description:
                        desc = result.description[:100] + "..." if len(result.description) > 100 else result.description
                        result_text += f"     {desc}\n"
                result_text += "\n"
            else:
                result_text += "  No results found\n\n"
        
        return result_text
        
    except Exception as e:
        return f"Multi-engine search failed: {str(e)}"


@browser_agent.tool
async def tool_go_back(_: RunContext[BrowserDeps]) -> str:
    """Go back to previous page."""
    return go_back()


@browser_agent.tool
async def tool_close_popups(_: RunContext[BrowserDeps]) -> str:
    """Close visible modals or pop-ups using multiple strategies."""
    return close_popups()


@browser_agent.tool
async def tool_smart_click(ctx: RunContext[BrowserDeps], target: str, timeout: int = 10) -> str:
    """
    Intelligently click on elements using multiple detection strategies.
    
    Args:
        target: Text content, CSS selector, or element description
        timeout: Maximum time to wait for element (default: 10 seconds)
    """
    try:
        return smart_click(target, timeout)
    except Exception as e:
        return f"Smart click failed for '{target}': {str(e)}"


@browser_agent.tool
async def tool_fill_form(ctx: RunContext[BrowserDeps], field_name: str, value: str) -> str:
    """
    Fill a form field with the specified value.
    
    Args:
        field_name: Name, ID, or placeholder text of the form field
        value: Value to enter in the field
    """
    try:
        # Try to find field by multiple attributes
        selectors = [
            f"input[name='{field_name}']",
            f"input[id='{field_name}']",
            f"input[placeholder*='{field_name}']",
            f"textarea[name='{field_name}']",
            f"textarea[id='{field_name}']",
            f"#{field_name}",  # Try as direct ID
            f"[name='{field_name}']",  # Any element with this name
        ]
        
        driver = get_driver()
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].is_displayed():
                    # Use enter_text_and_click without click selector to just enter text
                    result = enter_text_and_click(selector, value, click_selector=None)
                    return result
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
        
        return f"Could not find form field '{field_name}'"
        
    except Exception as e:
        return f"Form fill error: {str(e)}"


@browser_agent.tool
async def tool_select_dropdown(ctx: RunContext[BrowserDeps], dropdown_name: str, option_text: str) -> str:
    """
    Select an option from a dropdown menu.
    
    Args:
        dropdown_name: Name, ID, or label of the dropdown
        option_text: Text of the option to select
    """
    try:
        driver = get_driver()
        
        # Find dropdown element
        selectors = [
            f"select[name='{dropdown_name}']",
            f"select[id='{dropdown_name}']",
            f"//label[contains(text(), '{dropdown_name}')]/following-sibling::select",
            f"//label[contains(text(), '{dropdown_name}')]/..//select",
        ]
        
        dropdown_element = None
        for selector in selectors:
            try:
                if selector.startswith("//"):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements and elements[0].is_displayed():
                    dropdown_element = elements[0]
                    break
            except Exception as e:
                logger.debug(f"Dropdown selector '{selector}' failed: {e}")
        
        if not dropdown_element:
            return f"Could not find dropdown '{dropdown_name}'"
        
        # Select the option
        select = Select(dropdown_element)
        
        # Try different selection methods
        try:
            select.select_by_visible_text(option_text)
            return f"Selected '{option_text}' from dropdown '{dropdown_name}'"
        except:
            try:
                select.select_by_value(option_text)
                return f"Selected '{option_text}' by value from dropdown '{dropdown_name}'"
            except:
                # List available options for user
                options = [opt.text for opt in select.options]
                return f"Could not select '{option_text}'. Available options: {options}"
                
    except Exception as e:
        return f"Dropdown selection error: {str(e)}"


@browser_agent.tool  
async def tool_wait_for_element(ctx: RunContext[BrowserDeps], element_description: str, condition: str = "visible", timeout: int = 10) -> str:
    """
    Wait for an element to appear or meet certain conditions.
    
    Args:
        element_description: Description or selector of the element to wait for
        condition: Condition to wait for ('presence', 'visible', 'clickable')
        timeout: Maximum time to wait in seconds
    """
    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        
        driver = get_driver()
        wait = WebDriverWait(driver, timeout)
        
        # Try as CSS selector first
        try:
            if condition == "presence":
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, element_description)))
            elif condition == "visible":
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, element_description)))
            else:  # clickable
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, element_description)))
            return f"Element '{element_description}' is now {condition}"
        except TimeoutException:
            return f"Element '{element_description}' did not meet condition '{condition}' within {timeout} seconds"
        
    except Exception as e:
        return f"Wait for element error: {str(e)}"


@browser_agent.tool
async def tool_scroll_to_element(ctx: RunContext[BrowserDeps], element_text: str) -> str:
    """
    Scroll to a specific element on the page.
    
    Args:
        element_text: Text content of the element to scroll to
    """
    try:
        driver = get_driver()
        
        # Find element by text content
        xpath = f"//*[contains(text(), '{element_text}')]"
        elements = driver.find_elements(By.XPATH, xpath)
        
        if not elements:
            return f"Element with text '{element_text}' not found"
        
        element = elements[0]
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        
        # Brief highlight for user feedback
        driver.execute_script(
            "arguments[0].style.border='2px solid blue';"
            "setTimeout(function() { arguments[0].style.border=''; }, 1500);", 
            element
        )
        
        return f"Scrolled to element containing text '{element_text}'"
        
    except Exception as e:
        return f"Scroll to element error: {str(e)}"


@browser_agent.tool
async def tool_get_page_info(ctx: RunContext[BrowserDeps]) -> str:
    """Get comprehensive information about the current page."""
    try:
        driver = get_driver()
        
        info = {
            "title": driver.title,
            "url": driver.current_url,
            "ready_state": driver.execute_script("return document.readyState"),
            "page_height": driver.execute_script("return document.body.scrollHeight"),
            "viewport_height": driver.execute_script("return window.innerHeight"),
            "scroll_position": driver.execute_script("return window.pageYOffset"),
        }
        
        # Count common elements
        element_counts = {}
        for element_type in ["input", "button", "a", "form", "img", "div", "p"]:
            try:
                count = len(driver.find_elements(By.TAG_NAME, element_type))
                if count > 0:
                    element_counts[element_type] = count
            except:
                pass
        
        # Format response
        result = f"Page Info:\n"
        result += f"- Title: {info['title']}\n"
        result += f"- URL: {info['url']}\n"
        result += f"- Status: {info['ready_state']}\n"
        result += f"- Dimensions: {info['page_height']}px height, {info['viewport_height']}px viewport\n"
        result += f"- Scroll position: {info['scroll_position']}px\n"
        
        if element_counts:
            result += "- Elements: " + ", ".join([f"{count} {elem}" for elem, count in element_counts.items()])
        
        return result
        
    except Exception as e:
        return f"Failed to get page info: {str(e)}"


@browser_agent.tool
async def tool_handle_cookies(ctx: RunContext[BrowserDeps], action: str = "accept") -> str:
    """
    Handle cookie consent banners and notifications.
    
    Args:
        action: Action to take ('accept', 'decline', 'customize', 'close')
    """
    try:
        driver = get_driver()
        
        # Common cookie banner selectors and text patterns
        accept_patterns = [
            "accept all", "accept cookies", "i accept", "agree", "ok", "allow all",
            "accept and continue", "got it", "continue", "yes"
        ]
        
        decline_patterns = [
            "decline", "reject", "no thanks", "deny", "refuse", "opt out"
        ]
        
        customize_patterns = [
            "customize", "preferences", "settings", "manage", "choose", "options"
        ]
        
        close_patterns = [
            "close", "dismiss", "×", "✕", "later"
        ]
        
        # Select patterns based on action
        if action == "accept":
            search_patterns = accept_patterns
        elif action == "decline":
            search_patterns = decline_patterns  
        elif action == "customize":
            search_patterns = customize_patterns
        else:  # close
            search_patterns = close_patterns
        
        # Search for elements with these patterns
        for pattern in search_patterns:
            # Try multiple selector strategies
            selectors = [
                f"button:contains('{pattern}')",
                f"a:contains('{pattern}')",  
                f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')]",
                f"[aria-label*='{pattern}' i]",
                f"[title*='{pattern}' i]",
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            return f"Cookie banner handled: clicked '{pattern}' button"
                            
                except Exception as e:
                    logger.debug(f"Cookie selector '{selector}' failed: {e}")
        
        return f"No cookie banner elements found for action '{action}'"
        
    except Exception as e:
        return f"Cookie handling error: {str(e)}"


@browser_agent.tool
async def tool_enter_text_and_click(
    ctx: RunContext[BrowserDeps],
    text_selector: str,
    text: str,
    click_selector: Optional[str] = None
) -> str:
    """
    Enter text into a field and then click a button (or press Enter if no button specified).
    Useful for search boxes and forms.
    
    Args:
        text_selector: CSS selector for the text input field (e.g., 'input[type="search"]', '#search-box')
        text: Text to enter
        click_selector: CSS selector for button to click (if None, presses Enter)
    """
    try:
        result = enter_text_and_click(text_selector, text, click_selector, wait_before_click=0.5)
        return result
    except Exception as e:
        return f"Enter text and click failed: {str(e)}"


@browser_agent.tool
async def tool_press_key(ctx: RunContext[BrowserDeps], key_combination: str) -> str:
    """
    Press a key or key combination.
    
    Args:
        key_combination: Key combination string (e.g., 'Enter', 'Control+C', 'Alt+Tab', 'Escape')
    
    Examples:
        - 'Enter' - Press Enter key
        - 'Escape' - Press Escape key
        - 'Control+C' - Press Ctrl+C
        - 'PageDown' - Scroll down one page
    """
    try:
        result = press_key_combination(key_combination)
        return result
    except Exception as e:
        return f"Key press failed: {str(e)}"


@browser_agent.tool
async def tool_get_interactive_elements(ctx: RunContext[BrowserDeps]) -> str:
    """
    Get all interactive elements (buttons, links, inputs) on the current page.
    Useful for understanding what actions are available.
    """
    try:
        elements = get_interactive_elements()
        if not elements:
            return "No interactive elements found on the page"
        
        # Format for better readability
        result = f"Found {len(elements)} interactive elements:\n\n"
        
        # Group by type
        by_type = {}
        for elem in elements:
            elem_type = elem.get('type', 'unknown')
            if elem_type not in by_type:
                by_type[elem_type] = []
            by_type[elem_type].append(elem)
        
        for elem_type, elems in by_type.items():
            result += f"\n**{elem_type.upper()}S** ({len(elems)}):\n"
            for elem in elems[:10]:  # Limit to first 10 of each type
                text = elem.get('text', '')
                selector = elem.get('selector', '')
                if text:
                    result += f"  - {text[:50]} (selector: {selector})\n"
                else:
                    result += f"  - {selector}\n"
            if len(elems) > 10:
                result += f"  ... and {len(elems) - 10} more\n"
        
        return result
    except Exception as e:
        return f"Failed to get interactive elements: {str(e)}"


@browser_agent.tool
async def tool_scroll_to_top(ctx: RunContext[BrowserDeps]) -> str:
    """Scroll to the top of the page."""
    try:
        result = scroll_page(direction="top")
        return result
    except Exception as e:
        return f"Scroll to top failed: {str(e)}"


@browser_agent.tool
async def tool_scroll_to_bottom(ctx: RunContext[BrowserDeps]) -> str:
    """Scroll to the bottom of the page."""
    try:
        result = scroll_page(direction="bottom")
        return result
    except Exception as e:
        return f"Scroll to bottom failed: {str(e)}"




@browser_agent.instructions
def helium_instructions(_: RunContext[BrowserDeps]) -> str:
    return (
        "You are a web browsing assistant with powerful tools for interacting with web pages.\n\n"
        "CORE TOOLS:\n"
        "- tool_go_to(url): Navigate to a URL with proper page load handling\n"
        "- tool_click(text): Click on an element by its visible text or CSS selector\n"
        "- tool_smart_click(target): Intelligent click using multiple detection strategies\n"
        "- tool_enter_text_and_click(text_selector, text, click_selector): Enter text in a field and optionally click a button\n"
        "- tool_fill_form(field_name, value): Fill a form field by name, ID, or placeholder\n"
        "- tool_press_key(key_combination): Press keys like 'Enter', 'Escape', 'Control+C'\n\n"
        "NAVIGATION & SCROLLING:\n"
        "- tool_scroll_down(num_pixels): Scroll down by specified pixels\n"
        "- tool_scroll_to_top(): Scroll to the top of the page\n"
        "- tool_scroll_to_bottom(): Scroll to the bottom of the page\n"
        "- tool_go_back(): Navigate back to previous page\n\n"
        "INFORMATION GATHERING:\n"
        "- tool_get_page_text(): Get all visible text from the current page\n"
        "- tool_get_page_info(): Get page title, URL, and dimensions\n"
        "- tool_get_interactive_elements(): List all clickable/interactive elements on the page\n\n"
        "UTILITIES:\n"
        "- tool_close_popups(): Close modal dialogs and popups\n"
        "- tool_handle_cookies(action): Handle cookie consent banners ('accept', 'decline', 'close')\n"
        "- tool_enhanced_search(query): Perform web search to find URLs\n"
        "- tool_wait_for_element(selector, condition, timeout): Wait for an element to appear\n\n"
        "SEARCH BOX STRATEGY (CRITICAL FOR YOUTUBE, GOOGLE, ETC.):\n"
        "1. First, use tool_get_interactive_elements() to find available inputs\n"
        "2. Look for search input selectors like:\n"
        "   - input[type='search']\n"
        "   - input[name='search']\n"
        "   - input[placeholder*='Search']\n"
        "   - #search-box\n"
        "3. Use tool_enter_text_and_click(input_selector, search_query, button_selector)\n"
        "   - If no button selector is provided, Enter key is pressed automatically\n"
        "4. Example: tool_enter_text_and_click('input[name=\"search_query\"]', 'my song', None)\n\n"
        "BEST PRACTICES:\n"
        "- Always use CSS selectors for precise targeting (e.g., 'input[type=\"search\"]')\n"
        "- Use tool_get_interactive_elements() first to discover available elements\n"
        "- For clicking, prefer tool_smart_click which tries multiple strategies\n"
        "- Handle popups immediately with tool_close_popups()\n"
        "- For cookie banners, use tool_handle_cookies('accept')\n"
        "- Never attempt to log in to websites\n"
        "- Take one action at a time and observe results\n"
    )


async def run_with_screenshot(prompt: str, deps: Optional[BrowserDeps] = None) -> str:
    """Run the agent with optional screenshot analysis."""
    # Run the agent first
    logger.info("Running browser agent")
    result = await browser_agent.run(prompt, deps=deps or BrowserDeps())
    return result.output 
    # # For vision-capable models, capture and analyze screenshot
    # try:
    #     png_bytes = capture_screenshot()
    #     if png_bytes is not None:
    #         # Send a follow-up message with the screenshot for final analysis
    #         follow_up = await browser_agent.run(
    #             [
    #                 "Based on this screenshot of the current page, provide any additional useful details and finalize your answer:",
    #                 BinaryContent(data=png_bytes, media_type='image/png'),
    #             ],
    #             deps=deps or BrowserDeps(),
    #         )
    #         return follow_up.output
    # except Exception as e:
    #     return result.output
