from nonebot import on_command, on_regex, get_driver, get_bot
from nonebot.log import logger
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.data_access.plugin_manager import plugin_manager
from src.data_access.redis import *
from src.libraries.tool import hash
from src.libraries.image import *
from src.libraries.auto_naga_api import auto_naga, set_naga_secret
from collections import defaultdict
import asyncio
import re
import time
import json

set_naga_secret(get_driver().config.auto_naga_secret)

__plugin_meta = {
    "name": "NAGA",
    "enable": False,
    "help_text": "ms2th <雀魂牌谱链接>\nnaga解析 <雀魂牌谱编号> <小局编号>\nnaga解析 <天凤牌谱链接>\nnp查询"
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if not hasattr(event, 'group_id'):
        return False
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])
    

tbl = ['东 1 局','东 2 局','东 3 局','东 4 局','南 1 局','南 2 局','南 3 局','南 4 局','西 1 局','西 2 局','西 3 局','西 4 局']


ms2th = on_command('ms2th')

@ms2th.handle()
async def _(event: Event, message: Message = CommandArg()):
    await ms2th.send(f"正在转换雀魂牌谱，可能需要一定时间，请耐心等待……")
    data = await auto_naga.convert_majsoul(str(message))
    if data['status'] != 200:
        await ms2th.send(data['message'])
        return
    lst = []
    for i, log in enumerate(data['message']):
        lst.append(f"{i} - {tbl[log['log'][0][0][0]]} {log['log'][0][0][1]} 本场")
    await ms2th.send(f"牌谱编号{data['index']}\n{log['title'][0]} {log['title'][1]}\n{' '.join(log['name'])}\n" + '\n'.join(lst) + f"\n请输入 naga解析 {data['index']} 0 以解析某小局或\nnaga解析 {data['index']} 0-{i} 来解析所有对局")


naga_account = on_command('np查询')

@naga_account.handle()
async def _(event: Event, message: Message = CommandArg()):
    await naga_account.send(f'{event.user_id} 剩余 NP: {await auto_naga.get_np(event.user_id)}')


naga_add = on_command('np充值')

@naga_add.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        await naga.send('您没有权限使用此命令')
        return
    args = str(message).strip().split(' ')
    await auto_naga.add_np(int(args[0]), int(args[1]))
    await naga_add.send(f'{int(args[0])} 充值成功，剩余 NP: {await auto_naga.get_np(int(args[0]))}')


naga = on_command('naga解析')

@naga.handle()
async def _(event: Event, message: Message = CommandArg()):
    lst = str(message).strip().replace('&amp;', '&').split(' ')
    # read arguments
    try:
        if len(lst) == 1:
            custom = False
            np_enough, remaining, required = await auto_naga.cost_np(event.user_id, 50)
            if not np_enough:
                await naga.send(f'您的 NP 不足，剩余 {remaining} NP，需要 {required} NP')
                return
            data = await auto_naga.order(False, lst[0])
            if data['status'] == 400:
                if data['msg'] == 'すでに解析済みの牌譜です':
                    await naga.send('检查到已解析过此天凤牌谱，正在查找缓存中……')
                else:
                    await naga.send('天凤牌谱解析失败，请检查牌谱链接是否正确')
                    return
            else:
                await naga.send(f'解析申请已提交，请稍等数十秒到一分钟，已扣除 {required} NP，剩余 {remaining} NP')
        elif len(lst) == 2:
            custom = True
            index_data = DictRedisData('majsoul_convert_index_map')
            haihu_no = lst[0]
            print(index_data.data)
            if haihu_no not in index_data.data:
                await naga.send('未找到该编号的雀魂牌谱')
                return
            lst2 = []
            for i in lst[1].split(','):
                if '-' in i:
                    lst2.extend(range(int(i.split('-')[0]), int(i.split('-')[1]) + 1))
                else:
                    lst2.append(int(i))
            haihu_data = DictRedisData(index_data.data[haihu_no]).data['message']
            haihus = []
            lst2.sort()
            lst2 = list(set(lst2))
            for i in lst2:
                if i >= len(haihu_data):
                    await naga.send(f'小局编号{i}不存在')
                    return
                haihus.append(haihu_data[i])
            np_enough, remaining, required = await auto_naga.cost_np(event.user_id, len(haihus) * 10)
            if not np_enough:
                await naga.send(f'您的 NP 不足，剩余 {remaining} NP，需要 {required} NP')
                return
            data = await auto_naga.order(True, haihus)
            if data['status'] in [400, 405]:
                await naga.send('自定义牌谱解析失败，请检查牌谱链接是否正确')
                return
            else:
                ts = data["current"]
                await naga.send(f'解析申请已提交，请稍等数十秒到一分钟，已扣除 {required} NP，剩余 {remaining} NP')
        else:
            raise Exception()    
    except Exception as e:
        raise e
        await naga.send('Usage:\nnaga解析 <雀魂牌谱编号> <小局编号>\nnaga解析 <天凤牌谱链接>')
        return

    timeout = 0
    while timeout < 60:
        timeout += 1
        await asyncio.sleep(1)
        code, link, msg = await auto_naga.find_paipu(custom, lst[0] if not custom else ts)
        if code == 0:
            await naga.send(f'解析完成，牌谱链接：{link}')
            return
        elif code == 2:
            await naga.send(msg)
            return

    await naga.send('解析超时，请稍后重试')
    return