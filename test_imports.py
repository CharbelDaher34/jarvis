"""
Test script to verify all imports work correctly.
Run this from the parent directory: uv run python -m playwright_agent.test_imports
"""

def test_imports():
    """Test that all package imports work correctly."""
    print("Testing playwright_agent imports...\n")
    
    # Test 1: Agent functions
    print("[OK] Testing agent imports...")
    from playwright_agent import create_improved_agent, run_improved_agent
    print(f"  - create_improved_agent: {create_improved_agent.__name__}")
    print(f"  - run_improved_agent: {run_improved_agent.__name__}")
    
    # Test 2: Core classes
    print("\n[OK] Testing core imports...")
    from playwright_agent import (
        AsyncBrowserSession,
        VisionAnalyzer,
        VisualElement,
        PageVisualAnalysis,
        AdaptiveRetryManager,
        StrategyType,
        RetryStrategy
    )
    print(f"  - AsyncBrowserSession: {AsyncBrowserSession.__name__}")
    print(f"  - VisionAnalyzer: {VisionAnalyzer.__name__}")
    print(f"  - VisualElement: {VisualElement.__name__}")
    print(f"  - PageVisualAnalysis: {PageVisualAnalysis.__name__}")
    print(f"  - AdaptiveRetryManager: {AdaptiveRetryManager.__name__}")
    print(f"  - StrategyType: {StrategyType.__name__}")
    print(f"  - RetryStrategy: {RetryStrategy.__name__}")
    
    # Test 3: Configuration
    print("\n[OK] Testing configuration imports...")
    from playwright_agent import (
        AgentConfig,
        BrowserConfig,
        SearchConfig,
        SecurityConfig,
        load_config
    )
    print(f"  - AgentConfig: {AgentConfig.__name__}")
    print(f"  - BrowserConfig: {BrowserConfig.__name__}")
    print(f"  - SearchConfig: {SearchConfig.__name__}")
    print(f"  - SecurityConfig: {SecurityConfig.__name__}")
    print(f"  - load_config: {load_config.__name__}")
    
    # Test 4: Exceptions
    print("\n[OK] Testing exception imports...")
    from playwright_agent import (
        BrowserAgentError,
        BrowserConnectionError,
        PageLoadError,
        ElementNotFoundError,
        NavigationError,
        SearchError,
        SecurityError,
        ErrorSeverity
    )
    print(f"  - BrowserAgentError: {BrowserAgentError.__name__}")
    print(f"  - BrowserConnectionError: {BrowserConnectionError.__name__}")
    print(f"  - PageLoadError: {PageLoadError.__name__}")
    print(f"  - ElementNotFoundError: {ElementNotFoundError.__name__}")
    print(f"  - NavigationError: {NavigationError.__name__}")
    print(f"  - SearchError: {SearchError.__name__}")
    print(f"  - SecurityError: {SecurityError.__name__}")
    print(f"  - ErrorSeverity: {ErrorSeverity.__name__}")
    
    # Test 5: Utilities
    print("\n[OK] Testing utility imports...")
    from playwright_agent import (
        RetryConfig,
        with_retry,
        with_async_retry,
        TimeoutManager,
        CircuitBreaker,
        validate_url
    )
    print(f"  - RetryConfig: {RetryConfig.__name__}")
    print(f"  - with_retry: {with_retry.__name__}")
    print(f"  - with_async_retry: {with_async_retry.__name__}")
    print(f"  - TimeoutManager: {TimeoutManager.__name__}")
    print(f"  - CircuitBreaker: {CircuitBreaker.__name__}")
    print(f"  - validate_url: {validate_url.__name__}")
    
    # Test 6: Subpackage imports
    print("\n[OK] Testing subpackage imports...")
    from playwright_agent.core import AsyncBrowserSession as ABS
    from playwright_agent.agents import create_improved_agent as CIA
    from playwright_agent.config import load_config as LC
    print(f"  - playwright_agent.core.AsyncBrowserSession: {ABS.__name__}")
    print(f"  - playwright_agent.agents.create_improved_agent: {CIA.__name__}")
    print(f"  - playwright_agent.config.load_config: {LC.__name__}")
    
    # Test 7: Version
    print("\n[OK] Testing version...")
    import playwright_agent
    print(f"  - __version__: {playwright_agent.__version__}")
    
    # Test 8: __all__ exports
    print("\n[OK] Testing __all__ exports...")
    print(f"  - Total exports: {len(playwright_agent.__all__)}")
    print(f"  - Exports: {', '.join(playwright_agent.__all__[:5])}...")
    
    print("\n" + "="*50)
    print("[SUCCESS] All imports successful!")
    print("="*50)
    
    return True


if __name__ == "__main__":
    try:
        test_imports()
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        raise
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        raise

