"""
Planner Agent for Browser Automation

This agent is responsible for analyzing user queries and developing detailed,
executable plans for web automation tasks.
"""

from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIChatModel
import logging

from src.browser_agent.config import load_config
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


class PlannerOutput(BaseModel):
    """Output schema for the planner agent."""
    plan: str
    next_step: str


PLANNER_SYSTEM_PROMPT = """
You are a web automation task planner. You work in a loop: Planner[You] -> Browser Agent -> Critique.

Your job: Create a simple, step-by-step plan to gather the information needed to answer the user's query.

## Core Rules

1. **Search with Tools**: Use tool_enhanced_search() to find URLs. NEVER manually navigate to search engines or type in search boxes.
2. **Click Only**: Only click links on websites. No typing anywhere.
3. **One Step**: Each step = one action. Don't combine actions.
4. **Stay Simple**: Keep the plan clear and minimal.
5. **Focus on Goal**: Plan steps to get the specific information the user needs.

## Input You Receive

- User Query: What the user wants to know/find
- Missing Information: What specific data is still needed (from critique agent)
- Feedback: Progress update from previous step
- Current URL: Where the browser currently is

## Planning Steps

For a new task:
1. Use tool_enhanced_search(query) to get search results with URLs
2. Navigate to the best URL from the results
3. Navigate through the site using links to find the needed information

For ongoing tasks with missing information:
- Review what's missing
- Plan the next step to get that specific information
- Use feedback to adjust approach if needed
- Continue with link navigation

## Example 1: New Task

**User Query:** "Find Python FastAPI documentation"

**Output:**
```json
{
  "plan": "1. Use tool_enhanced_search('Python FastAPI documentation')\n2. Navigate to official documentation URL\n3. Browse docs via links",
  "next_step": "Use tool_enhanced_search('Python FastAPI documentation')"
}
```

## Example 2: With Missing Info

**User Query:** "What's the price of iPhone 15?"
**Missing Information:** "Need to visit Apple.com or retailer page to get actual iPhone 15 price"
**Current URL:** "https://www.google.com/search?q=iPhone+15+price"

**Output:**
```json
{
  "plan": "1. Use tool_enhanced_search('iPhone 15 price')\n2. Navigate to Apple.com or retailer\n3. Find and extract price",
  "next_step": "Navigate to Apple.com from search results"
}
```

## Remember

- Use tool_enhanced_search() for all searches
- NEVER go to Google/Bing manually
- NEVER type in search boxes
- Only click links on websites
- Plan to get the specific information that's missing
- Keep it simple and direct
"""


def create_planner_agent() -> Agent:
    """Create and configure the planner agent."""
    config = load_config()
    
    # Get model configuration
    model_type, model_config = config.get_available_model()
    
    if model_type != "openai":
        logger.warning(f"Planner agent optimized for OpenAI, but using {model_type}")
    
    # Create OpenAI model
    api_key = model_config.get("api_key")
    if api_key:
        import os
        os.environ["OPENAI_API_KEY"] = api_key
    
    model = OpenAIChatModel(
        model_name=model_config["model"],
        settings={"temperature": 0.5, "max_tokens": 2048}
    )
    
    logger.info(f"Created planner agent with {model_type} model: {model_config['model']}")
    
    return Agent(
        model,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        output_type=PlannerOutput,
        retries=2,
    )


# Create the planner agent instance
planner_agent = create_planner_agent()
