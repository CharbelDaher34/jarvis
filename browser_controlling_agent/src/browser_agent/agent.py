from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings

from src.browser_agent.tools import (
    search_item_ctrl_f,
    go_back,
    close_popups,
    capture_screenshot,
    get_driver,
    google_search,
    wait_for_element,
    smart_click,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import logging


@dataclass
class BrowserDeps:
    prompt: str = ""
    headless: bool = False


# Import configuration system
from src.browser_agent.config import load_config

logger = logging.getLogger(__name__)
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
    "You are a web browsing assistant. Use tools to navigate and interact with web pages. "
    "You can perform Google searches to find relevant URLs using tool_google_search. "
    "After clicking or navigation, always take a screenshot to observe the current state. "
    "Never attempt to log in to websites. "
    "Use helium commands for navigation: go_to(url), click('text'), scroll_down(num_pixels=1200), etc. "
    "When you encounter popups, use the close_popups tool rather than trying to click 'X' buttons. "
    "Use .exists() to check if elements exist before interacting with them. "
    "For example: if Text('Accept cookies?').exists(): click('I accept') "
    "Stop after each action to observe the results via screenshot. "
    "When searching for information, first use tool_google_search to find relevant URLs, then navigate to them."
)

browser_agent = Agent[BrowserDeps, str](
    model,
    deps_type=BrowserDeps,
    output_type=str,
    instructions=AGENT_INSTRUCTIONS,
)


@browser_agent.tool
async def tool_execute_python(ctx: RunContext[BrowserDeps], code: str) -> str:
    """Execute Python code for web automation. Helium is available."""
    try:
        # Import helium for the execution
        import helium
        
        # Create a safe execution environment with helium functions
        exec_globals = {
            'helium': helium,
            'go_to': helium.go_to,
            'click': helium.click,
            'scroll_down': helium.scroll_down,
            'scroll_up': helium.scroll_up,
            'Text': helium.Text,
            'Link': helium.Link,
            'Button': helium.Button,
            'write': helium.write,
            'press': helium.press,
            '__builtins__': __builtins__,
        }
        
        # Execute the code
        exec(code, exec_globals)
        return f"Successfully executed: {code}"
    except Exception as e:
        return f"Error executing code '{code}': {str(e)}"


