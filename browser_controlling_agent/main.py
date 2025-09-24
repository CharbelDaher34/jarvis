"""
Enhanced Browser Controlling Agent - Main Entry Point
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
# Load environment variables
load_dotenv()
from src.browser_agent.runner import run_task
from src.browser_agent.config import load_config
from src.browser_agent.user_experience import logger
from src.browser_agent.performance import start_performance_monitoring, stop_performance_monitoring


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


async def interactive_mode(headless: bool, performance: bool) -> None:
    """Run in interactive mode with command prompt."""
    print("🤖 Enhanced Browser Agent - Interactive Mode")
    print("=" * 50)
    print("Type your automation requests or commands:")
    print("  - 'exit' or 'quit' to stop")
    print("  - 'help' for available commands")
    print("  - 'status' for system information")
    print("  - 'clear' to clear screen")
    print()
    
    if performance:
        start_performance_monitoring()
    
    try:
        while True:
            try:
                # Get user input
                prompt = input("🎯 Agent > ").strip()
                
                if not prompt:
                    continue
                
                # Handle special commands
                if prompt.lower() in ['exit', 'quit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                elif prompt.lower() == 'help':
                    print_help()
                    continue
                
                elif prompt.lower() == 'status':
                    await print_status()
                    continue
                
                elif prompt.lower() == 'clear':
                    import os
                    os.system('cls' if os.name == 'nt' else 'clear')
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
        if performance:
            stop_performance_monitoring()


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
        from src.browser_agent.performance import get_performance_report
        
        report = get_performance_report()
        
        print("\n📊 System Status:")
        print("-" * 30)
        
        if report["performance"]["current"]:
            current = report["performance"]["current"]
            print(f"CPU Usage: {current['cpu_percent']:.1f}%")
            print(f"Memory: {current['memory_mb']:.1f}MB")
            if current['browser_memory_mb']:
                print(f"Browser Memory: {current['browser_memory_mb']:.1f}MB")
        
        tabs = report["tabs"]
        print(f"Browser Tabs: {tabs['count']}/{tabs['max_allowed']}")
        
        cleanup = report["cleanup"]
        print(f"Auto Cleanup: {'Enabled' if cleanup['auto_enabled'] else 'Disabled'}")
        print()
        
    except Exception as e:
        print(f"Could not get status: {e}")


async def run_single_task(prompt: str, headless: bool, performance: bool) -> None:
    """Run a single automation task."""
    logger.user_action("Starting single task execution", prompt)
    
    if performance:
        start_performance_monitoring()
    
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
        sys.exit(1)
    
    finally:
        if performance:
            stop_performance_monitoring()


def main() -> None:
    """Main entry point."""

    
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Configuration check mode
        if args.config_check:
            success = check_configuration()
            sys.exit(0 if success else 1)
        args.headless = False  # Force
        # Interactive mode
        if args.interactive:
            asyncio.run(interactive_mode(args.headless, args.performance))
            return
        
        # Single task mode
        if args.prompt:
            asyncio.run(run_single_task(args.prompt, args.headless, args.performance))
            return
        
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
