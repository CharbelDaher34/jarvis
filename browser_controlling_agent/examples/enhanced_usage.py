"""
Example usage of the enhanced browser automation agent with utilities.

This demonstrates how to use the new notification system, logging configuration,
and other utility functions.
"""

import asyncio
from src.browser_agent.runner import run_task
from src.browser_agent.utils import configure_logger, set_log_level


def notification_handler(notification: dict):
    """
    Custom notification handler that prints progress updates.
    
    Args:
        notification: Dictionary with 'message' and 'type' keys
    """
    msg_type = notification['type'].upper()
    message = notification['message']
    
    # Color codes for different message types
    colors = {
        'INFO': '\033[94m',      # Blue
        'SUCCESS': '\033[92m',   # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'STEP': '\033[96m',      # Cyan
    }
    reset = '\033[0m'
    
    color = colors.get(msg_type, '')
    print(f"{color}[{msg_type}]{reset} {message}")


async def example_basic_task():
    """Example: Basic task execution without notifications."""
    print("\n" + "="*60)
    print("Example 1: Basic Task")
    print("="*60)
    
    result = await run_task(
        prompt="Go to google.com and search for 'Python tutorials'",
        headless=False,
        screenshots_dir="./screenshots/example1"
    )
    
    print(f"\nResult: {result}")


async def example_with_notifications():
    """Example: Task with custom notification handler."""
    print("\n" + "="*60)
    print("Example 2: Task with Notifications")
    print("="*60)
    
    result = await run_task(
        prompt="Go to wikipedia.org and search for 'Artificial Intelligence'",
        headless=False,
        screenshots_dir="./screenshots/example2",
        notification_callback=notification_handler
    )
    
    print(f"\nResult: {result}")


async def example_with_starting_url():
    """Example: Task with predefined starting URL."""
    print("\n" + "="*60)
    print("Example 3: Task with Starting URL")
    print("="*60)
    
    result = await run_task(
        prompt="Find information about machine learning",
        starting_url="https://en.wikipedia.org",
        headless=False,
        screenshots_dir="./screenshots/example3",
        notification_callback=notification_handler
    )
    
    print(f"\nResult: {result}")


async def example_custom_logging():
    """Example: Custom logging configuration."""
    print("\n" + "="*60)
    print("Example 4: Custom Logging Configuration")
    print("="*60)
    
    # Configure logging with DEBUG level and file output
    configure_logger(level="DEBUG", log_file="browser_agent_debug.log")
    
    result = await run_task(
        prompt="Go to github.com and search for 'python browser automation'",
        headless=False,
        screenshots_dir="./screenshots/example4"
    )
    
    print(f"\nResult: {result}")
    print("\nCheck 'browser_agent_debug.log' for detailed logs")
    
    # Reset to INFO level
    set_log_level("INFO")


async def example_error_handling():
    """Example: Error handling with notifications."""
    print("\n" + "="*60)
    print("Example 5: Error Handling")
    print("="*60)
    
    try:
        result = await run_task(
            prompt="Click on a non-existent element with id 'does-not-exist'",
            starting_url="https://example.com",
            headless=False,
            screenshots_dir="./screenshots/example5",
            notification_callback=notification_handler
        )
        print(f"\nResult: {result}")
    except Exception as e:
        print(f"\n❌ Task failed as expected: {e}")
        print("Error screenshot saved to ./screenshots/example5/error_state_*.png")


async def main():
    """Run all examples."""
    print("\n" + "="*80)
    print(" " * 20 + "Browser Agent Enhancement Examples")
    print("="*80)
    
    # Configure logging
    configure_logger(level="INFO")
    
    # Run examples (comment out any you don't want to run)
    
    # Example 1: Basic usage
    # await example_basic_task()
    
    # Example 2: With notifications
    await example_with_notifications()
    
    # Example 3: With starting URL
    # await example_with_starting_url()
    
    # Example 4: Custom logging
    # await example_custom_logging()
    
    # Example 5: Error handling
    # await example_error_handling()
    
    print("\n" + "="*80)
    print(" " * 25 + "All examples completed!")
    print("="*80)


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
