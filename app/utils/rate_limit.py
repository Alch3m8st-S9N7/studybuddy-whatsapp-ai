import time
from typing import Dict, Tuple

class RateLimiter:
    """
    A simple in-memory rate limiter to prevent spam or abuse of the expensive LLM pipeline.
    In a real massive-scale production environment, use Redis for distributed rate limiting.
    """
    def __init__(self, limit: int = 5, window_seconds: int = 3600):
        self.limit = limit
        self.window_seconds = window_seconds
        # Stores user_id -> (count, first_request_timestamp)
        self._store: Dict[str, Tuple[int, float]] = {}

    def is_allowed(self, user_id: str) -> bool:
        """Returns True if user is allowed to proceed, False if rate limited."""
        now = time.time()
        
        if user_id not in self._store:
            self._store[user_id] = (1, now)
            return True
            
        count, first_req_time = self._store[user_id]
        
        # If the window has expired, reset
        if now - first_req_time > self.window_seconds:
            self._store[user_id] = (1, now)
            return True
            
        # Below limit in window
        if count < self.limit:
            self._store[user_id] = (count + 1, first_req_time)
            return True
            
        return False

# Limit to 5 documents per hour per user in memory
rate_limiter = RateLimiter(limit=5, window_seconds=3600)
