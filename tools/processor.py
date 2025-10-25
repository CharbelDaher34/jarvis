"""Tool processor with intelligent LLM-based routing."""

import asyncio
import os
from typing import List, Dict
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from .base import BaseTool
from .routing import (
    create_tool_selector_agent,
    create_formatter_agent,
    ToolSelection,
    FormattedResponse
)
from config import settings


class ToolProcessor:
    """Manages and executes registered tools with intelligent routing."""
    
    def __init__(self, approach: str = "selector"):
        """
        Initialize the tool processor.
        
        Args:
            approach: Routing approach to use:
                - "selector": Use LLM to select tools, then run them (default)
                - "native": Pass tools directly to agent as native Pydantic AI tools
        """
        self.tools: Dict[str, BaseTool] = {}
        self.approach = approach
        self.selector_agent = None
        self.formatter_agent = None
        self.native_agent = None
    
    def register(self, tool: BaseTool):
        """
        Register a tool.
        
        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool
        # Rebuild agents when tools change
        self._rebuild_agents()
    
    def unregister(self, tool_name: str):
        """
        Unregister a tool by name.
        
        Args:
            tool_name: Name of tool to remove
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            self._rebuild_agents()
    
    def _rebuild_agents(self):
        """Rebuild agents with current tool descriptions."""
        if not self.tools:
            return
        
        # Build tool descriptions for selector
        enabled_tools = {
            name: f"{tool.description}. Capabilities: {tool.capabilities}"
            for name, tool in self.tools.items()
            if tool.enabled
        }
        
        if not enabled_tools:
            return
        
        if self.approach == "selector":
            self.selector_agent = create_tool_selector_agent(enabled_tools)
            self.formatter_agent = create_formatter_agent()
        elif self.approach == "native":
            self._create_native_agent()
    
    def _create_native_agent(self):
        """Create agent with tools registered as native Pydantic AI tools."""
        # Ensure API key is set
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        system_prompt = """You are a helpful assistant with access to various tools.
Analyze the user's request and use the appropriate tools to help them.
You can use multiple tools if needed to provide a complete answer.
Be conversational and helpful in your responses."""
        
        self.native_agent = Agent(
            model=OpenAIChatModel("gpt-4o-mini"),
            system_prompt=system_prompt,
            deps_type=Dict[str, BaseTool],
        )
        
        # Register each enabled tool as a native Pydantic AI tool
        for tool_name, tool in self.tools.items():
            if tool.enabled:
                self._register_tool_function(tool_name, tool)
    
    def _register_tool_function(self, tool_name: str, tool: BaseTool):
        """Register a BaseTool as a native Pydantic AI tool function."""
        
        async def tool_function(ctx: RunContext[Dict[str, BaseTool]], query: str) -> str:
            """
            Execute the tool with the given query.
            
            Args:
                query: The input text to process with the tool
                
            Returns:
                The tool's output
            """
            tool_instance = ctx.deps.get(tool_name)
            if not tool_instance:
                return f"Tool {tool_name} not available"
            
            try:
                result = await tool_instance.process(query)
                return result if result else "No output from tool"
            except Exception as e:
                return f"Error executing tool: {str(e)}"
        
        # Set function metadata for better schema generation
        tool_function.__name__ = tool_name
        tool_function.__doc__ = f"{tool.description}\n\nCapabilities: {tool.capabilities}"
        
        # Register the tool function with the agent
        self.native_agent.tool(tool_function)
    
    async def process(self, text: str) -> str:
        """
        Process text using the configured routing approach.
        
        Args:
            text: Input text
            
        Returns:
            Formatted response from tool(s) or original text if no tools selected
        """
        # Get enabled tools
        enabled_tools = [t for t in self.tools.values() if t.enabled]
        
        if not enabled_tools:
            print("No enabled tools available")
            return text
        
        # Ensure agents are initialized
        if self.approach == "selector" and not self.selector_agent:
            self._rebuild_agents()
        elif self.approach == "native" and not self.native_agent:
            self._rebuild_agents()
        
        if self.approach == "selector":
            return await self._process_with_selector(text)
        elif self.approach == "native":
            return await self._process_with_native_agent(text)
        else:
            raise ValueError(f"Unknown approach: {self.approach}")
    
    async def _process_with_selector(self, text: str) -> str:
        """
        Process using selector approach.
        
        1. Use LLM to select appropriate tools
        2. Run selected tools in parallel
        3. Use LLM to format final response
        
        Args:
            text: Input text
            
        Returns:
            Formatted response from tool(s)
        """
        try:
            # Step 1: Let LLM select which tools to use
            print(f"\n[Selector Approach] Analyzing: '{text}'")
            selection_result = await self.selector_agent.run(text)
            selection: ToolSelection = selection_result.output
            
            print(f"[Selected] Tools: {selection.selected_tools}")
            print(f"[Reasoning] {selection.reasoning}")
            
            if not selection.selected_tools:
                print("No tools selected, returning original text")
                return text
            
            # Step 2: Run selected tools in parallel
            tool_tasks = []
            tool_names = []
            
            for tool_name in selection.selected_tools:
                if tool_name in self.tools and self.tools[tool_name].enabled:
                    tool_names.append(tool_name)
                    tool_tasks.append(self.tools[tool_name].process(text))
                    print(f"[Executing] {tool_name}")
            
            if not tool_tasks:
                print("No valid tools to execute")
                return text
            
            # Execute all tools concurrently
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
            
            # Collect results
            results_text = []
            for tool_name, result in zip(tool_names, tool_results):
                if isinstance(result, Exception):
                    error_msg = f"[{tool_name} error: {result}]"
                    print(f"[Error] {error_msg}")
                    results_text.append(error_msg)
                elif result:
                    print(f"[Success] {tool_name}: {len(result)} chars")
                    results_text.append(f"[{tool_name}]: {result}")
                else:
                    results_text.append(f"[{tool_name}]: No output")
            
            # Step 3: Use AI agent to formulate final response based on tool outputs
            combined_results = "\n\n".join(results_text)
            formatting_prompt = f"""User asked: {text}

Tool outputs:
{combined_results}

Create a natural, helpful response."""
            
            print("[Formatting] Creating response with AI agent...")
            format_result = await self.formatter_agent.run(formatting_prompt)
            formatted: FormattedResponse = format_result.output
            
            return formatted.response
            
        except Exception as e:
            print(f"Error in selector approach: {e}")
            import traceback
            traceback.print_exc()
            return text
    
    async def _process_with_native_agent(self, text: str) -> str:
        """
        Process using native Pydantic AI tool approach.
        
        The agent has direct access to all tools and decides when to use them.
        
        Args:
            text: Input text
            
        Returns:
            Agent's response after using appropriate tools
        """
        try:
            print(f"\n[Native Approach] Processing: '{text}'")
            
            # Pass the tools dict as dependencies so tool functions can access them
            result = await self.native_agent.run(text, deps=self.tools)
            
            print(f"[Native Agent] Response generated")
            return result.output
            
        except Exception as e:
            print(f"Error in native approach: {e}")
            import traceback
            traceback.print_exc()
            return text
    
    def get_enabled_tools(self) -> List[str]:
        """Get list of enabled tool names."""
        return [name for name, tool in self.tools.items() if tool.enabled]
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all registered tools."""
        return {
            name: f"{tool.description} - {tool.capabilities}"
            for name, tool in self.tools.items()
        }

