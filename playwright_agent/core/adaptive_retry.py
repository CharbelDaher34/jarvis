"""
Adaptive retry and error recovery strategies.
Instead of blindly retrying the same action, tries different approaches.
"""
from __future__ import annotations

import logging
from typing import Callable, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Types of element location strategies."""
    CSS_SELECTOR = "css_selector"
    TEXT_EXACT = "text_exact"
    TEXT_PARTIAL = "text_partial"
    XPATH = "xpath"
    ARIA_LABEL = "aria_label"
    PLACEHOLDER = "placeholder"
    ROLE = "role"
    VISION_BASED = "vision_based"


@dataclass
class RetryStrategy:
    """A specific retry strategy with its implementation."""
    name: str
    strategy_type: StrategyType
    implementation: Callable


class AdaptiveRetryManager:
    """
    Manages adaptive retry strategies for browser interactions.
    
    Instead of retrying the same action, intelligently tries
    alternative approaches when one fails.
    """
    
    def __init__(self):
        self.attempted_strategies: List[str] = []
        self.successful_strategies: List[str] = []
        self.failed_strategies: List[str] = []
    
    async def find_element(
        self,
        page,
        target: str,
        action_type: str = "click"
    ) -> Any:
        """
        Find element using multiple adaptive strategies.
        
        Args:
            page: Playwright page object
            target: Element description/selector
            action_type: Type of action ('click', 'type', etc.)
        
        Returns:
            Found element or raises exception
        """
        strategies = self._get_strategies_for_target(target, action_type)
        
        for strategy in strategies:
            try:
                logger.info(f"Trying strategy: {strategy.name}")
                self.attempted_strategies.append(strategy.name)
                
                element = await strategy.implementation(page, target)
                
                if element:
                    self.successful_strategies.append(strategy.name)
                    logger.info(f"✅ Success with strategy: {strategy.name}")
                    return element
                    
            except Exception as e:
                self.failed_strategies.append(strategy.name)
                logger.debug(f"Strategy '{strategy.name}' failed: {e}")
                continue
        
        # All strategies failed
        raise Exception(
            f"All {len(strategies)} strategies failed to find element: '{target}'\n"
            f"Attempted: {', '.join(self.attempted_strategies)}"
        )
    
    def _get_strategies_for_target(
        self,
        target: str,
        action_type: str
    ) -> List[RetryStrategy]:
        """
        Get ordered list of strategies based on target characteristics.
        """
        strategies = []
        
        # Strategy 1: If looks like CSS selector
        if self._looks_like_selector(target):
            strategies.append(RetryStrategy(
                name="CSS Selector",
                strategy_type=StrategyType.CSS_SELECTOR,
                implementation=self._try_css_selector,

            ))
        
        # Strategy 2: Exact text match
        strategies.append(RetryStrategy(
            name="Exact Text Match",
            strategy_type=StrategyType.TEXT_EXACT,
            implementation=self._try_exact_text,
        ))
        
        # Strategy 3: Partial text match
        strategies.append(RetryStrategy(
            name="Partial Text Match",
            strategy_type=StrategyType.TEXT_PARTIAL,
            implementation=self._try_partial_text,
        ))
        
        # Strategy 4: Role-based (for buttons, links, etc.)
        if action_type == "click":
            strategies.append(RetryStrategy(
                name="Role-based (button)",
                strategy_type=StrategyType.ROLE,
                implementation=lambda p, t: self._try_role(p, t, "button"),
            ))
            
            strategies.append(RetryStrategy(
                name="Role-based (link)",
                strategy_type=StrategyType.ROLE,
                implementation=lambda p, t: self._try_role(p, t, "link"),
            ))
        
        # Strategy 5: ARIA label
        strategies.append(RetryStrategy(
            name="ARIA Label",
            strategy_type=StrategyType.ARIA_LABEL,
            implementation=self._try_aria_label,
        ))
        
        # Strategy 6: Placeholder (for inputs)
        if action_type == "type":
            strategies.append(RetryStrategy(
                name="Placeholder",
                strategy_type=StrategyType.PLACEHOLDER,
                implementation=self._try_placeholder,
            ))
        
        # Strategy 7: XPath fallback
        strategies.append(RetryStrategy(
            name="XPath",
            strategy_type=StrategyType.XPATH,
            implementation=self._try_xpath,
        ))
        
        return strategies
    
    def _looks_like_selector(self, text: str) -> bool:
        """Check if text looks like a CSS selector."""
        selector_chars = ['.', '#', '[', ']', '>', '~', '+', ':']
        return any(char in text for char in selector_chars)
    
    async def _try_css_selector(self, page, target: str):
        """Try to find element using CSS selector."""
        return await page.wait_for_selector(target, state="visible", timeout=3000)
    
    async def _try_exact_text(self, page, target: str):
        """Try to find element by exact text match."""
        return await page.get_by_text(target, exact=True).first
    
    async def _try_partial_text(self, page, target: str):
        """Try to find element by partial text match."""
        return await page.get_by_text(target, exact=False).first
    
    async def _try_role(self, page, target: str, role: str):
        """Try to find element by role and name."""
        return await page.get_by_role(role, name=target).first
    
    async def _try_aria_label(self, page, target: str):
        """Try to find element by ARIA label."""
        return await page.locator(f"[aria-label='{target}']").first
    
    async def _try_placeholder(self, page, target: str):
        """Try to find input by placeholder."""
        return await page.get_by_placeholder(target).first
    
    async def _try_xpath(self, page, target: str):
        """Try to find element using XPath."""
        xpath = f"//*[contains(text(), '{target}')]"
        return await page.locator(f"xpath={xpath}").first
    
    def get_statistics(self) -> dict:
        """Get statistics about strategy effectiveness."""
        total = len(self.attempted_strategies)
        successes = len(self.successful_strategies)
        
        # Calculate success rate per strategy type
        strategy_stats = {}
        for strategy in set(self.attempted_strategies):
            attempts = self.attempted_strategies.count(strategy)
            successes = self.successful_strategies.count(strategy)
            strategy_stats[strategy] = {
                "attempts": attempts,
                "successes": successes,
                "success_rate": f"{(successes/attempts*100):.1f}%" if attempts > 0 else "0%"
            }
        
        return {
            "total_attempts": total,
            "total_successes": len(self.successful_strategies),
            "overall_success_rate": f"{(len(self.successful_strategies)/total*100):.1f}%" if total > 0 else "0%",
            "strategy_breakdown": strategy_stats
        }


class ErrorRecoveryStrategy:
    """
    Defines how to recover from specific error types.
    """
    
    @staticmethod
    async def recover_from_timeout(page, action_callback):
        """Recover from timeout errors."""
        logger.info("⚠️  Timeout detected, trying recovery strategies...")
        
        # Strategy 1: Wait longer
        try:
            await asyncio.sleep(2)
            result = await action_callback()
            logger.info("✅ Recovery successful: waited longer")
            return result
        except:
            pass
        
        # Strategy 2: Refresh page and retry
        try:
            logger.info("Attempting page refresh...")
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(1)
            result = await action_callback()
            logger.info("✅ Recovery successful: page refresh")
            return result
        except:
            pass
        
        raise Exception("Timeout recovery failed")
    
    @staticmethod
    async def recover_from_element_not_found(page, target: str):
        """Recover from element not found errors."""
        logger.info(f"⚠️  Element not found: {target}, trying recovery...")
        
        # Strategy 1: Close any popups/modals
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            logger.info("Closed potential popups")
        except:
            pass
        
        # Strategy 2: Scroll to make element visible
        try:
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(0.5)
            logger.info("Scrolled down to reveal more elements")
        except:
            pass
        
        # Strategy 3: Get list of all visible elements for debugging
        try:
            visible_text = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('button, a, input'));
                    return elements
                        .filter(el => el.offsetParent !== null)
                        .map(el => el.textContent?.trim() || el.ariaLabel || el.placeholder)
                        .filter(text => text)
                        .slice(0, 20);
                }
            """)
            logger.info(f"Visible interactive elements: {', '.join(visible_text)}")
        except:
            pass
        
        raise Exception(f"Element recovery failed for: {target}")


# Example usage
async def example_usage():
    """Demonstrate adaptive retry."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.python.org")
        
        # Use adaptive retry
        retry_manager = AdaptiveRetryManager()
        
        try:
            element = await retry_manager.find_element(
                page,
                "Downloads",  # Will try multiple strategies
                action_type="click"
            )
            await element.click()
            
            # Show statistics
            stats = retry_manager.get_statistics()
            print("Strategy Statistics:", stats)
            
        finally:
            await browser.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

