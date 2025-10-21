"""
Playwright Agent - Modern browser automation with vision capabilities.

This package provides:
- Async browser automation using Playwright
- Vision-based page understanding
- Adaptive retry strategies
- Consolidated, powerful toolset for agents

Example usage:
    from playwright_agent import create_improved_agent, AsyncBrowserSession
    
    agent = create_improved_agent()
    result = await agent.run("Search for Python tutorials")
"""

# Main agent functions
from .agents.improved_agent import create_improved_agent, run_improved_agent

# Core components
from .core.async_browser import AsyncBrowserSession
from .core.vision_analyzer import VisionAnalyzer, VisualElement, PageVisualAnalysis
from .core.adaptive_retry import AdaptiveRetryManager, StrategyType, RetryStrategy

# Search engines
from .search_engines import EnhancedSearchManager, SearchQuery

# Configuration
from .config import (
    AgentConfig,
    BrowserConfig,
    SearchConfig,
    SecurityConfig,
    load_config
)

# Error handling
from .error_handling import (
    BrowserAgentError,
    BrowserConnectionError,
    PageLoadError,
    ElementNotFoundError,
    NavigationError,
    SearchError,
    SecurityError,
    ErrorSeverity,
    RetryConfig,
    with_retry,
    with_async_retry,
    TimeoutManager,
    CircuitBreaker,
    validate_url
)

__version__ = "0.1.0"

__all__ = [
    # Agent functions
    "create_improved_agent",
    "run_improved_agent",
    
    # Core classes
    "AsyncBrowserSession",
    "VisionAnalyzer",
    "VisualElement",
    "PageVisualAnalysis",
    "AdaptiveRetryManager",
    "StrategyType",
    "RetryStrategy",
    
    # Configuration
    "AgentConfig",
    "BrowserConfig",
    "SearchConfig",
    "SecurityConfig",
    "load_config",
    
    # Exceptions
    "BrowserAgentError",
    "BrowserConnectionError",
    "PageLoadError",
    "ElementNotFoundError",
    "NavigationError",
    "SearchError",
    "SecurityError",
    "ErrorSeverity",
    
    # Utilities
    "RetryConfig",
    "with_retry",
    "with_async_retry",
    "TimeoutManager",
    "CircuitBreaker",
    "validate_url",
    "EnhancedSearchManager",
    "SearchQuery",
]

