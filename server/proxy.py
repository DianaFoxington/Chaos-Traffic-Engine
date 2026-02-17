import asyncio
import logging
import uuid
from typing import Optional

logger = logging.getLogger('CTE.Proxy')

class ProxyServer:
    
    def __init__(
        self,
        host: str,
        port: int,
        handlers: list,
        limiter,
        stats_collector,
        buffers: dict
    ):
        self.host = host
        self.port = port
        self.handlers = handlers
        self.limiter = limiter
        self.stats = stats_collector
        self.buffers = buffers
        
        self.server = None
        self.running = False
        
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
            
            addr = self.server.sockets[0].getsockname()
            logger.info("=" * 60)
            logger.info(f"🚀 Chaos Traffic Engine Started!")
            logger.info(f"📡 Listening on {addr[0]}:{addr[1]}")
            logger.info(f"🔧 Max connections: {self.limiter.max_connections}")
            logger.info("=" * 60)
            
            async with self.server:
                await self.server.serve_forever()
                
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.running = False
    
    async def stop(self):
        logger.info("Stopping proxy server...")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("Proxy server stopped")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        
        conn_id = str(uuid.uuid4())[:8]
        client_addr = writer.get_extra_info('peername')
        
        if not await self.limiter.acquire(timeout=1.0):
            logger.warning(f"Connection rejected (limit reached): {client_addr}")
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            return
        
        try:
            logger.debug(f"[{conn_id}] New connection from {client_addr}")
            
            first_bytes = await asyncio.wait_for(
                reader.read(self.buffers.get('small', 8192)),
                timeout=5.0
            )
            
            if not first_bytes:
                logger.debug(f"[{conn_id}] Empty request")
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
                logger.debug(f"[{conn_id}] First bytes: {first_bytes[:50]}")
                return
            
            self.stats.connection_started(
                conn_id,
                protocol_name,
                str(client_addr)
            )
            
            await detected_handler.handle(reader, writer, first_bytes)
            
            self.stats.connection_ended(conn_id, success=True)
            
        except asyncio.TimeoutError:
            logger.warning(f"[{conn_id}] Connection timeout")
            self.stats.connection_ended(conn_id, success=False)
        except Exception as e:
            logger.error(f"[{conn_id}] Connection error: {e}")
            self.stats.connection_ended(conn_id, success=False)
        finally:
            self.limiter.release()
            
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            
            logger.debug(f"[{conn_id}] Connection closed")
