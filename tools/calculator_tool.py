"""Calculator tool for mathematical calculations using LLM for expression generation."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from .base import BaseTool
from config import settings


class MathExpression(BaseModel):
    """Mathematical expression extracted from natural language."""
    expression: str = Field(
        description="Python-evaluable mathematical expression using +, -, *, /, **, (), etc."
    )
    reasoning: str = Field(
        description="Brief explanation of how the input was converted to the expression"
    )


class CalculatorTool(BaseTool):
    """Tool for performing mathematical calculations using LLM-generated expressions."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="calculator",
            description="Performs mathematical calculations and evaluates expressions",
            capabilities=(
                "Can evaluate mathematical expressions including basic arithmetic "
                "(addition, subtraction, multiplication, division), exponents, "
                "parentheses, and common math functions. Handles natural language like "
                "'twenty-five times four', 'what's 15 plus 37', 'compute 100 divided by 5'. "
                "Supports decimals, negative numbers, and complex expressions."
            ),
            enabled=enabled
        )
        self._init_agent()
    
    def _init_agent(self):
        """Initialize the LLM agent for expression generation."""
        # Ensure API key is set
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        system_prompt = """You are a mathematical expression generator. Convert natural language math questions into Python-evaluable expressions.

Rules:
- Use standard Python operators: +, -, *, /, ** (power), () for grouping
- Convert word numbers to digits: "twenty-five" → "25"
- Convert word operators: "plus" → "+", "times" → "*", "divided by" → "/"
- Keep expressions simple and direct
- Only output valid Python math expressions (no functions like sqrt, sin, etc.)

Examples:
- "twenty-five times four" → "25 * 4"
- "what's 15 plus 37" → "15 + 37"
- "compute 100 divided by 5" → "100 / 5"
- "2 to the power of 8" → "2 ** 8"
- "(10 plus 5) times 3" → "(10 + 5) * 3"
"""
        
        self.agent = Agent(
            model=OpenAIChatModel("gpt-4o-mini"),
            output_type=MathExpression,
            system_prompt=system_prompt,
        )
    
    async def process(self, text: str) -> Optional[str]:
        """
        Evaluate mathematical expressions from text using LLM.
        
        Args:
            text: User input containing math expression
            
        Returns:
            Calculation result or None on error
        """
        try:
            # Use LLM to generate expression
            result = await self.agent.run(text)
            math_expr: MathExpression = result.output
            
            print(f"[Calculator] Generated expression: {math_expr.expression}")
            print(f"[Calculator] Reasoning: {math_expr.reasoning}")
            
            # Safe evaluation
            calc_result = self._safe_eval(math_expr.expression)
            
            if calc_result is not None:
                return f"The result is: {calc_result}"
            else:
                return None
                
        except Exception as e:
            print(f"Calculator error: {e}")
            return None
    
    def _safe_eval(self, expression: str) -> Optional[float]:
        """Safely evaluate mathematical expression."""
        try:
            # Replace common patterns
            expression = expression.replace('^', '**')  # Handle caret as exponent
            expression = expression.replace('x', '*')   # Handle x as multiplication
            expression = expression.replace('÷', '/')   # Handle division symbol
            
            # Remove any non-math characters for safety
            allowed = set('0123456789+-*/(). ')
            if not all(c in allowed for c in expression):
                # Try to clean it
                cleaned = ''.join(c for c in expression if c in allowed)
                if cleaned:
                    expression = cleaned
                else:
                    return None
            
            # Evaluate using eval (safe because we filtered characters)
            result = eval(expression, {"__builtins__": {}}, {})
            
            # Round to reasonable precision
            if isinstance(result, (int, float)):
                if isinstance(result, float) and result.is_integer():
                    return int(result)
                elif isinstance(result, float):
                    return round(result, 6)
                return result
            
            return None
            
        except Exception as e:
            print(f"Evaluation error: {e}")
            return None

