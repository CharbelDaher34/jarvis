"""
Improved Browser Agent with consolidated tools and vision capabilities.

Key improvements:
1. Fewer, more powerful tools (6 instead of 20+)
2. Vision-based page understanding
3. State tracking and adaptive strategies
4. Better error recovery
"""
from __future__ import annotations

import logging
from typing import Optional, Literal
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel

from core.async_browser import AsyncBrowserSession
from core.vision_analyzer import VisionAnalyzer
from config import load_config

logger = logging.getLogger(__name__)


@dataclass
class BrowserContext:
    """Enhanced context with browser session and vision."""
    browser: AsyncBrowserSession
    vision: VisionAnalyzer
    task_goal: str
    conversation_history: list[str]


# System prompt for improved agent
IMPROVED_AGENT_PROMPT = """
You are an expert web automation agent with vision capabilities.

## Your Tools (6 core tools)

1. **search(query)** - Search the web, returns URLs
2. **navigate(url)** - Go to a specific URL
3. **interact(action, target, value)** - POWERFUL & FLEXIBLE interaction tool!
   - action: "click", "type", "select"
   - target: Describe what you see! Examples:
     * "Login" or "Sign Up" (button/link text)
     * "Documentation" (partial text match)
     * "Email" or "Password" (input field label/placeholder)
     * "#submit-btn" (CSS selector if you know it)
   - value: For "type" - the text to enter
   - This tool tries 8+ strategies automatically - just describe what you see!
4. **observe()** - Get detailed page analysis (text + vision)
5. **extract(selector)** - Extract specific content
6. **verify(question)** - Check completion

## Workflow

1. **Understand Goal** → What information does user need?
2. **Search** → Use search() if you need to find websites
3. **Navigate** → Use navigate() to go to URLs
4. **Observe FIRST** → ALWAYS use observe() to see page layout before interacting!
5. **Interact** → Use interact() with what you saw in observe()
   - You can use the exact text you see: interact("click", "Documentation")
   - Or describe the element: interact("type", "search", "hello")
6. **Extract** → Use extract() to get specific data
7. **Verify** → Use verify() to confirm you have what's needed

## Key Principle: OBSERVE BEFORE ACTING
- Always observe() to see what's on the page
- Then interact() using the text/elements you saw
- The interact tool is smart - it tries many strategies automatically!

## Decision Tree

```
Need to find websites? → search(query)
Have URL? → navigate(url)
Don't understand page? → observe()
Need to click something? → interact("click", target)
Need specific data? → extract(selector)
Ready to answer? → verify("Do I have enough information?")
```

## Examples

**Example 1: Simple Information Retrieval**
User: "What is the latest Python version?"

Your actions:
1. search("latest Python version official")
2. navigate("https://www.python.org")
3. observe()  # See the page structure
4. extract(".latest-version")  # Get version number
5. verify("Do I have the Python version?")

**Example 2: Multi-Step Navigation**
User: "Find FastAPI documentation for database connections"

Your actions:
1. search("FastAPI documentation")
2. navigate("https://fastapi.tiangolo.com")
3. observe()  # See navigation menu
4. interact("click", "Tutorial - User Guide")
5. observe()  # See sub-menu
6. interact("click", "SQL Databases")
7. extract("main")  # Get documentation content
8. verify("Do I have database connection docs?")

## Key Principles

- **One action at a time** - Don't rush, observe after each action
- **Use vision** - observe() gives you visual understanding
- **Be specific** - "blue login button" better than "button"
- **Verify often** - Check if you have enough information
- **Adapt** - If interaction fails, observe() and try different approach

## Important Notes

- interact("click", target) handles all clicking - no separate tools
- observe() combines text + vision - use it frequently
- search() only searches, navigate() only navigates - clear separation
- Always verify() before concluding task
"""


