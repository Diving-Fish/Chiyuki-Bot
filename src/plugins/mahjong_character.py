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

__plugin_meta = {
    "name": "麻将字符",
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


mc_tbl = {
    'z': '🀀🀁🀂🀃🀆🀅🀄',
    'm': '🀇🀈🀉🀊🀋🀌🀍🀎🀏',
    's': '🀐🀑🀒🀓🀔🀕🀖🀗🀘',
    'p': '🀙🀚🀛🀜🀝🀞🀟🀠🀡'
}

mahjong_char = on_command('麻将字符', rule=__group_checker)


@mahjong_char.handle()
async def _(event: Event, message: Message = CommandArg()):
    argv = str(message).split(' ')
    res = [''] * len(argv)
    s = []
    try:
        for i, arg in enumerate(argv):
            for c in arg:
                if c in '0123456789':
                    s.append(int(c))
                elif c in 'mspz':
                    res[i] += ''.join([mc_tbl[c][v-1] for v in s])
                    s = []
    except Exception:
        await mahjong_char.send('请检查输入')
    await mahjong_char.send(' '.join(res))