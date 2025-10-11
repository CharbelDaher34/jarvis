from enum import Enum


class MessageType(Enum):
    """Message types for browser automation tasks."""
    PLAN = "plan"
    STEP = "step"
    ACTION = "action"
    ANSWER = "answer"
    QUESTION = "question"
    INFO = "info"
    FINAL = "final"
    DONE = "transaction_done"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    MAX_TURNS_REACHED = "max_turns_reached"
    USER_QUERY = "user_query"


class TaskStatus(Enum):
    """Status of browser automation tasks."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
