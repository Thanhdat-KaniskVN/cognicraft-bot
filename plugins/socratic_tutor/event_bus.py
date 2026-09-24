# event_bus.py
"""
Event Bus - Pub/Sub system cho plugins
"""
import asyncio
from typing import Callable, Dict, List
from collections import defaultdict


class EventBus:
    """Event Bus cho plugins"""

    def __init__(self):
        self.subscribers = defaultdict(list)

    def on(self, event_name, callback):
        """Subscribe to event"""
        self.subscribers[event_name].append(callback)

    def off(self, event_name, callback):
        """Unsubscribe"""
        if callback in self.subscribers[event_name]:
            self.subscribers[event_name].remove(callback)

    async def emit(self, event_name, **kwargs):
        """Emit event to all subscribers"""
        handlers = self.subscribers.get(event_name, [])

        results = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**kwargs)
                else:
                    result = handler(**kwargs)
                results.append(result)
            except Exception as e:
                print(f"[EventBus] Error in {event_name}: {e}")
                results.append({"error": str(e)})

        return results

    def clear(self, event_name=None):
        """Clear subscribers"""
        if event_name:
            self.subscribers[event_name] = []
        else:
            self.subscribers.clear()


# Global instance
event_bus = EventBus()