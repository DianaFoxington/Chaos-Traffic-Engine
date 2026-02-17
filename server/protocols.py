

import asyncio
import logging
import struct
import base64
import hashlib
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger('CTE.Protocols')


class ProtocolHandler:
    
    
    def __init__(self, chaos_engine, dns_resolver, bypass_manager):
        self.chaos = chaos_engine
        self.dns = dns_resolver
        self.bypass = bypass_manager
    
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
            
            if self.bypass.should_bypass_domain(host):
                logger.info(f"🔀 Bypass: {host}")
                await self._relay_connect(reader, writer, host, port, bypass=True)
            else:
                logger.info(f"🔒 Tunnel: {host}")
                await self._relay_connect(reader, writer, host, port, bypass=False)
                
        except Exception as e:
            logger.error(f"CONNECT error: {e}")
    
    async def _handle_http(self, reader, writer, url: str, first_bytes: bytes):
        
        try:
            parsed = urlparse(url)
            host = parsed.hostname or parsed.path.split('/')[0]
            port = parsed.port or 80
            
            if self.bypass.should_bypass_domain(host):
                logger.info(f"🔀 Bypass HTTP: {host}")
            else:
                logger.info(f"🔒 Tunnel HTTP: {host}")
            
            await self._relay_connect(reader, writer, host, port, bypass=True)
            
        except Exception as e:
            logger.error(f"HTTP error: {e}")
    
    async def _relay_connect(self, client_reader, client_writer, host: str, port: int, bypass: bool):
        
        try:
            ip = await self.dns.resolve(host)
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
                logger.error(f"Connection failed to {ip}:{port} - {e}")
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
        
        async def forward(reader, writer, name):
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except Exception as e:
                logger.debug(f"Forward {name} error: {e}")
            finally:
                try:
                    writer.close()
                except:
                    pass
        
        await asyncio.gather(
            forward(client_reader, remote_writer, "client->remote"),
            forward(remote_reader, client_writer, "remote->client"),
            return_exceptions=True
        )


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
            
            if cmd != 0x01:  # Only CONNECT
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                return
            
            if atyp == 0x01:  # IPv4
                addr_data = await reader.read(4)
                host = '.'.join(str(b) for b in addr_data)
            elif atyp == 0x03:  # Domain
                length = (await reader.read(1))[0]
                addr_data = await reader.read(length)
                host = addr_data.decode('utf-8')
            elif atyp == 0x04:  # IPv6
                addr_data = await reader.read(16)
                host = addr_data.hex()
            else:
                writer.write(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                return
            
            port_data = await reader.read(2)
            port = struct.unpack('!H', port_data)[0]
            
            logger.info(f"SOCKS5: {host}:{port}")
            
            bypass = self.bypass.should_bypass_domain(host)
            if bypass:
                logger.info(f"🔀 Bypass: {host}")
            else:
                logger.info(f"🔒 Tunnel: {host}")
            
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
        
        async def forward(reader, writer):
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except:
                pass
            finally:
                try:
                    writer.close()
                except:
                    pass
        
        await asyncio.gather(
            forward(client_reader, remote_writer),
            forward(remote_reader, client_writer),
            return_exceptions=True
        )


class ShadowsocksHandler(ProtocolHandler):
    
    
    def __init__(self, chaos_engine, dns_resolver, bypass_manager, password: str = ""):
        super().__init__(chaos_engine, dns_resolver, bypass_manager)
        self.password = password or "default_password"
    
    async def detect(self, first_bytes: bytes) -> bool:
        
        try:
            if len(first_bytes) < 10:
                return False
            return False
        except:
            return False
    
    async def handle(self, reader, writer, first_bytes: bytes):
        
        logger.warning("Shadowsocks not fully implemented yet")
        writer.close()


class WebSocketHandler(ProtocolHandler):
    
    
    async def detect(self, first_bytes: bytes) -> bool:
        
        try:
            request = first_bytes.decode('utf-8', errors='ignore')
            return ('Upgrade: websocket' in request or
                    'upgrade: websocket' in request)
        except:
            return False
    
    async def handle(self, reader, writer, first_bytes: bytes):
        
        logger.warning("WebSocket not fully implemented yet")
        writer.close()


def create_handlers(chaos_engine, dns_resolver, bypass_manager):
    
    return [
        HTTPHandler(chaos_engine, dns_resolver, bypass_manager),
        SOCKS5Handler(chaos_engine, dns_resolver, bypass_manager),
        ShadowsocksHandler(chaos_engine, dns_resolver, bypass_manager),
        WebSocketHandler(chaos_engine, dns_resolver, bypass_manager),
    ]
