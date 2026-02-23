import asyncio
import json
import logging
import socket
import ssl
import struct
from typing import Optional

logger = logging.getLogger('CTE.DNS')

class DNSResolver:

    def __init__(self, config_file: str = 'dns_servers.json', mode: str = 'doh',
                 cache_ttl: int = 300, cache_max_size: int = 1000):
        self.mode = mode.lower()
        self.doh_servers = []
        self.dot_servers = []
        self.cache = {}
        self.cache_ttl = cache_ttl
        self.cache_max_size = cache_max_size
        self.cache_hits = 0
        self.cache_misses = 0

        self._load_servers(config_file)

        if not self.doh_servers and not self.dot_servers:
            logger.warning("No DNS servers loaded, using defaults")
            self._set_default_servers()

        logger.info(
            f"Loaded DNS servers: "
            f"{len(self.doh_servers)} DoH, {len(self.dot_servers)} DoT "
            f"(mode: {self.mode})"
        )

    def _load_servers(self, config_file: str):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.doh_servers = config.get('doh_servers', [])
                self.dot_servers = config.get('dot_servers', [])
                logger.info(
                    f"Loaded {len(self.doh_servers)} DoH + "
                    f"{len(self.dot_servers)} DoT servers from {config_file}"
                )
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def _set_default_servers(self):
        self.doh_servers = [
            {
                "name": "Cloudflare",
                "url": "https://1.1.1.1/dns-query",
                "ip": "1.1.1.1"
            },
            {
                "name": "Google",
                "url": "https://8.8.8.8/dns-query",
                "ip": "8.8.8.8"
            }
        ]
        self.dot_servers = [
            {
                "name": "Cloudflare",
                "host": "1.1.1.1",
                "port": 853,
                "hostname": "one.one.one.one"
            },
            {
                "name": "Google",
                "host": "8.8.8.8",
                "port": 853,
                "hostname": "dns.google"
            }
        ]

    async def resolve(self, hostname: str) -> Optional[str]:
        if hostname in self.cache:
            ip, timestamp = self.cache[hostname]
            if asyncio.get_running_loop().time() - timestamp < self.cache_ttl:
                self.cache_hits += 1
                logger.debug(f"Cache hit: {hostname} -> {ip}")
                return ip
            else:
                del self.cache[hostname]

        self.cache_misses += 1

        if self.mode == 'dot':
            ip = await self._dot_query(hostname)
        else:
            ip = await self._doh_query(hostname)

        if ip:
            if len(self.cache) >= self.cache_max_size:
                oldest = min(self.cache.items(), key=lambda x: x[1][1])
                del self.cache[oldest[0]]

            self.cache[hostname] = (ip, asyncio.get_running_loop().time())
            logger.info(f"Resolved {hostname} -> {ip} ({self.mode.upper()})")
            return ip

        logger.warning(f"Encrypted DNS failed for {hostname}, trying system DNS")
        return await self._system_resolve(hostname)

    async def _doh_query(self, hostname: str) -> Optional[str]:
        for server in self.doh_servers:
            try:
                ip = await self._query_doh_server(server, hostname)
                if ip:
                    return ip
            except Exception as e:
                logger.debug(f"DoH query failed for {server['name']}: {e}")
                continue

        return None

    async def _query_doh_server(self, server: dict, hostname: str) -> Optional[str]:
        url = server['url']

        if url.startswith('https://'):
            url = url[8:]

        parts = url.split('/', 1)
        host = parts[0]
        path = '/' + parts[1] if len(parts) > 1 else '/dns-query'

        query_url = f"{path}?name={hostname}&type=A"

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        server_ip = server.get('ip', host)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    server_ip, 443,
                    ssl=ssl_context,
                    server_hostname=host
                ),
                timeout=5.0
            )

            request = (
                f"GET {query_url} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Accept: application/dns-json\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )

            writer.write(request.encode())
            await writer.drain()

            response = b""
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                if not chunk:
                    break
                response += chunk

            writer.close()
            await writer.wait_closed()

            response_str = response.decode('utf-8', errors='ignore')

            parts = response_str.split('\r\n\r\n', 1)
            if len(parts) < 2:
                return None

            body = parts[1]

            data = json.loads(body)

            if 'Answer' in data:
                for answer in data['Answer']:
                    if answer.get('type') == 1:
                        ip = answer.get('data')
                        if ip:
                            logger.debug(f"DoH: {hostname} -> {ip} (via {server['name']})")
                            return ip

            return None

        except asyncio.TimeoutError:
            logger.debug(f"DoH timeout: {server['name']}")
            return None
        except Exception as e:
            logger.debug(f"DoH error: {server['name']}: {e}")
            return None

    async def _dot_query(self, hostname: str) -> Optional[str]:
        for server in self.dot_servers:
            try:
                ip = await self._query_dot_server(server, hostname)
                if ip:
                    return ip
            except Exception as e:
                logger.debug(f"DoT query failed for {server['name']}: {e}")
                continue

        return None

    async def _query_dot_server(self, server: dict, hostname: str) -> Optional[str]:
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    server['host'],
                    server['port'],
                    ssl=ssl_context,
                    server_hostname=server.get('hostname', server['host'])
                ),
                timeout=5.0
            )

            query = self._build_dns_query(hostname)

            query_length = struct.pack('!H', len(query))
            writer.write(query_length + query)
            await writer.drain()

            length_data = await asyncio.wait_for(reader.readexactly(2), timeout=5.0)
            response_length = struct.unpack('!H', length_data)[0]

            response = await asyncio.wait_for(
                reader.readexactly(response_length),
                timeout=5.0
            )

            writer.close()
            await writer.wait_closed()

            ip = self._parse_dns_response(response)
            if ip:
                logger.debug(f"DoT: {hostname} -> {ip} (via {server['name']})")
                return ip

            return None

        except asyncio.TimeoutError:
            logger.debug(f"DoT timeout: {server['name']}")
            return None
        except Exception as e:
            logger.debug(f"DoT error: {server['name']}: {e}")
            return None

    def _build_dns_query(self, hostname: str) -> bytes:
        import os
        query_id = os.urandom(2)

        flags = b'\x01\x00'

        counts = b'\x00\x01\x00\x00\x00\x00\x00\x00'

        question = b''
        for part in hostname.split('.'):
            question += bytes([len(part)]) + part.encode('ascii')
        question += b'\x00'

        question += b'\x00\x01\x00\x01'

        return query_id + flags + counts + question

    def _parse_dns_response(self, response: bytes) -> Optional[str]:
        try:
            offset = 12

            while offset < len(response) and response[offset] != 0:
                length = response[offset]
                offset += length + 1
            offset += 5

            while offset < len(response):
                if response[offset] & 0xC0 == 0xC0:
                    offset += 2
                else:
                    while offset < len(response) and response[offset] != 0:
                        offset += response[offset] + 1
                    offset += 1

                if offset + 10 > len(response):
                    break

                record_type = struct.unpack('!H', response[offset:offset+2])[0]
                offset += 2

                offset += 2

                offset += 4

                data_length = struct.unpack('!H', response[offset:offset+2])[0]
                offset += 2

                if record_type == 1 and data_length == 4:
                    ip = '.'.join(str(b) for b in response[offset:offset+4])
                    return ip

                offset += data_length

            return None

        except Exception as e:
            logger.debug(f"Error parsing DNS response: {e}")
            return None

    async def _system_resolve(self, hostname: str) -> Optional[str]:
        try:
            loop = asyncio.get_running_loop()
            result = await loop.getaddrinfo(
                hostname, None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM
            )

            if result:
                ip = result[0][4][0]
                logger.debug(f"System DNS: {hostname} -> {ip}")
                return ip

            return None
        except Exception as e:
            logger.error(f"System DNS failed for {hostname}: {e}")
            return None

    def get_cache_stats(self):
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            'cache_size': len(self.cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%"
        }