"""
Configuration management for the browser agent.
Handles environment variables, API keys, and browser settings using Pydantic Settings.
"""
from __future__ import annotations

import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class BrowserConfig(BaseSettings):
    """Browser-specific configuration settings."""
    headless: bool = Field(default=False, description="Run browser in headless mode")
    window_width: int = Field(default=1200, ge=100, description="Browser window width")
    window_height: int = Field(default=800, ge=100, description="Browser window height")
    page_load_timeout: int = Field(default=15, ge=1, description="Page load timeout in seconds")
    implicit_wait: int = Field(default=5, ge=0, description="Implicit wait time in seconds")
    download_directory: Optional[str] = Field(default=None, description="Download directory path")
    disable_images: bool = Field(default=False, description="Disable image loading")
    disable_javascript: bool = Field(default=False, description="Disable JavaScript")
    user_agent: Optional[str] = Field(default=None, description="Custom user agent string")
    remote_debugging_port: int = Field(default=9222, ge=1024, le=65535, description="Remote debugging port")
    allow_debugger_attach: bool = Field(default=True, description="Allow debugger to attach")
    
    model_config = SettingsConfigDict(
        env_prefix="BROWSER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class SearchConfig(BaseSettings):
    """Search engine configuration."""
    default_engine: str = Field(
        default="duckduckgo",
        description="Default search engine (google, duckduckgo, bing)"
    )
    max_results_per_search: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum search results per query"
    )
    search_timeout: int = Field(default=30, ge=1, description="Search timeout in seconds")
    result_cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    google_api_key: Optional[str] = Field(default=None, description="Google Custom Search API key")
    google_search_engine_id: Optional[str] = Field(default=None, description="Google CSE ID")
    bing_api_key: Optional[str] = Field(default=None, description="Bing Search API key")
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator("google_search_engine_id", mode="before")
    @classmethod
    def validate_google_cse_id(cls, v: Optional[str]) -> Optional[str]:
        """Allow GOOGLE_CSE_ID as alternative name."""
        import os
        if v is None:
            return os.getenv("GOOGLE_CSE_ID")
        return v


class SecurityConfig(BaseSettings):
    """Security and validation settings."""
    allowed_domains: List[str] = Field(
        default_factory=list,
        description="List of allowed domains (empty = allow all)"
    )
    blocked_domains: List[str] = Field(
        default_factory=lambda: ["malware.com", "phishing.com", "spam.com"],
        description="List of blocked domains"
    )
    max_redirects: int = Field(default=5, ge=0, description="Maximum number of redirects")
    ssl_verify: bool = Field(default=True, description="Verify SSL certificates")
    
    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator("allowed_domains", "blocked_domains", mode="before")
    @classmethod
    def parse_domain_list(cls, v) -> List[str]:
        """Parse comma-separated domain list from environment variable."""
        if isinstance(v, str):
            return [d.strip() for d in v.split(",") if d.strip()]
        return v if v else []
    
    @field_validator("allowed_domains", "blocked_domains")
    @classmethod
    def validate_domains(cls, v: List[str]) -> List[str]:
        """Validate domain format."""
        domain_pattern = re.compile(
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
            r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )
        for domain in v:
            if not domain_pattern.match(domain):
                raise ValueError(f"Invalid domain format: {domain}")
        return v


class AgentConfig(BaseSettings):
    """Main configuration for the browser agent."""
    
    # API Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Ollama base URL"
    )
    
    # Model Selection
    preferred_model: str = Field(
        default="auto",
        description="Preferred model: auto, openai, gemini, anthropic, ollama"
    )
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model name")
    anthropic_model: str = Field(
        default="claude-3-sonnet-20240229",
        description="Anthropic model name"
    )
    ollama_model: str = Field(default="llama3:8b", description="Ollama model name")
    
    # Logging and debugging
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    enable_screenshots: bool = Field(default=True, description="Enable screenshot capture")
    screenshot_on_error: bool = Field(default=True, description="Capture screenshot on error")
    
    # Sub-configurations (will be initialized separately)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    
    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, v: str) -> str:
        """Validate Ollama base URL format."""
        if v:
            try:
                parsed = urlparse(v)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError("Invalid Ollama base URL format")
            except Exception as e:
                raise ValueError(f"Invalid Ollama base URL: {e}")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {', '.join(valid_levels)}")
        return v_upper
    
    @model_validator(mode="after")
    def initialize_sub_configs(self) -> "AgentConfig":
        """Initialize sub-configurations with environment variables."""
        # Sub-configs are automatically initialized by Pydantic
        # This validator can be used for cross-field validation if needed
        return self

    
    def validate_api_keys(self) -> List[str]:
        """Validate API key configuration and return list of warnings."""
        warnings = []
        
        # Check if at least one API key is available
        if not any([self.openai_api_key, self.gemini_api_key, self.anthropic_api_key]):
            if self.preferred_model != "ollama":
                warnings.append(
                    "No API keys found. Set at least one: OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY. "
                    "Falling back to Ollama (local model)."
                )
        
        return warnings

    
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
    """
    Load and validate configuration from environment.
    Uses Pydantic Settings to automatically load from .env file.
    """
    try:
        config = AgentConfig()
        
        # Check for API key warnings
        warnings = config.validate_api_keys()
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(warning)
        
        return config
    except Exception as e:
        raise ValueError(f"Configuration loading failed: {e}")