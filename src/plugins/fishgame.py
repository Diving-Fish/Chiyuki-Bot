from copy import copy
from io import BytesIO
from typing import Any

from nonebot import get_bot, on_command, get_driver
from nonebot.rule import Rule
from nonebot.params import CommandArg, EventMessage, Depends
from nonebot.adapters import Bot, Event, Message, MessageSegment
from nonebot_plugin_alconna import UniMessage

from src.data_access.plugin_manager import plugin_manager
from src.data_access.open_helper import RealContext, get_real_context
from src.data_access.redis import DictRedisData
from src.libraries.fishgame.fishgame import *
from src.libraries.fishgame.fishgame_util import *
from src.libraries.fishgame.runtime import fish_games
from src.routes.fishgame import has_online_clients, online_clients_group_list, push_web_event
import time
from nonebot.log import logger


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
绑定捕鱼游戏 <群号> 将本群作为副群聊绑定到已有的捕鱼游戏（管理员）
解绑捕鱼游戏 解除当前群聊的副群绑定
天赋 显示天赋面板""",
}

plugin_manager.register_plugin(__plugin_meta)


class FishGameBindingStore(DictRedisData):
    """Persist bidirectional mappings between primary groups and their sub-chat mirrors."""

    def __init__(self):
        super().__init__(
            "fishgame_group_bindings",
            default={"group_to_primary": {}, "primary_to_subs": {}},
        )

    @staticmethod
    def _normalize(value: int | str) -> str:
        try:
            return str(int(str(value).strip()))
        except (TypeError, ValueError):
            return str(value)

    def get_primary_group(self, group_id: int | str) -> int:
        key = self._normalize(group_id)
        primary = self.data.setdefault("group_to_primary", {}).get(key)
        target = primary or key
        try:
            return int(target)
        except (TypeError, ValueError):
            try:
                return int(key)
            except (TypeError, ValueError):
                if isinstance(key, str) and key.startswith("0x"):
                    return int(key, 16)
                raise

    def get_all_related_groups(self, group_id: int | str) -> list[int]:
        primary = self.get_primary_group(group_id)
        subs = self.data.setdefault("primary_to_subs", {}).get(str(primary), [])
        groups: set[int] = {primary}
        for sub in subs:
            try:
                groups.add(int(sub))
            except (TypeError, ValueError):
                continue
        return sorted(groups)

    def bind_group(self, sub_group: int | str, target_primary: int | str) -> tuple[bool, int]:
        sub_key = self._normalize(sub_group)
        primary = self.get_primary_group(target_primary)
        primary_key = str(primary)
        if sub_key == primary_key:
            return False, primary

        mapping = self.data.setdefault("group_to_primary", {})
        reverse = self.data.setdefault("primary_to_subs", {})
        current_primary = mapping.get(sub_key)
        if current_primary == primary_key:
            return False, primary

        # detach from previous primary
        if current_primary:
            subs = reverse.get(current_primary, [])
            if sub_key in subs:
                subs.remove(sub_key)
                if not subs:
                    reverse.pop(current_primary, None)

        mapping[sub_key] = primary_key
        reverse.setdefault(primary_key, [])
        if sub_key not in reverse[primary_key]:
            reverse[primary_key].append(sub_key)
        self.save()
        return True, primary

    def unbind_group(self, sub_group: int | str) -> tuple[bool, int | None]:
        sub_key = self._normalize(sub_group)
        mapping = self.data.setdefault("group_to_primary", {})
        reverse = self.data.setdefault("primary_to_subs", {})
        current_primary = mapping.pop(sub_key, None)
        if not current_primary:
            return False, None
        subs = reverse.get(current_primary, [])
        if sub_key in subs:
            subs.remove(sub_key)
            if not subs:
                reverse.pop(current_primary, None)
        self.save()
        try:
            return True, int(current_primary)
        except (TypeError, ValueError):
            return True, None

    def get_sub_groups(self, group_id: int | str) -> list[int]:
        primary = self.get_primary_group(group_id)
        subs = self.data.setdefault("primary_to_subs", {}).get(str(primary), [])
        result: list[int] = []
        for item in subs:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result


_binding_store = FishGameBindingStore()


def resolve_game_group_id(group_id: int | str) -> int:
    return _binding_store.get_primary_group(group_id)


def get_linked_groups(group_id: int | str) -> list[int]:
    return _binding_store.get_all_related_groups(group_id)


def get_sub_groups(group_id: int | str) -> list[int]:
    return _binding_store.get_sub_groups(group_id)


def is_game_enabled(game_id: int | str) -> bool:
    for gid in get_linked_groups(game_id):
        if plugin_manager.get_enable(gid, __plugin_meta["name"]):
            return True
    return False


async def collect_member_ids(bot, game_id: int, accessible_groups: set[int]) -> list[str]:
    members: set[str] = set()
    for gid in get_linked_groups(game_id):
        if gid not in accessible_groups:
            continue
        try:
            group_members = await bot.get_group_member_list(group_id=gid)
        except Exception as exc:
            logger.warning("Failed to fetch member list for group %s: %s", gid, exc)
            continue
        for member in group_members:
            user_id = member.get("user_id")
            if user_id is not None:
                members.add(str(user_id))
    return list(members)


def gather_candidate_game_ids(qq_groups: set[int], web_groups: set[int]) -> list[int]:
    seen: set[int] = set()
    candidates: list[int] = []
    for gid in sorted(qq_groups | web_groups):
        try:
            game_id = resolve_game_group_id(gid)
        except Exception:
            continue
        if game_id in seen:
            continue
        seen.add(game_id)
        candidates.append(game_id)
    return candidates


async def is_group_admin(ctx: RealContext) -> bool:
    if str(ctx.user_id) in get_driver().config.superusers:
        return True
    try:
        bot = get_bot(str(get_driver().config.private_bot))
        info = await bot.get_group_member_info(group_id=ctx.group_id, user_id=ctx.user_id)
        return info.get("role") in {"owner", "admin"}
    except Exception as exc:
        logger.warning("Failed to verify admin for group %s user %s: %s", ctx.group_id, ctx.user_id, exc)
        return False


async def push_game_web_event(group_id: int | str, payload: dict):
    game_id = resolve_game_group_id(group_id)
    if not has_online_clients(str(game_id)):
        return
    body = dict(payload)
    body.setdefault("game", str(game_id))
    body.setdefault("timestamp", int(time.time()))
    try:
        await push_web_event(str(game_id), body)
    except Exception as exc:
        logger.warning("Failed to push web event for group %s: %s", game_id, exc)

async def __group_checker(bot: Bot, event: Event):
    if hasattr(event, 'group_openid') and bot.type == 'QQ' and bot.self_id != str(get_driver().config.chiyuki_bot):
        return False
    elif not hasattr(event, 'group_id') or hasattr(event, 'group_openid'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])

async def __not_group(event: Event):
    if hasattr(event, 'group_id') and not hasattr(event, 'group_openid'):
        return False
    return True


official_hybrid = Rule(__group_checker, __not_group)


from nonebot_plugin_apscheduler import scheduler


async def get_group_lists(qq_only=False) -> list[int]:
    groups = set()
    bot = get_bot(str(get_driver().config.private_bot))
    group_list = await bot.get_group_list()
    for group in group_list:
        groups.add(group['group_id'])
    if qq_only:
        return list(groups)
    for gid in online_clients_group_list():
        groups.add(int(gid))
    return list(groups)


async def dispatch_notifications(group_id: int, qq_message: str | None = None, web_event: dict | None = None):
    """Send QQ message and/or web push event based on availability."""
    bot = get_bot(str(get_driver().config.private_bot))
    game_id = resolve_game_group_id(group_id)
    if qq_message:
        available_groups = set(await get_group_lists(qq_only=True))
        for target in get_linked_groups(game_id):
            if target not in available_groups:
                continue
            if not plugin_manager.get_enable(target, __plugin_meta["name"]):
                continue
            try:
                await bot.send_msg(message_type="group", group_id=target, message=qq_message)
            except Exception as exc:
                logger.warning("Failed to send QQ message to group %s: %s", target, exc)
    if web_event:
        await push_game_web_event(game_id, web_event)


def ensure_game(group_id: int) -> FishGame:
    realid = resolve_game_group_id(group_id)
    if realid not in fish_games:
        fish_games[realid] = FishGame(realid)
    return fish_games[realid]

def ensure_player(user_id: int | str) -> FishPlayer:
    return FishPlayer(str(user_id))


def reply_text(ctx: RealContext, text: str) -> UniMessage:
    return UniMessage.reply(ctx.message_id) + UniMessage.text(text)


def reply_image(ctx: RealContext, image: Any) -> UniMessage:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return UniMessage.reply(ctx.message_id) + UniMessage.image(raw=buffer)


def normalize_event_text(message: Message | None) -> str:
    text = str(message).strip() if message is not None else ""
    while text.startswith('/'):
        text = text[1:].lstrip()
    return text


async def get_member_display_name(group_id: int, user_id: int, player: FishPlayer | None = None) -> str:
    fallback = None
    if player is not None:
        fallback = player.data.get('name') or player.data.get('nickname')
    try:
        bot = get_bot(str(get_driver().config.private_bot))
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        card = info.get("card")
        if card:
            return card
        nickname = info.get("nickname")
        if nickname:
            return nickname
    except Exception as exc:
        logger.warning("Failed to fetch member info for group %s user %s: %s", group_id, user_id, exc)
    return fallback or str(user_id)

@scheduler.scheduled_job("cron", minute="*/1", jitter=30)
async def try_spawn_fish():
    # 如果不在 8 到 24 点则不尝试生成
    if 1 <= time.localtime().tm_hour < 8:
        return

    bot = get_bot(str(get_driver().config.private_bot))
    qq_groups = set(await get_group_lists(qq_only=True))
    web_groups: set[int] = set()
    for gid in online_clients_group_list():
        try:
            web_groups.add(int(gid))
        except (TypeError, ValueError):
            continue

    candidate_games = gather_candidate_game_ids(qq_groups, web_groups)
    for game_id in candidate_games:
        if not is_game_enabled(game_id):
            continue
        game = ensure_game(game_id)
        member_ids = await collect_member_ids(bot, game_id, qq_groups)
        game.update_average_power(member_ids)

        if game.current_fish is not None:
            current_fish = game.current_fish
            leave = game.count_down()
            if leave:
                leave_msg = "鱼离开了..." if not game.is_fever else '鱼群散去了！'
                await dispatch_notifications(
                    game_id,
                    leave_msg,
                    {
                        "type": "fish_leave",
                        "fish": current_fish.data if current_fish else None,
                        "reason": "timeout",
                        "isFever": game.is_fever,
                    }
                )
        if game.current_fish is None:
            fish: Fish = game.spawn_fish()
            if fish is not None:
                shiny_mark = "✨异色✨" if game.current_fish_is_shiny else ""
                if fish.rarity == 'UR':
                    spawn_msg = f"{shiny_mark}{fish.name}【{fish.rarity}】 █████！\n使用【████】指███████获████！"
                else:
                    spawn_msg = f"{shiny_mark}{fish.name}【{fish.rarity}】 出现了！\n使用【捕鱼】指令进行捕获吧！"
                if game.current_fish_is_shiny:
                    spawn_msg += "\n🌟这是一只异色宝可梦！捕获后经验和金币翻4倍！"
                await dispatch_notifications(
                    game_id,
                    spawn_msg,
                    {
                        "type": "spawn",
                        "fish": fish.data,
                        "rarity": fish.rarity,
                        "isFever": game.is_fever,
                        "isShiny": game.current_fish_is_shiny,
                    }
                )

        if game.check_oversea_spawn():
            battle = game.oversea_battle
            alert_msg = f"警报！海上发现了巨大的身影！\n{battle.data['monster_name']} 正在接近！\n请各位渔者前往【港口】进行讨伐！"
            await dispatch_notifications(
                game_id,
                alert_msg,
                {
                    "type": "oversea_spawn",
                    "battle": battle.data,
                }
            )

# 港口战斗推进 (每3分钟)
@scheduler.scheduled_job("cron", minute="*/3")
async def process_oversea_battle():
    qq_groups = set(await get_group_lists(qq_only=True))
    web_groups: set[int] = set()
    for gid in online_clients_group_list():
        try:
            web_groups.add(int(gid))
        except (TypeError, ValueError):
            continue

    for game_id in gather_candidate_game_ids(qq_groups, web_groups):
        if not is_game_enabled(game_id):
            continue
        game = ensure_game(game_id)
        res = game.process_oversea_turn()
        if not res:
            continue

        msg = f"【港口战报】第 {game.oversea_battle.data['current_round']} 轮结束\n"
        if 'logs' in res:
            logs = res['logs']
            msg += "\n".join(logs)

        if res['status'] == 'success':
            msg += f"\n\n讨伐成功！{game.oversea_battle.data['monster_name']} 已被击败！"
        elif res['status'] == 'fail':
            msg += f"\n\n讨伐失败... {res['message']}"

        await dispatch_notifications(
            game_id,
            msg if res['status'] in ('success', 'fail') else None
,
            {
                "type": "oversea_battle_update",
                "status": res.get('status'),
                "logs": res.get('logs'),
                "round": game.oversea_battle.data.get('current_round') if game.oversea_battle else None,
            }
        )


@scheduler.scheduled_job("cron", hour=19, minute=30)
async def test_if_group_come():
    bot = get_bot(str(get_driver().config.private_bot))
    group_list = await bot.get_group_list()
    processed: set[int] = set()
    for obj in group_list:
        group = obj['group_id']
        game_id = resolve_game_group_id(group)
        if game_id in processed or not is_game_enabled(game_id):
            continue
        processed.add(game_id)
        fish_game = ensure_game(game_id)
        fish_game.refresh_buff()
        rate = fish_game.data['feed_time'] / 5
        if random.random() < rate:
            fish_game.trigger_fever()
            minute = (fish_game.data['fever_expire'] - time.time()) // 60
            fever_msg = f"大量的鱼群聚集了起来！\n接下来{int(minute)}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n但与此同时，你的等级和渔具的效果似乎受到了削弱……"
            await dispatch_notifications(
                game_id,
                fever_msg,
                {
                    "type": "fever_start",
                    "duration": int(fish_game.data['fever_expire'] - time.time()),
                    "expireAt": fish_game.data['fever_expire'],
                }
            )


panel = on_command('面板', rule=official_hybrid)

@panel.handle()
async def _(ctx: RealContext = Depends(get_real_context)):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    player.refresh_buff()
    player.data['name'] = await get_member_display_name(ctx.group_id, ctx.user_id, player)
    avatar = await get_qq_avatar(ctx.user_id)
    character_panel = create_character_panel(player, avatar, game)
    await reply_image(ctx, character_panel).send()

bag = on_command('背包', rule=official_hybrid)

@bag.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    player = ensure_player(ctx.user_id)
    page = 1
    page_text = str(message).strip()
    if page_text:
        try:
            page = max(1, int(page_text))
        except ValueError:
            await reply_text(ctx, "页数必须是数字").send()
            return
    bag_items = sorted(player.bag.items, key=lambda x: x['item'].id)
    total_pages = max(1, (len(bag_items) - 1) // 10 + 1)
    page = min(page, total_pages)
    bag_panel = create_inventory_panel(
        bag_items[(page - 1) * 10:page * 10],
        page,
        total_pages,
        player.equipment.ids,
    )
    await reply_image(ctx, bag_panel).send()

# 查看配件详细技能
view_accessory = on_command('查看配件', rule=official_hybrid)

@view_accessory.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    args = str(message).strip().split()
    if len(args) != 1:
        await reply_text(ctx, "用法：查看配件 <配件编号>").send()
        return
    try:
        acc_id = int(args[0])
    except ValueError:
        await reply_text(ctx, "编号必须是数字").send()
        return
    player = ensure_player(ctx.user_id)
    item = FishItem.get(str(acc_id))
    if not item or item.type != 'accessory':
        await reply_text(ctx, "未找到该配件").send()
        return
    if player.bag.get_item(acc_id) is None:
        await reply_text(ctx, "你未持有该配件").send()
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
    await reply_text(ctx, "\n".join(lines)).send()

# 查看当前玩家所有生效技能（配件 + 未来可能的 rod/tool）
skill_list_cmd = on_command('技能列表', rule=official_hybrid)

@skill_list_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context)):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    skills = player.get_equipped_skills()
    if not skills:
        await reply_text(ctx, "当前没有任何生效技能").send()
        return
    img = create_skill_list_image(skills, game)
    await reply_image(ctx, img).send()

catch = on_command('捕鱼', aliases={'大师球'}, rule=official_hybrid)

@catch.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    text = normalize_event_text(message)
    master_ball = text.endswith('大师球')
    fish_before = game.current_fish.data if game.current_fish else None
    res = game.catch_fish(player, master_ball)
    await reply_text(ctx, res['message']).send()

    if fish_before:
        display = await get_member_display_name(ctx.group_id, ctx.user_id, player)
        await push_game_web_event(
            ctx.group_id,
            {
                "type": "catch",
                "by": str(ctx.user_id),
                "display": display,
                "fish": fish_before,
                "code": res.get('code'),
                "message": res.get('message'),
                "success": res.get('code') == 0,
                "isShiny": res.get('is_shiny', False),
                "fishStillPresent": game.current_fish is not None,
                "isFever": game.is_fever,
                "source": "qq",
            },
        )


GACHA_MODES = {
    '单抽': (False, False, False),
    '十连': (True, False, False),
    '百连': (False, True, False),
    '千连': (False, False, True),
}


MYSTERY_GACHA_MODES = {
    '神秘单抽': (False, False, False),
    '神秘十连': (True, False, False),
    '神秘百连': (False, True, False),
    '神秘千连': (False, False, True),
}

draw = on_command('单抽', aliases={'十连', '百连', '千连'}, rule=official_hybrid)

@draw.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    mode = normalize_event_text(message)
    flags = GACHA_MODES.get(mode)
    if flags is None:
        return
    ten_time, hundred_time, thousand_time = flags
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    res = game.gacha(player, ten_time, hundred_time, thousand_time)
    if res['code'] == 0:
        gacha_panel = create_gacha_panel(res['message'])
        await reply_image(ctx, gacha_panel).send()
    else:
        await reply_text(ctx, res['message']).send()

# 神秘抽卡
mystery_draw = on_command('神秘单抽', aliases={'神秘十连', '神秘百连', '神秘千连'}, rule=official_hybrid)

@mystery_draw.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    mode = normalize_event_text(message)
    flags = MYSTERY_GACHA_MODES.get(mode)
    if flags is None:
        return
    ten_time, hundred_time, thousand_time = flags
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    res = game.mystery_gacha(player, ten_time=ten_time, hundred_time=hundred_time, thousand_time=thousand_time)
    if res['code'] == 0:
        gacha_panel = create_gacha_panel(res['message'])
        await reply_image(ctx, gacha_panel).send()
    else:
        await reply_text(ctx, res['message']).send()

shop = on_command('商店', rule=official_hybrid)

@shop.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    msg = normalize_event_text(message)
    if msg and msg != '商店':
        return
    game = ensure_game(ctx.group_id)
    shop_panel = create_shop_panel(game.get_shop())
    await reply_image(ctx, shop_panel).send()

buy = on_command('商店购买', rule=official_hybrid)

@buy.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    raw = str(message).strip()
    if not raw:
        await reply_text(ctx, "请输入商品编号").send()
        return
    try:
        item_id = int(raw)
    except ValueError:
        await reply_text(ctx, "未找到该商品").send()
        return
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    try:
        res = game.shop_buy(player, item_id)
        await reply_text(ctx, res['message']).send()
    except Exception:
        logger.exception("Shop buy failed", exc_info=True)
        await reply_text(ctx, "未找到该商品").send()

use = on_command('使用', aliases={'强制使用'}, rule=official_hybrid)

@use.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    raw = normalize_event_text(message)
    if not raw:
        await reply_text(ctx, "未找到该道具").send()
        return
    force = False
    payload = raw
    if raw.startswith('强制使用'):
        force = True
        payload = raw.replace('强制使用', '', 1).strip()
    elif raw.startswith('使用'):
        payload = raw.replace('使用', '', 1).strip()
    parts = payload.split()
    try:
        item_id = int(parts[0])
    except (IndexError, ValueError):
        await reply_text(ctx, "未找到该道具").send()
        return
    remain_args = parts[1:]
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    messages: list[str] = []
    count = 1
    copied_args = copy(remain_args)
    try:
        while count > 0:
            res = game.use_item(player, item_id, force, copied_args)
            messages.append(res['message'])
            if res['code'] != 0:
                break
            if len(copied_args) == 1 and getattr(FishItem.get(item_id), 'batch_use', False):
                try:
                    count = int(copied_args[0]) - 1
                except ValueError:
                    break
                copied_args = copy(remain_args)
                if copied_args:
                    copied_args[-1] = str(count)
                if count <= 0:
                    break
            else:
                count -= 1
        if not messages:
            await reply_text(ctx, "没有可执行的效果").send()
            return
        if len(messages) > 10:
            summary = f"...(省略了{len(messages) - 10}条)\n" + "\n".join(messages[-10:])
        else:
            summary = "\n".join(messages)
        await reply_text(ctx, summary).send()
    except Exception:
        logger.exception("Use item failed", exc_info=True)
        await reply_text(ctx, "未找到该道具").send()

status = on_command('状态', aliases={'池子状态', '完整状态'}, rule=official_hybrid)

@status.handle()
async def _(ctx: RealContext = Depends(get_real_context), msg: Message = EventMessage()):
    content = normalize_event_text(msg)
    game = ensure_game(ctx.group_id)
    bot = get_bot(str(get_driver().config.private_bot))
    try:
        qq_list = await bot.get_group_member_list(group_id=ctx.group_id)
        member_ids = [str(qq['user_id']) for qq in qq_list]
    except Exception as exc:
        logger.warning("Failed to fetch member list for group %s: %s", ctx.group_id, exc)
        member_ids = [str(ctx.user_id)]
    game.update_average_power(member_ids)
    player = ensure_player(ctx.user_id)
    player.refresh_buff()
    buff_lines: list[str] = []
    for buff in player.buff:
        line = ""
        if buff.get('power', 0) > 0:
            line += f"渔力+{buff['power']}，"
        elif buff.get('fishing_bonus', 0) > 0:
            line += f"渔获+{buff['fishing_bonus'] * 100}%，"
        if buff.get('time') is not None:
            line += f"剩余{buff['time']}次"
        elif buff.get('expire') is not None:
            line += f"剩余{int(buff['expire'] - time.time())}秒"
        if line:
            buff_lines.append(line)
    buffs_text = "\n".join(buff_lines)
    pool_status = game.get_status()['message']
    simulate = game.simulate_spawn_fish()
    if content == '状态':
        if not buffs_text:
            await reply_text(ctx, "当前没有任何玩家状态，请尝试命令【池子状态】或【完整状态】").send()
        else:
            await reply_text(ctx, buffs_text).send()
    elif content == '池子状态':
        await reply_text(ctx, pool_status).send()
    elif content == '完整状态':
        combined = (buffs_text + "\n" if buffs_text else '') + pool_status + "\n当前刷新鱼概率：\n" + simulate
        await reply_text(ctx, combined).send()

refresh_counts = on_command('饿鱼')

@refresh_counts.handle()
async def _(ctx: RealContext = Depends(get_real_context)):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    game = ensure_game(ctx.group_id)
    game.data['feed_time'] = 0
    game.save()
    await reply_text(ctx, "已重置投放食料的计数").send()


bind_game_cmd = on_command('绑定捕鱼游戏', rule=official_hybrid)


@bind_game_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if not await is_group_admin(ctx):
        await reply_text(ctx, "只有群管理员可以配置副群聊").send()
        return
    payload = str(message).strip()
    current_primary = resolve_game_group_id(ctx.group_id)

    if not payload:
        subs = get_sub_groups(ctx.group_id)
        if current_primary == ctx.group_id:
            if subs:
                await reply_text(
                    ctx,
                    "本群当前为主群聊，已挂载的副群聊：" + ", ".join(str(sub) for sub in subs),
                ).send()
            else:
                await reply_text(ctx, "本群当前为主群聊，未绑定到其他游戏").send()
        else:
            await reply_text(ctx, f"本群当前绑定到 {current_primary}，副群聊无法使用 web 面板").send()
        return

    try:
        target_group = int(payload)
    except ValueError:
        await reply_text(ctx, "请输入正确的目标群号").send()
        return

    if current_primary == ctx.group_id and get_sub_groups(ctx.group_id):
        await reply_text(ctx, "本群挂载了其他副群聊，请先让这些群解绑后再绑定").send()
        return

    try:
        changed, primary = _binding_store.bind_group(ctx.group_id, target_group)
    except Exception:
        logger.exception("Failed to bind fishgame group", exc_info=True)
        await reply_text(ctx, "绑定失败，请稍后再试").send()
        return

    if not changed:
        if ctx.group_id == primary:
            await reply_text(ctx, "目标群号与当前群号相同，无需绑定").send()
        else:
            await reply_text(ctx, f"本群已绑定到 {primary}").send()
        return

    fish_games.pop(ctx.group_id, None)
    await reply_text(ctx, f"已将本群绑定到 {primary} 的捕鱼游戏，副群聊不支持 web 面板").send()


unbind_game_cmd = on_command('解绑捕鱼游戏', rule=official_hybrid)


@unbind_game_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context)):
    if not await is_group_admin(ctx):
        await reply_text(ctx, "只有群管理员可以解除绑定").send()
        return
    changed, primary = _binding_store.unbind_group(ctx.group_id)
    if not changed:
        if resolve_game_group_id(ctx.group_id) == ctx.group_id:
            await reply_text(ctx, "本群当前不是副群聊").send()
        else:
            await reply_text(ctx, "未找到可解除的绑定，请稍后再试").send()
        return
    fish_games.pop(ctx.group_id, None)
    await reply_text(ctx, "已解除绑定，本群将拥有独立的捕鱼游戏，web 面板请使用本群群号登录").send()

force_spawn = on_command('刷鱼')

@force_spawn.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split()
    if len(args) != 2:
        await reply_text(ctx, "参数错误，格式：刷鱼 <群号> <鱼编号>").send()
        return
    try:
        group = int(args[0])
    except ValueError:
        await reply_text(ctx, "群号必须是数字").send()
        return
    fish_id = args[1]
    game = ensure_game(group)
    fish = game.force_spawn_fish(fish_id)
    if fish is not None:
        if fish.rarity == 'UR':
            spawn_msg = f"{fish.name}【{fish.rarity}】 █████！\n使用【████】指███████获████！"
        else:
            spawn_msg = f"{fish.name}【{fish.rarity}】 出现了！\n使用【捕鱼】指令进行捕获吧！"
        await dispatch_notifications(
            group,
            spawn_msg,
            {
                "type": "spawn",
                "fish": fish.data,
                "rarity": fish.rarity,
                "isFever": game.is_fever,
                "isShiny": game.current_fish_is_shiny,
            }
        )
    await reply_text(ctx, f"已尝试在 {group} 刷鱼").send()
    
force_fever = on_command('强制fever')
@force_fever.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    try:
        group = int(str(message).strip())
    except ValueError:
        await reply_text(ctx, "请输入群号").send()
        return
    game = ensure_game(group)
    game.trigger_fever()
    minute = int((game.data['fever_expire'] - time.time()) // 60)
    await get_bot(str(get_driver().config.private_bot)).send_msg(
        message_type="group",
        group_id=group,
        message=f"大量的鱼群聚集了起来！\n接下来{minute}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n但与此同时，你的等级和渔具的效果似乎受到了削弱……",
    )
    await reply_text(ctx, f"{group} 已进入 Fever 状态").send()


force_dex = on_command('开图鉴')
@force_dex.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    try:
        group = int(str(message).strip())
    except ValueError:
        await reply_text(ctx, "请输入群号").send()
        return
    game = ensure_game(group)
    game.unlock_all()
    await get_bot(str(get_driver().config.private_bot)).send_msg(
        message_type="group",
        group_id=group,
        message="已开所有图鉴",
    )
    await reply_text(ctx, f"{group} 图鉴已解锁").send()


force_item = on_command('给道具')
@force_item.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split()
    if len(args) not in (2, 3):
        await reply_text(ctx, "参数错误，格式：给道具 <QQ号> <物品编号> [数量]").send()
        return
    qq = args[0]
    try:
        item_id = int(args[1])
        count = int(args[2]) if len(args) == 3 else 1
    except ValueError:
        await reply_text(ctx, "参数错误，格式：给道具 <QQ号> <物品编号> [数量]").send()
        return
    player = FishPlayer(qq)
    item = FishItem.get(item_id)
    if item is None:
        await reply_text(ctx, "未找到该物品").send()
        return
    player.bag.add_item(item_id, count)
    player.save()
    msg = UniMessage.reply(ctx.message_id) + UniMessage.text("已给予") + UniMessage.at(str(qq)) + UniMessage.text(f" {item.name} x{count}")
    await msg.send()

force_gold = on_command('给金币', aliases={'给钱'})
@force_gold.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split()
    if len(args) != 2:
        await reply_text(ctx, "参数错误，格式：给金币 <QQ号> <数量>").send()
        return
    qq = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await reply_text(ctx, "数量必须是数字").send()
        return
    player = FishPlayer(qq)
    player.data['gold'] += amount
    player.save()
    msg = UniMessage.reply(ctx.message_id) + UniMessage.text("已给予") + UniMessage.at(str(qq)) + UniMessage.text(f" {amount}金币")
    await msg.send()

force_building = on_command('设置建筑等级')
@force_building.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if str(ctx.user_id) not in get_driver().config.superusers:
        return
    args = str(message).strip().split()
    if len(args) != 2:
        await reply_text(ctx, "参数错误，格式：设置建筑等级 <建筑名> <等级>").send()
        return

    building_name, level_str = args
    try:
        level = int(level_str)
    except ValueError:
        await reply_text(ctx, "等级必须是数字").send()
        return

    game = ensure_game(ctx.group_id)
    attr = building_name_map.get(building_name)
    if not attr or not hasattr(game, attr):
        await reply_text(ctx, "未找到对应建筑").send()
        return
    building: BuildingBase = getattr(game, attr)
    building.level = level
    game.save()
    await reply_text(ctx, f"已将 {building_name} 的等级设置为 {level}").send()


craft = on_command('合成', rule=official_hybrid)

@craft.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)

    args = str(message).strip()
    page = 1
    is_page_cmd = False

    if args == '' or args == '合成':
        is_page_cmd = True
    elif args.startswith('#'):
        try:
            page = int(args[1:])
            is_page_cmd = True
        except ValueError:
            pass

    if is_page_cmd:
        craftable_items = game.get_craftable_items()
        if not craftable_items:
            await reply_text(ctx, "暂无可合成的物品").send()
            return
        items_per_page = 12
        total_pages = max(1, (len(craftable_items) - 1) // items_per_page + 1)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * items_per_page
        page_items = craftable_items[start_idx:start_idx + items_per_page]
        craft_panel = create_craft_panel(page_items, player.bag, player, page, total_pages)
        await reply_image(ctx, craft_panel).send()
    else:
        parts = args.split()
        try:
            item_id = int(parts[0])
            count = int(parts[1]) if len(parts) > 1 else 1
        except (ValueError, IndexError):
            await reply_text(ctx, "请输入正确的物品编号").send()
            return
        target_item = FishItem.get(item_id)
        if target_item is None:
            await reply_text(ctx, "未找到该物品").send()
            return
        if count > 1 and getattr(target_item, 'batch_craft', False):
            results = []
            for _ in range(count):
                res = game.craft_item(player, item_id)
                results.append(res['message'])
                if res['code'] != 0:
                    break
            if len(results) > 10:
                summary = f"...(省略了{len(results) - 10}条)\n" + "\n".join(results[-10:])
            else:
                summary = "\n".join(results)
            await reply_text(ctx, summary.strip()).send()
        else:
            res = game.craft_item(player, item_id)
            await reply_text(ctx, res['message']).send()


gift = on_command('赠送', rule=official_hybrid)

@gift.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    if not hasattr(ctx, 'group_id'):
        return
    group = ctx.group_id
    game = ensure_game(group)
    player = ensure_player(ctx.user_id)
    
    args = str(message).strip().split()

    if len(args) != 2:
        msg = UniMessage.reply(ctx.message_id) + UniMessage.text("使用格式：赠送 <QQ号> <物品编号>")
        await msg.send()
        return
    
    try:
        receiver_qq = args[0]
        item_id = int(args[1])
        
        # 验证QQ号格式（简单检查是否为数字）
        if not receiver_qq.isdigit():
            await (UniMessage.reply(ctx.message_id) + UniMessage.text("请输入正确的QQ号")).send()
            return
        
        # 不能赠送给自己
        if receiver_qq == str(ctx.user_id):
            await (UniMessage.reply(ctx.message_id) + UniMessage.text("不能赠送给自己")).send()
            return
        
        res = game.gift_item(player, receiver_qq, item_id)
        msg = UniMessage.reply(ctx.message_id) + UniMessage.text(res['message'])
        if res.get('receiver') is not None:
            msg += UniMessage.at(res['receiver'])
        await msg.send()
        
    except Exception as e:
        logger.exception("Gift command failed", exc_info=True)
        await (UniMessage.reply(ctx.message_id) + UniMessage.text("参数格式错误，使用格式：赠送 <QQ号> <物品编号>")).send()


buildings = on_command('建筑', rule=official_hybrid)

@buildings.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    content = str(message).strip()
    if not content:
        buildings_panel = create_buildings_panel(game)
        await reply_image(ctx, buildings_panel).send()
        return
    args = content.split()
    if len(args) != 2:
        await reply_text(ctx, "参数格式错误，使用格式：建筑 <建筑名称> <材料编号/升级>").send()
        return
    building_name, material = args
    if material == '升级':
        ret = game.building_level_up(building_name)
        await reply_text(ctx, ret['message']).send()
        return
    try:
        item_id = int(material)
    except ValueError:
        await reply_text(ctx, "参数格式错误，使用格式：建筑 <建筑名称> <材料编号>").send()
        return
    ret = game.build(player, building_name, item_id)
    await reply_text(ctx, ret['message']).send()

# ---------------- Port Commands ----------------
port_cmd = on_command('港口', rule=official_hybrid)

@port_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    args = str(message).strip().split()
    if not args or args[0] == '帮助':
        help_msg = """港口指令帮助：
