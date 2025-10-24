#!/usr/bin/env python3
"""Test all tools with intelligent routing."""

import asyncio
from tools import ToolProcessor
from tools.calculator_tool import CalculatorTool
from tools.datetime_tool import DateTimeTool
from tools.example_tool import ExampleTool


async def test_tools():
    """Test intelligent routing with multiple tools."""
    
    print("=" * 70)
    print("Testing Intelligent Tool Routing with Multiple Tools")
    print("=" * 70)
    
    # Create processor
    processor = ToolProcessor()
    
    # Register all tools
    calculator = CalculatorTool(enabled=True)
    datetime = DateTimeTool(enabled=True)
    example = ExampleTool(enabled=True)
    
    processor.register(calculator)
    processor.register(datetime)
    processor.register(example)
    
    print(f"\nRegistered tools: {processor.get_enabled_tools()}")
    print("\nTool descriptions:")
    for name, desc in processor.get_tool_descriptions().items():
        print(f"  - {name}: {desc[:100]}...")
    
    # Test cases
    test_cases = [
        "What time is it?",
        "Calculate 25 times 4",
        "What's 15 plus 37?",
        "What's today's date?",
        "Compute 100 divided by 5",
        "What day is it?",
    ]
    
    for i, test_input in enumerate(test_cases, 1):
        print("\n" + "=" * 70)
        print(f"Test {i}: {test_input}")
        print("=" * 70)
        
        result = await processor.process(test_input)
        
        print(f"\nFinal result: {result}")
    
    print("\n" + "=" * 70)
    print("All Tests Complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_tools())
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()

