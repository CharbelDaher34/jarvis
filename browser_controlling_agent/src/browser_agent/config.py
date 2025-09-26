"""
Configuration management for the browser agent.
Handles environment variables, API keys, and browser settings.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from urllib.parse import urlparse

@dataclass
class BrowserConfig:
    """Browser-specific configuration settings."""
    headless: bool = False
    window_width: int = 1200
    window_height: int = 800
    page_load_timeout: int = 30
    implicit_wait: int = 10
    download_directory: Optional[str] = None
    disable_images: bool = False
    disable_javascript: bool = False
    user_agent: Optional[str] = None
    remote_debugging_port: int = 9222
    allow_debugger_attach: bool = True
    
@dataclass
class SearchConfig:
    """Search engine configuration."""
    default_engine: str = "google"
    max_results_per_search: int = 10
    search_timeout: int = 30
    result_cache_ttl: int = 300  # 5 minutes
    
@dataclass
class SecurityConfig:
    """Security and validation settings."""
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=lambda: [
        "malware.com", "phishing.com", "spam.com"  # Example blocked domains
    ])
    max_redirects: int = 5
    ssl_verify: bool = True
    
@dataclass
class AgentConfig:
    """Main configuration for the browser agent."""
    # API Configuration
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434/v1"
    
    # Model Selection
    preferred_model: str = "auto"  # auto, openai, gemini, anthropic, ollama
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"
    anthropic_model: str = "claude-3-sonnet-20240229"
    ollama_model: str = "llama3:8b"
    
    # Sub-configurations
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Logging and debugging
    log_level: str = "INFO"
    enable_screenshots: bool = True
    screenshot_on_error: bool = True
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """Create configuration from environment variables."""
        config = cls()
        
        # Load API keys from environment
        config.openai_api_key = os.getenv("OPENAI_API_KEY")
        config.gemini_api_key = os.getenv("GEMINI_API_KEY") 
        config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        config.ollama_base_url = os.getenv("OLLAMA_BASE_URL", config.ollama_base_url)
        
        # Model configuration
        config.preferred_model = os.getenv("PREFERRED_MODEL", config.preferred_model)
        config.openai_model = os.getenv("OPENAI_MODEL", config.openai_model)
        config.gemini_model = os.getenv("GEMINI_MODEL", config.gemini_model)
        
        # Browser settings
        config.browser.headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
        config.browser.window_width = int(os.getenv("BROWSER_WIDTH", str(config.browser.window_width)))
        config.browser.window_height = int(os.getenv("BROWSER_HEIGHT", str(config.browser.window_height)))
        config.browser.page_load_timeout = int(os.getenv("PAGE_LOAD_TIMEOUT", str(config.browser.page_load_timeout)))
        config.browser.remote_debugging_port = int(os.getenv("BROWSER_DEBUG_PORT", str(config.browser.remote_debugging_port)))
        config.browser.allow_debugger_attach = os.getenv("BROWSER_ATTACH_DEBUGGER", "true").lower() == "true"
        
        # Search settings
        config.search.default_engine = os.getenv("DEFAULT_SEARCH_ENGINE", config.search.default_engine)
        config.search.max_results_per_search = int(os.getenv("MAX_SEARCH_RESULTS", str(config.search.max_results_per_search)))
        
        # Security settings
        allowed_domains = os.getenv("ALLOWED_DOMAINS")
        if allowed_domains:
            config.security.allowed_domains = [domain.strip() for domain in allowed_domains.split(",")]
        
        # Logging
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)
        config.enable_screenshots = os.getenv("ENABLE_SCREENSHOTS", "true").lower() == "true"
        
        return config
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check if at least one API key is available
        if not any([self.openai_api_key, self.gemini_api_key, self.anthropic_api_key]):
            if self.preferred_model != "ollama":
                errors.append("No API keys found. Set at least one: OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY")
        
        # Validate browser settings
        if self.browser.window_width < 100 or self.browser.window_height < 100:
            errors.append("Browser window dimensions must be at least 100x100")
            
        if self.browser.page_load_timeout < 1:
            errors.append("Page load timeout must be at least 1 second")
        
        # Validate URLs
        if self.ollama_base_url:
            try:
                parsed = urlparse(self.ollama_base_url)
                if not parsed.scheme or not parsed.netloc:
                    errors.append("Invalid Ollama base URL format")
            except Exception:
                errors.append("Invalid Ollama base URL")
        
        # Validate domains
        domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        for domain in self.security.allowed_domains + self.security.blocked_domains:
            if not domain_pattern.match(domain):
                errors.append(f"Invalid domain format: {domain}")
        
        return errors
    
    def get_available_model(self) -> tuple[str, Dict[str, Any]]:
        """
        Get the first available model based on API key availability.
        Returns (model_type, model_config).
        """
        if self.preferred_model != "auto":
            return self._get_specific_model(self.preferred_model)
        
        # Auto-detect available model
        if self.openai_api_key and self.openai_api_key != "your-openai-api-key-here":
            return "openai", {"model": self.openai_model, "api_key": self.openai_api_key}
        
        if self.gemini_api_key and self.gemini_api_key != "your-gemini-api-key-here":
            return "gemini", {"model": self.gemini_model, "api_key": self.gemini_api_key}
        
        if self.anthropic_api_key and self.anthropic_api_key != "your-anthropic-api-key-here":
            return "anthropic", {"model": self.anthropic_model, "api_key": self.anthropic_api_key}
        
        # Fallback to Ollama (local)
        return "ollama", {"model": self.ollama_model, "base_url": self.ollama_base_url}
    
    def _get_specific_model(self, model_type: str) -> tuple[str, Dict[str, Any]]:
        """Get configuration for a specific model type."""
        if model_type == "openai":
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return "openai", {"model": self.openai_model, "api_key": self.openai_api_key}
        
        elif model_type == "gemini":
            if not self.gemini_api_key:
                raise ValueError("Gemini API key not configured")
            return "gemini", {"model": self.gemini_model, "api_key": self.gemini_api_key}
        
        elif model_type == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            return "anthropic", {"model": self.anthropic_model, "api_key": self.anthropic_api_key}
        
        elif model_type == "ollama":
            return "ollama", {"model": self.ollama_model, "base_url": self.ollama_base_url}
        
        else:
            raise ValueError(f"Unknown model type: {model_type}")

def load_config() -> AgentConfig:
    """Load and validate configuration from environment."""
    config = AgentConfig.from_env()
    errors = config.validate()
    
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        raise ValueError(error_msg)
    
    return config