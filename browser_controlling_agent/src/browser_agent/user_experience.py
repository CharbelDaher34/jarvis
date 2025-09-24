"""
User experience enhancements including progress tracking, logging, and interactive feedback.
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
import threading
import queue

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ProgressStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ProgressStep:
    """Individual step in a progress tracking sequence."""
    id: str
    description: str
    status: ProgressStatus = ProgressStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    substeps: List['ProgressStep'] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration in seconds if both start and end times are set."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def start(self) -> None:
        """Mark step as started."""
        self.status = ProgressStatus.IN_PROGRESS
        self.start_time = datetime.now()
    
    def complete(self, result: Optional[str] = None) -> None:
        """Mark step as completed."""
        self.status = ProgressStatus.COMPLETED
        self.end_time = datetime.now()
        if result:
            self.result = result
    
    def fail(self, error: str) -> None:
        """Mark step as failed."""
        self.status = ProgressStatus.FAILED
        self.end_time = datetime.now()
        self.error = error
    
    def skip(self, reason: str) -> None:
        """Mark step as skipped."""
        self.status = ProgressStatus.SKIPPED
        self.end_time = datetime.now()
        self.result = f"Skipped: {reason}"

class ProgressTracker:
    """Tracks progress of multi-step operations with user feedback."""
    
    def __init__(self, operation_name: str, enable_console_output: bool = True):
        self.operation_name = operation_name
        self.enable_console_output = enable_console_output
        self.steps: List[ProgressStep] = []
        self.current_step: Optional[ProgressStep] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self._step_callbacks: List[Callable[[ProgressStep], None]] = []
        
    def add_step(self, step_id: str, description: str) -> ProgressStep:
        """Add a new step to track."""
        step = ProgressStep(id=step_id, description=description)
        self.steps.append(step)
        return step
    
    def add_step_callback(self, callback: Callable[[ProgressStep], None]) -> None:
        """Add callback to be called when step status changes."""
        self._step_callbacks.append(callback)
    
    def start_step(self, step_id: str) -> ProgressStep:
        """Start a specific step."""
        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step '{step_id}' not found")
        
        # Complete previous step if it was in progress
        if self.current_step and self.current_step.status == ProgressStatus.IN_PROGRESS:
            self.current_step.complete()
        
        step.start()
        self.current_step = step
        
        if self.enable_console_output:
            print(f"🔄 {step.description}...")
        
        # Notify callbacks
        for callback in self._step_callbacks:
            try:
                callback(step)
            except Exception as e:
                logging.warning(f"Progress callback failed: {e}")
        
        return step
    
    def complete_current_step(self, result: Optional[str] = None) -> None:
        """Complete the current step."""
        if not self.current_step:
            return
        
        self.current_step.complete(result)
        
        if self.enable_console_output:
            duration_str = ""
            if self.current_step.duration:
                duration_str = f" ({self.current_step.duration:.1f}s)"
            print(f"✅ {self.current_step.description} - Completed{duration_str}")
            if result:
                print(f"   → {result}")
        
        # Notify callbacks
        for callback in self._step_callbacks:
            try:
                callback(self.current_step)
            except Exception:
                pass
    
    def fail_current_step(self, error: str) -> None:
        """Mark current step as failed."""
        if not self.current_step:
            return
        
        self.current_step.fail(error)
        
        if self.enable_console_output:
            duration_str = ""
            if self.current_step.duration:
                duration_str = f" ({self.current_step.duration:.1f}s)"
            print(f"❌ {self.current_step.description} - Failed{duration_str}")
            print(f"   → Error: {error}")
        
        # Notify callbacks
        for callback in self._step_callbacks:
            try:
                callback(self.current_step)
            except Exception:
                pass
    
    def skip_current_step(self, reason: str) -> None:
        """Skip the current step."""
        if not self.current_step:
            return
        
        self.current_step.skip(reason)
        
        if self.enable_console_output:
            print(f"⏭️  {self.current_step.description} - Skipped ({reason})")
        
        # Notify callbacks
        for callback in self._step_callbacks:
            try:
                callback(self.current_step)
            except Exception:
                pass
    
    def finish(self, success: bool = True) -> None:
        """Finish progress tracking."""
        if self.current_step and self.current_step.status == ProgressStatus.IN_PROGRESS:
            if success:
                self.complete_current_step()
            else:
                self.fail_current_step("Operation was terminated")
        
        self.end_time = datetime.now()
        
        if self.enable_console_output:
            self._print_summary()
    
    def _find_step(self, step_id: str) -> Optional[ProgressStep]:
        """Find step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def _print_summary(self) -> None:
        """Print operation summary."""
        total_duration = (self.end_time - self.start_time).total_seconds()
        completed_count = sum(1 for step in self.steps if step.status == ProgressStatus.COMPLETED)
        failed_count = sum(1 for step in self.steps if step.status == ProgressStatus.FAILED)
        
        print(f"\n📊 {self.operation_name} Summary:")
        print(f"   • Total time: {total_duration:.1f}s")
        print(f"   • Steps completed: {completed_count}/{len(self.steps)}")
        if failed_count > 0:
            print(f"   • Steps failed: {failed_count}")
        
        # Show failed steps
        for step in self.steps:
            if step.status == ProgressStatus.FAILED:
                print(f"   ❌ {step.description}: {step.error}")
    
    @contextmanager
    def step(self, step_id: str, description: Optional[str] = None):
        """Context manager for automatic step management."""
        if description:
            step = self.add_step(step_id, description)
        
        self.start_step(step_id)
        try:
            yield self.current_step
            self.complete_current_step()
        except Exception as e:
            self.fail_current_step(str(e))
            raise

