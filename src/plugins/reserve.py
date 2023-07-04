from nonebot import on_command, on_regex, get_driver, get_bot
from nonebot.log import logger
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.data_access.plugin_manager import plugin_manager
from src.data_access.redis import *
from src.libraries.tool import hash
from src.libraries.image import *
from collections import defaultdict
import asyncio
import re
import time
import json

__plugin_meta = {
    "name": "预定",
    "enable": False,
    "help_text": "有没有xx/什么时候xx - 预定某项目\n没有xx/不xx了 - 退出预定某项目\nxx来人 - bot帮你喊人"
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return False
    elif not hasattr(event, 'group_id'):
        return False
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])


reserve_data = defaultdict(lambda: {'id': [], 'date': None})

def add_id_to_dict(data, uid):
    # by ChatGPT
    # 获取当前时间戳的日期
    current_date = time.strftime('%Y-%m-%d', time.localtime())
    if current_date == data.get('date'):
        # 如果当前时间和dict里面记录的时间戳为同一天，则在数组中添加id
        if uid not in data['id']:
            data['id'].append(uid)
    else:
        # 否则清空数组再加入id
        data['id'] = [uid]
        data['date'] = current_date


on_reserve = on_regex(r"^(有没有|什么时候)(.+)$", rule=__group_checker)

@on_reserve.handle()
async def _(event: Event, message: Message = EventMessage()):
    regex = "^(有没有|什么时候)(.+)"
    name = re.match(regex, str(message)).groups()[1].strip()
    data = reserve_data[name + str(event.group_id)]
    add_id_to_dict(data, str(event.user_id))
    await on_reserve.send(f'已预约{name}，现在一共有{len(data["id"])}人')
    

on_cancel = on_regex(r"^(没有(.+)|不(.+)了)$", rule=__group_checker)
@on_cancel.handle()
async def _(event: Event, message: Message = EventMessage()):
    regex = "^(没有(.+)|不(.+)了)"
    lst = re.match(regex, str(message)).groups()
    name = lst[1] if lst[2] is None else lst[2]
    if name + str(event.group_id) in reserve_data:
        data = reserve_data[name + str(event.group_id)]
        if str(event.user_id) not in data['id']:
            await on_cancel.send(f'你又没说要来你叫什么')
        else:
            del data['id'][data['id'].index(str(event.user_id))]
            await on_cancel.send(f'不来以后都别来了')


on_call = on_regex(r"^(.+)来人$", rule=__group_checker)
@on_call.handle()
async def _(event: Event, message: Message = EventMessage()):
    regex = "^(.+)来人"
    name = re.match(regex, str(message)).groups()[0].strip()
    if name + str(event.group_id) in reserve_data:
        data = reserve_data[name + str(event.group_id)]
        if len(data['id']) > 0:
            msgs = []
            for uid in data['id']:
                msgs.append(MessageSegment("at", {
                    "qq": uid
                }))
            await on_call.send(Message(msgs))
        else:
            await on_call.send(f"没人{name}")
    else:
        await on_call.send(f"没人{name}")
    


