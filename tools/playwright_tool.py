"""Playwright agent tool wrapper."""

from typing import Optional
from .base import BaseTool


class PlaywrightTool(BaseTool):
    """Tool that uses playwright_agent for web automation tasks."""
    
    def __init__(self, enabled: bool = True, headless: bool = True):
        super().__init__(
            name="playwright_agent",
            description="Web browser automation for searching, navigating, and extracting information from websites",
            capabilities=(
                "Can search the web using search engines (Google, DuckDuckGo, etc.), "
                "navigate to specific URLs, interact with web pages (click, type, scroll), "
                "extract text and data from websites, read documentation, "
                "find information online, and perform multi-step web research tasks. "
                "Has vision capabilities to understand page layout and elements."
            ),
            enabled=enabled,
            priority=100
        )
        self.headless = headless
    
    async def process(self, text: str) -> Optional[str]:
        """
        Process text using playwright agent.
        
        Args:
            text: User input/command
            
        Returns:
            Agent result or None on error
        """
        try:
            import os
            from config import settings
            from playwright_agent import run_improved_agent
            
            # Ensure OpenAI API key is in environment
            if settings.OPENAI_API_KEY:
                os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            
            if settings.OPENAI_ORG_ID:
                os.environ["OPENAI_ORG_ID"] = settings.OPENAI_ORG_ID
            
            result = await run_improved_agent(
                task=text,
                headless=self.headless,
                keep_browser_open=False
            )
            return result
        except Exception as e:
            print(f"Playwright agent error: {e}")
            return None

