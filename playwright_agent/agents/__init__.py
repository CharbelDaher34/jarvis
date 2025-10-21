"""
Browser Automation Agents

This package contains specialized agents for browser automation:
- improved_agent: Main browser execution agent with vision capabilities
"""

from .improved_agent import (
    create_improved_agent,
    run_improved_agent,
    BrowserContext,
)

__all__ = [
    "create_improved_agent",
    "run_improved_agent",
    "BrowserContext",
]