import asyncio
import logging
from typing import Optional

logger = logging.getLogger('CTE.Limiter')

class ConnectionLimiter:

    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(max_connections)
        self._lock = asyncio.Lock()
        self.current_connections = 0
        self.rejected_total = 0

        logger.info(f"✓ Connection limit: {max_connections}")

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        try:
            if timeout:
                await asyncio.wait_for(
                    self.semaphore.acquire(),
                    timeout=timeout
                )
            else:
                await self.semaphore.acquire()

            async with self._lock:
                self.current_connections += 1
            logger.debug(f"Connection accepted ({self.current_connections}/{self.max_connections})")
            return True

        except asyncio.TimeoutError:
            async with self._lock:
                self.rejected_total += 1
            logger.warning(
                f"Connection rejected (timeout) - "
                f"Active connections: {self.current_connections}/{self.max_connections}"
            )
            return False
        except Exception as e:
            async with self._lock:
                self.rejected_total += 1
            logger.error(f"  acquire: {e}")
            return False

    async def release(self):
        try:
            self.semaphore.release()
            async with self._lock:
                self.current_connections -= 1
            logger.debug(f"Connection released ({self.current_connections}/{self.max_connections})")
        except Exception as e:
            logger.error(f"  release: {e}")

    def is_available(self) -> bool:
        return self.current_connections < self.max_connections

    def get_stats(self) -> dict:
        return {
            'max_connections': self.max_connections,
            'current_connections': self.current_connections,
            'available_slots': self.max_connections - self.current_connections,
            'rejected_total': self.rejected_total,
            'utilization_percent': (self.current_connections / self.max_connections) * 100
        }

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()

class MaxConnectionError(Exception):
    pass