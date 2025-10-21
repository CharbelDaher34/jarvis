"""
Vision-based page analysis using multimodal LLMs.
Enables agent to understand page layout visually.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel

logger = logging.getLogger(__name__)


class VisualElement(BaseModel):
    """Represents an element identified visually."""
    element_type: str  # button, link, input, etc.
    text_content: str
    location_description: str  # "top-right corner", "center of page"
    purpose: Optional[str]  # Inferred purpose


class PageVisualAnalysis(BaseModel):
    """Result of visual page analysis."""
    layout_description: str
    key_elements: List[VisualElement]
    navigation_elements: List[str]
    call_to_action: Optional[str]
    page_purpose: str
    potential_issues: List[str]  # e.g., "popup blocking content"


class VisionAnalyzer:
    """
    Analyzes screenshots using vision-capable LLMs with Pydantic AI.
    
    Supports:
    - GPT-4o (vision built-in)
    - Claude 3.5 Sonnet (vision)
    """
    
    def __init__(self, model_type: str = "auto"):
        """
        Initialize vision analyzer.
        
        Args:
            model_type: 'openai', 'anthropic', or 'auto'
        """
        self.model_type = model_type
        self.model = self._initialize_model()
        
        # Create agents for different analysis types
        self.general_agent = Agent(
            self.model,
            output_type=str,
            system_prompt="You are an expert at analyzing webpage screenshots. Provide detailed, accurate descriptions."
        )
        
        self.structured_agent = Agent(
            self.model,
            output_type=PageVisualAnalysis,
            system_prompt="You are an expert at analyzing webpage structure. Provide structured analysis of page layouts."
        )
    
    def _initialize_model(self):
        """
        Initialize the vision model based on configuration.
        
        Pydantic AI automatically reads API keys from environment variables:
        - OPENAI_API_KEY for OpenAI models
        - ANTHROPIC_API_KEY for Anthropic models
        """
        import os
        
        # Check which API keys are available in environment
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        
        # Try to use available vision model
        if has_openai and self.model_type in ("openai", "auto"):
            logger.info("✅ Initialized GPT-4o (vision) with Pydantic AI")
            return OpenAIChatModel("gpt-4o")
        elif has_anthropic and self.model_type in ("anthropic", "auto"):
            logger.info("✅ Initialized Claude 3.5 Sonnet (vision) with Pydantic AI")
            return AnthropicModel("claude-3-5-sonnet-20241022")
        else:
            logger.warning("No vision model API key found in environment - defaulting to GPT-4o")
            # Fall back to OpenAI (will fail if OPENAI_API_KEY not set)
            return OpenAIChatModel("gpt-4o")
    
    def _create_image_message(self, screenshot: bytes, prompt: str) -> List[Dict[str, Any]]:
        """
        Create message with image for vision models.
        
        Args:
            screenshot: Screenshot bytes
            prompt: Text prompt
        
        Returns:
            Message list with image and text
        """
        base64_image = base64.b64encode(screenshot).decode('utf-8')
        image_url = f"data:image/png;base64,{base64_image}"
        
        return [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
            ]
        }]
    
    async def analyze_screenshot(
        self,
        screenshot: bytes,
        prompt: str = "Describe this webpage and identify all interactive elements."
    ) -> str:
        """
        Analyze screenshot with vision model using Pydantic AI.
        
        Args:
            screenshot: Screenshot bytes (PNG/JPEG)
            prompt: Analysis prompt
        
        Returns:
            Analysis text from vision model
        """
        try:
            # Create message with image
            messages = self._create_image_message(screenshot, prompt)
            
            # Run agent with image
            result = await self.general_agent.run(prompt, message_history=messages)
            
            return result.output
        
        except Exception as e:
            logger.error("Vision analysis failed: %s", e)
            return f"Vision analysis error: {str(e)}"
    
    async def analyze_page_structure(self, screenshot: bytes) -> PageVisualAnalysis:
        """
        Perform structured analysis of page layout with Pydantic AI.
        
        Args:
            screenshot: Page screenshot
        
        Returns:
            Structured PageVisualAnalysis object
        """
        prompt = """