港口 面板 - 查看当前海怪讨伐状态
港口 组队 - 加入当前的讨伐队伍
港口 退出 - 退出当前的讨伐队伍
港口 物品 <物品ID> - 携带讨伐物品（鱼叉/尾鳍）
港口 开始战斗 - 开始讨伐（需要全员准备）
港口 帮助 - 显示此帮助"""
        await reply_text(ctx, help_msg).send()
        return

    cmd = args[0]

    if cmd == '面板':
        panel_img = create_oversea_panel(game)
        await reply_image(ctx, panel_img).send()
    elif cmd == '组队':
        nickname = await get_member_display_name(ctx.group_id, ctx.user_id, player)
        res = game.join_oversea(player, nickname)
        await reply_text(ctx, res['message']).send()
    elif cmd == '退出':
        res = game.leave_oversea(player)
        await reply_text(ctx, res['message']).send()
    elif cmd == '物品':
        if len(args) < 2:
            await reply_text(ctx, "请输入物品ID").send()
            return
        res = game.equip_oversea_item(player, args[1])
        await reply_text(ctx, res['message']).send()
    elif cmd == '开始战斗':
        res = game.start_oversea_battle()
        await reply_text(ctx, res['message']).send()
    elif cmd == '刷新' and str(ctx.user_id) in get_driver().config.superusers:
        game.spawn_oversea_monster()
        await reply_text(ctx, "已强制刷新港口怪物").send()
    elif cmd == '推进' and str(ctx.user_id) in get_driver().config.superusers:
        res = game.process_oversea_turn()
        if res:
            await reply_text(ctx, f"已强制推进回合: {res['message']}").send()
        else:
            await reply_text(ctx, "无法推进回合（可能未开始战斗）").send()

pot = on_command('大锅', rule=official_hybrid)

@pot.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)

    if game.big_pot.level == 0:
        await reply_text(ctx, '还没有建造大锅哦……').send()
        return

    content = str(message).strip()
    if not content:
        ret = game.get_pot_status()
        msg = reply_text(ctx, ret) + UniMessage.text('\nUsage：大锅 添加 <物品ID> [数量]')
        await msg.send()
        return

    args = content.split()
    if args[0] == '添加':
        if len(args) < 2:
            await reply_text(ctx, '未提供物品ID').send()
            return
        item = FishItem.get(args[1])
        if item is None:
            await reply_text(ctx, f'未找到物品 {args[1]}').send()
            return
        count = 1
        if len(args) == 3:
            try:
                count = int(args[2])
            except ValueError:
                pass
        ret = game.pot_add_item(player, item, count)
        await reply_text(ctx, ret['message']).send()
    else:
        ret = game.get_pot_status()
        msg = reply_text(ctx, ret) + UniMessage.text('\nUsage：大锅 添加 <物品ID> [数量]')
        await msg.send()

# 签到
sign_in_cmd = on_command('签到', rule=official_hybrid)

@sign_in_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    if normalize_event_text(message) != '签到':
        return
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    res = game.sign_in(player)
    await reply_text(ctx, res['message']).send()

# 天赋面板
talent_cmd = on_command('天赋', rule=official_hybrid)

@talent_cmd.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = EventMessage()):
    if normalize_event_text(message) != '天赋':
        return
    game = ensure_game(ctx.group_id)
    player = ensure_player(ctx.user_id)
    panel_img = create_talent_panel(player, game)
    await reply_image(ctx, panel_img).send()

