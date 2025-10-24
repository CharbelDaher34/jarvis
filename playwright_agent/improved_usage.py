"""
Examples demonstrating the playwright_agent (browser automation tool).

These examples show how to use the playwright_agent directly.
In the main Jarvis assistant (main.py), this is wrapped as a tool
and called automatically based on your voice commands.

Run these to test the playwright_agent capabilities.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to sys.path for relative imports
# sys.path.insert(0, str(Path(__file__).parent))

# go back 1 directory for imports
# sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
from dotenv import load_dotenv
load_dotenv()
import os
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


async def example_1_basic_usage():
    """Example 1: Basic usage - Find information."""
    print("\n" + "="*60)
    print("Example 1: Basic Information Retrieval")
    print("="*60)
    
    from playwright_agent import run_improved_agent
    
    result = await run_improved_agent(
        task="navigate to www.google.com and search for 'Fine tuning llms with unsloth' (write it in the search bar) and read the blog. After it tell me how to cook a rabbit",
        headless=False,  # Set to True for production
        keep_browser_open=False)
    
    print("\n✅ Result:")
    print(result)


async def example_2_multi_step():
    """Example 2: Multi-step navigation task."""
    print("\n" + "="*60)
    print("Example 2: Multi-Step Navigation")
    print("="*60)
    
    from playwright_agent import run_improved_agent
    
    result = await run_improved_agent(
        task="Find FastAPI documentation on database connections and summarize the main approach",
        headless=False
    )
    
    print("\n✅ Result:")
    print(result)


async def example_3_vision_capabilities():
    """Example 3: Demonstrate vision-powered observation."""
    print("\n" + "="*60)
    print("Example 3: Vision-Powered Page Understanding")
    print("="*60)
    
    from playwright_agent.core.async_browser import AsyncBrowserSession
    from playwright_agent.core.vision_analyzer import VisionAnalyzer
    
    async with AsyncBrowserSession(headless=False) as browser:
        # Navigate to a page
        await browser.navigate("https://www.python.org")
        
        # Take screenshot
        screenshot = await browser.screenshot()
        
        # Analyze with vision
        vision = VisionAnalyzer()
        analysis = await vision.analyze_screenshot(
            screenshot,
            "What interactive elements are visible on this page? Describe the layout."
        )
        
        print("\n👁️  Vision Analysis:")
        print(analysis)
        
        # Get suggested next action
        suggestion = await vision.identify_next_action(
            screenshot,
            goal="find documentation"
        )
        
        print("\n💡 Suggested Next Action:")
        print(suggestion)


async def example_4_error_recovery():
    """Example 4: Demonstrate adaptive error recovery."""
    print("\n" + "="*60)
    print("Example 4: Adaptive Error Recovery")
    print("="*60)
    
    from playwright_agent import AsyncBrowserSession
    from playwright_agent import AdaptiveRetryManager
    
    async with AsyncBrowserSession(headless=False) as browser:
        await browser.navigate("https://www.python.org")
        
        # Try to click element with slight text variation
        retry_manager = AdaptiveRetryManager()
        
        try:
            # Will try multiple strategies automatically
            element = await retry_manager.find_element(
                browser.page,
                "Download",  # Might be "Downloads" on page
                action_type="click"
            )
            
            print("\n✅ Element found using adaptive retry!")
            
            # Show which strategies were tried
            stats = retry_manager.get_statistics()
            print("\n📊 Strategy Statistics:")
            for strategy, data in stats['strategy_breakdown'].items():
                print(f"  - {strategy}: {data['success_rate']} success rate")
            
        except Exception as e:
            print(f"\n❌ All strategies failed: {e}")


async def example_5_state_tracking():
    """Example 5: Demonstrate state tracking and metrics."""
    print("\n" + "="*60)
    print("Example 5: State Tracking & Metrics")
    print("="*60)
    
    from core.async_browser import AsyncBrowserSession
    
    async with AsyncBrowserSession(headless=False) as browser:
        # Perform several actions
        await browser.navigate("https://www.python.org")
        await browser.click("text=Downloads")
        await browser.navigate("https://docs.python.org/3/")
        
        # Get page content
        content = await browser.get_page_content()
        
        print(f"\n📍 Current URL: {content['url']}")
        print(f"📄 Page Title: {content['title']}")
        print(f"🔢 Interactive Elements: {content['element_count']}")
        
        # Get session metrics
        metrics = browser.get_metrics()
        print("\n📊 Session Metrics:")
        print(f"  Total Actions: {metrics['total_actions']}")
        print(f"  Failed Actions: {metrics['failed_actions']}")
        print(f"  Success Rate: {metrics['success_rate']}")
        print(f"  URLs Visited: {metrics['unique_urls_visited']}")
        
        # Review action history
        print("\n📜 Action History:")
        for i, action in enumerate(browser.action_history[-5:], 1):  # Last 5 actions
            success = "✅" if action.get('success', False) else "❌"
            print(f"  {i}. {success} {action['action']} - {action.get('url', 'N/A')[:50]}")


async def example_6_comparison():
    """Example 6: Side-by-side comparison of old vs new."""
    print("\n" + "="*60)
    print("Example 6: Performance Comparison")
    print("="*60)
    
    import time
    
    task = "Find the latest Python version"
    
    # Try old approach (if available)
    print("\n🕰️  OLD APPROACH (Selenium):")
    try:
        from runner import run_task
        
        start = time.time()
        old_result = await run_task(task, headless=True, use_multi_agent=False)
        old_time = time.time() - start
        
        print(f"  ✅ Completed in {old_time:.2f}s")
        print(f"  Result: {old_result[:100]}...")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        old_time = None
    
    # Try new approach
    print("\n⚡ NEW APPROACH (Playwright + Vision):")
    try:
        from agents.improved_agent import run_improved_agent
        
        start = time.time()
        new_result = await run_improved_agent(task, headless=True)
        new_time = time.time() - start
        
        print(f"  ✅ Completed in {new_time:.2f}s")
        print(f"  Result: {new_result[:100]}...")
        
        if old_time:
            improvement = ((old_time - new_time) / old_time) * 100
            print(f"\n📈 IMPROVEMENT: {improvement:.1f}% faster!")
    except Exception as e:
        print(f"  ❌ Failed: {e}")


async def example_7_consolidated_tools():
    """Example 7: Demonstrate consolidated tool usage."""
    print("\n" + "="*60)
    print("Example 7: Consolidated Tools (6 vs 20+)")
    print("="*60)
    
    from core.async_browser import AsyncBrowserSession
    from core.vision_analyzer import VisionAnalyzer
    from agents.improved_agent import create_improved_agent, BrowserContext
    
    async with AsyncBrowserSession(headless=False) as browser:
        vision = VisionAnalyzer()
        agent = create_improved_agent(browser, vision)
        
        context = BrowserContext(
            browser=browser,
            vision=vision,
            task_goal="Find documentation",
            conversation_history=[]
        )
        
        print("\n🛠️  Available Tools:")
        print("  1. search(query) - Search the web")
        print("  2. navigate(url) - Go to URL")
        print("  3. interact(action, target, value) - Click/Type/Select")
        print("  4. observe() - Understand page with vision")
        print("  5. extract(selector) - Get content")
        print("  6. verify(question) - Check completion")
        
        print("\n🎯 Running task with 6 consolidated tools...")
        result = await agent.run(
            "Find Python documentation and tell me the URL",
            deps=context
        )
        
        print(f"\n✅ Result: {result.output}")


# Main menu
async def main():
    """Run examples."""
    examples = [
        ("Basic Usage", example_1_basic_usage),
        ("Multi-Step Navigation", example_2_multi_step),
        ("Vision Capabilities", example_3_vision_capabilities),
        ("Error Recovery", example_4_error_recovery),
        ("State Tracking", example_5_state_tracking),
        ("Performance Comparison", example_6_comparison),
        ("Consolidated Tools", example_7_consolidated_tools),
    ]
    
    print("\n" + "="*60)
    print("IMPROVED BROWSER AGENT EXAMPLES")
    print("="*60)
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  0. Run all examples")
    
    choice = input("\nSelect example (0-7): ").strip()
    
    if choice == "0":
        # Run all examples
        for name, func in examples:
            try:
                await func()
                await asyncio.sleep(2)  # Pause between examples
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Example '{name}' failed: {e}")
                continue
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        # Run selected example
        name, func = examples[int(choice) - 1]
        try:
            await func()
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            raise
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

