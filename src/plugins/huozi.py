from nonebot import on_command, on_regex
from nonebot.params import RawCommand, CommandArg
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot

from src.data_access.plugin_manager import plugin_manager, get_string_hash
from src.data_access.redis import redis_global
from src.libraries.tool import hash
from src.libraries.maimaidx_music import *
from src.libraries.image import *
from src.libraries.maimai_best_40 import generate
from src.libraries.maimai_best_50 import generate50
import re
import aiohttp

__plugin_meta = {
    "name": "活字印刷",
    "enable": True,
    "help_text": ""
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return False
    elif not hasattr(event, 'group_id'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])


huozi = on_command('活字印刷', rule=__group_checker)


@huozi.handle()
async def _(event: Event, message: Message = CommandArg()):
    msg = str(message)
    if len(msg) > 40:
        await huozi.send("最多活字印刷 40 个字符噢")
        return
    payload = {
        "rawData": msg,
        "inYsddMode": True,
        "norm": True,
        "reverse": False,
        "speedMult": 1.0,
        "pitchMult": 1.0
    }
    async with aiohttp.request("POST", "https://www.diving-fish.com/api/huozi/make", json=payload) as resp:
        if resp.status == 404:
            await huozi.send("生成失败！")
        else:
            obj = await resp.json()
            await huozi.send(Message([
                MessageSegment("record", {
                    "file": f"https://www.diving-fish.com/api/huozi/get/{obj['id']}.mp3"
                })
            ]))