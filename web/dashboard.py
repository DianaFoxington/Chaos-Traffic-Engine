import asyncio
import logging
from pathlib import Path
from aiohttp import web

logger = logging.getLogger('CTE.Web')

STATIC_DIR = Path(__file__).parent / 'static'

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response

class WebDashboard:

    def __init__(self, stats_collector, chaos_engine, dns_resolver, proxy_server=None, port=8080, enabled=True):
        self.stats = stats_collector
        self.chaos = chaos_engine
        self.dns = dns_resolver
        self.proxy = proxy_server
        self.port = port
        self.enabled = enabled
        self.app = None
        self.runner = None

        if not enabled:
            logger.info("Web dashboard disabled")

    async def start(self, web_api=None):
        if not self.enabled:
            return

        self.app = web.Application(middlewares=[cors_middleware])
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/stats', self.handle_stats)
        self.app.router.add_get('/api/chaos', self.handle_chaos)
        self.app.router.add_get('/api/dns', self.handle_dns)
        self.app.router.add_static('/static', STATIC_DIR)

        if web_api is not None:
            web_api.register_routes(self.app)
            logger.info("✓ WebAPI routes registered (/api/status, /api/health)")

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()

        logger.info(f"🌐 Web dashboard started: http://0.0.0.0:{self.port}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            logger.info("Web dashboard stopped")

    async def handle_index(self, request):
        index_file = STATIC_DIR / 'index.html'
        try:
            return web.Response(text=index_file.read_text(), content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Dashboard not found", status=404)

    async def handle_stats(self, request):
        return web.json_response(await self.stats.get_json_summary())

    async def handle_chaos(self, request):
        return web.json_response(self.chaos.get_chaos_metrics())

    async def handle_dns(self, request):
        return web.json_response(self.dns.get_cache_stats())