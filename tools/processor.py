"""Tool processor with intelligent LLM-based routing."""

import asyncio
from typing import List, Dict
from .base import BaseTool
from .routing import (
    create_tool_selector_agent,
    create_formatter_agent,
    ToolSelection,
    FormattedResponse
)


class ToolProcessor:
    """Manages and executes registered tools with intelligent routing."""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.selector_agent = None
        self.formatter_agent = None
    
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
        """Rebuild selector agent with current tool descriptions."""
        if not self.tools:
            return
        
        # Build tool descriptions for selector
        enabled_tools = {
            name: f"{tool.description}. Capabilities: {tool.capabilities}"
            for name, tool in self.tools.items()
            if tool.enabled
        }
        
        if enabled_tools:
            self.selector_agent = create_tool_selector_agent(enabled_tools)
            self.formatter_agent = create_formatter_agent()
    
    async def process(self, text: str) -> str:
        """
        Process text using intelligent tool routing.
        
        1. Use LLM to select appropriate tools
        2. Run selected tools in parallel
        3. Use LLM to format final response
        
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
        if not self.selector_agent:
            self._rebuild_agents()
        
        try:
            # Step 1: Let LLM select which tools to use
            print(f"\n[Analyzing] Request: '{text}'")
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
            
            # Step 3: Format final response
            combined_results = "\n\n".join(results_text)
            formatting_prompt = f"""User asked: {text}

Tool outputs:
{combined_results}

Create a natural, helpful response."""
            
            print("[Formatting] Creating response...")
            format_result = await self.formatter_agent.run(formatting_prompt)
            formatted: FormattedResponse = format_result.output
            
            return formatted.response
            
        except Exception as e:
            print(f"Error in intelligent routing: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return original text
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

