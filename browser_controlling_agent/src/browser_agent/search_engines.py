"""
Enhanced search capabilities with multiple search engines and intelligent filtering.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import json
import hashlib

from src.browser_agent.error_handling import SearchError, validate_url, with_retry, RetryConfig
from src.browser_agent.config import load_config

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Structured search result with metadata."""
    title: str
    url: str
    description: str
    source_engine: str
    rank: int
    domain: str = ""
    cached_at: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.domain:
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.lower()

@dataclass 
class SearchQuery:
    """Enhanced search query with filtering options."""
    query: str
    max_results: int = 10
    language: str = "en"
    region: str = "us"
    time_filter: Optional[str] = None  # "day", "week", "month", "year"
    site_filter: Optional[str] = None  # Restrict to specific site
    filetype_filter: Optional[str] = None  # "pdf", "doc", etc.
    exclude_terms: List[str] = None
    
    def __post_init__(self):
        if self.exclude_terms is None:
            self.exclude_terms = []

class SearchEngine(ABC):
    """Abstract base class for search engines."""
    
    @abstractmethod
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform search and return structured results."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the search engine."""
        pass

class GoogleSearchEngine(SearchEngine):
    """Google search implementation."""
    
    @property
    def name(self) -> str:
        return "google"
    
    @with_retry(RetryConfig(max_attempts=3, base_delay=2.0), (Exception,), logger)
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform Google search."""
        try:
            from googlesearch import search
            
            # Build search string with filters
            search_string = self._build_search_string(query)
            
            results = []
            rank = 1
            
            for url in search(
                search_string, 
                num_results=query.max_results,
                # stop=query.max_results,
                unique=True,
                lang=query.language,
                # tld=f"google.{query.region}" if query.region != "us" else "google.com"
            ):
                # Validate URL
                is_valid, error = validate_url(url)
                if not is_valid:
                    logger.warning(f"Skipping invalid URL: {url} ({error})")
                    continue
                
                result = SearchResult(
                    title=f"Result {rank}",  # Google search doesn't return titles
                    url=url,
                    description="",  # Would need additional scraping
                    source_engine=self.name,
                    rank=rank,
                    cached_at=datetime.now()
                )
                results.append(result)
                rank += 1
                
            logger.info(f"Google search for '{query.query}' returned {len(results)} results")
            return results
            
        except ImportError:
            raise SearchError("googlesearch-python package not installed")
        except Exception as e:
            raise SearchError(f"Google search failed: {str(e)}")
    
    def _build_search_string(self, query: SearchQuery) -> str:
        """Build Google search string with filters."""
        search_parts = [query.query]
        
        # Site filter
        if query.site_filter:
            search_parts.append(f"site:{query.site_filter}")
        
        # Filetype filter
        if query.filetype_filter:
            search_parts.append(f"filetype:{query.filetype_filter}")
        
        # Time filter (using Google's date syntax)
        if query.time_filter:
            time_mapping = {
                "day": "d1",
                "week": "w1", 
                "month": "m1",
                "year": "y1"
            }
            if query.time_filter in time_mapping:
                search_parts.append(f"after:{time_mapping[query.time_filter]}")
        
        # Exclude terms
        for exclude_term in query.exclude_terms:
            search_parts.append(f"-{exclude_term}")
        
        return " ".join(search_parts)

class DuckDuckGoSearchEngine(SearchEngine):
    """DuckDuckGo search implementation."""
    
    @property 
    def name(self) -> str:
        return "duckduckgo"
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform DuckDuckGo search."""
        try:
            # Prefer the renamed package `ddgs`; fall back to legacy `duckduckgo_search`.
            try:
                from ddgs import DDGS  # type: ignore
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore
            
            search_string = self._build_search_string(query)
            
            with DDGS() as ddgs:
                results = []
                rank = 1
                
                ddgs_results = ddgs.text(
                    search_string,
                    max_results=query.max_results,
                    region=f"{query.language}-{query.region}",
                    safesearch="moderate"
                )
                
                for result_data in ddgs_results:
                    # Validate URL
                    url = result_data.get('href', '')
                    is_valid, error = validate_url(url)
                    if not is_valid:
                        logger.warning(f"Skipping invalid URL: {url} ({error})")
                        continue
                    
                    result = SearchResult(
                        title=result_data.get('title', f'Result {rank}'),
                        url=url,
                        description=result_data.get('body', ''),
                        source_engine=self.name,
                        rank=rank,
                        cached_at=datetime.now()
                    )
                    results.append(result)
                    rank += 1
                
                logger.info(f"DuckDuckGo search for '{query.query}' returned {len(results)} results")
                return results
                
        except ImportError:
            raise SearchError("ddgs (or legacy duckduckgo-search) package not installed. Install via 'pip install ddgs'.")
        except Exception as e:
            raise SearchError(f"DuckDuckGo search failed: {str(e)}")
    
    def _build_search_string(self, query: SearchQuery) -> str:
        """Build DuckDuckGo search string with filters."""
        search_parts = [query.query]
        
        # Site filter
        if query.site_filter:
            search_parts.append(f"site:{query.site_filter}")
        
        # Filetype filter  
        if query.filetype_filter:
            search_parts.append(f"filetype:{query.filetype_filter}")
        
        # Exclude terms
        for exclude_term in query.exclude_terms:
            search_parts.append(f"-{exclude_term}")
        
        return " ".join(search_parts)