Analyze this webpage screenshot and provide structured information:

1. layout_description: Overall page structure (header, main content, sidebar, footer)
2. key_elements: Important interactive elements (buttons, links, forms) with:
   - element_type (button/link/input/etc)
   - text_content
   - location_description (top-left, center, etc)
   - purpose
3. navigation_elements: Menu items, breadcrumbs, tabs
4. call_to_action: Primary action user should take (or null if none)
5. page_purpose: What is this page for?
6. potential_issues: Any popups, overlays, or accessibility issues
"""
        
        try:
            # Create message with image
            messages = self._create_image_message(screenshot, prompt)
            
            # Run structured agent with image - returns PageVisualAnalysis directly
            result = await self.structured_agent.run(prompt, message_history=messages)
            
            return result.output
        
        except Exception as e:
            logger.error("Structured analysis failed: %s", e)
            # Return fallback
            return PageVisualAnalysis(
                layout_description=f"Analysis failed: {str(e)}",
                key_elements=[],
                navigation_elements=[],
                call_to_action=None,
                page_purpose="Unknown",
                potential_issues=[f"Analysis error: {str(e)}"]
            )
    
    async def find_element_visually(
        self,
        screenshot: bytes,
        element_description: str
    ) -> Dict[str, Any]:
        """
        Locate element based on visual description using Pydantic AI.
        
        Args:
            screenshot: Page screenshot
            element_description: Description like "blue login button in top-right"
        
        Returns:
            Dict with element location and details
        """
        prompt = f"""
Find this element on the page: "{element_description}"

If found, describe:
1. Exact text on the element
2. Location (use percentages from top-left, e.g., "80% right, 10% from top")
3. Element type (button, link, input, etc.)
4. Surrounding elements for context
5. A CSS selector that might work

If not found, explain what you see instead.
"""
        
        analysis = await self.analyze_screenshot(screenshot, prompt)
        
        return {
            "found": "not found" not in analysis.lower(),
            "description": element_description,
            "analysis": analysis
        }
    
    async def detect_page_changes(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes
    ) -> str:
        """
        Compare two screenshots to detect changes.
        
        Useful for verifying actions succeeded.
        """
        # Note: This would require sending both images
        # Currently most APIs don't support direct comparison
        # Would need to analyze both separately and compare results
        
        before_analysis = await self.analyze_screenshot(
            before_screenshot,
            "List all visible interactive elements and their state."
        )
        
        after_analysis = await self.analyze_screenshot(
            after_screenshot,
            "List all visible interactive elements and their state."
        )
        
        # Basic text comparison
        if before_analysis != after_analysis:
            return "Page changed - new elements or state detected"
        else:
            return "No significant changes detected"
    
    async def identify_next_action(self, screenshot: bytes, goal: str) -> str:
        """
        Suggest next action based on current page and goal.
        
        Args:
            screenshot: Current page
            goal: User's goal (e.g., "find pricing information")
        
        Returns:
            Suggested action
        """
        prompt = f"""
User Goal: {goal}

Analyze this webpage and suggest the SINGLE best next action to achieve the goal.

Provide:
1. Recommended action (click, scroll, navigate, extract)
2. Target element (exact text or description)
3. Reasoning

Be specific and actionable.
"""
        
        return await self.analyze_screenshot(screenshot, prompt)


# Example usage
async def example_usage():
    """Demonstrate vision analysis."""
    analyzer = VisionAnalyzer()
    
    # Load a test screenshot
    with open("test_screenshot.png", "rb") as f:
        screenshot = f.read()
    
    # Analyze page
    analysis = await analyzer.analyze_screenshot(
        screenshot,
        "What interactive elements are visible on this page?"
    )
    print("Analysis:", analysis)
    
    # Find specific element
    element_info = await analyzer.find_element_visually(
        screenshot,
        "login button"
    )
    print("Element:", element_info)
    
    # Get next action suggestion
    suggestion = await analyzer.identify_next_action(
        screenshot,
        "find documentation"
    )
    print("Suggested action:", suggestion)


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

