"""Base class for all tools."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    def __init__(
        self,
        name: str,
        description: str,
        capabilities: str,
        enabled: bool = True
        ):
        """
        Initialize a tool.
        
        Args:
            name: Tool name (used as identifier)
            description: Short description of what the tool does
            capabilities: Detailed description of tool's capabilities
            enabled: Whether the tool is active
        """
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.enabled = enabled
    
    @abstractmethod
    async def process(self, text: str) -> Optional[str]:
        """
        Process input text and return result.
        
        Args:
            text: Input text to process
            
        Returns:
            Processed text or None if tool doesn't handle this input
        """
        ...

