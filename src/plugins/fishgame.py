from copy import copy
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
以下命令中，<>表示必要参数，[]表示可选参数
可用命令列表：
捕鱼 在鱼出现时进行捕鱼
面板 查看自己的角色面板
背包 [页数] 查看自己的背包列表
使用 <道具编号> [其他参数] 使用道具
单抽/十连/百连 使用金币进行抽奖（单抽10金币，十连100金币，百连1000金币）
神秘单抽/神秘十连/神秘百连 使用金币进行神秘抽奖（100/1000/10000 金币）
状态 查看池子状态
商店 查看商店
商店购买 <商品编号> 购买商品
合成 查看合成工坊
合成 <道具编号> [数量] 合成指定道具
赠送 <QQ号> <道具编号> 赠送道具给其他玩家（24小时冷却，仅限部分道具）
建筑 显示建筑面板
大锅 显示大锅面板
天赋 显示天赋面板""",
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

# 查看配件详细技能
view_accessory = on_command('查看配件', rule=__group_checker)

@view_accessory.handle()
async def _(event: Event, message: Message = CommandArg()):
    args = str(message).strip().split()
    if len(args) != 1:
        await view_accessory.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("用法：查看配件 <配件编号>")
        ]))
        return
    acc_id = args[0]
    try:
        acc_id_int = int(acc_id)
    except ValueError:
        await view_accessory.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("编号必须是数字")
        ]))
        return
    player = FishPlayer(str(event.user_id))
    item = FishItem.get(str(acc_id_int))
    if not item or item.type != 'accessory':
        await view_accessory.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("未找到该配件")
        ]))
        return
    # 仅允许查看自己拥有的配件
    if player.bag.get_item(acc_id_int) is None:
        await view_accessory.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("你未持有该配件")
        ]))
        return
    from src.libraries.fishgame.data import get_skill
    lines = [f"配件 {item.name} (ID:{item.id})", f"描述: {item.description}"]
    if getattr(item, 'skills', []):
        lines.append("技能:")
        for sk in item.skills:
            sk_obj = get_skill(sk['id'])
            if not sk_obj:
                continue
            lines.append(f" - {sk_obj.name} Lv{sk['level']} | {sk_obj.desc}")
    else:
        lines.append("无技能")
    await view_accessory.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text('\n'.join(lines))
    ]))

# 查看当前玩家所有生效技能（配件 + 未来可能的 rod/tool）
skill_list_cmd = on_command('技能列表', rule=__group_checker)

@skill_list_cmd.handle()
async def _(event: Event):
    player = FishPlayer(str(event.user_id))
    from src.libraries.fishgame.data import get_skill, FishItem
    equipped_items = [player.equipment.rod, player.equipment.tool, player.equipment.accessory]
    all_skills = {}
    for eq in equipped_items:
        if not eq:
            continue
        for sk in getattr(eq, 'skills', []):
            sk_id = sk['id']
            sk_level = sk['level']
            if sk_id in all_skills:
                all_skills[sk_id] = max(all_skills[sk_id], sk_level)
            else:
                all_skills[sk_id] = sk_level
    if not all_skills:
        await skill_list_cmd.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("当前没有任何生效技能")
        ]))
        return
    lines = ["当前生效技能："]
    for sk_id, lv in sorted(all_skills.items()):
        sk_obj = get_skill(sk_id)
        if not sk_obj:
            continue
        lines.append(f" - {sk_obj.name} Lv{lv} | {sk_obj.desc}")
        lines.append(sk_obj.get_detail_for_level(lv))
    await skill_list_cmd.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text('\n'.join(lines))
    ]))

catch = on_command('捕鱼', aliases={'大师球'}, rule=__group_checker)

@catch.handle()
async def _(event: Event, message: Message = EventMessage()):
    if str(message) != '捕鱼' and str(message) != '大师球':
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.catch_fish(player, str(message) == '大师球')
    await catch.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(res['message'])
    ]))

draw = on_command('单抽', aliases={'十连', '百连', '千连'}, rule=__group_checker)

@draw.handle()
async def _(event: Event, message: Message = EventMessage()):
    msg = str(message).strip()
    if msg == '单抽':
        ten_time = False
        hundred_time = False
        thousand_time = False
    elif msg == '十连':
        ten_time = True
        hundred_time = False
        thousand_time = False
    elif msg == '百连':
        ten_time = False
        hundred_time = True
        thousand_time = False
    elif msg == '千连':
        ten_time = False
        hundred_time = False
        thousand_time = True
    else:
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group) 
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.gacha(player, ten_time, hundred_time, thousand_time)
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

# 神秘抽卡
mystery_draw = on_command('神秘单抽', aliases={'神秘十连', '神秘百连', '神秘千连'}, rule=__group_checker)

@mystery_draw.handle()
async def _(event: Event, message: Message = EventMessage()):
    msg = str(message).strip()
    if msg == '神秘单抽':
        ten_time = False
        hundred_time = False
        thousand_time = False
    elif msg == '神秘十连':
        ten_time = True
        hundred_time = False
        thousand_time = False
    elif msg == '神秘百连':
        ten_time = False
        hundred_time = True
        thousand_time = False
    elif msg == '神秘千连':
        ten_time = False
        hundred_time = False
        thousand_time = True
    else:
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    res = game.mystery_gacha(player, ten_time=ten_time, hundred_time=hundred_time, thousand_time=thousand_time)
    if res['code'] == 0:
        # 复用现有的 gacha 面板
        gacha_panel = create_gacha_panel(res['message'])
        await mystery_draw.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(gacha_panel), encoding='utf-8')}"
            })
        ]))
    else:
        await mystery_draw.send(Message([
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
        remain_args = args[1].strip().split(' ')
        id = int(remain_args[0].strip())
        remain_args = remain_args[1:]
        count = 1
        copied_remain_args = copy(remain_args)
        group = event.group_id
        if group not in fish_games:
            fish_games[group] = FishGame(group) 
        game: FishGame = fish_games[group]
        player = FishPlayer(str(event.user_id))
        msg = []
        while count > 0:
            res = game.use_item(player, id, force, copied_remain_args)
            if len(copied_remain_args) == 1 and FishItem.get(id).batch_use:
                count = int(copied_remain_args[0]) - 1
                copied_remain_args = copy(remain_args)
                copied_remain_args[-1] = str(count)
            else:
                count -= 1
            msg.append(res['message'])
            if res['code'] != 0:
                break
        if len(msg) > 10:
            msg = f'...(省略了{len(msg)-10}条)' + '\n' + '\n'.join(msg[-10:])
        else:
            msg = '\n'.join(msg)
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(msg)
        ]))
    except Exception as e:
        await catch.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text('未找到该道具')
        ]))
        raise e

status = on_command('状态', aliases={'池子状态', '完整状态'}, rule=__group_checker)

@status.handle()
async def _(event: Event, msg: Message = EventMessage()):
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
    res = game.get_status()['message']
    simulate = game.simulate_spawn_fish()
    if str(msg) == '状态':
        if s == "":
            await status.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("当前没有任何玩家状态，请尝试命令【池子状态】或【完整状态】")
            ]))
        else:
            await status.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text(s)
            ]))
    elif str(msg) == "池子状态":
        await status.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(res)
        ]))
    elif str(msg) == "完整状态":
        await status.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(s + res + '\n当前刷新鱼概率：\n' + simulate)
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
    if len(args) != 2 and len(args) != 3:
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给道具 <QQ号> <物品编号>")
        ]))
        return
    try:
        qq = args[0]
        item_id = int(args[1])
        try:
            count = int(args[2])
        except Exception:
            count = 1
        player = FishPlayer(qq)
        item = FishItem.get(item_id)
        if item is None:
            await force_item.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text("未找到该物品")
            ]))
            return
        player.bag.add_item(item_id, count)
        player.save()
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(f"已给予"),
            MessageSegment.at(qq),
            MessageSegment.text(f" {item.name} x{count}")
        ]))
    except Exception as e:
        await force_item.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给道具 <QQ号> <物品编号>")
        ]))
        raise e
    return

force_gold = on_command('给金币', aliases={'给钱'})
@force_gold.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split(' ')
    if len(args) != 2:
        await force_gold.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给金币 <QQ号> <数量>")
        ]))
        return
    try:
        qq = args[0]
        amount = int(args[1])
        player = FishPlayer(qq)
        player.data['gold'] += amount
        player.save()
        await force_gold.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(f"已给予"),
            MessageSegment.at(qq),
            MessageSegment.text(f" {amount}金币")
        ]))
    except Exception as e:
        await force_gold.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：给金币 <QQ号> <数量>")
        ]))

force_building = on_command('设置建筑等级', rule=__group_checker)
@force_building.handle()
async def _(event: Event, message: Message = CommandArg()):
    if str(event.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split(' ')
    if len(args) != 2:
        await force_building.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数错误，格式：设置建筑等级 <建筑名> <等级>")
        ]))
        return
    
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]

    building_name = args[0]
    level = int(args[1])
    building: BuildingBase = game.__getattribute__(building_name_map[building_name])
    building.level = level
    game.save()
    await force_building.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(f"已将 {building_name} 的等级设置为 {level}")
    ]))


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
        
        craft_panel = create_craft_panel(craftable_items, player.bag, player)
        await craft.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(craft_panel), encoding='utf-8')}"
            })
        ]))
    else:
        # 尝试合成指定物品
        try:
            args = args.split(' ')
            item_id = int(args[0].strip())
            count = int(args[1].strip()) if len(args) > 1 else 1
            if count > 1 and FishItem.get(item_id).batch_craft:
                msg = []
                for _ in range(count):
                    res = game.craft_item(player, item_id)
                    if res['code'] == 0:
                        msg.append(res['message'])
                    else:
                        msg.append(res['message'])
                        break
                if len(msg) > 10:
                    msg = f'...(省略了{len(msg)-10}条)' + '\n' + '\n'.join(msg[-10:])
                else:
                    msg = '\n'.join(msg)
                await craft.send(Message([
                    MessageSegment.reply(event.message_id),
                    MessageSegment.text(msg.strip())
                ]))
            else:
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
        if res.get('receiver') is not None:
            await gift.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text(res['message']),
                MessageSegment.at(res['receiver'])
            ]))
        else:
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


buildings = on_command('建筑', rule=__group_checker)

@buildings.handle()
async def _(event: Event, message: Message = CommandArg()):
    if not hasattr(event, 'group_id'):
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))
    
    # 如果没有额外参数，显示建筑面板
    if not str(message).strip():
        buildings_panel = create_buildings_panel(game)
        await buildings.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(buildings_panel), encoding='utf-8')}"
            })
        ]))
        return
    
    args = str(message).strip().split(' ')
    if len(args) != 2:
        await buildings.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数格式错误，使用格式：建筑 <建筑名称> <材料编号>")
        ]))
    
    building_name = args[0]
    if args[1] == '升级':
        ret = game.building_level_up(building_name)
        await buildings.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(ret['message'])
        ]))
        return
    try:
        item_id = int(args[1])
    except ValueError:
        await buildings.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("参数格式错误，使用格式：建筑 <建筑名称> <材料编号>")
        ]))
        return

    ret = game.build(player, building_name, item_id)
    await buildings.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(ret['message'])
    ]))

pot = on_command('大锅', rule=__group_checker)

@pot.handle()
async def _(event: Event, message: Message = CommandArg()):
    if not hasattr(event, 'group_id'):
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))

    if game.big_pot.level == 0:
        await pot.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(f'还没有建造大锅哦……')
        ]))
        return

    args = str(message).strip().split(' ')
    if args[0] == '添加':
        item = FishItem.get(args[1])
        if item is None:
            await pot.send(Message([
                MessageSegment.reply(event.message_id),
                MessageSegment.text(f'未找到物品 { args[1] }')
            ]))
            return
        count = 1
        if len(args) == 3:
            try:
                count = int(args[2])
            except ValueError:
                pass
        ret = game.pot_add_item(player, item, count)
        await pot.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(ret['message'])
        ]))
    else:
        ret = game.get_pot_status()
        await pot.send(Message([
            MessageSegment.text(ret),
            MessageSegment.text('\nUsage：大锅 添加 <物品ID> [数量]')
        ]))

# 天赋面板
talent_cmd = on_command('天赋', rule=__group_checker)

@talent_cmd.handle()
async def _(event: Event, message: Message = EventMessage()):
    # 仅群聊或频道环境启用（与其他命令一致）
    if not hasattr(event, 'group_id'):
        return
    if str(message) != '天赋':
        return
    group = event.group_id
    if group not in fish_games:
        fish_games[group] = FishGame(group)
    game: FishGame = fish_games[group]
    player = FishPlayer(str(event.user_id))

    panel_img = create_talent_panel(player, game)
    await talent_cmd.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment("image", {
            "file": f"base64://{str(image_to_base64(panel_img), encoding='utf-8')}"
        })
    ]))