from nonebot import get_driver
import asyncio
from src.routes.app import quart_app
import importlib
import os

# Import all packages in src/routes directory
routes_dir = os.path.join(os.path.dirname(__file__), 'routes')
if os.path.exists(routes_dir):
    for filename in os.listdir(routes_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            importlib.import_module(f'src.routes.{module_name}')

# Import all packages in private/routes directory
private_routes_dir = os.path.join(os.path.dirname(__file__), '..', 'private', 'routes')
if os.path.exists(private_routes_dir):
    for filename in os.listdir(private_routes_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            importlib.import_module(f'private.routes.{module_name}')

quart_task = None

async def startup():
    pass

async def shutdown():
    pass

get_driver().on_startup(startup)
get_driver().on_shutdown(shutdown)
