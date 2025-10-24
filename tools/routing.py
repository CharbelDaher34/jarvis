"""Intelligent tool routing using LLM-based selection."""

import os
from typing import List
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from config import settings


class ToolSelection(BaseModel):
    """Selected tools with reasoning."""
    selected_tools: List[str] = Field(
        description="List of tool names to use for this task"
    )
    reasoning: str = Field(
        description="Brief explanation of why these tools were selected"
    )


class FormattedResponse(BaseModel):
    """Final formatted response."""
    response: str = Field(
        description="Clear, concise response that answers the user's request"
    )


def create_tool_selector_agent(tool_descriptions: dict[str, str]) -> Agent:
    """
    Create an agent that selects appropriate tools based on user input.
    
    Args:
        tool_descriptions: Dict mapping tool name to its capabilities description
        
    Returns:
        Configured pydantic-ai agent for tool selection
    """
    # Ensure API key is set
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    
    # Build tool list description for prompt
    tools_desc = "\n".join([
        f"- **{name}**: {desc}"
        for name, desc in tool_descriptions.items()
    ])
    
    system_prompt = f"""You are a tool routing assistant. Your job is to analyze the user's request and select the most appropriate tool(s) to handle it.

Available tools:
{tools_desc}

Instructions:
1. Carefully analyze what the user is asking for
2. Select ONE or MORE tools that can best accomplish the task
3. If multiple tools are needed, list them all
4. If no tools are appropriate, return an empty list
5. Provide brief reasoning for your selection

Be strategic:
- Use multiple tools when the task requires different capabilities
- Don't select tools unnecessarily
- Consider the most efficient combination
"""
    
    return Agent(
        model=OpenAIChatModel("gpt-4o-mini"),
        output_type=ToolSelection,
        system_prompt=system_prompt,
    )


def create_formatter_agent() -> Agent:
    """
    Create an agent that formats final responses from tool outputs.
    
    Returns:
        Configured pydantic-ai agent for response formatting
    """
    # Ensure API key is set
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    
    system_prompt = """You are a response formatting assistant. Your job is to take the results from various tools and create a clear, natural response for the user.

Instructions:
1. Synthesize information from all tool outputs
2. Create a coherent, conversational response
3. Keep it concise but informative
4. If tools failed or returned errors, acknowledge gracefully
5. Speak naturally as if talking to the user

Style:
- Be friendly and helpful
- Don't mention tool names or technical details
- Focus on answering the user's question
- If results are incomplete, say so honestly
"""
    
    return Agent(
        model=OpenAIChatModel("gpt-4o-mini"),
        output_type=FormattedResponse,
        system_prompt=system_prompt,
    )

