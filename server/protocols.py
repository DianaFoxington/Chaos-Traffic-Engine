import asyncio
import logging
import struct
import base64
import hashlib
import uuid
from typing import Optional, Tuple
from urllib.parse import urlparse

from core.engine import ChaosEngine
from core.tls import TLSFragmenter

logger = logging.getLogger('CTE.Protocols')

class ProtocolHandler:
    def __init__(self, chaos_engine, dns_resolver, bypass_manager, stats_collector, tls_fragmenter=None, domain_fronter=None):
        self.chaos = chaos_engine
        self.dns = dns_resolver
        self.bypass = bypass_manager
        self.stats = stats_collector
        self.tls = tls_fragmenter
        self.fronter = domain_fronter
        self._aggressive = tls_fragmenter.aggressive if tls_fragmenter else True

    def _make_fragmenter(self) -> TLSFragmenter:
        conn_id = uuid.uuid4().bytes
        engine = ChaosEngine(connection_id=conn_id)
        return TLSFragmenter(engine, aggressive=self._aggressive)

    async def detect(self, first_bytes: bytes) -> bool:
        raise NotImplementedError

    async def handle(self, reader, writer, first_bytes: bytes):

        raise NotImplementedError

class HTTPHandler(ProtocolHandler):

    async def detect(self, first_bytes: bytes) -> bool:

        try:
            return first_bytes.startswith((
                b'GET ', b'POST ', b'PUT ', b'DELETE ',
                b'HEAD ', b'CONNECT ', b'OPTIONS ', b'PATCH '
            ))
        except:
            return False

    async def handle(self, reader, writer, first_bytes: bytes):

        try:
            request_line = first_bytes.split(b'\r\n')[0].decode('utf-8')
            parts = request_line.split(' ')

            if len(parts) < 2:
                writer.close()
                return

            method = parts[0]
            url = parts[1]

            logger.info(f"HTTP Request: {method} {url}")

            if method == 'CONNECT':
                await self._handle_connect(reader, writer, url, first_bytes)
            else:
                await self._handle_http(reader, writer, url, first_bytes)

        except Exception as e:
            logger.error(f"HTTP handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def _handle_connect(self, reader, writer, url: str, first_bytes: bytes):

        try:
            if ':' in url:
                host, port = url.split(':', 1)
                port = int(port)
            else:
                host = url
                port = 443

            conn_id = writer.get_extra_info('peername', ('unknown',))[0]
            if self.bypass.should_bypass_domain(host):
                logger.info(f"🔀 Bypass: {host}")
                await self.stats.record_bypass(conn_id, 'domain_bypass')
                await self._relay_connect(reader, writer, host, port, bypass=True)
            else:
                logger.info(f"🔒 Tunnel: {host}")
                await self.stats.record_tunnel(conn_id)
                await self._relay_connect(reader, writer, host, port, bypass=False)

        except Exception as e:
            logger.error(f"CONNECT error: {e}")

    async def _handle_http(self, reader, writer, url: str, first_bytes: bytes):

        try:
            parsed = urlparse(url)
            host = parsed.hostname or parsed.path.split('/')[0]
            port = parsed.port or 80

            bypass = self.bypass.should_bypass_domain(host)
            if bypass:
                logger.info(f"🔀 Bypass HTTP: {host}")
            else:
                logger.info(f"🔒 Tunnel HTTP: {host}")

            await self._relay_connect(reader, writer, host, port, bypass=bypass)

        except Exception as e:
            logger.error(f"HTTP error: {e}")

    NO_FRONT_DOMAINS = {
        'google.com', 'youtube.com', 'googleapis.com', 'gstatic.com',
        'googlevideo.com', 'ggpht.com', 'googleusercontent.com',
        'ytimg.com', 'youtu.be', 'gmail.com', 'accounts.google.com',
    }

    async def _relay_connect(self, client_reader, client_writer, host: str, port: int, bypass: bool):

        try:
            connect_host = host
            if not bypass and port == 443 and self.fronter is not None:
                host_lower = host.lower()
                can_front = not any(
                    host_lower == d or host_lower.endswith('.' + d)
                    for d in self.NO_FRONT_DOMAINS
                )
                if can_front:
                    front = self.fronter.select_front_domain(real_domain=host)
                    if front:
                        connect_host = front

            ip = await self.dns.resolve(connect_host)
            if not ip:
                logger.error(f"DNS resolution failed: {host}")
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
                return

            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                client_writer.write(b'HTTP/1.1 504 Gateway Timeout\r\n\r\n')
                await client_writer.drain()
                return
            except Exception as e:
                logger.error(f"Connection failed to {connect_host}:{port} - {e}")
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
                return

            client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await client_writer.drain()

            await self._relay_data(client_reader, client_writer, remote_reader, remote_writer)

        except Exception as e:
            logger.error(f"Relay error: {e}")
        finally:
            try:
                remote_writer.close()
                await remote_writer.wait_closed()
            except:
                pass

    async def _relay_data(self, client_reader, client_writer, remote_reader, remote_writer):
        conn_fragmenter = self._make_fragmenter() if self.tls is not None else None

        async def forward_client_to_remote():
            first = True
            total_sent = 0
            try:
                while True:
                    data = await client_reader.read(65536)
                    if not data:
                        break
                    if first and conn_fragmenter is not None:
                        first = False
                        fragments = conn_fragmenter.fragment(data)
                        for chunk, delay in fragments:
                            remote_writer.write(chunk)
                            await remote_writer.drain()
                            if delay > 0:
                                await asyncio.sleep(delay)
                    else:
                        first = False
                        remote_writer.write(data)
                        await remote_writer.drain()
                    total_sent += len(data)
            except Exception as e:
                logger.debug(f"Forward client->remote error: {e}")
            finally:
                try:
                    if remote_writer.can_write_eof():
                        remote_writer.write_eof()
                except Exception:
                    pass
            return total_sent

        async def forward_remote_to_client():
            total_recv = 0
            try:
                while True:
                    data = await remote_reader.read(65536)
                    if not data:
                        break
                    client_writer.write(data)
                    await client_writer.drain()
                    total_recv += len(data)
            except Exception as e:
                logger.debug(f"Forward remote->client error: {e}")
            return total_recv

        results = await asyncio.gather(
            forward_client_to_remote(),
            forward_remote_to_client(),
            return_exceptions=True
        )

        sent = results[0] if isinstance(results[0], int) else 0
        recv = results[1] if isinstance(results[1], int) else 0
        if sent or recv:
            conn_id = id(client_writer)
            await self.stats.record_traffic(str(conn_id), bytes_sent=sent, bytes_received=recv)

        for writer in (remote_writer, client_writer):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

class SOCKS5Handler(ProtocolHandler):

    async def detect(self, first_bytes: bytes) -> bool:

        try:
            return len(first_bytes) >= 2 and first_bytes[0] == 0x05
        except:
            return False

    async def handle(self, reader, writer, first_bytes: bytes):

        try:
            if len(first_bytes) < 2:
                return

            version = first_bytes[0]
            nmethods = first_bytes[1]

            if version != 0x05:
                return

            if len(first_bytes) < 2 + nmethods:
                methods_data = first_bytes[2:] + await reader.read(2 + nmethods - len(first_bytes))
            else:
                methods_data = first_bytes[2:2+nmethods]

            writer.write(b'\x05\x00')
            await writer.drain()

            request = await reader.read(4)
            if len(request) < 4:
                return

            ver, cmd, rsv, atyp = request

            if cmd != 0x01:
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                return

            if atyp == 0x01:
                addr_data = await reader.read(4)
                host = '.'.join(str(b) for b in addr_data)
            elif atyp == 0x03:
                length = (await reader.read(1))[0]
                addr_data = await reader.read(length)
                host = addr_data.decode('utf-8')
            elif atyp == 0x04:
                addr_data = await reader.read(16)
                host = addr_data.hex()
            else:
                writer.write(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                return

            port_data = await reader.read(2)
            port = struct.unpack('!H', port_data)[0]

            logger.info(f"SOCKS5: {host}:{port}")

            conn_id = writer.get_extra_info('peername', ('unknown',))[0]
            bypass = self.bypass.should_bypass_domain(host)
            if bypass:
                logger.info(f"🔀 Bypass: {host}")
                await self.stats.record_bypass(conn_id, 'domain_bypass')
            else:
                logger.info(f"🔒 Tunnel: {host}")
                await self.stats.record_tunnel(conn_id)

            ip = await self.dns.resolve(host)
            if not ip:
                writer.write(b'\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00')
                return

            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=10.0
                )
            except:
                writer.write(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
                return

            writer.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
            await writer.drain()

            await self._relay_data(reader, writer, remote_reader, remote_writer)

        except Exception as e:
            logger.error(f"SOCKS5 error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def _relay_data(self, client_reader, client_writer, remote_reader, remote_writer):
        conn_fragmenter = self._make_fragmenter() if self.tls is not None else None

        async def forward_client_to_remote():
            first = True
            total_sent = 0
            try:
                while True:
                    data = await client_reader.read(65536)
                    if not data:
                        break
                    if first and conn_fragmenter is not None:
                        first = False
                        fragments = conn_fragmenter.fragment(data)
                        for chunk, delay in fragments:
                            remote_writer.write(chunk)
                            await remote_writer.drain()
                            if delay > 0:
                                await asyncio.sleep(delay)
                    else:
                        first = False
                        remote_writer.write(data)
                        await remote_writer.drain()
                    total_sent += len(data)
            except Exception:
                pass
            finally:
                try:
                    if remote_writer.can_write_eof():
                        remote_writer.write_eof()
                except Exception:
                    pass
            return total_sent

        async def forward_remote_to_client():
            total_recv = 0
            try:
                while True:
                    data = await remote_reader.read(65536)
                    if not data:
                        break
                    client_writer.write(data)
                    await client_writer.drain()
                    total_recv += len(data)
            except Exception:
                pass
            return total_recv

        results = await asyncio.gather(
            forward_client_to_remote(),
            forward_remote_to_client(),
            return_exceptions=True
        )

        sent = results[0] if isinstance(results[0], int) else 0
        recv = results[1] if isinstance(results[1], int) else 0
        if sent or recv:
            conn_id = id(client_writer)
            await self.stats.record_traffic(str(conn_id), bytes_sent=sent, bytes_received=recv)

        for writer in (remote_writer, client_writer):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

class WebSocketHandler(ProtocolHandler):

    async def detect(self, first_bytes: bytes) -> bool:

        try:
            request = first_bytes.decode('utf-8', errors='ignore')
            return ('Upgrade: websocket' in request or
                    'upgrade: websocket' in request)
        except:
            return False

    async def handle(self, reader, writer, first_bytes: bytes):
        try:
            request = first_bytes.decode('utf-8', errors='ignore')
            lines = request.split('\r\n')

            headers = {}
            for line in lines[1:]:
                if ': ' in line:
                    k, v = line.split(': ', 1)
                    headers[k.lower()] = v

            ws_key = headers.get('sec-websocket-key', '')
            host = headers.get('host', '').split(':')[0]
            port_str = headers.get('host', '').split(':')
            port = int(port_str[1]) if len(port_str) > 1 else 80

            if not host:
                writer.close()
                return

            accept_key = base64.b64encode(
                hashlib.sha1((ws_key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()
            ).decode()

            handshake = (
                'HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept_key}\r\n'
                '\r\n'
            )
            writer.write(handshake.encode())
            await writer.drain()

            logger.info(f"WebSocket tunnel: {host}:{port}")

            bypass = self.bypass.should_bypass_domain(host)
            ip = await self.dns.resolve(host)
            if not ip:
                logger.error(f"DNS failed for WebSocket host: {host}")
                writer.close()
                return

            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"WebSocket remote connect failed: {e}")
                writer.close()
                return

            await self._relay_ws(reader, writer, remote_reader, remote_writer)

        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def _relay_ws(self, client_reader, client_writer, remote_reader, remote_writer):
        async def ws_client_to_remote():
            try:
                while True:
                    header = await client_reader.readexactly(2)
                    if not header:
                        break
                    opcode = header[0] & 0x0F
                    masked = (header[1] & 0x80) != 0
                    payload_len = header[1] & 0x7F

                    if payload_len == 126:
                        ext = await client_reader.readexactly(2)
                        payload_len = struct.unpack('!H', ext)[0]
                    elif payload_len == 127:
                        ext = await client_reader.readexactly(8)
                        payload_len = struct.unpack('!Q', ext)[0]

                    mask_key = b''
                    if masked:
                        mask_key = await client_reader.readexactly(4)

                    payload = await client_reader.readexactly(payload_len)

                    if masked:
                        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
                    if opcode == 8:
                        break
                    elif opcode in (9, 10):
                        continue  
                    if payload:
                        remote_writer.write(payload)
                        await remote_writer.drain()

            except (asyncio.IncompleteReadError, ConnectionResetError):
                pass
            except Exception as e:
                logger.debug(f"WS client->remote: {e}")
            finally:
                try:
                    remote_writer.close()
                except:
                    pass

        async def raw_remote_to_ws_client():
            try:
                while True:
                    data = await remote_reader.read(65536)
                    if not data:
                        break
                    frame = bytearray()
                    frame.append(0x82)
                    length = len(data)
                    if length < 126:
                        frame.append(length)
                    elif length < 65536:
                        frame.append(126)
                        frame += struct.pack('!H', length)
                    else:
                        frame.append(127)
                        frame += struct.pack('!Q', length)
                    frame += data

                    client_writer.write(bytes(frame))
                    await client_writer.drain()

            except Exception as e:
                logger.debug(f"WS remote->client: {e}")
            finally:
                try:
                    client_writer.close()
                except:
                    pass

        await asyncio.gather(
            ws_client_to_remote(),
            raw_remote_to_ws_client(),
            return_exceptions=True
        )

def create_handlers(chaos_engine, dns_resolver, bypass_manager, stats_collector, tls_fragmenter=None, domain_fronter=None):
    return [
        HTTPHandler(chaos_engine, dns_resolver, bypass_manager, stats_collector, tls_fragmenter, domain_fronter),
        SOCKS5Handler(chaos_engine, dns_resolver, bypass_manager, stats_collector, tls_fragmenter, domain_fronter),
        WebSocketHandler(chaos_engine, dns_resolver, bypass_manager, stats_collector),
    ]

#این منو به گاه داد