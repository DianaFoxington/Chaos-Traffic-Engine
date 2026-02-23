import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger('CTE.Relay')

class TrafficRelay:

    def __init__(
        self,
        chaos_engine,
        tls_fragmenter,
        stats_collector,
        buffers: dict,
        enable_padding: bool = True,
        enable_dummy: bool = True
    ):
        self.chaos = chaos_engine
        self.fragmenter = tls_fragmenter
        self.stats = stats_collector
        self.buffers = buffers
        self.enable_padding = enable_padding
        self.enable_dummy = enable_dummy
        self.target_packet_size = 1400

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
                total_sent = 0

                while True:
                    data = await client_reader.read(self.buffers.get('large', 262144))
                    if not data:
                        break

                    remote_writer.write(data)
                    await remote_writer.drain()
                    total_sent += len(data)

                await self.stats.record_traffic(conn_id, bytes_sent=total_sent)

            except Exception as e:
                logger.debug(f"[{conn_id}] Client->Remote error: {e}")
            finally:
                try:
                    remote_writer.close()
                except:
                    pass

        async def remote_to_client():
            try:
                total_received = 0

                while True:
                    data = await remote_reader.read(self.buffers.get('large', 262144))
                    if not data:
                        break

                    client_writer.write(data)
                    await client_writer.drain()
                    total_received += len(data)

                await self.stats.record_traffic(conn_id, bytes_received=total_received)

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
                await self.stats.record_traffic(conn_id, bytes_sent=total_bytes)
            else:
                await self.stats.record_traffic(conn_id, bytes_received=total_bytes)

        except Exception as e:
            logger.debug(f"[{conn_id}] Relay {direction} error: {e}")
        finally:
            try:
                dest_writer.close()
            except:
                pass

    def apply_padding(self, data: bytes, framing_header: bytes = b'', framing_footer: bytes = b'') -> bytes:
        if not self.enable_padding:
            return data

        overhead = len(framing_header) + len(framing_footer)
        if len(data) + overhead >= self.target_packet_size:
            return data

        padding_size = self.target_packet_size - len(data) - overhead
        padding = os.urandom(padding_size)
        return data + padding

    async def inject_dummy_traffic(self, writer: asyncio.StreamWriter):
        pass