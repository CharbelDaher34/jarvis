import json
import re
from typing import Any


def escape_js_message(message: str) -> str:
    """
    Properly escape message for JavaScript while preserving formatting.
    
    Args:
        message: The message to escape
        
    Returns:
        Escaped message string ready for JavaScript injection
    """
    if not isinstance(message, str):
        message = str(message)
        
    # Convert newlines to HTML line breaks
    message = message.replace('\n', '<br>')
    
    # Escape backslashes first, then quotes
    message = message.replace('\\', '\\\\')
    message = message.replace('"', '\\"')
    message = message.replace("'", "\\'")
    
    return f'"{message}"'


def beautify_plan_message(message: str) -> str:
    """
    Add newlines between numbered steps in plan messages for better readability.
    
    Args:
        message: The plan message
        
    Returns:
        Formatted plan message with newlines between steps
    """
    # Add a newline before each numbered step that is not already preceded by a newline
    plan_with_newlines = re.sub(r'(?<!\n)(\d+\.)', r'\n\1', message)
    return plan_with_newlines.strip()


def format_error_message(error: Exception, context: str = "") -> str:
    """
    Format an error message with context for better debugging.
    
    Args:
        error: The exception object
        context: Additional context about where the error occurred
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"[{error_type}] {context}: {error_msg}"
    return f"[{error_type}] {error_msg}"


def sanitize_selector(selector: str) -> str:
    """
    Sanitize a CSS selector for safe use in JavaScript.
    
    Args:
        selector: The CSS selector to sanitize
        
    Returns:
        Sanitized selector
    """
    # Escape quotes and backslashes
    selector = selector.replace('\\', '\\\\')
    selector = selector.replace('"', '\\"')
    selector = selector.replace("'", "\\'")
    return selector


def format_time_elapsed(seconds: float) -> str:
    """
    Format elapsed time in a human-readable format.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
