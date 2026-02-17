import time
import logging
from dataclasses import dataclass, field
from typing import Dict
from threading import Lock

logger = logging.getLogger('CTE.Stats')

@dataclass
class ConnectionStats:
    start_time: float
    protocol: str
    remote_host: str = ""
    bytes_sent: int = 0
    bytes_received: int = 0
    is_bypassed: bool = False
    bypass_reason: str = ""

class StatsCollector:
    
    def __init__(self):
        self.lock = Lock()
        
        self.start_time = time.time()
        self.connections_active = 0
        self.connections_total = 0
        self.connections_success = 0
        self.connections_failed = 0
        
        self.bytes_sent_total = 0
        self.bytes_received_total = 0
        
        self.bypassed_total = 0
        self.tunneled_total = 0
        
        self.protocol_counts: Dict[str, int] = {}
        
        self.active_connections: Dict[str, ConnectionStats] = {}
        
        logger.info("✓ Stats collector initialized")
    
    def connection_started(self, conn_id: str, protocol: str, remote_host: str = ""):
        with self.lock:
            self.connections_active += 1
            self.connections_total += 1
            
            self.protocol_counts[protocol] = self.protocol_counts.get(protocol, 0) + 1
            
            self.active_connections[conn_id] = ConnectionStats(
                start_time=time.time(),
                protocol=protocol,
                remote_host=remote_host
            )
            
            logger.debug(f"New connection: {conn_id} [{protocol}] -> {remote_host}")
    
    def connection_ended(self, conn_id: str, success: bool = True):
        with self.lock:
            if conn_id in self.active_connections:
                conn = self.active_connections[conn_id]
                duration = time.time() - conn.start_time
                
                self.connections_active -= 1
                if success:
                    self.connections_success += 1
                else:
                    self.connections_failed += 1
                
                logger.debug(
                    f"Connection closed: {conn_id} "
                    f"[{conn.protocol}] "
                    f"↑{self._format_bytes(conn.bytes_sent)} "
                    f"↓{self._format_bytes(conn.bytes_received)} "
                    f"({duration:.1f}s)"
                )
                
                del self.active_connections[conn_id]
    
    def record_traffic(self, conn_id: str, bytes_sent: int = 0, bytes_received: int = 0):
        with self.lock:
            if conn_id in self.active_connections:
                conn = self.active_connections[conn_id]
                conn.bytes_sent += bytes_sent
                conn.bytes_received += bytes_received
            
            self.bytes_sent_total += bytes_sent
            self.bytes_received_total += bytes_received
    
    def record_bypass(self, conn_id: str, reason: str):
        with self.lock:
            self.bypassed_total += 1
            
            if conn_id in self.active_connections:
                conn = self.active_connections[conn_id]
                conn.is_bypassed = True
                conn.bypass_reason = reason
    
    def record_tunnel(self, conn_id: str):
        with self.lock:
            self.tunneled_total += 1
    
    def get_summary(self) -> dict:
        with self.lock:
            uptime = time.time() - self.start_time
            
            return {
                'uptime_seconds': uptime,
                'uptime_formatted': self._format_uptime(uptime),
                'connections': {
                    'active': self.connections_active,
                    'total': self.connections_total,
                    'success': self.connections_success,
                    'failed': self.connections_failed,
                },
                'traffic': {
                    'sent': self.bytes_sent_total,
                    'sent_formatted': self._format_bytes(self.bytes_sent_total),
                    'received': self.bytes_received_total,
                    'received_formatted': self._format_bytes(self.bytes_received_total),
                    'total': self.bytes_sent_total + self.bytes_received_total,
                    'total_formatted': self._format_bytes(
                        self.bytes_sent_total + self.bytes_received_total
                    ),
                },
                'routing': {
                    'bypassed': self.bypassed_total,
                    'tunneled': self.tunneled_total,
                },
                'protocols': dict(self.protocol_counts),
            }
    
    def print_summary(self):
        stats = self.get_summary()
        
        print("\n" + "=" * 60)
        print("📊 Chaos Traffic Engine Statistics")
        print("=" * 60)
        print(f"⏱️  Uptime: {stats['uptime_formatted']}")
        print()
        print(f"🔌 Connections:")
        print(f"   • active: {stats['connections']['active']}")
        print(f"   • total: {stats['connections']['total']}")
        print(f"   • success: {stats['connections']['success']}")
        print(f"   • success: {stats['connections']['failed']}")
        print()
        print(f"📡 Traffic:")
        print(f"   • sent: {stats['traffic']['sent_formatted']}")
        print(f"   • received: {stats['traffic']['received_formatted']}")
        print(f"   • total: {stats['traffic']['total_formatted']}")
        print()
        print(f"🔀 Routing:")
        print(f"   • bypassed: {stats['routing']['bypassed']}")
        print(f"   • tunneled: {stats['routing']['tunneled']}")
        print()
        if stats['protocols']:
            print(f"🔧 total‌:")
            for proto, count in stats['protocols'].items():
                print(f"   • {proto}: {count}")
        print("=" * 60 + "\n")
    
    @staticmethod
    def _format_bytes(bytes_count: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)

stats = StatsCollector()