def create_improved_agent(
    browser: AsyncBrowserSession,
    vision: VisionAnalyzer
) -> Agent:
    """Create agent with consolidated tools."""
    config = load_config()
    
    # Get model
    model_type, model_config = config.get_available_model()
    api_key = model_config.get("api_key")
    if api_key:
        import os
        os.environ["OPENAI_API_KEY"] = api_key
    
    model = OpenAIChatModel(
        model_name=model_config["model"],
        settings={"parallel_tool_calls": False, "max_tokens": 2048}
    )
    
    agent = Agent(
        model,
        deps_type=BrowserContext,
        output_type=str,
        system_prompt=IMPROVED_AGENT_PROMPT,
        retries=2
    )
    
    # Register 6 consolidated tools
    
    @agent.tool
    async def search(ctx: RunContext[BrowserContext], query: str) -> str:
        """
        Search the web for URLs.
        
        Args:
            query: Search query (e.g., "Python documentation", "fastapi tutorial")
        
        Returns:
            Formatted list of search results with URLs
        """
        try:
            from search_engines import (
                EnhancedSearchManager,
                SearchQuery
            )
            
            logger.info(f"🔍 Searching: {query}")
            
            manager = EnhancedSearchManager()
            search_query = SearchQuery(query=query, max_results=5)
            results = manager.search(search_query)
            
            if not results:
                return f"No results found for: {query}"
            
            # Format results
            output = f"Found {len(results)} results for '{query}':\n\n"
            for r in results:
                output += f"{r.rank}. **{r.title}**\n"
                output += f"   URL: {r.url}\n"
                if r.description:
                    desc = r.description[:120] + "..." if len(r.description) > 120 else r.description
                    output += f"   {desc}\n"
                output += "\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Search error: {str(e)}"
    
    @agent.tool
    async def navigate(ctx: RunContext[BrowserContext], url: str) -> str:
        """
        Navigate to a specific URL.
        
        Args:
            url: Full URL to visit
        
        Returns:
            Confirmation with page title
        """
        try:
            logger.info(f"🌐 Navigating to: {url}")
            
            result = await ctx.deps.browser.navigate(url)
            
            return f"✅ Navigated to {url}\nTitle: {result['title']}"
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return f"Navigation error: {str(e)}"
    
    @agent.tool
    async def interact(
        ctx: RunContext[BrowserContext],
        action: Literal["click", "type", "select"],
        target: str,
        value: Optional[str] = None
    ) -> str:
        """
        Interact with page elements - HIGHLY FLEXIBLE!
        
        This tool accepts NATURAL LANGUAGE descriptions and tries 8+ strategies automatically.
        You don't need precise selectors - describe what you see!
        
        Args:
            action: Type of interaction - "click", "type", or "select"
            target: What to interact with - can be:
                   * Visible text: "Login", "Sign Up", "Submit"
                   * Partial text: "Download", "documentation"
                   * Button/link description: "blue login button"
                   * Input placeholder: "Enter your email"
                   * Field label: "Username", "Password"
                   * CSS selector: "#login-btn", ".submit-button"
            value: For type/select - the text to enter or option to choose
        
        Examples:
            - interact("click", "Login")  ← clicks button/link with "Login" text
            - interact("click", "Documentation")  ← finds and clicks docs link
            - interact("type", "Email", "user@example.com")  ← finds email input
            - interact("type", "search", "Python tutorial")  ← finds search box
        
        The tool will automatically try multiple strategies until one works!
        
        Returns:
            Confirmation of action with strategy used
        """
        try:
            logger.info(f"🎯 Interaction: {action} on '{target}'" + (f" with value '{value}'" if value else ""))
            
            browser = ctx.deps.browser
            
            if action == "click":
                result = await browser.click(target)
                return f"✅ {result}"
            
            elif action == "type":
                if not value:
                    return "❌ Error: 'value' required for type action"
                result = await browser.type_text(target, value)
                return f"✅ {result}"
            
            elif action == "select":
                if not value:
                    return "❌ Error: 'value' required for select action"
                # Handle dropdown selection
                await browser.click(target)
                await browser.click(value)
                return f"✅ Selected '{value}' from '{target}'"
            
        except Exception as e:
            logger.error(f"Interaction failed: {e}")
            return f"❌ Interaction error: {str(e)}\nTry using observe() to see available elements."
    
    @agent.tool
    async def observe(ctx: RunContext[BrowserContext]) -> str:
        """
        Get comprehensive understanding of current page using text + vision.
        
        This is your primary observation tool - use it frequently to understand
        what's on the page before taking actions.
        
        Returns:
            Detailed page analysis including:
            - Page title and URL
            - Visual layout description (from vision model)
            - Interactive elements (buttons, links, inputs)
            - Main content summary
        """
        try:
            logger.info("👀 Observing page...")
            
            browser = ctx.deps.browser
            vision = ctx.deps.vision
            
            # Get page content
            content = await browser.get_page_content()
            
            # Get screenshot and analyze visually
            screenshot = await browser.screenshot()
            visual_analysis = await vision.analyze_screenshot(
                screenshot,
                "Describe the page layout and identify all interactive elements (buttons, links, forms). "
                "Note any popups, navigation menus, or important UI elements."
            )
            
            # Combine text and vision analysis
            output = f"""
📍 **Current Page Analysis**

**URL:** {content['url']}
**Title:** {content['title']}

**Visual Layout:**
{visual_analysis}

**Interactive Elements Found:** {content['element_count']}

**Key Elements:**
"""
            
            # List interactive elements grouped by type
            elements = content['interactive_elements']
            
            # Group by type
            by_type = {}
            for elem in elements:
                elem_type = elem.get('tag', 'unknown')
                if elem_type not in by_type:
                    by_type[elem_type] = []
                by_type[elem_type].append(elem)
            
            for elem_type, items in by_type.items():
                output += f"\n**{elem_type.upper()}S** ({len(items)}):\n"
                for item in items[:5]:  # Show first 5 of each type
                    text = item.get('text', '')
                    if text:
                        output += f"  - {text[:60]}\n"
                if len(items) > 5:
                    output += f"  ... and {len(items) - 5} more\n"
            
            # Add page text preview
            text_preview = content['text_content'][:300]
            output += f"\n**Page Content Preview:**\n{text_preview}...\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Observation failed: {e}")
            return f"Observation error: {str(e)}"
    
    @agent.tool
    async def extract(ctx: RunContext[BrowserContext], selector: str) -> str:
        """
        Extract specific content from the page.
        
        Args:
            selector: CSS selector for content to extract
                     (e.g., ".price", "#description", "main article")
        
        Returns:
            Extracted text content
        """
        try:
            logger.info(f"📤 Extracting: {selector}")
            
            page = ctx.deps.browser.page
            
            # Try to find and extract element content
            try:
                element = await page.query_selector(selector)
                if element:
                    content = await element.inner_text()
                    return f"✅ Extracted from '{selector}':\n\n{content}"
                else:
                    return f"❌ Element not found: '{selector}'\nUse observe() to see available elements."
            except Exception as e:
                return f"❌ Extraction failed: {str(e)}"
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return f"Extraction error: {str(e)}"
    
    @agent.tool
    async def verify(ctx: RunContext[BrowserContext], question: str) -> str:
        """
        Verify if you have sufficient information to answer the user's goal.
        
        Args:
            question: Question to verify (e.g., "Do I have the pricing information?")
        
        Returns:
            Assessment of whether you can answer the user's goal
        """
        try:
            logger.info(f"✔️  Verifying: {question}")
            
            # Get current state
            browser = ctx.deps.browser
            content = await browser.get_page_content()
            
            # Take screenshot for visual verification
            screenshot = await browser.screenshot()
            
            # Use vision to assess if we have the needed information
            vision = ctx.deps.vision
            assessment = await vision.analyze_screenshot(
                screenshot,
                f"User's goal: {ctx.deps.task_goal}\n\n"
                f"Question: {question}\n\n"
                f"Current page title: {content['title']}\n"
                f"Current URL: {content['url']}\n\n"
                "Based on what you see on this page, can you answer the user's goal? "
                "Explain what information is visible and if it's sufficient."
            )
            
            return f"**Verification Assessment:**\n{assessment}"
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return f"Verification error: {str(e)}"
    
    logger.info("✅ Created improved browser agent with 6 consolidated tools")
    return agent


async def run_improved_agent(task: str, headless: bool = False) -> str:
    """
    Run the improved agent on a task.
    
    Args:
        task: User's task description
        headless: Whether to run browser in headless mode
    
    Returns:
        Task result
    """
    # Initialize browser and vision
    browser = AsyncBrowserSession(headless=headless)
    await browser.start()
    
    vision = VisionAnalyzer()
    
    try:
        # Create agent
        agent = create_improved_agent(browser, vision)
        
        # Create context
        context = BrowserContext(
            browser=browser,
            vision=vision,
            task_goal=task,
            conversation_history=[]
        )
        
        # Run agent
        logger.info(f"🚀 Starting task: {task}")
        result = await agent.run(task, deps=context)
        
        # Log metrics
        metrics = browser.get_metrics()
        logger.info(f"📊 Task Metrics: {metrics}")
        
        return result.output
        
    finally:
        await browser.close()


# Example usage
async def example_usage():
    """Demonstrate improved agent."""
    result = await run_improved_agent(
        "Find the latest Python version from python.org",
        headless=False
    )
    print("Result:", result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

