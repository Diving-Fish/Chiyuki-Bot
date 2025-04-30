from nonebot import get_bot, on_command, on_regex
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.libraries.image import image_to_base64
from src.data_access.plugin_manager import plugin_manager
from src.libraries.fishgame import *
from src.libraries.fishgame_util import *
import re
import time


__plugin_meta = {
    "name": "捕鱼",
    "enable": False,
    "help_text": """以成为捕鱼达人为目标吧！
群里会随机出现鱼，在出现的时候【捕鱼】即可！
鱼3分钟就会离开，请尽快捕获！
可用命令列表：
捕鱼 在鱼出现时进行捕鱼
面板 查看自己的角色面板
背包 [页数] 查看自己的背包列表
使用 <道具编号> 使用道具
单抽/十连 使用每抽10金币的价格进行抽奖
状态 查看池子状态
商店 查看商店
商店购买 <商品编号> 购买商品""",
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return True
    elif not hasattr(event, 'group_id'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])


from nonebot_plugin_apscheduler import scheduler

fish_games = {}

@scheduler.scheduled_job("cron", minute="*/1", jitter=30)
async def try_spawn_fish():
    group_list = await get_bot().get_group_list()
    print(group_list)
    # 如果不在 8 到 24 点则不尝试生成
    if 1 <= time.localtime().tm_hour < 8:
        return
    for obj in group_list:
        group = obj['group_id']
        if not plugin_manager.get_enable(group, __plugin_meta["name"]):
            continue
        if group not in fish_games:
            fish_games[group] = FishGame(group)
        qq_list = await get_bot().get_group_member_list(group_id=group)
        qq_list = [str(qq['user_id']) for qq in qq_list]
        game: FishGame = fish_games[group]
        game.update_average_power(qq_list)
        print(f'{group} 尝试刷鱼')
        if game.current_fish is not None:
            leave = game.count_down()
            if leave:
                await get_bot().send_msg(message_type="group", group_id=group, message=f"鱼离开了...")
        else:       
            fish = game.spawn_fish()
            if fish is not None:
                if fish['rarity'] == 'UR':
                    await get_bot().send_msg(message_type="group", group_id=group, message=f"{fish['name']}【{fish['rarity']}】 █████！\n使用【████】指███████获████！")
                else:
                    await get_bot().send_msg(message_type="group", group_id=group, message=f"{fish['name']}【{fish['rarity']}】 出现了！\n使用【捕鱼】指令进行捕获吧！")


panel = on_command('面板', rule=__group_checker)

@panel.handle()
async def _(event: Event):
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    # game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    player.refresh_buff()
    info = await get_bot().get_group_member_info(group_id=group, user_id=event.user_id)
    player.data['name'] = info['card'] if (info['card'] != '' and info['card'] is not None) else info['nickname']
    avatar = await get_qq_avatar(event.user_id)
    character_panel = create_character_panel(player, avatar)
    await panel.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment("image", {
            "file": f"base64://{str(image_to_base64(character_panel), encoding='utf-8')}"
        })
    ]))

bag = on_command('背包', rule=__group_checker)

@bag.handle()
async def _(event: Event, message: Message = CommandArg()):
    player = FishPlayer(str(event.user_id))
    player.sort_bag()
    page = 1
    if message:
        page = int(str(message))
    bag_panel = create_inventory_panel(player.bag[(page - 1) * 10:page * 10], page, (len(player.bag) - 1) // 10 + 1)
    await bag.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment("image", {
            "file": f"base64://{str(image_to_base64(bag_panel), encoding='utf-8')}"
        })
    ]))

catch = on_command('捕鱼', aliases={'捕捉', '捕获'}, rule=__group_checker)

@catch.handle()
async def _(event: Event, message: Message = EventMessage()):
    if str(message) != '捕鱼':
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.catch_fish(player)
    await catch.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(res['message'])
    ]))

draw = on_command('单抽', aliases={'十连'}, rule=__group_checker)

@draw.handle()
async def _(event: Event, message: Message = EventMessage()):
    msg = str(message).strip()
    if msg == '单抽':
        ten_time = False
    elif msg == '十连':
        ten_time = True
    else:
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group) 
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.gacha(player, ten_time)
    if res['code'] == 0:
        gacha_panel = create_gacha_panel(res['message'])
        await draw.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(gacha_panel), encoding='utf-8')}"
            })
        ]))
    else:
        await draw.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(res['message'])
        ]))

shop = on_command('商店', rule=__group_checker)

@shop.handle()
async def _(event: Event, message: Message = EventMessage()):
    msg = str(message).strip()
    if msg != '商店':
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group) 
    game: FishGame = fish_games[group]
    shop_panel = create_shop_panel(game.get_shop())
    await draw.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment("image", {
            "file": f"base64://{str(image_to_base64(shop_panel), encoding='utf-8')}"
        })
    ]))

buy = on_command('商店购买', rule=__group_checker)

@buy.handle()
async def _(event: Event, message: Message = CommandArg()):
    try:
        id = int(str(message).strip())
        group = event.group_id
        if group not in fish_games:
            fish_games[group] = FishGame(group) 
        game: FishGame = fish_games[group]
        player = FishPlayer(str(event.user_id))
        res = game.shop_buy(player, id)
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(res['message'])
        ]))
    except Exception as e:
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text('未找到该商品')
        ]))
        raise e

use = on_command('使用', rule=__group_checker)

@use.handle()
async def _(event: Event, message: Message = CommandArg()):
    try:
        id = int(str(message).strip())
        group = event.group_id
        if group not in fish_games:
            fish_games[group] = FishGame(group) 
        game: FishGame = fish_games[group]
        player = FishPlayer(str(event.user_id))
        res = game.use_item(player, id-1)
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(res['message'])
        ]))
    except Exception as e:
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text('未找到该道具')
        ]))
        raise e

status = on_command('状态', rule=__group_checker)

@status.handle()
async def _(event: Event):
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    player.refresh_buff()
    s = ""
    for buff in player.buff:
        if buff.get('power', 0) > 0:
            s += f"渔力+{buff['power']}，"
        elif buff.get('fishing_bonus', 0) > 0:
            s += f"渔获+{buff['fishing_bonus']*100}%，"
        if buff.get('time', None) is not None:
            s += f"剩余{buff['time']}次\n"
        elif buff.get('expire', None) is not None:
            s += f"剩余{int(buff['expire'] - time.time())}秒\n"
    res = game.get_status()['message'] + '\n当前刷新鱼概率：\n'
    simulate = game.simulate_spawn_fish()
    await status.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(s + res + simulate)
    ]))