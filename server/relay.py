import asyncio
import logging
from typing import Optional

logger = logging.getLogger('CTE.Relay')

class TrafficRelay:
    
    def __init__(
        self,
        chaos_engine,
        tls_fragmenter,
        stats_collector,
        buffers: dict
    ):
        self.chaos = chaos_engine
        self.fragmenter = tls_fragmenter
        self.stats = stats_collector
        self.buffers = buffers
    
    async def relay_bidirectional(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
        conn_id: str,
        enable_fragmentation: bool = True
    ):
        
        async def client_to_remote():
            try:
                total_received = 0
                
                while True:
                    data = await remote_reader.read(self.buffers.get('large', 262144))
                    if not data:
                        break
                    
                    client_writer.write(data)
                    await client_writer.drain()
                    total_received += len(data)
                
                self.stats.record_traffic(conn_id, bytes_received=total_received)
                
            except Exception as e:
                logger.debug(f"[{conn_id}] Remote->Client error: {e}")
            finally:
                try:
                    client_writer.close()
                except:
                    pass
        
        await asyncio.gather(
            client_to_remote(),
            remote_to_client(),
            return_exceptions=True
        )
    
    async def relay_simple(
        self,
        source_reader: asyncio.StreamReader,
        dest_writer: asyncio.StreamWriter,
        conn_id: str,
        direction: str = "forward"
    ):
        try:
            total_bytes = 0
            
            while True:
                data = await source_reader.read(self.buffers.get('medium', 65536))
                if not data:
                    break
                
                dest_writer.write(data)
                await dest_writer.drain()
                total_bytes += len(data)
            
            if direction == "forward":
                self.stats.record_traffic(conn_id, bytes_sent=total_bytes)
            else:
                self.stats.record_traffic(conn_id, bytes_received=total_bytes)
            
        except Exception as e:
            logger.debug(f"[{conn_id}] Relay {direction} error: {e}")
        finally:
            try:
                dest_writer.close()
            except:
                pass
