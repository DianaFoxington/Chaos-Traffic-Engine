import asyncio
import logging
import uuid

logger = logging.getLogger('CTE.Proxy')

class ProxyServer:

    def __init__(self, host, port, handlers, limiter, stats_collector, buffers):
        self.host = host
        self.port = port
        self.handlers = handlers
        self.limiter = limiter
        self.stats = stats_collector
        self.buffers = buffers

        self.server = None
        self.running = False
        self._active_tasks: set = set()
        self._shutdown_event = asyncio.Event()

        logger.info(f"Proxy server initialized: {host}:{port}")
        logger.info(f"Protocols: {len(handlers)}")

    async def start(self):
        try:
            self.server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port
            )

            self.running = True
            self._shutdown_event.clear()

            addr = self.server.sockets[0].getsockname()
            logger.info("=" * 60)
            logger.info("🚀 Chaos Traffic Engine Started!")
            logger.info(f"📡 Listening on {addr[0]}:{addr[1]}")
            logger.info(f"🔧 Max connections: {self.limiter.max_connections}")
            logger.info("=" * 60)

            await self.server.start_serving()
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.running = False

    async def stop(self):
        if not self.running and not self._active_tasks:
            return

        logger.info("Stopping proxy server...")
        self.running = False

        if self.server:
            self.server.close()

        if self._active_tasks:
            logger.info(f"Cancelling {len(self._active_tasks)} active connections...")
            for task in list(self._active_tasks):
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        if self.server:
            try:
                await asyncio.wait_for(self.server.wait_closed(), timeout=3.0)
            except asyncio.TimeoutError:
                pass

        logger.info("Proxy server stopped")
        self._shutdown_event.set()

    async def _handle_connection(self, reader, writer):
        task = asyncio.current_task()
        self._active_tasks.add(task)

        conn_id = str(uuid.uuid4())[:8]
        client_addr = writer.get_extra_info('peername')

        if not await self.limiter.acquire(timeout=1.0):
            logger.warning(f"Connection rejected (limit reached): {client_addr}")
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            self._active_tasks.discard(task)
            return

        try:
            first_bytes = await asyncio.wait_for(
                reader.read(self.buffers.get('small', 8192)),
                timeout=5.0
            )

            if not first_bytes:
                return

            detected_handler = None
            for handler in self.handlers:
                if await handler.detect(first_bytes):
                    detected_handler = handler
                    protocol_name = handler.__class__.__name__.replace('Handler', '')
                    logger.info(f"[{conn_id}] Protocol: {protocol_name}")
                    break

            if not detected_handler:
                logger.warning(f"[{conn_id}] Unknown protocol")
                return

            await self.stats.connection_started(conn_id, protocol_name, str(client_addr))
            await detected_handler.handle(reader, writer, first_bytes)
            await self.stats.connection_ended(conn_id, success=True)

        except asyncio.CancelledError:
            logger.debug(f"[{conn_id}] Cancelled (shutdown)")
            try:
                await self.stats.connection_ended(conn_id, success=False)
            except:
                pass
            raise
        except asyncio.TimeoutError:
            logger.warning(f"[{conn_id}] Timeout")
            await self.stats.connection_ended(conn_id, success=False)
        except Exception as e:
            logger.error(f"[{conn_id}] Error: {e}")
            await self.stats.connection_ended(conn_id, success=False)
        finally:
            self._active_tasks.discard(task)
            await self.limiter.release()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass