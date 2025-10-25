"""Test script comparing both tool processing approaches."""

import asyncio
from tools.processor import ToolProcessor
from tools.calculator_tool import CalculatorTool
from tools.datetime_tool import DateTimeTool
from tools.search_tool import SearchTool


async def test_selector_approach():
    """Test the selector approach (original method)."""
    print("=" * 60)
    print("Testing SELECTOR Approach")
    print("=" * 60)
    
    processor = ToolProcessor(approach="selector")
    
    # Register tools
    processor.register(CalculatorTool())
    processor.register(DateTimeTool())
    processor.register(SearchTool())
    
    # Test query
    query = "who is the CEO of eurisko?"
    result = await processor.process(query)
    
    print("\n" + "=" * 60)
    print(f"Query: {query}")
    print(f"Result: {result}")
    print("=" * 60)


async def test_native_approach():
    """Test the native Pydantic AI tool approach."""
    print("\n\n" + "=" * 60)
    print("Testing NATIVE Approach")
    print("=" * 60)
    
    processor = ToolProcessor(approach="native")
    
    # Register tools
    processor.register(CalculatorTool())
    processor.register(DateTimeTool())
    processor.register(SearchTool())
    
    # Test query
    query = "who is the CEO of eurisko? Then tell me today's date then add 10 to today's year"
    result = await processor.process(query)
    
    print("\n" + "=" * 60)
    print(f"Query: {query}")
    print(f"Result: {result}")
    print("=" * 60)


async def test_both_approaches():
    """Test both approaches with the same query."""
    # await test_selector_approach()
    await test_native_approach()


if __name__ == "__main__":
    asyncio.run(test_both_approaches())

