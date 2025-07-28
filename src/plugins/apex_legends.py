from nonebot import on_command, on_regex, get_driver, get_bot
from nonebot.log import logger
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.data_access.plugin_manager import plugin_manager
from src.data_access.redis import redis_global
from src.libraries.tool import hash
from src.libraries.image import *
from src.libraries.apexlegends_api import ApexLegendsAPI, set_apex_token
from collections import defaultdict
import asyncio
import re
import time
import json

set_apex_token(get_driver().config.apexlegendsstatus_token)

__plugin_meta = {
    "name": "APEX",
    "enable": False,
    "help_text": ""
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return False
    elif not hasattr(event, 'group_id'):
        return False
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])

def apex_list():
    lst = redis_global.get("apex_list")
    if not lst:
        lst = []
    else:
        lst = json.loads(lst)
    return lst

def get_rank_text(rank):
    div_text = rank['rankDiv']
    if div_text == 0:
        div_text = ""
    else:
        div_text = " " + str(div_text)
    return f"{rank['rankName']}{div_text}"
        

apex_add = on_command('apex添加', rule=__group_checker)

@apex_add.handle()
async def _(event: Event, message: Message = CommandArg()):
    uid = str(message)
    bridge_str, status = await ApexLegendsAPI.player_statistics_uid(uid)
    if status != 200:
        await apex_add.send(f"未直接找到{uid}，正在尝试搜索，可能需要花费数秒到一分钟，请耐心等待……")
        res = await ApexLegendsAPI.search_player(uid)
        if (len(res) > 0):
            s = ''
            i = 0
            for uid2, data in res.items():
                i += 1
                s += f"{data['name']}({uid2}), {data['level']}级，上次使用{data['selected']}，{data['rp']}RP\n"
                if i == 20:
                    break
            await apex_add.send(f"搜索到了以下玩家：\n" + s + "如果需要添加，请重新输入 “apex添加 <uid>”，如还未找到，请尝试直接搜索橘子ID")
        else:
            await apex_add.send(f"未搜索到{uid}")
        return
    bridge = json.loads(bridge_str)
    lst = apex_list()
    gid = getattr(event, "group_id", -1)
    for u, g in lst:
        if int(uid) == u and gid == g:
            await apex_add.send(f"已经添加过了")
            return
    lst.append([int(uid), gid])
    redis_global.set("apex_list", json.dumps(lst))
    redis_global.set(f"apexcache_{uid}", bridge_str)
    await apex_add.send(f"添加成功：{uid}({bridge['global']['name']})")
    return
    

apex_del = on_command('apex删除', rule=__group_checker)

@apex_del.handle()
async def _(event: Event, message: Message = CommandArg()):
    uid = str(message)
    try:
        lst = apex_list()
        gid = getattr(event, "group_id", -1)
        del_count = 0
        for i in range(len(lst) - 1, -1, -1):
            u, g = lst[i]
            if (gid == -1 or gid == g) and int(uid) == u:
                del lst[i]
                del_count += 1
        if del_count == 0:
            await apex_del.send(f"未找到{uid}")
        else:
            await apex_del.send(f"删除成功")
        redis_global.set("apex_list", json.dumps(lst))
    except ValueError:
        await apex_del.send(f"未找到{uid}")
    return

apex_query = on_command('apex查询', rule=__group_checker)

@apex_query.handle()
async def _(event: Event, message: Message = CommandArg()):
    uid_or_name = str(message)
    q_uid = 0
    lst = apex_list()
    for uid, _ in lst:
        if str(uid) == uid_or_name:
            q_uid = uid
            break
        cache = json.loads(redis_global.get(f"apexcache_{uid}"))
        if cache["global"]["name"] == uid_or_name:
            q_uid = cache["global"]["uid"]
    if q_uid == 0:
        await apex_query.send("请先添加监视之后再查询")
        return
    bridge_str, status = await ApexLegendsAPI.player_statistics_uid(q_uid)
    if status != 200:
        await apex_query.send(f"查询暂时错误: {q_uid}")
        return
    redis_global.set(f"apexcache_{q_uid}", bridge_str)
    bridge = json.loads(bridge_str)
    await apex_query.send(f"""{bridge['global']['name']} - {bridge['global']['uid']}
Status: {bridge['realtime']['currentStateAsText']}
{get_rank_text(bridge['global']['rank'])} - {bridge['global']['rank']['rankScore']}RP""")

apex_show_list = on_command('apex列表', rule=__group_checker)

@apex_show_list.handle()
async def _(event: Event, message: Message = CommandArg()):
    lst = apex_list()
    s = "以下是本群添加的apex玩家列表："
    for uid, gid in lst:
        if getattr(event, "group_id", 100) == gid:
            cache = json.loads(redis_global.get(f"apexcache_{uid}"))
            print(f"{cache['global']['name']}({uid})")
            s += f"\n{cache['global']['name']}({uid})"
    await apex_show_list.send(s)

async def apex_auto_update():
    while True:
        try:
            t = time.time_ns()
            group_message_dict = defaultdict(lambda: [])
            uid_to_gid_dict = defaultdict(lambda: [])
            for uid, group_id in apex_list():
                uid_to_gid_dict[uid].append(group_id)
            for uid, gid_list in uid_to_gid_dict.items():
                bridge_str, status = await ApexLegendsAPI.player_statistics_uid(uid)
                if status == 200:
                    cache_bridge = json.loads(redis_global.get(f"apexcache_{uid}"))
                    cache_rank = cache_bridge["global"]["rank"]
                    cache_realtime_data = cache_bridge["realtime"]
                    bridge = json.loads(bridge_str)
                    realtime_data = bridge["realtime"]
                    rank = bridge["global"]["rank"]
                    redis_global.set(f"apexcache_{uid}", bridge_str)
                    if len(gid_list) > 0:
                        # 检查 RP 变动
                        if cache_rank["rankScore"] != rank["rankScore"]:
                            cache_rank_text = get_rank_text(cache_rank)
                            rank_text = get_rank_text(rank)
                            rp_text = rank["rankScore"] - cache_rank["rankScore"]
                            if -200 < rp_text < 1000:
                                if rp_text > 0:
                                    rp_text = f"+{rp_text}"
                                sub_s = f"{bridge['global']['name']} {rp_text}RP ({rank['rankScore']}RP)"
                                if cache_rank_text != rank_text:
                                    sub_s += f", rank changed to {rank_text}"
                                for gid in gid_list:
                                    group_message_dict[gid].append(sub_s)
                        # 检查是否开了一局新游戏
                        if realtime_data["currentState"] == "inMatch":
                            if cache_realtime_data["currentState"] != "inMatch" or \
                                (cache_realtime_data["currentState"] == "inMatch" and cache_realtime_data["currentStateSecsAgo"] > realtime_data["currentStateSecsAgo"]):
                                for gid in gid_list:
                                    group_message_dict[gid].append(f"{bridge['global']['name']} started a game as {realtime_data['selectedLegend']}")
                    await asyncio.sleep(1)
            for gid, messages in group_message_dict.items():
                if plugin_manager.get_enable(gid, __plugin_meta["name"]):
                    await get_bot().send_msg(message_type="group", group_id=gid, message='\n'.join(messages))
            t = int((time.time_ns() - t) / 1e9)
            logger.success("APEX 数据自动更新完成")
            await asyncio.sleep(120 - t)
        except Exception:
            pass

# get_driver().on_startup(lambda: asyncio.get_running_loop().create_task(apex_auto_update()))
