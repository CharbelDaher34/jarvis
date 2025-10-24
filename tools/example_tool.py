"""Example tool implementation - demonstrates how to create custom tools."""

from typing import Optional
from .base import BaseTool


class ExampleTool(BaseTool):
    """
    Example tool that demonstrates the BaseTool interface.
    
    This tool simply echoes back the input with a prefix.
    Replace this with your actual tool logic.
    """
    
    def __init__(self, enabled: bool = True, prefix: str = "Echo"):
        """
        Initialize the example tool.
        
        Args:
            enabled: Whether the tool is active
            prefix: Prefix to add to echoed text
        """
        super().__init__(
            name="example_tool",
            description="Simple echo tool for testing and demonstration",
            capabilities=(
                "Echoes back user input with a configurable prefix. "
                "Useful for testing the tool system and as a template for new tools."
            ),
            enabled=enabled,
            priority=10
        )
        self.prefix = prefix
    
    async def process(self, text: str) -> Optional[str]:
        """
        Process the input text.
        
        Args:
            text: Input text to process
            
        Returns:
            Processed result or None on error
        """
        try:
            # Your tool logic here
            result = f"{self.prefix}: {text}"
            return result
        except Exception as e:
            print(f"Error in {self.name}: {e}")
            return None


# To use this tool:
# 1. Add "example_tool" to enabled_tools in config.py
# 2. In main.py, import and register:
#
#    from tools.example_tool import ExampleTool
#    
#    if "example_tool" in settings.enabled_tools:
#        example_tool = ExampleTool(enabled=True, prefix="My Echo")
#        processor.register(example_tool)
#
# Note: With intelligent routing, the LLM will decide when to use this tool
# based on its description and capabilities, not manual conditions.


