from nonebot import get_bot, on_command, on_regex, get_driver
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.libraries.image import image_to_base64
from src.data_access.plugin_manager import plugin_manager
from src.libraries.fishgame.fishgame import *
from src.libraries.fishgame.fishgame_util import *
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
单抽/十连/百连 使用金币进行抽奖（单抽10金币，十连100金币，百连1000金币）
状态 查看池子状态
商店 查看商店
商店购买 <商品编号> 购买商品
合成 查看合成工坊
合成 <物品编号> 合成指定物品
赠送 <QQ号> <物品编号> 赠送物品给其他玩家（24小时冷却，仅限部分物品）""",
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
    # print(group_list)
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
        # print(f'{group} 尝试刷鱼')
        if game.current_fish is not None:
            leave = game.count_down()
            if leave:
                await get_bot().send_msg(message_type="group", group_id=group, message=f"鱼离开了..." if not game.is_fever else '鱼群散去了！')
        if game.current_fish is None:     
            fish: Fish = game.spawn_fish()
            if fish is not None:
                if fish.rarity == 'UR':
                    await get_bot().send_msg(message_type="group", group_id=group, message=f"{fish.name}【{fish.rarity}】 █████！\n使用【████】指███████获████！")
                else:
                    await get_bot().send_msg(message_type="group", group_id=group, message=f"{fish.name}【{fish.rarity}】 出现了！\n使用【捕鱼】指令进行捕获吧！")


@scheduler.scheduled_job("cron", hour=19, minute=30)
async def test_if_group_come():
    group_list = await get_bot().get_group_list()
    for obj in group_list:
        group = obj['group_id']
        if not plugin_manager.get_enable(group, __plugin_meta["name"]):
            continue
        if group not in fish_games:
            fish_games[group] = FishGame(group)
        fish_game: FishGame = fish_games[group]
        fish_game.refresh_buff()
        rate = fish_game.data['feed_time'] / 5
        if random.random() < rate:
            fish_game.trigger_fever()
            minute = (fish_game.data['fever_expire'] - time.time()) // 60
            await get_bot().send_msg(message_type="group", group_id=group, message=f"大量的鱼群聚集了起来！\n接下来{minute}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n但与此同时，你的等级和渔具的效果似乎受到了削弱……")


panel = on_command('面板', rule=__group_checker)

@panel.handle()
async def _(event: Event):
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    player.refresh_buff()
    info = await get_bot().get_group_member_info(group_id=group, user_id=event.user_id)
    player.data['name'] = info['card'] if (info['card'] != '' and info['card'] is not None) else info['nickname']
    avatar = await get_qq_avatar(event.user_id)
    character_panel = create_character_panel(player, avatar, game)
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
    # player.sort_bag()
    page = 1
    if message:
        page = int(str(message))
    bag_items = player.bag.items
    bag_items.sort(key=lambda x: x['item'].id)
    bag_panel = create_inventory_panel(bag_items[(page - 1) * 10:page * 10], page, (len(bag_items) - 1) // 10 + 1, player.equipment.ids)
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

draw = on_command('单抽', aliases={'十连', '百连'}, rule=__group_checker)

@draw.handle()
async def _(event: Event, message: Message = EventMessage()):
    msg = str(message).strip()
    if msg == '单抽':
        ten_time = False
        hundred_time = False
    elif msg == '十连':
        ten_time = True
        hundred_time = False
    elif msg == '百连':
        ten_time = False
        hundred_time = True
    else:
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group) 
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.gacha(player, ten_time, hundred_time)
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

use = on_command('使用', aliases={'强制使用'}, rule=__group_checker)

@use.handle()
async def _(event: Event, message: Message = EventMessage()):
    try:
        args = str(message).strip().split('使用')
        force = args[0].strip() == '强制'
        id = int(args[1].strip())
        group = event.group_id
        if group not in fish_games:
            fish_games[group] = FishGame(group) 
        game: FishGame = fish_games[group]
        player = FishPlayer(str(event.user_id))
        res = game.use_item(player, id, force)
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
    qq_list = await get_bot().get_group_member_list(group_id=group)
    qq_list = [str(qq['user_id']) for qq in qq_list]
    game: FishGame = fish_games[group]
    game.update_average_power(qq_list)
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

refresh_counts = on_command('饿鱼')

@refresh_counts.handle()
async def _(event: Event):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    game.data['feed_time'] = 0
    game.save()
    await refresh_counts.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text("已重置投放食料的计数")
        ]))
    return

force_spawn = on_command('刷鱼')

@force_spawn.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    args = str(message).split(' ')
    group = int(args[0])
    fish_id = str(args[1])
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    fish: Fish = game.force_spawn_fish(fish_id)
    await get_bot().send_msg(message_type="group", group_id=group, message=f"{fish.name}【{fish.rarity}】 出现了！\n使用【捕鱼】指令进行捕获吧！")

force_fever = on_command('强制fever')
@force_fever.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    group = int(str(message).strip())
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    fish: Fish = game.trigger_fever()
    minute = (game.data['fever_expire'] - time.time()) // 60
    await get_bot().send_msg(message_type="group", group_id=group, message=f"大量的鱼群聚集了起来！\n接下来{minute}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n但与此同时，你的等级和渔具的效果似乎受到了削弱……")


force_dex = on_command('开图鉴')
@force_dex.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    group = int(str(message).strip())
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    game.unlock_all()
    await get_bot().send_msg(message_type="group", group_id=group, message=f"已开所有图鉴")


force_item = on_command('给道具')
@force_item.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split(' ')
    if len(args) != 2:
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给道具 <QQ号> <物品编号>")
        ]))
        return
    try:
        qq = args[0]
        item_id = int(args[1])
        player = FishPlayer(qq)
        item = FishItem.get(item_id)
        if item is None:
            await force_item.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("未找到该物品")
            ]))
            return
        player.bag.add_item(item_id, 1)
        player.save()
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(f"已给予{qq} {item.name} x1")
        ]))
    except Exception as e:
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给道具 <QQ号> <物品编号>")
        ]))
        raise e
    return

craft = on_command('合成', rule=__group_checker)

@craft.handle()
async def _(event: Event, message: Message = CommandArg()):
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    
    args = str(message).strip()
    
    if args == '' or args == '合成':
        # 显示合成面板
        craftable_items = game.get_craftable_items()
        if not craftable_items:
            await craft.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("暂无可合成的物品")
            ]))
            return
        
        craft_panel = create_craft_panel(craftable_items, player.bag, player.score)
        await craft.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(craft_panel), encoding='utf-8')}"
            })
        ]))
    else:
        # 尝试合成指定物品
        try:
            item_id = int(args)
            res = game.craft_item(player, item_id)
            await craft.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text(res['message'])
            ]))
        except ValueError:
            await craft.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("请输入正确的物品编号")
            ]))


gift = on_command('赠送', rule=__group_checker)

@gift.handle()
async def _(event: Event, message: Message = CommandArg()):
    if not hasattr(event, 'group_id'):
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    
    args = str(message).strip().split()

    if len(args) != 2:
        await gift.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("使用格式：赠送 <QQ号> <物品编号>")
        ]))
        return
    
    try:
        receiver_qq = args[0]
        item_id = int(args[1])
        
        # 验证QQ号格式（简单检查是否为数字）
        if not receiver_qq.isdigit():
            await gift.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("请输入正确的QQ号")
            ]))
            return
        
        # 不能赠送给自己
        if receiver_qq == str(event.user_id):
            await gift.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("不能赠送给自己")
            ]))
            return
        
        res = game.gift_item(player, receiver_qq, item_id)
        await gift.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(res['message'])
        ]))
        
    except Exception as e:
        await gift.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数格式错误，使用格式：赠送 <QQ号> <物品编号>")
        ]))
        raise e