from typing import Callable, Dict, List


class NotificationManager:
    """
    Manages notification dispatching to registered listeners.
    Useful for task progress monitoring and event handling.
    """

    def __init__(self):
        """Initialize the NotificationManager with no listeners."""
        self.listeners: List[Callable[[Dict[str, str]], None]] = []

    def notify(self, message: str, message_type: str) -> None:
        """
        Notify all registered listeners with a message and its type.
        
        Args:
            message: The message to notify
            message_type: The type/category of the message
        """
        notification = {
            "message": message,
            "type": message_type,
        }

        if self.listeners:
            for listener in self.listeners:
                try:
                    listener(notification)
                except Exception as e:
                    print(f"Error notifying listener: {e}")
        else:
            # Fallback to console if no listeners
            print(f"[{message_type.upper()}] {message}")

    def register_listener(self, listener: Callable[[Dict[str, str]], None]) -> None:
        """
        Register a new listener to receive notifications.
        
        Args:
            listener: Callback function that accepts notification dict
        """
        if listener not in self.listeners:
            self.listeners.append(listener)

    def unregister_listener(self, listener: Callable[[Dict[str, str]], None]) -> None:
        """
        Unregister a listener from receiving notifications.
        
        Args:
            listener: Callback function to remove
        """
        if listener in self.listeners:
            self.listeners.remove(listener)

    def clear_listeners(self) -> None:
        """Remove all registered listeners."""
        self.listeners.clear()
