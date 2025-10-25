"""Configuration management using Pydantic BaseSettings."""

import logging
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Speech Recognition and TTS Configuration
    mic_device_index: Optional[int] = Field(None, description="Microphone device index (None = default)")
    language: str = Field("en-US", description="Language code for STT & TTS")
    tts_rate: int = Field(170, description="TTS speaking rate")
    tts_volume: float = Field(1.0, description="TTS volume 0.0–1.0")
    pause_threshold: float = Field(0.6, description="Seconds of silence to consider phrase complete")
    phrase_time_limit: float = Field(12.0, description="Max seconds to listen per phrase")
    timeout: Optional[float] = Field(None, description="Max seconds to wait for speech start (None = no timeout)")
    force_sphinx: bool = Field(True, description="Force offline STT with PocketSphinx")
    use_whisper: bool = Field(True, description="Use Whisper for speech recognition")
    whisper_model: str = Field("tiny", description="Whisper model size")
    
    # Stop words
    stop_words: str = Field("stop,quit,exit", description="Comma-separated words that end the program when spoken")
    
    # Main.py Configuration
    mic_index: Optional[int] = Field(None, description="Microphone index for main.py")
    trigger_word: str = Field("jarvis", description="Wake word to activate the assistant")
    conversation_timeout: int = Field(30, description="Seconds of inactivity before exiting conversation mode")
    ollama_model: str = Field("qwen3:1.7b", description="Ollama model to use")
    
    # TTS Voice Settings
    tts_voice_preference: str = Field("jamie", description="Preferred TTS voice name")
    tts_rate_main: int = Field(180, description="TTS rate for main.py")
    
    # OpenAI Configuration (if needed)
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    OPENAI_ORG_ID: Optional[str] = Field(None, description="OpenAI organization ID")
    
    # Logging
    log_level: str = Field("DEBUG", description="Logging level")
    
    # Tools Configuration
    enabled_tools: List[str] = Field(
        default_factory=lambda: ["playwright_agent", "calculator", "datetime", "gmail"],
        description="List of enabled tools"
    )
    playwright_headless: bool = Field(True, description="Run playwright in headless mode")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }
    
    def get_stop_words_list(self) -> List[str]:
        """Convert comma-separated stop words to list."""
        return [word.strip() for word in self.stop_words.split(",") if word.strip() != ""]
    
    def get_logging_level(self) -> int:
        """Convert string log level to logging constant."""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return level_map.get(self.log_level.upper() if isinstance(self.log_level, str) else self.log_level.upper(), logging.DEBUG)


# Global settings instance
settings = Settings()
