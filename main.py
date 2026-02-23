import asyncio
import signal
import sys
import yaml
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.engine import ChaosEngine
from core.dns import DNSResolver
from core.tls import TLSFragmenter
from server.protocols import create_handlers
from server.proxy import ProxyServer
from server.relay import TrafficRelay
from evasion.fronting import DomainFronter
from monitoring.stats import StatsCollector
from monitoring.limiter import ConnectionLimiter
from utils.logger import setup_logging, get_logger
from utils.bypass import BypassManager
from web.dashboard import WebDashboard
from web.api import WebAPI

logger = None

def load_config(config_file: str = 'config.yaml') -> dict:
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Config file not found: {config_file}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML in config: {e}")
        sys.exit(1)

async def main():
    global logger
    config = load_config('config.yaml')
    log_config = config.get('logging', {})
    setup_logging(
        level=log_config.get('level', 'INFO'),
        log_file=log_config.get('file'),
        console=log_config.get('console', True)
    )
    logger = get_logger('Main')

    logger.info("=" * 60)
    logger.info("🚀 Chaos Traffic Engine")
    logger.info("Anti-Censorship Proxy")
    logger.info("=" * 60)

    stats_collector = None
    proxy_server = None

    try:
        logger.info("Initializing components...")

        chaos_engine = ChaosEngine()
        logger.info("✓ Chaos Engine initialized")

        dns_config = config.get('dns', {})
        dns_resolver = DNSResolver(
            config_file='config/' + dns_config.get('servers_file', 'dns_servers.json'),
            mode=dns_config.get('mode', 'doh'),
            cache_ttl=dns_config.get('cache_ttl', 300),
            cache_max_size=dns_config.get('cache_max_size', 1000)
        )
        
        logger.info("✓ DNS Resolver initialized")

        chaos_config = config.get('chaos', {})
        tls_fragmenter = TLSFragmenter(
            chaos_engine,
            aggressive=chaos_config.get('aggressive', True)
        )
        
        logger.info("✓ TLS Fragmenter initialized")

        evasion_config = config.get('evasion', {})
        domain_fronter = DomainFronter(
            config_file='config/' + evasion_config.get('cdn_domains_file', 'cdn_domains.json'),
            enabled=evasion_config.get('domain_fronting', True)
        )
        
        logger.info("✓ Domain Fronting initialized")

        bypass_config = config.get('bypass', {})
        bypass_manager = BypassManager(
            config_file='config/' + bypass_config.get('iranian_domains_file', 'iranian_domains.json')
        )
        
        logger.info("✓ Bypass Manager initialized")

        stats_collector = StatsCollector()
        logger.info("✓ Stats Collector initialized")

        limits_config = config.get('limits', {})
        limiter = ConnectionLimiter(
            max_connections=limits_config.get('max_connections', 100)
        )
        
        logger.info("✓ Connection Limiter initialized")

        buffers_config = config.get('buffers', {})
        traffic_relay = TrafficRelay(
            chaos_engine,
            tls_fragmenter,
            stats_collector,
            buffers_config
        )
        
        logger.info("✓ Traffic Relay initialized")

        handlers = create_handlers(
            chaos_engine,
            dns_resolver,
            bypass_manager,
            stats_collector,
            tls_fragmenter,
            domain_fronter
        )
        
        logger.info(f"✓ {len(handlers)} Protocol Handlers initialized")

        server_config = config.get('server', {})
        proxy_server = ProxyServer(
            host=server_config.get('host', '0.0.0.0'),
            port=server_config.get('port', 10809),
            handlers=handlers,
            limiter=limiter,
            stats_collector=stats_collector,
            buffers=buffers_config
        )
        
        logger.info("✓ Proxy Server initialized")

        web_config = config.get('web', {})
        web_dashboard = WebDashboard(
            stats_collector=stats_collector,
            chaos_engine=chaos_engine,
            dns_resolver=dns_resolver,
            proxy_server=proxy_server,
            port=web_config.get('port', 8080),
            enabled=web_config.get('enabled', True)
        )
        
        web_api = WebAPI(
            stats_collector=stats_collector,
            chaos_engine=chaos_engine,
            dns_resolver=dns_resolver,
            proxy_server=proxy_server
        )
        
        if web_config.get('enabled', True):
            await web_dashboard.start(web_api=web_api)

        logger.info("=" * 60)
        logger.info("All components initialized successfully!")
        logger.info("=" * 60)

        loop = asyncio.get_running_loop()
        shutdown_called = False

        def signal_handler(sig):
            nonlocal shutdown_called
            if shutdown_called:
                return
            shutdown_called = True
            logger.info(f"\n📊 Received signal {sig}, shutting down...")
            loop.create_task(proxy_server.stop())

        import platform
        if platform.system() != 'Windows':
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        await proxy_server.start()

    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
        if proxy_server:
            await proxy_server.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1
    finally:
        if logger:
            logger.info("=" * 60)
            logger.info("📊 Final Statistics:")
            logger.info("=" * 60)
            if stats_collector:
                await stats_collector.print_summary()
            logger.info("=" * 60)
            logger.info("👋 Chaos Traffic Engine stopped")
            logger.info("=" * 60)
    return 0

if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(0)