class BingSearchEngine(SearchEngine):
    """Bing search implementation (requires API key)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._get_api_key()
    
    @property
    def name(self) -> str:
        return "bing"
    
    def _get_api_key(self) -> Optional[str]:
        """Get Bing API key from environment."""
        import os
        return os.getenv("BING_SEARCH_API_KEY")
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform Bing search via API."""
        if not self.api_key:
            raise SearchError("Bing API key not configured")
        
        try:
            import requests
            
            search_url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            
            params = {
                "q": query.query,
                "count": min(query.max_results, 50),  # Bing max is 50
                "mkt": f"{query.language}-{query.region}",
                "responseFilter": "webpages",
                "answerCount": 1
            }
            
            # Add time filter if specified
            if query.time_filter:
                freshness_mapping = {
                    "day": "Day",
                    "week": "Week", 
                    "month": "Month"
                }
                if query.time_filter in freshness_mapping:
                    params["freshness"] = freshness_mapping[query.time_filter]
            
            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if "webPages" in data and "value" in data["webPages"]:
                for idx, result_data in enumerate(data["webPages"]["value"], 1):
                    url = result_data.get("url", "")
                    
                    # Validate URL
                    is_valid, error = validate_url(url)
                    if not is_valid:
                        logger.warning(f"Skipping invalid URL: {url} ({error})")
                        continue
                    
                    result = SearchResult(
                        title=result_data.get("name", f"Result {idx}"),
                        url=url,
                        description=result_data.get("snippet", ""),
                        source_engine=self.name,
                        rank=idx,
                        cached_at=datetime.now()
                    )
                    results.append(result)
            
            logger.info(f"Bing search for '{query.query}' returned {len(results)} results")
            return results
            
        except ImportError:
            raise SearchError("requests package not installed")
        except Exception as e:
            raise SearchError(f"Bing search failed: {str(e)}")