class EnhancedLogger:
    """Enhanced logging with user-friendly formatting and progress integration."""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create console handler with custom formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.value))
        
        # Custom formatter with icons and colors
        formatter = CustomFormatter()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, **kwargs)
    
    def user_action(self, action: str, details: Optional[str] = None) -> None:
        """Log user-facing action with special formatting."""
        message = f"🎯 {action}"
        if details:
            message += f" - {details}"
        self.info(message)
    
    def browser_action(self, action: str, url: Optional[str] = None) -> None:
        """Log browser action with special formatting."""
        message = f"🌐 {action}"
        if url:
            message += f" ({url})"
        self.info(message)
    
    def search_action(self, query: str, results_count: int, engine: str = "unknown") -> None:
        """Log search action with results summary."""
        self.info(f"🔍 Search '{query}' returned {results_count} results (via {engine})")
    
    def timing_info(self, operation: str, duration: float) -> None:
        """Log timing information."""
        self.info(f"⏱️  {operation} completed in {duration:.2f}s")

class CustomFormatter(logging.Formatter):
    """Custom log formatter with colors and icons."""
    
    # Color codes (works in most terminals)
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    ICONS = {
        'DEBUG': '🔧',
        'INFO': 'ℹ️ ',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }
    
    def format(self, record):
        # Add color and icon
        level_name = record.levelname
        color = self.COLORS.get(level_name, '')
        icon = self.ICONS.get(level_name, '')
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Build message
        message = f"{color}{icon} [{timestamp}] {record.getMessage()}{reset}"
        
        return message

class FeedbackCollector:
    """Collects and manages user feedback during operations."""
    
    def __init__(self):
        self.feedback_queue = queue.Queue()
        self.active_prompts: Dict[str, Any] = {}
    
    def prompt_user(self, prompt_id: str, message: str, options: Optional[List[str]] = None, timeout: Optional[float] = None) -> Optional[str]:
        """
        Prompt user for input with optional timeout.
        
        Args:
            prompt_id: Unique identifier for the prompt
            message: Message to display to user
            options: List of valid options (if any)
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            User input or None if timeout/cancelled
        """
        self.active_prompts[prompt_id] = {
            "message": message,
            "options": options,
            "start_time": time.time()
        }
        
        try:
            # Display prompt
            print(f"\n💬 {message}")
            if options:
                for i, option in enumerate(options, 1):
                    print(f"   {i}. {option}")
                print("   Enter choice number or type option:")
            else:
                print("   Enter your response:")
            
            # Get input with timeout
            if timeout:
                # For simplicity, we'll use a basic approach
                # In a real implementation, you might want to use threading or asyncio
                print(f"   (Timeout: {timeout}s)")
            
            user_input = input("   > ").strip()
            
            # Validate against options if provided
            if options and user_input:
                # Try to match by number
                try:
                    choice_num = int(user_input)
                    if 1 <= choice_num <= len(options):
                        user_input = options[choice_num - 1]
                except ValueError:
                    # Try to match by text
                    matching_options = [opt for opt in options if opt.lower().startswith(user_input.lower())]
                    if len(matching_options) == 1:
                        user_input = matching_options[0]
                    elif len(matching_options) > 1:
                        print(f"   Ambiguous choice. Matches: {matching_options}")
                        return None
                    elif user_input.lower() not in [opt.lower() for opt in options]:
                        print(f"   Invalid choice. Valid options: {options}")
                        return None
            
            return user_input if user_input else None
            
        finally:
            # Clean up prompt
            if prompt_id in self.active_prompts:
                del self.active_prompts[prompt_id]
    
    def confirm_action(self, action: str, default: bool = False) -> bool:
        """
        Ask user to confirm an action.
        
        Args:
            action: Description of the action to confirm
            default: Default choice if user just presses Enter
            
        Returns:
            True if confirmed, False otherwise
        """
        default_text = " [Y/n]" if default else " [y/N]"
        response = self.prompt_user(
            f"confirm_{int(time.time())}",
            f"Confirm: {action}?{default_text}",
            ["yes", "no", "y", "n"]
        )
        
        if not response:
            return default
        
        return response.lower() in ["yes", "y", "true", "1"]
    
    def get_user_preference(self, preference_name: str, options: List[str], default: Optional[str] = None) -> Optional[str]:
        """Get user preference from list of options."""
        message = f"Select {preference_name}"
        if default:
            message += f" (default: {default})"
        
        response = self.prompt_user(
            f"pref_{preference_name}_{int(time.time())}",
            message,
            options
        )
        
        return response or default

# Global instances for easy access
logger = EnhancedLogger("browser_agent")
feedback = FeedbackCollector()

def create_progress_tracker(operation_name: str) -> ProgressTracker:
    """Create a new progress tracker for an operation."""
    return ProgressTracker(operation_name)