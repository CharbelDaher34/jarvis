"""Search tool for querying multiple search engines with LLM-based query parsing."""

import os
from typing import Optional, List
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from .base import BaseTool
from config import settings

# Import from playwright_agent's search engines
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright_agent.search_engines import (
    EnhancedSearchManager,
    SearchQuery,
    SearchResult
)


class ParsedSearchQuery(BaseModel):
    """Parsed search query from natural language."""
    search_terms: str = Field(
        description="Main search terms/keywords to look for"
    )
    max_results: int = Field(
        default=5,
        description="Number of results to return per engine (1-20)"
    )
    site_filter: Optional[str] = Field(
        default=None,
        description="Restrict search to specific site (e.g., 'python.org')"
    )
    filetype_filter: Optional[str] = Field(
        default=None,
        description="Filter by file type (e.g., 'pdf', 'doc')"
    )
    exclude_terms: List[str] = Field(
        default_factory=list,
        description="Terms to exclude from results"
    )
    use_multiple_engines: bool = Field(
        default=True,
        description="Whether to search across multiple engines for better coverage"
    )
    reasoning: str = Field(
        description="Brief explanation of the parsed query"
    )


class SearchTool(BaseTool):
    """Tool for searching the web using multiple search engines in parallel."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="search_tool",
            description="Search the web for information using multiple search engines",
            capabilities=(
                "Searches across Google, DuckDuckGo, and other search engines simultaneously "
                "for comprehensive results. Can answer questions like 'search for Python tutorials', "
                "'find information about climate change', 'look up latest news on AI', "
                "'search python.org for documentation', 'find PDF documents about machine learning'. "
                "Returns aggregated results from multiple sources for better coverage and reliability. "
                "Different from playwright_agent which browses and extracts content from pages - "
                "this tool just finds relevant URLs and summaries."
            ),
            enabled=enabled,
            priority=85
        )
        self._init_agent()
        self.search_manager = EnhancedSearchManager()
    
    def _init_agent(self):
        """Initialize the LLM agent for query parsing."""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        system_prompt = """You are a search query analyzer. Parse natural language search requests into structured queries.

Extract Information:
- search_terms: The main keywords/phrases to search for
- max_results: How many results per engine (default 5, max 20)
- site_filter: If user wants results from specific site (e.g., "site:reddit.com")
- filetype_filter: If user wants specific file types (e.g., "pdf", "doc")
- exclude_terms: Words that should NOT appear in results
- use_multiple_engines: True for better coverage (default), False for single engine

Examples:
- "search for Python tutorials"
  → search_terms: "Python tutorials", max_results: 5, use_multiple_engines: True

- "find latest AI news"
  → search_terms: "latest AI news", max_results: 5, use_multiple_engines: True

- "look up Python documentation on python.org"
  → search_terms: "Python documentation", site_filter: "python.org", max_results: 5

- "find PDF papers about machine learning"
  → search_terms: "machine learning papers", filetype_filter: "pdf", max_results: 5

- "search for React tutorials but not TypeScript"
  → search_terms: "React tutorials", exclude_terms: ["TypeScript"], max_results: 5

- "find top 10 JavaScript frameworks"
  → search_terms: "JavaScript frameworks", max_results: 10, use_multiple_engines: True
"""
        
        self.agent = Agent(
            model=OpenAIChatModel("gpt-4o-mini"),
            output_type=ParsedSearchQuery,
            system_prompt=system_prompt,
        )
    
    async def process(self, text: str) -> Optional[str]:
        """
        Perform web search based on LLM-parsed request.
        
        Args:
            text: User input requesting search
            
        Returns:
            Formatted search results or None on error
        """
        try:
            # Use LLM to understand the search query
            result = await self.agent.run(text)
            parsed_query: ParsedSearchQuery = result.output
            
            print(f"[Search] Query: {parsed_query.search_terms}")
            print(f"[Search] Reasoning: {parsed_query.reasoning}")
            if parsed_query.site_filter:
                print(f"[Search] Site filter: {parsed_query.site_filter}")
            if parsed_query.filetype_filter:
                print(f"[Search] Filetype: {parsed_query.filetype_filter}")
            
            # Create SearchQuery object
            search_query = SearchQuery(
                query=parsed_query.search_terms,
                max_results=min(parsed_query.max_results, 20),
                site_filter=parsed_query.site_filter,
                filetype_filter=parsed_query.filetype_filter,
                exclude_terms=parsed_query.exclude_terms
            )
            
            # Get available engines
            available_engines = self.search_manager.get_available_engines()
            
            if not available_engines:
                return "No search engines are currently available. Please configure search engine API keys."
            
            print(f"[Search] Available engines: {', '.join(available_engines)}")
            
            # Perform search (multi-engine or single)
            if parsed_query.use_multiple_engines and len(available_engines) > 1:
                print(f"[Search] Searching across {len(available_engines)} engines in parallel...")
                results_by_engine = self.search_manager.multi_engine_search(
                    search_query,
                    engines=available_engines
                )
                
                # Format multi-engine results
                return self._format_multi_engine_results(results_by_engine, parsed_query.search_terms)
            else:
                print(f"[Search] Searching with primary engine...")
                results = self.search_manager.search(search_query)
                
                # Format single engine results
                return self._format_results(results, parsed_query.search_terms)
                
        except Exception as e:
            print(f"[Search] Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _format_results(self, results: List[SearchResult], query: str) -> str:
        """Format search results from a single engine."""
        if not results:
            return f"No results found for '{query}'."
        
        output = f"Found {len(results)} results for '{query}':\n\n"
        
        for i, result in enumerate(results[:10], 1):  # Limit to top 10
            output += f"{i}. **{result.title}**\n"
            output += f"   URL: {result.url}\n"
            output += f"   {result.description}\n"
            output += f"   Source: {result.source_engine}\n\n"
        
        return output.strip()
    
    def _format_multi_engine_results(
        self,
        results_by_engine: dict,
        query: str
    ) -> str:
        """Format search results from multiple engines."""
        # Count total results
        total_results = sum(len(results) for results in results_by_engine.values())
        
        if total_results == 0:
            return f"No results found for '{query}' across any search engine."
        
        # Aggregate and deduplicate results by URL
        all_results = []
        seen_urls = set()
        
        for engine_name, results in results_by_engine.items():
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    all_results.append(result)
        
        # Sort by rank (lower is better)
        all_results.sort(key=lambda r: r.rank)
        
        output = f"Found {len(all_results)} unique results for '{query}' "
        output += f"(searched {len(results_by_engine)} engines):\n\n"
        
        # Show top 10 results
        for i, result in enumerate(all_results[:10], 1):
            output += f"{i}. **{result.title}**\n"
            output += f"   URL: {result.url}\n"
            output += f"   {result.description[:200]}{'...' if len(result.description) > 200 else ''}\n"
            output += f"   Source: {result.source_engine}\n\n"
        
        # Show breakdown by engine
        output += "\n---\n"
        output += "Results by engine:\n"
        for engine_name, results in results_by_engine.items():
            output += f"- {engine_name}: {len(results)} results\n"
        
        return output.strip()

