"""
Example usage of the browser automation system.

The orchestrator now handles the decision between multi-agent and single-agent mode.
Runner always uses the orchestrator.
"""

import asyncio
from src.browser_agent.runner import run_task


async def example_single_agent():
    """Simple task using single browser agent."""
    result = await run_task(
        prompt="Research and compare the top 3 Python web frameworks",
        headless=False,
        use_multi_agent=False  # Single browser agent
    )
    print(f"Result: {result}")


async def example_multi_agent():
    """Complex task using multi-agent system (Planner->Browser->Critique)."""
    result = await run_task(
        prompt="Research and compare the top 3 Python web frameworks",
        headless=False,
        use_multi_agent=True,  # Multi-agent system
        max_iterations=3
    )
    print(f"Result: {result}")


async def example_with_starting_url():
    """Task with a starting URL."""
    result = await run_task(
        prompt="Find the documentation for FastAPI",
        starting_url="https://www.google.com",
        headless=False,
        use_multi_agent=False
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    # Run single agent example
    # asyncio.run(example_single_agent())
    
    # Run multi-agent example
    asyncio.run(example_multi_agent())
    
    # Run with starting URL
    # asyncio.run(example_with_starting_url())
