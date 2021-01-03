from PIL import Image
from nonebot import on_command, on_message, on_notice, require, get_bots
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot
from nonebot.adapters.cqhttp import Message
from random import randint
import asyncio

from src.libraries.image import image_to_base64, path, draw_text, get_jlpx
from src.libraries.tool import hash

import time
from collections import defaultdict


scheduler = require("nonebot_plugin_apscheduler").scheduler


help_text = """桜千雪です、よろしく。
可用命令如下：
.help 输出此消息
.jrrp 显示今天的人品值
.bind <角色名称> 绑定角色
.r/roll <掷骰表达式> 掷骰
.rc/rollcheck <技能/属性> [值] 技能/属性检定
.sc/sancheck <成功> <失败> 理智检定
.stat/st <技能/属性> <add|sub|set> <值> [触发时间（小时）] 增加/减少/设置属性值，可设定触发时间
.time <pass> [小时] 设置经过时间
.query/q <玩家名/QQ> <技能/属性> 查询某玩家的某属性
.intro/.i <玩家名> 查询此角色的基本信息
.showall/.sa 获取当前玩家的所有信息（将私聊发送）
.unbind 解绑角色
车卡网址：https://www.diving-fish.com/coc_card
要查看舞萌bot的有关帮助，请输入.help mai"""
mai_help_text = """桜千雪です、よろしく。
可用命令如下：
今日舞萌 查看今天的舞萌运势
XXXmaimaiXXX什么 随机一首歌
随个[dx/标准][绿黄红紫白]<难度> 随机一首指定条件的乐曲
[绿黄红紫白]<歌曲编号> 查询乐曲信息或谱面信息
<歌曲别名>是什么歌 查询乐曲别名对应的乐曲
定数查歌 <定数>  查询定数对应的乐曲
定数查歌 <定数下限> <定数上限>"""


help = on_command('help')


@help.handle()
async def _(bot: Bot, event: Event, state: T_State):
    v = str(event.get_message()).strip()
    if v == "":
        await help.finish('''.help coc \t查看跑团相关功能
.help mai \t查看舞萌相关功能''')
    elif v == "mai":
        await help.finish(mai_help_text)
    elif v == "coc":
        await help.finish(help_text)


jrrp = on_command('jrrp')


@jrrp.handle()
async def _(bot: Bot, event: Event, state: dict):
    qq = int(event.get_user_id())
    h = hash(qq)
    rp = h % 100
    await jrrp.finish("【%s】今天的人品值为：%d" % (event.sender.nickname, rp))


async def _group_poke(bot: Bot, event: Event, state: dict) -> bool:
    value = (event.notice_type == "notify" and event.sub_type == "poke" and event.target_id == int(bot.self_id))
    return value


poke = on_notice(rule=_group_poke, priority=10, block=True)
poke_dict = defaultdict(lambda: defaultdict(int))


@poke.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if event.__getattribute__('group_id') is None:
        event.__delattr__('group_id')
    else:
        group_dict = poke_dict[event.__getattribute__('group_id')]
        group_dict[event.sender_id] += 1
    r = randint(1, 14)
    if r == 1:
        img_p = Image.open(path)
        draw_text(img_p, '戳你妈', 0)
        draw_text(img_p, '有尝试过玩Cytus II吗', 400)
        await poke.send(Message([{
            "type": "image",
            "data": {
                "file": f"base64://{str(image_to_base64(img_p), encoding='utf-8')}"
            }
        }]))
    elif r == 2:
        await poke.send(Message('妈你戳'))
    elif r == 3:
        await poke.send(Message([{
            "type": "image",
            "data": {
                "file": get_jlpx('戳', '你妈', '闲着没事干')
            }
        }]))
    elif r == 4:
        await poke.send(Message([{
            "type": "poke",
            "data": {
                "qq": f"{event.sender_id}"
            }
        }]))
    elif r == 5:
        await poke.send(Message('呜呜呜再戳人家要哭哭了啦'))
    elif r <= 7:
        await poke.send(Message([{
            "type": "image",
            "data": {
                "file": f"https://www.diving-fish.com/images/poke/{r - 5}.gif",
            }
        }]))
    elif r <= 12:
        await poke.send(Message([{
            "type": "image",
            "data": {
                "file": f"https://www.diving-fish.com/images/poke/{r - 7}.jpg",
            }
        }]))
    else:
        await poke.send(Message('戳你妈'))


async def send_poke_stat(group_id: int, bot: Bot):
    if group_id not in poke_dict:
        return
    else:
        group_stat = poke_dict[group_id]
        sorted_dict = {k: v for k, v in sorted(group_stat.items(), key=lambda item: item[1], reverse=True)}
        index = 0
        data = []
        for k in sorted_dict:
            data.append((k, sorted_dict[k]))
            index += 1
            if index == 3:
                break
        await bot.send_msg(group_id=group_id, message="接下来公布一下我上次重启以来，本群最闲着没事干玩戳一戳的人")
        await asyncio.sleep(1)
        if len(data) == 3:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第三名，"}},
                {"type": "at", "data": {"qq": f"{data[2][0]}"}},
                {"type": "text", "data": {"text": f"，一共戳了我{data[2][1]}次，这就算了"}},
            ]))
            await asyncio.sleep(1)
        if len(data) >= 2:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第二名，"}},
                {"type": "at", "data": {"qq": f"{data[1][0]}"}},
                {"type": "text", "data": {"text": f"，一共戳了我{data[1][1]}次，也太几把闲得慌了，建议多戳戳自己肚皮"}},
            ]))
            await asyncio.sleep(1)
        await bot.send_msg(group_id=group_id, message=Message([
            {"type": "text", "data": {"text": "最JB离谱的第一名，"}},
            {"type": "at", "data": {"qq": f"{data[0][0]}"}},
            {"type": "text", "data": {"text": f"，一共戳了我{data[0][1]}次，就那么喜欢听我骂你吗"}},
        ]))


poke_stat = on_command("本群戳一戳情况")


@poke_stat.handle()
async def _(bot: Bot, event: Event, state: T_State):
    group_id = event.group_id
    await send_poke_stat(group_id, bot)


@scheduler.scheduled_job("cron", hour="*/12", id="time_for_poke_stat")
async def run_every_4_hour():
    for k in get_bots():
        bot = get_bots()[k]
    for group_id in poke_dict:
        await send_poke_stat(group_id, bot)


scheduler.add_job(run_every_4_hour)


repeat = on_message(priority=99)


@repeat.handle()
async def _(bot: Bot, event: Event, state: T_State):
    r = randint(1, 100)
    if r <= 2:
        await repeat.finish(event.get_message())
