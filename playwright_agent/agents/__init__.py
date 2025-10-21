"""
Browser Automation Agents

This package contains specialized agents for browser automation:
- agent: Main browser execution agent
- planner_agent: Task planning and decomposition agent
- critique_agent: Progress analysis and feedback agent
"""

from .improved_agent import (
    create_improved_agent,
    run_improved_agent
)

__all__ = [
    'create_improved_agent',
    'run_improved_agent'
]