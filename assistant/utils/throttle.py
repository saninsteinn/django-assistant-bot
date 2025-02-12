import asyncio
import logging
import time


logger = logging.getLogger(__name__)


class Throttle:
    def __init__(self, time_period: float):
        """
        Initialize the Throttle.

        :param time_period: Minimum time period in seconds between calls.
        """
        self.time_period = time_period
        self.last_call = 0

    async def __call__(self):
        """
        Throttle the function calls.
        """
        current_time = time.time()
        time_since_last_call = current_time - self.last_call

        if time_since_last_call < self.time_period:
            logger.debug(f"Throttling for {self.time_period - time_since_last_call} seconds")
            await asyncio.sleep(self.time_period - time_since_last_call)

        self.last_call = time.time()
