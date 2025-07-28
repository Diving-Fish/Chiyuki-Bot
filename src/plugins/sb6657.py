from nonebot import on_regex, on_notice, get_driver
from nonebot.params import CommandArg, EventMessage
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, Event, Bot, MessageSegment
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from src.libraries.image import *
from src.libraries.pokemon_img import get_image
from src.data_access.plugin_manager import plugin_manager
from src.data_access.redis import redis_global
import os
import aiohttp
import re
import random
import json

__plugin_meta = {
    "name": "sb6657",
    "enable": False,
    "help_text": "",
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return False
    elif not hasattr(event, 'group_id'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])

sb6657 = on_regex(r'^(6657)(.*)$')

@sb6657.handle()
async def _(event: Event, message: Message = EventMessage()):
    search_val = re.match(r'^(6657)(.*)$', str(message)).groups()[1].strip()
    key = 'sb6657_' + search_val
    if search_val:
        cached_data = redis_global.get(key)
        if cached_data:
            datas = json.loads(cached_data)
        else:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://hguofichp.cn:10086/machine/Query', json={'barrage': search_val}) as response:
                    if response.status == 200:
                        result = await response.json()
                        datas = result['data']
                        if len(datas) > 0:
                            redis_global.set(key, json.dumps(datas), ex=3600)
                        else:
                            async with session.get('https://hguofichp.cn:10086/machine/getRandOne') as response:
                                if response.status == 200:
                                    result = await response.json()
                                    barrage = result['data']['barrage']
                                    await sb6657.finish(barrage)
        if datas:
            random_data = random.choice(datas)
            await sb6657.finish(random_data['barrage'])
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://hguofichp.cn:10086/machine/getRandOne') as response:
                if response.status == 200:
                    result = await response.json()
                    barrage = result['data']['barrage']
                    await sb6657.finish(barrage)
    