class SearchResultCache:
    """Simple in-memory cache for search results."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_cache_key(self, query: SearchQuery, engine_name: str) -> str:
        """Generate cache key for query."""
        query_data = {
            "query": query.query,
            "engine": engine_name,
            "max_results": query.max_results,
            "language": query.language,
            "region": query.region,
            "site_filter": query.site_filter,
            "filetype_filter": query.filetype_filter,
            "exclude_terms": sorted(query.exclude_terms)
        }
        
        query_str = json.dumps(query_data, sort_keys=True)
        return hashlib.md5(query_str.encode()).hexdigest()
    
    def get(self, query: SearchQuery, engine_name: str) -> Optional[List[SearchResult]]:
        """Get cached results if available and not expired."""
        cache_key = self._get_cache_key(query, engine_name)
        
        if cache_key not in self.cache:
            return None
        
        cached_data = self.cache[cache_key]
        cached_at = cached_data["timestamp"]
        
        # Check if expired
        if datetime.now() - cached_at > timedelta(seconds=self.ttl_seconds):
            del self.cache[cache_key]
            return None
        
        logger.debug(f"Cache hit for query '{query.query}' on engine '{engine_name}'")
        return cached_data["results"]
    
    def put(self, query: SearchQuery, engine_name: str, results: List[SearchResult]) -> None:
        """Cache search results."""
        cache_key = self._get_cache_key(query, engine_name)
        
        self.cache[cache_key] = {
            "timestamp": datetime.now(),
            "results": results
        }
        
        logger.debug(f"Cached {len(results)} results for query '{query.query}' on engine '{engine_name}'")
    
    def clear_expired(self) -> int:
        """Remove expired cache entries and return count removed."""
        now = datetime.now()
        expired_keys = []
        
        for key, data in self.cache.items():
            if now - data["timestamp"] > timedelta(seconds=self.ttl_seconds):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)

class EnhancedSearchManager:
    """Manages multiple search engines with caching and result aggregation."""
    
    def __init__(self):
        self.engines: Dict[str, SearchEngine] = {}
        self.cache = SearchResultCache()
        self._initialize_engines()
    
    def _initialize_engines(self):
        """Initialize available search engines."""
        # Google (always available with googlesearch-python)
        self.engines["google"] = GoogleSearchEngine()
        
        # DuckDuckGo (if package available)
        try:
            self.engines["duckduckgo"] = DuckDuckGoSearchEngine()
        except ImportError:
            logger.warning("DuckDuckGo search not available - install duckduckgo-search package")
        
        # Bing (if API key available)
        bing_engine = BingSearchEngine()
        if bing_engine.api_key:
            self.engines["bing"] = bing_engine
        else:
            logger.info("Bing search not available - BING_SEARCH_API_KEY not configured")
    
    def get_available_engines(self) -> List[str]:
        """Get list of available search engine names."""
        return list(self.engines.keys())
    
    def search(self, query: SearchQuery, engine_name: Optional[str] = None) -> List[SearchResult]:
        """
        Perform search using specified engine or default.
        
        Args:
            query: Search query with filters
            engine_name: Specific engine to use, or None for default
            
        Returns:
            List of search results
        """
        config = load_config()
        
        # Determine which engine to use
        if engine_name and engine_name in self.engines:
            selected_engine = engine_name
        elif config.search.default_engine in self.engines:
            selected_engine = config.search.default_engine
        elif self.engines:
            selected_engine = next(iter(self.engines.keys()))
        else:
            raise SearchError("No search engines available")
        
        engine = self.engines[selected_engine]
        
        # Check cache first
        cached_results = self.cache.get(query, selected_engine)
        if cached_results:
            return cached_results
        
        # Perform search
        try:
            results = engine.search(query)
            
            # Apply security filtering
            filtered_results = self._apply_security_filters(results)
            
            # Cache results
            self.cache.put(query, selected_engine, filtered_results)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Search failed on engine '{selected_engine}': {e}")
            
            # Try fallback engines if primary fails
            for fallback_engine_name, fallback_engine in self.engines.items():
                if fallback_engine_name != selected_engine:
                    try:
                        logger.info(f"Trying fallback search engine: {fallback_engine_name}")
                        results = fallback_engine.search(query)
                        filtered_results = self._apply_security_filters(results)
                        self.cache.put(query, fallback_engine_name, filtered_results)
                        return filtered_results
                    except Exception as fallback_error:
                        logger.warning(f"Fallback engine '{fallback_engine_name}' also failed: {fallback_error}")
            
            # All engines failed
            raise SearchError(f"All search engines failed. Last error: {str(e)}")
    
    def _apply_security_filters(self, results: List[SearchResult]) -> List[SearchResult]:
        """Apply security filtering to search results."""
        config = load_config()
        filtered_results = []
        
        for result in results:
            # Check blocked domains
            if any(blocked in result.domain for blocked in config.security.blocked_domains):
                logger.info(f"Filtering out blocked domain: {result.domain}")
                continue
            
            # Check allowed domains (if configured)
            if config.security.allowed_domains:
                if not any(allowed in result.domain for allowed in config.security.allowed_domains):
                    logger.info(f"Filtering out non-allowed domain: {result.domain}")
                    continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    def multi_engine_search(self, query: SearchQuery, engines: Optional[List[str]] = None) -> Dict[str, List[SearchResult]]:
        """
        Search across multiple engines and return aggregated results.
        
        Args:
            query: Search query
            engines: List of engine names to use, or None for all available
            
        Returns:
            Dict mapping engine names to their results
        """
        if engines is None:
            engines = self.get_available_engines()
        
        results = {}
        
        for engine_name in engines:
            if engine_name in self.engines:
                try:
                    engine_results = self.search(query, engine_name)
                    results[engine_name] = engine_results
                except Exception as e:
                    logger.error(f"Multi-engine search failed for '{engine_name}': {e}")
                    results[engine_name] = []
        
        return results