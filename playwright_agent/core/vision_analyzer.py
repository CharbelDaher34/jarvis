"""
Vision-based page analysis using multimodal LLMs.
Enables agent to understand page layout visually.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from pydantic import BaseModel

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
    Analyzes screenshots using vision-capable LLMs.
    
    Supports:
    - GPT-4o (vision built-in)
    - Claude 3.5 Sonnet (vision)
    - Gemini Pro Vision
    """
    
    def __init__(self, model_type: str = "auto"):
        """
        Initialize vision analyzer.
        
        Args:
            model_type: 'gpt4v', 'claude', 'gemini', or 'auto'
        """
        self.model_type = model_type
        self._vision_model = self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the vision model based on configuration."""
        from config import load_config
        
        config = load_config()
        
        # Try to use available vision model
        if config.openai_api_key and self.model_type in ("gpt4v", "auto"):
            return self._init_gpt4v(config)
        elif config.anthropic_api_key and self.model_type in ("claude", "auto"):
            return self._init_claude(config)
        elif config.gemini_api_key and self.model_type in ("gemini", "auto"):
            return self._init_gemini(config)
        else:
            logger.warning("No vision model available - vision analysis disabled")
            return None
    
    def _init_gpt4v(self, config):
        """Initialize GPT-4o with vision."""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=config.openai_api_key)
        logger.info("✅ Initialized GPT-4o (vision)")
        return ("gpt4v", client)
    
    def _init_claude(self, config):
        """Initialize Claude with vision."""
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic(api_key=config.anthropic_api_key)
        logger.info("✅ Initialized Claude 3.5 Sonnet (vision)")
        return ("claude", client)
    
    def _init_gemini(self, config):
        """Initialize Gemini with vision."""
        import google.generativeai as genai
        
        genai.configure(api_key=config.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro-vision')
        logger.info("✅ Initialized Gemini Pro Vision")
        return ("gemini", model)
    
    async def analyze_screenshot(
        self,
        screenshot: bytes,
        prompt: str = "Describe this webpage and identify all interactive elements."
    ) -> str:
        """
        Analyze screenshot with vision model.
        
        Args:
            screenshot: Screenshot bytes (PNG/JPEG)
            prompt: Analysis prompt
        
        Returns:
            Analysis text from vision model
        """
        if not self._vision_model:
            return "Vision analysis not available - no vision model configured"
        
        model_type, client = self._vision_model
        
        try:
            if model_type == "gpt4v":
                return await self._analyze_with_gpt4v(screenshot, prompt, client)
            elif model_type == "claude":
                return await self._analyze_with_claude(screenshot, prompt, client)
            elif model_type == "gemini":
                return await self._analyze_with_gemini(screenshot, prompt, client)
        
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"Vision analysis error: {str(e)}"
    
    async def _analyze_with_gpt4v(self, screenshot: bytes, prompt: str, client) -> str:
        """Analyze with GPT-4o (vision built-in)."""
        # Encode image to base64
        base64_image = base64.b64encode(screenshot).decode('utf-8')
        
        response = await client.chat.completions.create(
            model="gpt-4o",  # Updated from deprecated gpt-4-vision-preview
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    async def _analyze_with_claude(self, screenshot: bytes, prompt: str, client) -> str:
        """Analyze with Claude 3.5 Sonnet."""
        base64_image = base64.b64encode(screenshot).decode('utf-8')
        
        message = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        
        return message.content[0].text
    
    async def _analyze_with_gemini(self, screenshot: bytes, prompt: str, model) -> str:
        """Analyze with Gemini Pro Vision."""
        import PIL.Image
        import io
        
        # Convert bytes to PIL Image
        image = PIL.Image.open(io.BytesIO(screenshot))
        
        response = await model.generate_content_async([prompt, image])
        return response.text
    
    async def analyze_page_structure(self, screenshot: bytes) -> PageVisualAnalysis:
        """
        Perform structured analysis of page layout.
        
        Args:
            screenshot: Page screenshot
        
        Returns:
            Structured PageVisualAnalysis object
        """
        prompt = """
Analyze this webpage screenshot and provide:

1. Layout Description: Overall page structure (header, main content, sidebar, footer)
2. Key Elements: Important interactive elements (buttons, links, forms)
   For each element note:
   - Type (button/link/input/etc)
   - Text content
   - Location (top-left, center, etc)
   - Purpose
3. Navigation Elements: Menu items, breadcrumbs, tabs
4. Call to Action: Primary action user should take
5. Page Purpose: What is this page for?
6. Potential Issues: Any popups, overlays, or accessibility issues

Format as JSON.
"""
        
        result = await self.analyze_screenshot(screenshot, prompt)
        
        # Parse response into structured format
        # (In production, use structured output from LLM)
        return PageVisualAnalysis(
            layout_description=result[:200],
            key_elements=[],
            navigation_elements=[],
            call_to_action=None,
            page_purpose=result[:100],
            potential_issues=[]
        )
    
    async def find_element_visually(
        self,
        screenshot: bytes,
        element_description: str
    ) -> Dict[str, Any]:
        """
        Locate element based on visual description.
        
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
        
        # Parse and return structured data
        return {
            "found": True,  # Would parse from analysis
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

