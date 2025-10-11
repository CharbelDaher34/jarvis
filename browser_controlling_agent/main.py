"""
Enhanced Browser Controlling Agent - Main Entry Point
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from dotenv import load_dotenv
# Load environment variables
load_dotenv()
from src.browser_agent.runner import run_task
from src.browser_agent.config import load_config

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


EXIT_COMMANDS = {"exit", "quit", "q"}


async def _show_help() -> None:
    print_help()


async def _show_status() -> None:
    await print_status()


async def _clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


COMMAND_HANDLERS: Dict[str, Callable[[], Awaitable[None]]] = {
    "help": _show_help,
    "status": _show_status,
    "clear": _clear_screen,
}


@dataclass
class Args:
    """Command line arguments."""
    prompt: Optional[str]
    headless: bool
    interactive: bool
    performance: bool
    config_check: bool


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced PydanticAI Browser Agent with multi-engine search and advanced automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Search for best restaurants in New York"
  python main.py "Find information about climate change on Wikipedia" --headless
  python main.py --interactive --performance
  python main.py --config-check
        """
    )
    
    parser.add_argument(
        "prompt", 
        nargs="?",
        help="Task prompt for the browser agent to execute"
    )
    
    parser.add_argument(
        "--headless", 
        action="store_true", 
        help="Run Chrome in headless mode (no GUI)"
    )
    
    parser.add_argument(
        "--interactive", 
        action="store_true", 
        help="Run in interactive mode with command prompt"
    )
    
    parser.add_argument(
        "--performance", 
        action="store_true", 
        help="Enable performance monitoring during execution"
    )
    
    parser.add_argument(
        "--config-check", 
        action="store_true", 
        help="Check configuration and exit"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.prompt and not args.interactive and not args.config_check:
        parser.error("Either provide a prompt, use --interactive mode, or use --config-check")
    
    return Args(
        prompt=args.prompt,
        headless=args.headless,
        interactive=args.interactive,
        performance=args.performance,
        config_check=args.config_check
    )


def check_configuration() -> bool:
    """Check and display configuration status."""
    try:
        config = load_config()
        
        print("🔧 Configuration Check")
        print("=" * 50)
        
        # Check API keys
        model_type, model_config = config.get_available_model()
        print(f"✅ Available AI Model: {model_type}")
        print(f"   Model: {model_config.get('model', 'Unknown')}")
        
        # Check browser settings
        print(f"\n🌐 Browser Configuration:")
        print(f"   Headless: {config.browser.headless}")
        print(f"   Window Size: {config.browser.window_width}x{config.browser.window_height}")
        print(f"   Page Load Timeout: {config.browser.page_load_timeout}s")
        
        # Check search settings
        print(f"\n🔍 Search Configuration:")
        print(f"   Default Engine: {config.search.default_engine}")
        print(f"   Max Results: {config.search.max_results_per_search}")
        print(f"   Cache TTL: {config.search.result_cache_ttl}s")
        
        # Check security settings
        print(f"\n🔒 Security Configuration:")
        if config.security.allowed_domains:
            print(f"   Allowed Domains: {', '.join(config.security.allowed_domains)}")
        else:
            print(f"   Allowed Domains: All (no restrictions)")
        
        if config.security.blocked_domains:
            print(f"   Blocked Domains: {', '.join(config.security.blocked_domains)}")
        
        print(f"\n✅ Configuration is valid!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        return False

# 
async def interactive_mode(headless: bool, performance: bool) -> None:
    """Run in interactive mode with a simple command loop."""
    print("🤖 Enhanced Browser Agent - Interactive Mode")
    print("=" * 50)
    print("Type your automation requests or commands:")
    print("  - 'exit' or 'quit' to stop")
    print("  - 'help' for available commands")
    print("  - 'status' for system information")
    print("  - 'clear' to clear screen")
    print()
    
    if performance:
        logger.info("Performance monitoring requested (not available in simplified version)")
    
    try:
        while True:
            try:
                # Get user input
                prompt = input("🎯 Agent > ").strip()
                
                if not prompt:
                    continue
                
                command = prompt.lower()

                if command in EXIT_COMMANDS:
                    print("👋 Goodbye!")
                    break

                handler = COMMAND_HANDLERS.get(command)
                if handler:
                    await handler()
                    continue
                
                # Execute automation task
                print(f"\n🚀 Executing: {prompt}")
                print("-" * 50)
                
                result = await run_task(prompt, headless=headless)
                
                print(f"\n✅ Task completed successfully!")
                print(f"📝 Result length: {len(result)} characters")
                print()
                
            except KeyboardInterrupt:
                print("\n\n⏹️  Task interrupted by user")
                continue
            except Exception as e:
                logger.error(f"Task failed: {e}")
                print(f"❌ Error: {e}")
                continue
    
    finally:
        pass  # Cleanup handled by context managers


def print_help() -> None:
    """Print help information."""
    print("""
📚 Available Commands:
  exit, quit, q     - Exit interactive mode
  help             - Show this help message
  status           - Show system and performance status
  clear            - Clear the screen

🎯 Task Examples:
  "Search for best Italian restaurants in Rome"
  "Find the latest news about artificial intelligence"
  "Compare prices for iPhone 15 on Amazon and Best Buy"
  "Research climate change effects and summarize findings"
  "Find Python programming tutorials for beginners"

💡 Tips:
  - Be specific in your requests for better results
  - You can ask for comparisons across multiple websites
  - The agent can fill forms, handle popups, and navigate complex sites
  - Use natural language - no special syntax required
    """)


async def print_status() -> None:
    """Print current system status."""
    try:
        import psutil
        
        print("\n📊 System Status:")
        print("-" * 30)
        
        # Basic system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        print(f"CPU Usage: {cpu_percent:.1f}%")
        print(f"Memory: {memory.used / (1024 * 1024):.1f}MB ({memory.percent:.1f}%)")
        
        # Browser process info if available
        try:
            browser_count = 0
            browser_memory = 0
            for process in psutil.process_iter(['pid', 'name', 'memory_info']):
                if 'chrome' in process.info['name'].lower():
                    browser_count += 1
                    browser_memory += process.info['memory_info'].rss
            
            if browser_count > 0:
                print(f"Browser Processes: {browser_count}")
                print(f"Browser Memory: {browser_memory / (1024 * 1024):.1f}MB")
        except:
            pass
        
        print()
        
    except ImportError:
        print("📊 Status: psutil not installed for system monitoring")
    except Exception as e:
        print(f"Could not get status: {e}")


async def run_single_task(prompt: str, headless: bool, performance: bool) -> None:
    """Run a single automation task."""
    logger.info(f"Starting single task execution: {prompt}")
    
    if performance:
        logger.info("Performance monitoring requested (not available in simplified version)")
    
    try:
        result = await run_task(prompt, headless=headless)
        
        if result:
            print(f"\n{'='*60}")
            print("🎉 TASK COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}")
        else:
            print("⚠️  Task completed but no output was generated")
        
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise
    
    finally:
        pass  # Cleanup handled by context managers

async def _dispatch(args: Args) -> int:
    """Execute the requested mode and return an exit code."""
    if args.config_check:
        success = check_configuration()
        return 0 if success else 1

    if args.interactive:
        await interactive_mode(args.headless, args.performance)
        return 0

    if args.prompt:
        await run_single_task(args.prompt, args.headless, args.performance)
        return 0

    # parse_args enforces that one of the above is true
    return 0


def main() -> None:
    """Main entry point."""
    try:
        args = parse_args()
        exit_code = asyncio.run(_dispatch(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
