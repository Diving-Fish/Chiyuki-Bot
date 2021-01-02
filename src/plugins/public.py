from nonebot import on_command, on_message, on_notice
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot

from src.libraries.tool import hash

import time
from collections import defaultdict


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


@poke.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if event.__getattribute__('group_id') is None:
        event.__delattr__('group_id')
    await poke.send('戳你妈')


repeat = on_message(priority=99)


@repeat.handle()
async def _(bot: Bot, event: Event, state: T_State):
    await repeat.finish(event.get_message())
