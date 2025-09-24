"""
Enhanced error handling and reliability utilities for browser automation.
Includes retry mechanisms, timeout handling, and custom exceptions.
"""
from __future__ import annotations

import asyncio
import time
import logging
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Union
from functools import wraps
from dataclasses import dataclass

# Custom exceptions for better error handling
class BrowserAgentError(Exception):
    """Base exception for browser agent errors."""
    pass

class BrowserConnectionError(BrowserAgentError):
    """Browser connection or initialization failed."""
    pass

class PageLoadError(BrowserAgentError):
    """Page failed to load within timeout."""
    pass

class ElementNotFoundError(BrowserAgentError):
    """Required element not found on page."""
    pass

class NavigationError(BrowserAgentError):
    """Navigation to URL failed."""
    pass

class SearchError(BrowserAgentError):
    """Search operation failed."""
    pass

class SecurityError(BrowserAgentError):
    """Security validation failed (blocked domain, etc.)."""
    pass

class ErrorSeverity(Enum):
    """Error severity levels for handling decisions."""
    LOW = "low"           # Continue operation, log warning
    MEDIUM = "medium"     # Retry operation, log error  
    HIGH = "high"         # Fail operation, log error
    CRITICAL = "critical" # Abort session, log critical

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 30.0  # Maximum delay between retries
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add random jitter to delays
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number (0-indexed)."""
        import random
        
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)

T = TypeVar('T')

def with_retry(
    retry_config: Optional[RetryConfig] = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
):
    """
    Decorator to add retry logic to functions.
    
    Args:
        retry_config: Retry configuration, defaults to RetryConfig()
        exceptions: Tuple of exception types to catch and retry
        logger: Logger for retry information
    """
    if retry_config is None:
        retry_config = RetryConfig()
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(retry_config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == retry_config.max_attempts - 1:
                        # Last attempt failed
                        logger.error(f"Function {func.__name__} failed after {retry_config.max_attempts} attempts: {e}")
                        break
                    
                    delay = retry_config.get_delay(attempt)
                    logger.warning(f"Function {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
            
            # Re-raise the last exception
            raise last_exception
        
        return wrapper
    return decorator

def with_async_retry(
    retry_config: Optional[RetryConfig] = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
):
    """
    Async version of the retry decorator.
    """
    if retry_config is None:
        retry_config = RetryConfig()
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(retry_config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == retry_config.max_attempts - 1:
                        logger.error(f"Async function {func.__name__} failed after {retry_config.max_attempts} attempts: {e}")
                        break
                    
                    delay = retry_config.get_delay(attempt)
                    logger.warning(f"Async function {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator

class TimeoutManager:
    """Context manager for operations with timeouts."""
    
    def __init__(self, timeout: float, operation_name: str = "operation"):
        self.timeout = timeout
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout:
                raise TimeoutError(f"{self.operation_name} exceeded timeout of {self.timeout}s (took {elapsed:.2f}s)")
    
    def check_timeout(self):
        """Check if timeout has been exceeded and raise TimeoutError if so."""
        if self.start_time and (time.time() - self.start_time) > self.timeout:
            elapsed = time.time() - self.start_time
            raise TimeoutError(f"{self.operation_name} exceeded timeout of {self.timeout}s (took {elapsed:.2f}s)")
    
    @property 
    def elapsed(self) -> float:
        """Get elapsed time since context manager started."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

def safe_execute(
    operation: Callable[[], T], 
    fallback: Optional[T] = None,
    error_message: str = "Operation failed",
    logger: Optional[logging.Logger] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> tuple[Optional[T], Optional[Exception]]:
    """
    Safely execute an operation with proper error handling.
    
    Returns:
        Tuple of (result, exception). One will be None.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        result = operation()
        return result, None
    except Exception as e:
        # Log based on severity
        if severity == ErrorSeverity.LOW:
            logger.warning(f"{error_message}: {e}")
        elif severity == ErrorSeverity.MEDIUM:
            logger.error(f"{error_message}: {e}")
        elif severity == ErrorSeverity.HIGH:
            logger.error(f"{error_message}: {e}", exc_info=True)
        else:  # CRITICAL
            logger.critical(f"{error_message}: {e}", exc_info=True)
        
        return fallback, e

async def safe_execute_async(
    operation: Callable[[], Any],
    fallback: Optional[T] = None, 
    error_message: str = "Async operation failed",
    logger: Optional[logging.Logger] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> tuple[Optional[T], Optional[Exception]]:
    """Async version of safe_execute."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        result = await operation()
        return result, None
    except Exception as e:
        if severity == ErrorSeverity.LOW:
            logger.warning(f"{error_message}: {e}")
        elif severity == ErrorSeverity.MEDIUM:
            logger.error(f"{error_message}: {e}")  
        elif severity == ErrorSeverity.HIGH:
            logger.error(f"{error_message}: {e}", exc_info=True)
        else:  # CRITICAL
            logger.critical(f"{error_message}: {e}", exc_info=True)
        
        return fallback, e

def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL format and security.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    import re
    from urllib.parse import urlparse
    
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    # Basic URL pattern validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False, "Invalid URL format"
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "URL missing scheme or domain"
        
        if parsed.scheme not in ['http', 'https']:
            return False, "Only HTTP and HTTPS protocols are allowed"
            
    except Exception as e:
        return False, f"URL parsing error: {e}"
    
    return True, None

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "open":
                if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise BrowserAgentError("Circuit breaker is open - too many recent failures")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _on_success(self):
        """Called when operation succeeds."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Called when operation fails."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"