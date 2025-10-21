"""
Playwright Agent - Modern browser automation with vision capabilities.

This package provides:
- Async browser automation using Playwright
- Vision-based page understanding
- Adaptive retry strategies
- Consolidated, powerful toolset for agents
"""

from .agents.improved_agent import create_improved_agent, run_improved_agent
from .core.async_browser import AsyncBrowserSession
from .core.vision_analyzer import VisionAnalyzer
from .core.adaptive_retry import AdaptiveRetryManager

__all__ = [
    'create_improved_agent',
    'run_improved_agent',
    'AsyncBrowserSession',
    'VisionAnalyzer',
    'AdaptiveRetryManager',
]

