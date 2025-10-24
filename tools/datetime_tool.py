"""DateTime tool for time and date information using LLM for query understanding."""

import os
from typing import Optional, Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from .base import BaseTool
from datetime import datetime
from config import settings


class DateTimeQuery(BaseModel):
    """Parsed datetime query from natural language."""
    query_type: Literal["time", "date", "day", "month", "year", "full"] = Field(
        description="Type of datetime information requested"
    )
    format_preference: Optional[str] = Field(
        default=None,
        description="Preferred format if specified (e.g., '12-hour', '24-hour')"
    )
    reasoning: str = Field(
        description="Brief explanation of what the user is asking for"
    )


class DateTimeTool(BaseTool):
    """Tool for getting current time, date, and timezone information using LLM parsing."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="datetime",
            description="Provides current time, date, day of week, and timezone information",
            capabilities=(
                "Can tell you the current time, date, day of the week, month, year. "
                "Provides information in various formats (12-hour, 24-hour). "
                "Can answer questions like 'what time is it', 'what's the date', "
                "'what day is it', 'what's today', 'current time', 'tell me the month', etc. "
                "Understands natural language requests for date and time."
            ),
            enabled=enabled,
            priority=90
        )
        self._init_agent()
    
    def _init_agent(self):
        """Initialize the LLM agent for query understanding."""
        # Ensure API key is set
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        system_prompt = """You are a datetime query analyzer. Parse natural language requests for time/date information and categorize them.

Query Types:
- "time": User wants to know the current time
- "date": User wants the full date (day, month, year)
- "day": User wants to know the day of the week
- "month": User wants to know the current month
- "year": User wants to know the current year
- "full": User wants both date and time, or the query is ambiguous

Examples:
- "what time is it" → query_type: "time"
- "what's the date" → query_type: "date"
- "what day is it" → query_type: "day"
- "what's today" → query_type: "date"
- "tell me the current month" → query_type: "month"
- "what year is it" → query_type: "year"
- "give me date and time" → query_type: "full"
"""
        
        self.agent = Agent(
            model=OpenAIChatModel("gpt-4o-mini"),
            output_type=DateTimeQuery,
            system_prompt=system_prompt,
        )
    
    async def process(self, text: str) -> Optional[str]:
        """
        Provide time/date information based on LLM-parsed request.
        
        Args:
            text: User input requesting time/date info
            
        Returns:
            Formatted time/date information or None
        """
        try:
            # Use LLM to understand the query
            result = await self.agent.run(text)
            query: DateTimeQuery = result.output
            
            print(f"[DateTime] Query type: {query.query_type}")
            print(f"[DateTime] Reasoning: {query.reasoning}")
            
            # Get current datetime
            now = datetime.now()
            
            # Provide appropriate information based on query type
            if query.query_type == "time":
                return self._format_time(now)
            elif query.query_type == "date":
                return self._format_date(now)
            elif query.query_type == "day":
                return self._format_day(now)
            elif query.query_type == "month":
                return f"It's {now.strftime('%B %Y')}"
            elif query.query_type == "year":
                return f"The year is {now.year}"
            else:  # full
                return self._format_full(now)
                
        except Exception as e:
            print(f"DateTime error: {e}")
            return None
    
    def _format_time(self, dt: datetime) -> str:
        """Format current time."""
        time_12hr = dt.strftime('%I:%M %p')
        time_24hr = dt.strftime('%H:%M')
        return f"It's {time_12hr} ({time_24hr})"
    
    def _format_date(self, dt: datetime) -> str:
        """Format current date."""
        date_str = dt.strftime('%A, %B %d, %Y')
        return f"Today is {date_str}"
    
    def _format_day(self, dt: datetime) -> str:
        """Format day of week."""
        return f"Today is {dt.strftime('%A')}"
    
    def _format_full(self, dt: datetime) -> str:
        """Format full date and time."""
        date_str = dt.strftime('%A, %B %d, %Y')
        time_str = dt.strftime('%I:%M %p')
        return f"It's {time_str} on {date_str}"

