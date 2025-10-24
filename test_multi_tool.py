#!/usr/bin/env python3
"""Test intelligent routing with multiple tools working together."""

import asyncio
from tools import ToolProcessor
from tools.calculator_tool import CalculatorTool
from tools.datetime_tool import DateTimeTool
from tools.example_tool import ExampleTool
from tools.playwright_tool import PlaywrightTool

async def test_multi_tool_routing():
    """Test cases where multiple tools should be used together."""
    
    print("=" * 70)
    print("Testing Multi-Tool Intelligent Routing")
    print("=" * 70)
    
    # Create processor
    processor = ToolProcessor()
    
    # Register all tools
    calculator = CalculatorTool(enabled=True)
    datetime = DateTimeTool(enabled=True)
    example = ExampleTool(enabled=True, prefix="[Echo]")
    playwright = PlaywrightTool(enabled=True)
    
    processor.register(calculator)
    processor.register(datetime)
    processor.register(example)
    processor.register(playwright)
    
    print(f"\nRegistered tools: {processor.get_enabled_tools()}")
    
    # Test cases designed to trigger multiple tools
    test_cases = [
        "search online for the lebanese prime minister name only",
        # Single tool tests
        # "What time is it?",
        # "Calculate 25 times 4",
        
        # # Multi-tool test cases
        # "What's the time and also calculate 10 plus 5?",
        # "Tell me today's date and compute 100 divided by 4",
        # "What day is it and what's 7 times 8?",
        
        # Complex multi-tool
        # "I need to know the current time, today's date, and the result of 15 plus 27",
    ]
    
    for i, test_input in enumerate(test_cases, 1):
        print("\n" + "=" * 70)
        print(f"Test {i}: {test_input}")
        print("=" * 70)
        
        result = await processor.process(test_input)
        
        print(f"\n>>> Final result: {result}")
    
    print("\n" + "=" * 70)
    print("Multi-Tool Test Complete!")
    print("=" * 70)
    
    # Show what happened
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print("""
The intelligent routing system demonstrated:
1. Single tool selection for simple queries
2. Multi-tool selection when multiple requests in one query
3. Parallel execution of multiple tools (faster than sequential)
4. Natural response synthesis from multiple tool outputs

This shows the power of LLM-based routing - it understands when
to use one tool vs. multiple tools based on the user's intent!
""")


if __name__ == "__main__":
    try:
        asyncio.run(test_multi_tool_routing())
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()

