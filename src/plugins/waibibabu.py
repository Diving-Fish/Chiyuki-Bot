from nonebot import on_command, on_message, on_notice
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot


encode_list = ['歪', '比', '巴', '卜']
decode_map = {'歪': 0, '比': 1, '巴': 2, '卜': 3}


def byte2str(b):
    bit01 = b & 0x3
    b >>= 2
    bit23 = b & 0x3
    b >>= 2
    bit45 = b & 0x3
    b >>= 2
    bit67 = b & 0x3
    return f'{encode_list[bit67]}{encode_list[bit45]}{encode_list[bit23]}{encode_list[bit01]}'


def str2byte(s):
    return (decode_map[s[0]] << 6) + (decode_map[s[1]] << 4) + (decode_map[s[2]] << 2) + decode_map[s[3]]


def encode(s: str):
    rets = ''
    for b in bytes(s, encoding='utf-8'):
        rets += byte2str(b)
    return rets


def decode(s: str):
    blist = []
    try:
        for i in range(0, len(s), 4):
            blist.append(str2byte(s[i:i+4]))
        return str(bytes(blist), encoding='utf-8')
    except Exception:
        return '解析出错'


wb = on_command('歪比')


@wb.handle()
async def _(bot: Bot, event: Event, state: dict):
    await wb.send(encode(str(event.get_message())))

bb = on_command('巴卜')


@bb.handle()
async def _(bot: Bot, event: Event, state: dict):
    await bb.send(decode(str(event.get_message())))


