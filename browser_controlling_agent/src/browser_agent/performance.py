"""
Performance monitoring and resource management for browser automation.
"""
from __future__ import annotations

import gc
import psutil
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import logging

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """System performance metrics snapshot."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    browser_memory_mb: Optional[float] = None
    browser_cpu_percent: Optional[float] = None
    page_load_time: Optional[float] = None
    operation_duration: Optional[float] = None

@dataclass
class ResourceLimits:
    """Resource usage limits and thresholds."""
    max_memory_mb: float = 2048  # 2GB default
    max_cpu_percent: float = 80.0
    max_browser_memory_mb: float = 1024  # 1GB for browser
    page_load_timeout: float = 30.0
    operation_timeout: float = 300.0  # 5 minutes
    
class PerformanceMonitor:
    """Monitors system and browser performance metrics."""
    
    def __init__(self, sample_interval: float = 1.0, history_size: int = 100):
        self.sample_interval = sample_interval
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.resource_limits = ResourceLimits()
        self._performance_callbacks: List[Callable[[PerformanceMetrics], None]] = []
        
    def start_monitoring(self):
        """Start background performance monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        logger.info("Performance monitoring stopped")
    
    def add_callback(self, callback: Callable[[PerformanceMetrics], None]):
        """Add callback to be called when metrics are collected."""
        self._performance_callbacks.append(callback)
    
    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        while self.monitoring:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Check for resource limit violations
                self._check_resource_limits(metrics)
                
                # Notify callbacks
                for callback in self._performance_callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        logger.warning(f"Performance callback failed: {e}")
                
                time.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                time.sleep(self.sample_interval)
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_mb = memory.used / (1024 * 1024)
        
        # Browser-specific metrics (if available)
        browser_memory_mb = None
        browser_cpu_percent = None
        
        try:
            # Try to find Chrome processes
            for process in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    if 'chrome' in process.info['name'].lower():
                        if browser_memory_mb is None:
                            browser_memory_mb = 0
                            browser_cpu_percent = 0
                        
                        memory_info = process.memory_info()
                        browser_memory_mb += memory_info.rss / (1024 * 1024)
                        browser_cpu_percent += process.cpu_percent()
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.debug(f"Could not collect browser metrics: {e}")
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            browser_memory_mb=browser_memory_mb,
            browser_cpu_percent=browser_cpu_percent
        )
    
    def _check_resource_limits(self, metrics: PerformanceMetrics):
        """Check if resource limits are exceeded and log warnings."""
        if metrics.memory_mb > self.resource_limits.max_memory_mb:
            logger.warning(f"System memory usage high: {metrics.memory_mb:.1f}MB > {self.resource_limits.max_memory_mb}MB")
        
        if metrics.cpu_percent > self.resource_limits.max_cpu_percent:
            logger.warning(f"System CPU usage high: {metrics.cpu_percent:.1f}% > {self.resource_limits.max_cpu_percent}%")
        
        if metrics.browser_memory_mb and metrics.browser_memory_mb > self.resource_limits.max_browser_memory_mb:
            logger.warning(f"Browser memory usage high: {metrics.browser_memory_mb:.1f}MB > {self.resource_limits.max_browser_memory_mb}MB")
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the most recent metrics."""
        if not self.metrics_history:
            return self._collect_metrics()
        return self.metrics_history[-1]
    
    def get_average_metrics(self, duration_minutes: int = 5) -> Optional[PerformanceMetrics]:
        """Get average metrics over the specified duration."""
        if not self.metrics_history:
            return None
        
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        relevant_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not relevant_metrics:
            return None
        
        # Calculate averages
        avg_cpu = sum(m.cpu_percent for m in relevant_metrics) / len(relevant_metrics)
        avg_memory_percent = sum(m.memory_percent for m in relevant_metrics) / len(relevant_metrics)
        avg_memory_mb = sum(m.memory_mb for m in relevant_metrics) / len(relevant_metrics)
        
        browser_metrics = [m for m in relevant_metrics if m.browser_memory_mb is not None]
        avg_browser_memory = None
        avg_browser_cpu = None
        
        if browser_metrics:
            avg_browser_memory = sum(m.browser_memory_mb for m in browser_metrics) / len(browser_metrics)
            avg_browser_cpu = sum(m.browser_cpu_percent for m in browser_metrics) / len(browser_metrics)
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=avg_cpu,
            memory_percent=avg_memory_percent,
            memory_mb=avg_memory_mb,
            browser_memory_mb=avg_browser_memory,
            browser_cpu_percent=avg_browser_cpu
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        current = self.get_current_metrics()
        average = self.get_average_metrics(5)
        
        summary = {
            "monitoring_active": self.monitoring,
            "samples_collected": len(self.metrics_history),
            "current": None,
            "average_5min": None,
            "resource_limits": {
                "max_memory_mb": self.resource_limits.max_memory_mb,
                "max_cpu_percent": self.resource_limits.max_cpu_percent,
                "max_browser_memory_mb": self.resource_limits.max_browser_memory_mb
            }
        }
        
        if current:
            summary["current"] = {
                "cpu_percent": current.cpu_percent,
                "memory_mb": current.memory_mb,
                "browser_memory_mb": current.browser_memory_mb
            }
        
        if average:
            summary["average_5min"] = {
                "cpu_percent": average.cpu_percent,
                "memory_mb": average.memory_mb,
                "browser_memory_mb": average.browser_memory_mb
            }
        
        return summary

class ResourceManager:
    """Manages system resources and implements cleanup strategies."""
    
    def __init__(self, monitor: Optional[PerformanceMonitor] = None):
        self.monitor = monitor or PerformanceMonitor()
        self.cleanup_callbacks: List[Callable[[], None]] = []
        self.memory_threshold = 0.8  # 80% memory usage triggers cleanup
        self.auto_cleanup_enabled = True
        
    def register_cleanup_callback(self, callback: Callable[[], None]):
        """Register a callback to be called during resource cleanup."""
        self.cleanup_callbacks.append(callback)
    
    def force_cleanup(self):
        """Force immediate resource cleanup."""
        logger.info("Performing forced resource cleanup")
        
        # Call registered cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")
        
        # Force garbage collection
        gc.collect()
        
        # Additional cleanup strategies can be added here
        self._cleanup_browser_cache()
        
        logger.info("Resource cleanup completed")
    
    def _cleanup_browser_cache(self):
        """Attempt to clear browser cache and temporary data."""
        try:
            from src.browser_agent.tools import get_driver
            
            driver = get_driver()
            if driver:
                # Clear cookies
                driver.delete_all_cookies()
                
                # Clear local storage and session storage
                driver.execute_script("window.localStorage.clear();")
                driver.execute_script("window.sessionStorage.clear();")
                
                # Clear browser cache (if supported)
                try:
                    driver.execute_cdp_cmd("Network.clearBrowserCache", {})
                except Exception as e:
                    logger.debug(f"Could not clear browser cache: {e}")
                
                logger.info("Browser cache cleared")
                
        except Exception as e:
            logger.debug(f"Browser cache cleanup failed: {e}")
    
    def check_and_cleanup_if_needed(self):
        """Check resource usage and cleanup if thresholds are exceeded."""
        if not self.auto_cleanup_enabled:
            return
        
        current_metrics = self.monitor.get_current_metrics()
        if not current_metrics:
            return
        
        memory_usage_ratio = current_metrics.memory_percent / 100.0
        
        if memory_usage_ratio > self.memory_threshold:
            logger.warning(f"Memory usage high ({memory_usage_ratio:.1%}), triggering cleanup")
            self.force_cleanup()
    
    def start_auto_cleanup(self, check_interval: int = 30):
        """Start automatic resource monitoring and cleanup."""
        def cleanup_monitor():
            while self.auto_cleanup_enabled:
                try:
                    self.check_and_cleanup_if_needed()
                    time.sleep(check_interval)
                except Exception as e:
                    logger.error(f"Auto cleanup monitor error: {e}")
                    time.sleep(check_interval)
        
        cleanup_thread = threading.Thread(target=cleanup_monitor, daemon=True)
        cleanup_thread.start()
        logger.info("Auto cleanup monitoring started")
    
    def stop_auto_cleanup(self):
        """Stop automatic cleanup monitoring."""
        self.auto_cleanup_enabled = False
        logger.info("Auto cleanup monitoring stopped")

class BrowserSessionManager:
    """Manages browser sessions and tabs for optimal resource usage."""
    
    def __init__(self, max_tabs: int = 5, tab_timeout: int = 300):
        self.max_tabs = max_tabs
        self.tab_timeout = tab_timeout  # seconds
        self.active_tabs: Dict[str, Dict[str, Any]] = {}
        self.tab_creation_times: Dict[str, datetime] = {}
    
    def get_current_tab_count(self) -> int:
        """Get number of currently open tabs."""
        try:
            from src.browser_agent.tools import get_driver
            driver = get_driver()
            return len(driver.window_handles) if driver else 0
        except Exception:
            return 0
    
    def cleanup_old_tabs(self):
        """Close tabs that have been open longer than the timeout."""
        try:
            from src.browser_agent.tools import get_driver
            
            driver = get_driver()
            if not driver:
                return
            
            current_time = datetime.now()
            handles_to_close = []
            
            # Find tabs older than timeout
            for handle in driver.window_handles[:-1]:  # Keep at least one tab
                if handle in self.tab_creation_times:
                    age = current_time - self.tab_creation_times[handle]
                    if age.total_seconds() > self.tab_timeout:
                        handles_to_close.append(handle)
            
            # Close old tabs
            for handle in handles_to_close:
                try:
                    driver.switch_to.window(handle)
                    driver.close()
                    del self.tab_creation_times[handle]
                    if handle in self.active_tabs:
                        del self.active_tabs[handle]
                except Exception as e:
                    logger.debug(f"Could not close tab {handle}: {e}")
            
            # Switch back to the remaining tab
            if driver.window_handles:
                driver.switch_to.window(driver.window_handles[-1])
            
            if handles_to_close:
                logger.info(f"Closed {len(handles_to_close)} old tabs")
                
        except Exception as e:
            logger.error(f"Tab cleanup failed: {e}")
    
    def limit_tab_count(self):
        """Ensure tab count doesn't exceed maximum."""
        try:
            from src.browser_agent.tools import get_driver
            
            driver = get_driver()
            if not driver:
                return
            
            handles = driver.window_handles
            if len(handles) <= self.max_tabs:
                return
            
            # Close oldest tabs first
            excess_count = len(handles) - self.max_tabs
            oldest_handles = []
            
            for handle in handles[:-1]:  # Always keep the current tab
                if handle in self.tab_creation_times:
                    oldest_handles.append((handle, self.tab_creation_times[handle]))
            
            # Sort by creation time and close oldest
            oldest_handles.sort(key=lambda x: x[1])
            
            for handle, _ in oldest_handles[:excess_count]:
                try:
                    driver.switch_to.window(handle)
                    driver.close()
                    del self.tab_creation_times[handle]
                    if handle in self.active_tabs:
                        del self.active_tabs[handle]
                except Exception as e:
                    logger.debug(f"Could not close tab {handle}: {e}")
            
            # Switch back to a remaining tab
            if driver.window_handles:
                driver.switch_to.window(driver.window_handles[-1])
            
            logger.info(f"Limited tabs to {self.max_tabs} (closed {excess_count})")
            
        except Exception as e:
            logger.error(f"Tab limiting failed: {e}")
    
    def register_new_tab(self, url: str = "about:blank"):
        """Register a new tab creation."""
        try:
            from src.browser_agent.tools import get_driver
            
            driver = get_driver()
            if not driver:
                return None
            
            # Create new tab
            driver.execute_script("window.open('about:blank', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            
            handle = driver.current_window_handle
            self.tab_creation_times[handle] = datetime.now()
            self.active_tabs[handle] = {"url": url, "created": datetime.now()}
            
            # Navigate to URL if provided
            if url != "about:blank":
                driver.get(url)
            
            # Enforce limits
            self.limit_tab_count()
            
            return handle
            
        except Exception as e:
            logger.error(f"Tab registration failed: {e}")
            return None
    
    def cleanup_all_tabs(self):
        """Close all tabs except the current one."""
        try:
            self.cleanup_old_tabs()
            self.limit_tab_count()
        except Exception as e:
            logger.error(f"Tab cleanup failed: {e}")

# Global instances
performance_monitor = PerformanceMonitor()
resource_manager = ResourceManager(performance_monitor)
session_manager = BrowserSessionManager()

def start_performance_monitoring():
    """Start global performance monitoring."""
    performance_monitor.start_monitoring()
    resource_manager.start_auto_cleanup()

def stop_performance_monitoring():
    """Stop global performance monitoring."""
    performance_monitor.stop_monitoring()
    resource_manager.stop_auto_cleanup()

def get_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report."""
    return {
        "performance": performance_monitor.get_performance_summary(),
        "tabs": {
            "count": session_manager.get_current_tab_count(),
            "max_allowed": session_manager.max_tabs,
            "timeout_seconds": session_manager.tab_timeout
        },
        "cleanup": {
            "auto_enabled": resource_manager.auto_cleanup_enabled,
            "memory_threshold": resource_manager.memory_threshold
        }
    }