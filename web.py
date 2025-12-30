from aiohttp import web
import time

routes = web.RouteTableDef()

# ✅ Health check endpoint for Docker & Koyeb
@routes.get('/health')
async def health_check(request):
    return web.json_response({
        'status': 'healthy',
        'timestamp': int(time.time())
    })

# Existing routes
@routes.get('/', allow_head=True)
async def root_route_handler(request):
    return web.json_response({
        'status': 'running',
        'message': 'Bot is alive!'
    })

# Add your other routes here (stream, etc.)
# @routes.get('/stream/{file_id}')
# async def stream_handler(request):
#     ...

# Create app
web_app = web.Application()
web_app.add_routes(routes)
