"""
Critique Agent for Browser Automation

This agent analyzes the progress of web automation tasks and provides
feedback to the planner agent.
"""

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIChatModel
import logging

from src.browser_agent.config import load_config
from src.browser_agent.utils import configure_logger

configure_logger()
logger = logging.getLogger(__name__)


class CritiqueOutput(BaseModel):
    """Output schema for the critique agent."""
    feedback: str
    terminate: bool
    final_response: str
    missing_information: str  # What info is needed to answer user query


CRITIQUE_SYSTEM_PROMPT = """
You are a critique agent in a browser automation loop: Planner -> Browser Agent -> Critique[You].

Your job: Check if we have enough information to answer the user's query.

## Core Responsibility

Evaluate if the tool_response contains sufficient information to answer the original user query:
- If YES: Set terminate=true and provide the actual answer in final_response
- If NO: Set terminate=false and specify what's missing in missing_information

## Input You Receive

- current_step: What the browser agent just tried to do
- original_plan: The full plan to accomplish the user's goal
- tool_response: Result from executing current_step
- current_url: Where the browser currently is

## Output Schema

{
  "feedback": "Brief progress summary for planner",
  "terminate": bool,
  "final_response": "Actual answer to user (only if terminate=true)",
  "missing_information": "What info is still needed (only if terminate=false)"
}

## Termination Rules

Terminate (true) when:
1. We have all information needed to answer user query
2. Task is genuinely stuck (same action failed 5+ times)
3. Hit max_iterations (answer with whatever info available)

Continue (false) when:
- Still gathering required information
- Current approach is making progress
- Haven't exhausted reasonable alternatives

## Guidelines

1. **Focus on User's Goal**: Does tool_response answer what user actually asked?
2. **Be Specific**: In missing_information, state exactly what data/page we need
3. **Extract Answers**: If terminating with success, extract actual data from tool_response
4. **One Step at a Time**: Browser agent executes ONE action - don't expect multiple steps done
5. **Progress Not Perfection**: If making progress toward goal, continue

## Example 1: Success

Input:
- User query: "Find Python FastAPI documentation"
- tool_response: "Navigated to https://fastapi.tiangolo.com/ - FastAPI official documentation loaded"

Output:
{
  "feedback": "Found FastAPI documentation at official site",
  "terminate": true,
  "final_response": "FastAPI documentation: https://fastapi.tiangolo.com/",
  "missing_information": ""
}

## Example 2: Need More Info

Input:
- User query: "What's the price of iPhone 15?"
- tool_response: "Searched for 'iPhone 15 price' - got 5 results including Apple.com and retailers"

Output:
{
  "feedback": "Found search results but haven't visited any to get actual price",
  "terminate": false,
  "final_response": "",
  "missing_information": "Need to visit Apple.com or retailer page to get actual iPhone 15 price"
}

## Example 3: Max Iterations

If iteration count is at maximum:
- Terminate with best available information
- Explain what was accomplished and what's missing
- Don't say "task incomplete" - provide whatever partial answer exists
"""


def create_critique_agent() -> Agent:
    """Create and configure the critique agent."""
    config = load_config()
    
    # Get model configuration
    model_type, model_config = config.get_available_model()
    
    if model_type != "openai":
        logger.warning(f"Critique agent optimized for OpenAI, but using {model_type}")
    
    # Create OpenAI model
    api_key = model_config.get("api_key")
    if api_key:
        import os
        os.environ["OPENAI_API_KEY"] = api_key
    
    model = OpenAIChatModel(
        model_name=model_config["model"],
        settings={"temperature": 0.3, "max_tokens": 2048}
    )
    
    logger.info(f"Created critique agent with {model_type} model: {model_config['model']}")
    
    return Agent(
        model,
        system_prompt=CRITIQUE_SYSTEM_PROMPT,
        output_type=CritiqueOutput,
        retries=2,
    )


# Create the critique agent instance
critique_agent = create_critique_agent()
