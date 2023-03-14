from nonebot import on_command, on_regex
from nonebot.params import RawCommand
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

__plugin_meta = {
    "name": "阳性报备",
    "enable": False,
    "help_text": ""
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if not hasattr(event, 'group_id'):
        return False
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])


impositive = on_command('我阳了', rule=__group_checker)

@impositive.handle()
async def _(event: Event):
    v = redis_global.get(get_string_hash("covid" + str(event.group_id)))
    if not v:
        v = "[]"
    data = json.loads(v)
    if event.user_id not in data:
        data.append(event.user_id)
    redis_global.set(get_string_hash("covid" + str(event.group_id)), json.dumps(data))
    await impositive.finish("你阳了")


imnotpositive = on_command('我没阳', rule=__group_checker)

@imnotpositive.handle()
async def _(event: Event):
    v = redis_global.get(get_string_hash("covid" + str(event.group_id)))
    if not v:
        v = "[]"
    data = json.loads(v)
    if event.user_id in data:
        del data[data.index(event.user_id)]
    redis_global.set(get_string_hash("covid" + str(event.group_id)), json.dumps(data))
    await impositive.finish("你没阳")


hepositive = on_command('他阳了', rule=__group_checker)

@hepositive.handle()
async def _(event: Event):
    v = redis_global.get(get_string_hash("covid" + str(event.group_id)))
    if not v:
        v = "[]"
    data = json.loads(v)
    for message in event.original_message:
        print(message)
        if message.type == 'at':
            user_id = message.data['qq']
            if int(user_id) not in data:
                data.append(int(user_id))
    redis_global.set(get_string_hash("covid" + str(event.group_id)), json.dumps(data))
    await hepositive.finish("他阳了")


whopositive = on_command('谁阳了', rule=__group_checker)

@whopositive.handle()
async def _(bot: Bot, event: Event):
    s = "现在阳的人有这些："
    v = redis_global.get(get_string_hash("covid" + str(event.group_id)))
    if not v:
        v = "[]"
    data = json.loads(v)
    for uid in data:
        user = await bot.get_group_member_info(group_id=event.group_id, user_id=uid)
        if user:
            s += f"\n{user['card'] if user['card'] != '' else user['nickname']}({uid})"
    await whopositive.finish(s)
