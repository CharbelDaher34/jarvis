"""
Multi-Agent Orchestrator for Browser Automation

Coordinates the Planner, Browser, and Critique agents in a loop to accomplish
web automation tasks.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional
from datetime import datetime

from src.browser_agent.agents.planner_agent import planner_agent, PlannerOutput
from src.browser_agent.agents.critique_agent import critique_agent, CritiqueOutput
from src.browser_agent.agents.agent import browser_agent, BrowserDeps
from src.browser_agent.tools import get_driver
from src.browser_agent.utils import (
    configure_logger,
    NotificationManager,
    MessageType,
    TaskStatus,
    format_time_elapsed
)

configure_logger()
logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates the multi-agent browser automation workflow."""
    
    def __init__(self, headless: bool = False, max_iterations: int = 20, use_multi_agent: bool = False):
        """
        Initialize the orchestrator.
        
        Args:
            headless: Whether to run browser in headless mode
            max_iterations: Maximum number of planner->browser->critique loops
            use_multi_agent: Whether to use multi-agent system (Planner->Browser->Critique) or single browser agent
        """
        self.headless = headless
        self.max_iterations = max_iterations
        self.use_multi_agent = use_multi_agent
        self.iteration_counter = 0
        
        # Message histories for each agent
        self.message_histories = {
            'planner': [],
            'browser': [],
            'critique': []
        }
        
        # Token usage tracking
        self.cumulative_tokens = {
            'planner': {'total': 0, 'request': 0, 'response': 0},
            'browser': {'total': 0, 'request': 0, 'response': 0},
            'critique': {'total': 0, 'request': 0, 'response': 0}
        }
        
        # Notification system
        self.notification_manager = NotificationManager()
        
        # Task state
        self.terminate = False
        self.current_plan = None
        self.current_url = "https://www.google.com"
        
    def update_token_usage(self, agent_type: str, usage):
        """Update cumulative token usage for an agent."""
        if hasattr(usage, 'total_tokens'):
            self.cumulative_tokens[agent_type]['total'] += usage.total_tokens
            self.cumulative_tokens[agent_type]['request'] += usage.request_tokens
            self.cumulative_tokens[agent_type]['response'] += usage.response_tokens
    
    def log_token_usage(self, agent_type: str, usage, step: Optional[int] = None):
        """Log token usage for an agent."""
        self.update_token_usage(agent_type, usage)
        step_info = f" (Iteration {step})" if step is not None else ""
        logger.info(
            f"\n{'='*60}\n"
            f"Token Usage - {agent_type.upper()}{step_info}\n"
            f"{'='*60}\n"
            f"This iteration: {usage.total_tokens if hasattr(usage, 'total_tokens') else 0} tokens\n"
            f"Cumulative total: {self.cumulative_tokens[agent_type]['total']} tokens\n"
            f"  - Request: {self.cumulative_tokens[agent_type]['request']}\n"
            f"  - Response: {self.cumulative_tokens[agent_type]['response']}\n"
            f"{'='*60}"
        )
    
    def get_current_url(self) -> str:
        """Get the current URL from the browser."""
        try:
            driver = get_driver()
            if driver:
                return driver.current_url
        except Exception as e:
            logger.debug(f"Could not get current URL: {e}")
        return self.current_url
    
    async def run_planner(self, user_query: str, feedback: Optional[str] = None, missing_info: Optional[str] = None) -> PlannerOutput:
        """Run the planner agent."""
        logger.info(f"\n{'='*60}\n🎯 PLANNER AGENT - Iteration {self.iteration_counter}\n{'='*60}")
        
        # Build planner prompt
        prompt_parts = [f"User Query: {user_query}"]
        
        if self.current_plan:
            prompt_parts.append(f"Original Plan: {self.current_plan}")
        
        if feedback:
            prompt_parts.append(f"Feedback: {feedback}")
        
        if missing_info:
            prompt_parts.append(f"Missing Information: {missing_info}")
        
        # Add current URL context
        current_url = self.get_current_url()
        if current_url:
            prompt_parts.append(f"Current URL: {current_url}")
        
        prompt = "\n\n".join(prompt_parts)
        
        try:
            self.notification_manager.notify(
                "🎯 Planner analyzing task...",
                MessageType.STEP.value
            )
            
            planner_response = await planner_agent.run(
                user_prompt=prompt,
                message_history=self.message_histories['planner']
            )
            
            # Update message history
            self.message_histories['planner'].extend(planner_response.new_messages())
            
            # Store the plan
            if not self.current_plan or self.iteration_counter == 1:
                self.current_plan = planner_response.output.plan
            
            # Log results
            logger.info(f"\n📋 Plan:\n{planner_response.output.plan}")
            logger.info(f"\n▶️  Next Step:\n{planner_response.output.next_step}")
            
            self.notification_manager.notify(
                f"📋 Next step: {planner_response.output.next_step[:100]}...",
                MessageType.INFO.value
            )
            
            # Log token usage
            if hasattr(planner_response, '_usage'):
                self.log_token_usage('planner', planner_response._usage, self.iteration_counter)
            
            return planner_response.output
            
        except Exception as e:
            logger.error(f"Planner agent failed: {e}", exc_info=True)
            raise
    
    async def run_browser_agent(self, plan: str, current_step: str) -> str:
        """Run the browser agent."""
        logger.info(f"\n{'='*60}\n🤖 BROWSER AGENT - Iteration {self.iteration_counter}\n{'='*60}")
        
        # Build browser agent prompt
        prompt = (
            f"Plan: {plan}\n\n"
            f"Current Step: {current_step}\n\n"
            f"Execute the current step using available tools."
        )
        
        try:
            self.notification_manager.notify(
                f"🤖 Executing: {current_step[:100]}...",
                MessageType.STEP.value
            )
            
            browser_response = await browser_agent.run(
                user_prompt=prompt,
                deps=BrowserDeps(headless=self.headless),
                message_history=self.message_histories['browser']
            )
            
            # Update message history
            self.message_histories['browser'].extend(browser_response.new_messages())
            
            # Extract tool interactions
            tool_response = browser_response.output
            logger.info(f"\n✅ Browser Response:\n{tool_response}")
            
            self.notification_manager.notify(
                "✅ Step executed",
                MessageType.SUCCESS.value
            )
            
            # Log token usage
            if hasattr(browser_response, '_usage'):
                self.log_token_usage('browser', browser_response._usage, self.iteration_counter)
            
            return tool_response
            
        except Exception as e:
            error_msg = f"Browser agent execution failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.notification_manager.notify(
                f"❌ Error: {str(e)[:100]}",
                MessageType.ERROR.value
            )
            return error_msg
    
    async def run_critique(
        self,
        current_step: str,
        original_plan: str,
        tool_response: str
    ) -> CritiqueOutput:
        """Run the critique agent."""
        logger.info(f"\n{'='*60}\n🔍 CRITIQUE AGENT - Iteration {self.iteration_counter}\n{'='*60}")
        
        # Build critique prompt with max_iterations context
        current_url = self.get_current_url()
        at_max_iterations = self.iteration_counter >= self.max_iterations
        
        prompt = (
            f"Current Step: {current_step}\n\n"
            f"Original Plan: {original_plan}\n\n"
            f"Tool Response: {tool_response}\n\n"
            f"Current URL: {current_url}\n\n"
            f"At Max Iterations: {at_max_iterations}"
        )
        
        try:
            self.notification_manager.notify(
                "🔍 Analyzing progress...",
                MessageType.STEP.value
            )
            
            critique_response = await critique_agent.run(
                user_prompt=prompt,
                message_history=self.message_histories['critique']
            )
            
            # Update message history
            self.message_histories['critique'].extend(critique_response.new_messages())
            
            # Log results
            logger.info(f"\n💬 Feedback:\n{critique_response.output.feedback}")
            if critique_response.output.missing_information:
                logger.info(f"\n❓ Missing Info:\n{critique_response.output.missing_information}")
            logger.info(f"\n🎬 Terminate: {critique_response.output.terminate}")
            
            if critique_response.output.terminate:
                logger.info(f"\n✨ Final Response:\n{critique_response.output.final_response}")
                self.notification_manager.notify(
                    "✨ Task completed",
                    MessageType.SUCCESS.value
                )
            
            # Log token usage
            if hasattr(critique_response, '_usage'):
                self.log_token_usage('critique', critique_response._usage, self.iteration_counter)
            
            return critique_response.output
            
        except Exception as e:
            logger.error(f"Critique agent failed: {e}", exc_info=True)
            raise
    
    async def run(self, user_query: str) -> str:
        """
        Execute the orchestration workflow.
        
        Chooses between multi-agent system (Planner->Browser->Critique loop) or
        single browser agent based on use_multi_agent flag.
        
        Args:
            user_query: The user's task description
            
        Returns:
            Final response from the agents
        """
        if self.use_multi_agent:
            return await self._run_multi_agent(user_query)
        else:
            return await self._run_single_agent(user_query)
    
    async def _run_single_agent(self, user_query: str) -> str:
        """
        Execute task using single browser agent.
        
        Args:
            user_query: The user's task description
            
        Returns:
            Response from the browser agent
        """
        logger.info(f"\n{'#'*80}\n# SINGLE BROWSER AGENT MODE\n{'#'*80}")
        logger.info(f"\n📝 User Query: {user_query}")
        
        start_time = datetime.now()
        self.notification_manager.notify(
            f"🚀 Starting task: {user_query[:100]}...",
            MessageType.INFO.value
        )
        
        try:
            self.notification_manager.notify(
                "🤖 Executing task...",
                MessageType.STEP.value
            )
            
            browser_response = await browser_agent.run(
                user_prompt=user_query,
                deps=BrowserDeps(headless=self.headless),
                message_history=[]
            )
            
            result = browser_response.output
            logger.info(f"\n✅ Task Result:\n{result}")
            
            # Calculate elapsed time
            elapsed = (datetime.now() - start_time).total_seconds()
            elapsed_str = format_time_elapsed(elapsed)
            
            # Log summary
            logger.info(
                f"\n{'#'*80}\n"
                f"# TASK COMPLETE\n"
                f"{'#'*80}\n"
                f"⏱️  Duration: {elapsed_str}\n"
                f"{'#'*80}"
            )
            
            self.notification_manager.notify(
                f"✅ Task completed in {elapsed_str}",
                MessageType.DONE.value
            )
            
            return result or "Task completed but no output generated"
            
        except KeyboardInterrupt:
            logger.warning("⚠️  Task interrupted by user")
            self.notification_manager.notify(
                "⚠️  Task interrupted",
                MessageType.WARNING.value
            )
            raise
        except Exception as e:
            logger.error(f"❌ Task execution failed: {e}", exc_info=True)
            self.notification_manager.notify(
                f"❌ Error: {str(e)}",
                MessageType.ERROR.value
            )
            raise
    
    async def _run_multi_agent(self, user_query: str) -> str:
        """
        Execute the multi-agent orchestration loop.
        
        Args:
            user_query: The user's task description
            
        Returns:
            Final response from the critique agent
        """
        logger.info(f"\n{'#'*80}\n# MULTI-AGENT BROWSER AUTOMATION\n{'#'*80}")
        logger.info(f"\n📝 User Query: {user_query}")
        
        start_time = datetime.now()
        self.notification_manager.notify(
            f"🚀 Starting task: {user_query[:100]}...",
            MessageType.INFO.value
        )
        
        feedback = None
        missing_info = None
        final_response = None
        
        try:
            # Main orchestration loop
            while not self.terminate and self.iteration_counter < self.max_iterations:
                self.iteration_counter += 1
                
                logger.info(
                    f"\n{'#'*80}\n"
                    f"# ITERATION {self.iteration_counter}/{self.max_iterations}\n"
                    f"{'#'*80}"
                )
                
                # Step 1: Run planner
                planner_output = await self.run_planner(user_query, feedback, missing_info)
                
                # Step 2: Run browser agent
                tool_response = await self.run_browser_agent(
                    planner_output.plan,
                    planner_output.next_step
                )
                
                # Step 3: Run critique
                critique_output = await self.run_critique(
                    planner_output.next_step,
                    planner_output.plan,
                    tool_response
                )
                
                # Update feedback and missing info for next iteration
                feedback = critique_output.feedback
                missing_info = critique_output.missing_information
                
                # Check termination
                if critique_output.terminate:
                    self.terminate = True
                    final_response = critique_output.final_response
                    break
            
            # Handle max iterations reached
            if self.iteration_counter >= self.max_iterations and not self.terminate:
                logger.warning(f"⚠️  Reached maximum iterations ({self.max_iterations})")
                
                # Give critique agent one final chance to answer with available info
                logger.info("Running final critique to provide best available answer...")
                final_critique = await self.run_critique(
                    "Max iterations reached",
                    self.current_plan or "No plan available",
                    f"Max iterations ({self.max_iterations}) reached. Provide answer with available information."
                )
                
                final_response = final_critique.final_response or (
                    f"Task did not complete within {self.max_iterations} iterations. "
                    f"Last feedback: {feedback}"
                )
                self.notification_manager.notify(
                    "⚠️  Maximum iterations reached",
                    MessageType.WARNING.value
                )
            
            # Calculate elapsed time
            elapsed = (datetime.now() - start_time).total_seconds()
            elapsed_str = format_time_elapsed(elapsed)
            
            # Log summary
            logger.info(
                f"\n{'#'*80}\n"
                f"# ORCHESTRATION COMPLETE\n"
                f"{'#'*80}\n"
                f"⏱️  Duration: {elapsed_str}\n"
                f"🔄 Iterations: {self.iteration_counter}\n"
                f"📊 Total Tokens: {sum(agent['total'] for agent in self.cumulative_tokens.values())}\n"
                f"{'#'*80}"
            )
            
            self.notification_manager.notify(
                f"✅ Task completed in {elapsed_str} ({self.iteration_counter} iterations)",
                MessageType.DONE.value
            )
            
            return final_response or "Task completed but no final response generated"
            
        except KeyboardInterrupt:
            logger.warning("⚠️  Task interrupted by user")
            self.notification_manager.notify(
                "⚠️  Task interrupted",
                MessageType.WARNING.value
            )
            raise
        except Exception as e:
            logger.error(f"❌ Orchestration failed: {e}", exc_info=True)
            self.notification_manager.notify(
                f"❌ Error: {str(e)}",
                MessageType.ERROR.value
            )
            raise
    
    def reset(self):
        """Reset orchestrator state for a new task."""
        self.iteration_counter = 0
        self.terminate = False
        self.current_plan = None
        self.message_histories = {
            'planner': [],
            'browser': [],
            'critique': []
        }
        logger.info("🔄 Orchestrator state reset")


async def run_with_orchestrator(
    prompt: str,
    headless: bool = False,
    max_iterations: int = 20,
    use_multi_agent: bool = False,
    notification_callback: Optional[callable] = None
) -> str:
    """
    Run a browser automation task using the orchestrator.
    
    Args:
        prompt: Task description
        headless: Whether to run browser in headless mode
        max_iterations: Maximum number of agent loop iterations (only used if use_multi_agent=True)
        use_multi_agent: Whether to use multi-agent system (Planner->Browser->Critique) or single browser agent
        notification_callback: Optional callback for progress notifications
        
    Returns:
        Final response from the task
    """
    orchestrator = AgentOrchestrator(
        headless=headless, 
        max_iterations=max_iterations,
        use_multi_agent=use_multi_agent
    )
    
    # Register notification callback if provided
    if notification_callback:
        orchestrator.notification_manager.register_listener(notification_callback)
    
    try:
        result = await orchestrator.run(prompt)
        return result
    finally:
        # Cleanup
        orchestrator.reset()