@browser_agent.tool
async def tool_go_to(ctx: RunContext[BrowserDeps], url: str) -> str:
    """Navigate to a specific URL."""
    try:
        import helium
        try:
            driver = get_driver()
        except Exception as exc:
            logger.debug("Unable to acquire driver before opening new tab: %s", exc)
            driver = None
        if driver:
            try:
                driver.switch_to.new_window("tab")
            except Exception:
                driver.execute_script("window.open('about:blank', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])
        logger.info("Navigating to %s", url)
        helium.go_to(url)
        return f"Successfully navigated to {url}"
    except Exception as e:
        return f"Failed to navigate to {url}: {str(e)}"


@browser_agent.tool
async def tool_click(ctx: RunContext[BrowserDeps], text: str) -> str:
    """Click on an element with the given text."""
    try:
        import helium
        helium.click(text)
        return f"Successfully clicked on '{text}'"
    except Exception as e:
        return f"Failed to click on '{text}': {str(e)}"


@browser_agent.tool
async def tool_scroll_down(ctx: RunContext[BrowserDeps], num_pixels: int = 1200) -> str:
    """Scroll down by the specified number of pixels."""
    try:
        import helium
        helium.scroll_down(num_pixels=num_pixels)
        return f"Successfully scrolled down {num_pixels} pixels"
    except Exception as e:
        return f"Failed to scroll down: {str(e)}"


@browser_agent.tool
async def tool_get_page_text(ctx: RunContext[BrowserDeps]) -> str:
    """Get the visible text content of the current page."""
    try:
        driver = get_driver()
        # Get the page text content
        body_text = driver.find_element(By.TAG_NAME, "body").text
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
        # Fallback to original google search
        try:
            urls = google_search(query, num_results)
            if not urls:
                return f"No search results found for query: '{query}'"
            
            result = f"Found {len(urls)} search results for '{query}' (fallback):\n"
            for idx, url in enumerate(urls, 1):
                result += f"{idx}. {url}\n"
            return result
        except Exception as fallback_error:
            return f"Search failed: {str(e)}. Fallback also failed: {str(fallback_error)}"


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
async def tool_search_item_ctrl_f(_: RunContext[BrowserDeps], text: str, nth_result: int = 1) -> str:
    """Search for text on the current page via Ctrl+F-like contains search and focus the nth occurrence."""
    return search_item_ctrl_f(text=text, nth_result=nth_result)


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
        import helium
        
        # Try multiple strategies to find and fill the field
        strategies = [
            lambda: helium.write(value, into=field_name),
            lambda: helium.write(value, into=helium.TextField(field_name)),
        ]
        
        for strategy in strategies:
            try:
                strategy()
                return f"Successfully filled field '{field_name}' with value '{value}'"
            except Exception as e:
                logger.debug(f"Form fill strategy failed: {e}")
        
        # Fallback to Selenium
        driver = get_driver()
        
        # Try to find field by multiple attributes
        selectors = [
            f"input[name='{field_name}']",
            f"input[id='{field_name}']",
            f"input[placeholder*='{field_name}']",
            f"textarea[name='{field_name}']",
            f"textarea[id='{field_name}']",
        ]
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].is_displayed():
                    element = elements[0]
                    element.clear()
                    element.send_keys(value)
                    return f"Successfully filled field '{field_name}' using selector '{selector}'"
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
        # Convert description to locator
        locators_to_try = [
            (By.CSS_SELECTOR, element_description),
            (By.XPATH, f"//*[contains(text(), '{element_description}')]"),
            (By.ID, element_description),
            (By.NAME, element_description),
        ]
        
        for locator in locators_to_try:
            if wait_for_element(locator, timeout, condition):
                return f"Element '{element_description}' is now {condition} (found using {locator[0]})"
        
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
async def tool_get_performance_info(ctx: RunContext[BrowserDeps]) -> str:
    """Get current performance and resource usage information."""
    try:
        from src.browser_agent.performance import get_performance_report
        
        report = get_performance_report()
        
        result = "🔧 Performance Report:\n\n"
        
        # System performance
        if report["performance"]["current"]:
            current = report["performance"]["current"]
            result += f"**Current System Usage:**\n"
            result += f"  • CPU: {current['cpu_percent']:.1f}%\n"
            result += f"  • Memory: {current['memory_mb']:.1f}MB\n"
            if current['browser_memory_mb']:
                result += f"  • Browser Memory: {current['browser_memory_mb']:.1f}MB\n"
        
        # Average performance
        if report["performance"]["average_5min"]:
            avg = report["performance"]["average_5min"]
            result += f"\n**5-Minute Average:**\n"
            result += f"  • CPU: {avg['cpu_percent']:.1f}%\n"
            result += f"  • Memory: {avg['memory_mb']:.1f}MB\n"
            if avg['browser_memory_mb']:
                result += f"  • Browser Memory: {avg['browser_memory_mb']:.1f}MB\n"
        
        # Browser tabs
        tabs = report["tabs"]
        result += f"\n**Browser Session:**\n"
        result += f"  • Open tabs: {tabs['count']}/{tabs['max_allowed']}\n"
        result += f"  • Tab timeout: {tabs['timeout_seconds']}s\n"
        
        # Resource limits
        limits = report["performance"]["resource_limits"]
        result += f"\n**Resource Limits:**\n"
        result += f"  • Max Memory: {limits['max_memory_mb']}MB\n"
        result += f"  • Max CPU: {limits['max_cpu_percent']}%\n"
        result += f"  • Max Browser Memory: {limits['max_browser_memory_mb']}MB\n"
        
        return result
        
    except Exception as e:
        return f"Failed to get performance info: {str(e)}"


@browser_agent.tool
async def tool_cleanup_resources(ctx: RunContext[BrowserDeps]) -> str:
    """Force cleanup of browser resources and memory."""
    try:
        from src.browser_agent.performance import resource_manager, session_manager
        
        # Clean up tabs
        session_manager.cleanup_all_tabs()
        
        # Force resource cleanup
        resource_manager.force_cleanup()
        
        return "🧹 Resource cleanup completed: cleared browser cache, closed old tabs, and freed memory"
        
    except Exception as e:
        return f"Resource cleanup failed: {str(e)}"


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




@browser_agent.instructions
def helium_instructions(_: RunContext[BrowserDeps]) -> str:
    return (
        "You can use helium to access websites. The helium driver is already managed for you.\n"
        "Available helium commands:\n"
        "- Use go_to('url') to navigate to pages\n"
        "- Use click('Text') to click on elements with that text\n"
        "- Use click(Link('Text')) for links\n"
        "- Use scroll_down(num_pixels=1200) to scroll\n"
        "- Use .exists() to test elements, e.g.: if Text('Accept cookies?').exists(): click('I accept')\n"
        "If an element is not found, you'll get LookupError; do one action at a time.\n"
        "Use the close_popups tool for modal windows rather than clicking 'X'.\n"
        "Stop your action after each button click to see what happens via screenshot.\n"
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
