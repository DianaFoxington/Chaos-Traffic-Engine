from aiohttp import web

class WebAPI:
    def __init__(self, stats_collector, chaos_engine, dns_resolver, proxy_server):
        self.stats = stats_collector
        self.chaos = chaos_engine
        self.dns = dns_resolver
        self.proxy = proxy_server

    def register_routes(self, app: web.Application):
        app.router.add_get('/api/status', self.get_full_status)
        app.router.add_get('/api/health', self.get_health)

    async def get_full_status(self, request):
        return web.json_response({
            'status': 'running' if self.proxy.running else 'stopped',
            'stats': await self.stats.get_json_summary(),
            'chaos': self.chaos.get_chaos_metrics(),
            'dns': self.dns.get_cache_stats(),
            'pool': {
                'size': len(self.proxy.connection_pool),
                'max': self.proxy.pool_max_size
            }
        })

    async def get_health(self, request):
        return web.json_response({
            'status': 'healthy',
            'running': self.proxy.running
        })