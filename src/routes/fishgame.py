from pathlib import Path
import json
import time
from collections import Counter
from quart import jsonify, request, send_file, websocket

from src.routes.app import quart_app
from src.data_access.redis import DictRedisData
from src.libraries.fishgame.player import FishPlayer
from src.libraries.fishgame.data import Fish, fish_item, FishItem, fish_skills
from src.libraries.fishgame.buildings import building_name_map
from src.libraries.fishgame.runtime import ensure_game
from src.libraries.fishgame.oversea import battle_buffs
from nonebot.log import logger


class WsMessageStore(DictRedisData):
    """Fixed-size Redis-backed buffer for websocket broadcast messages."""

    MAX_MESSAGES = 500

    def __init__(self, game_id: str):
        super().__init__(f"fishgame_ws_msg_store:{game_id}", default={"messages": []})

    def record(self, payload: dict):
        messages = self.data.setdefault("messages", [])
        messages.append(dict(payload))
        if len(messages) > self.MAX_MESSAGES:
            del messages[:-self.MAX_MESSAGES]
        self.save()

    def tail(self, limit: int = 200) -> list[dict]:
        messages = self.data.get("messages", [])
        if limit <= 0 or limit >= len(messages):
            return list(messages)
        return messages[-limit:]


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template"
FISH_TEMPLATE = TEMPLATE_DIR / "fishgame.html"

# In-memory registry of websocket connections by game id
_GROUP_CONNECTIONS: dict[str, set] = {}

_BUILDING_KEYS = [
    "big_pot",
    "fish_factory",
    "building_center",
    "fish_lab",
    "ice_hole",
    "mystic_shop",
    "seven_statue",
    "forge_shop",
    "port",
]

_BUILDING_LABELS = {value: key for key, value in building_name_map.items()}
_GLOW_NAME_MAP = {
    "glow_stick_normal": "普通荧光棒",
    "glow_stick_special": "海皇荧光棒",
}

_DRAW_TYPE_FLAGS = {
    "single": (False, False, False),
    "ten": (True, False, False),
    "hundred": (False, True, False),
    "thousand": (False, False, True),
}

_PORT_LOADOUT_ITEM_IDS = list(range(33, 41)) + [49, 310]


def _persist_ws_payload(game_id: str, payload: dict):
    try:
        store = WsMessageStore(game_id)
        store.record(payload)
    except Exception:
        logger.exception("Failed to persist websocket payload for game %s", game_id)


def _prepare_ws_payload(game_id: str, message: dict) -> dict:
    payload = dict(message)
    payload.setdefault("pushedAt", int(time.time()))
    _persist_ws_payload(game_id, payload)
    return payload


def _resolve_building_label(key: str) -> str:
    return _BUILDING_LABELS.get(key, key)


def _resolve_draw_flags(draw_type: str):
    normalized = str(draw_type or "").lower()
    if normalized.isdigit():
        mapping = {"1": "single", "10": "ten", "100": "hundred", "1000": "thousand"}
        normalized = mapping.get(normalized, normalized)
    return _DRAW_TYPE_FLAGS.get(normalized)


def _safe_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _count_equipped(eq_ids, material_id) -> int:
    if not eq_ids:
        return 0
    try:
        return eq_ids.count(material_id)
    except AttributeError:
        if isinstance(eq_ids, dict):
            iterable = eq_ids.values()
        else:
            iterable = eq_ids
        return sum(1 for val in iterable if str(val) == str(material_id))
    except Exception:
        return 0


def _craftable_item_payload(item_obj, player, game_obj, eq_ids):
    materials = []
    for material_id, needed in Counter(item_obj.craftby or []).items():
        mat_meta = FishItem.get(str(material_id))
        owned_total = player.bag.get_item_count(material_id)
        equipped = _count_equipped(eq_ids, material_id)
        materials.append(
            {
                "id": _safe_number(material_id),
                "name": mat_meta.name if mat_meta else f"物品{material_id}",
                "rarity": getattr(mat_meta, "rarity", 1),
                "needed": int(needed),
                "owned": max(0, owned_total - equipped),
            }
        )
    materials.sort(key=lambda entry: entry["id"])

    requirements = []
    require_map = getattr(item_obj, "require", {}) or {}
    for building_key, level in require_map.items():
        attr_name = building_name_map.get(building_key, building_key)
        building = getattr(game_obj, attr_name, None)
        label = getattr(building, "name", _resolve_building_label(attr_name))
        current_level = building.level if building else 0
        requirements.append(
            {
                "key": building_key,
                "label": label,
                "requiredLevel": int(level),
                "currentLevel": int(current_level),
                "met": current_level >= level,
            }
        )
    requirements.sort(key=lambda entry: entry["label"])

    prereq_payload = None
    prereq_id = getattr(item_obj, "prerequisite_item", 0)
    if prereq_id:
        prereq_meta = FishItem.get(str(prereq_id))
        prereq_payload = {
            "id": prereq_id,
            "name": prereq_meta.name if prereq_meta else f"物品{prereq_id}",
            "rarity": getattr(prereq_meta, "rarity", 1),
        }

    return {
        "id": item_obj.id,
        "name": item_obj.name,
        "rarity": getattr(item_obj, "rarity", 1),
        "description": getattr(item_obj, "description", ""),
        "craftScoreCost": getattr(item_obj, "craft_score_cost", 0),
        "materials": materials,
        "requires": requirements,
        "prerequisiteItem": prereq_payload,
    }


def _build_building_snapshot(game_obj) -> list[dict]:
    payload: list[dict] = []
    for key in _BUILDING_KEYS:
        building = getattr(game_obj, key, None)
        if building is None:
            continue
        materials = []
        for request, current in building.get_materials_status():
            materials.append(
                {
                    "label": request.desc,
                    "current": current,
                    "required": getattr(request, "count", 0),
                }
            )
        prerequisites = []
        if building.level < building.max_level:
            reqs = building.get_level_prerequisites(building.level + 1) or {}
            for prereq_key, required_level in reqs.items():
                prereq_building = getattr(game_obj, prereq_key, None)
                current_level = prereq_building.level if prereq_building else 0
                prerequisites.append(
                    {
                        "key": prereq_key,
                        "label": _resolve_building_label(prereq_key),
                        "current": current_level,
                        "required": required_level,
                        "met": current_level >= required_level,
                    }
                )
        payload.append(
            {
                "key": key,
                "name": getattr(building, "name", _resolve_building_label(key)),
                "level": building.level,
                "maxLevel": building.max_level,
                "description": getattr(building, "description", ""),
                "currentEffect": building.level_effect_desc(building.level)
                if building.level > 0
                else "未建造",
                "nextEffect": building.level_effect_desc(building.level + 1)
                if building.level < building.max_level
                else "",
                "materials": materials,
                "prerequisites": prerequisites,
                "canUpgrade": building.can_upgrade(),
            }
        )
    return payload


def _build_pot_snapshot(game_obj) -> dict:
    pot = game_obj.big_pot
    return {
        "level": pot.level,
        "capacity": pot.capacity,
        "current": pot.current,
        "consumeSpeed": pot.consume_speed,
        "averagePowerBoost": pot.average_power_boost,
        "powerBoost": pot.power_boost,
        "description": pot.description,
        "nextEffect": pot.level_effect_desc(pot.level + 1)
        if pot.level < pot.max_level
        else "",
    }


def _build_pool_snapshot(game_obj) -> dict:
    status = game_obj.get_status()
    message = (status.get("message", "") + '\n当前刷新鱼概率：\n' + game_obj.simulate_spawn_fish()) if isinstance(status, dict) else str(status)
    summary = message.split("\n", 1)[0] if message else ""
    now = time.time()

    glow_info = []
    for buff in game_obj.data.get("avgp_buff", []):
        label = _GLOW_NAME_MAP.get(buff.get("key"), buff.get("key"))
        remaining = max(0, int(buff.get("expire", 0) - now))
        if label:
            glow_info.append({"label": label, "remaining": remaining})

    rarity_buffs = []
    for buff in game_obj.data.get("buff", []):
        rarity = buff.get("rarity")
        if not rarity:
            continue
        remaining = max(0, int(buff.get("expire", 0) - now)) if buff.get("expire") else 0
        rarity_buffs.append(
            {
                "rarity": rarity,
                "bonus": int(buff.get("bonus", 0)),
                "remaining": remaining,
            }
        )

    fever_remaining = (
        max(0, int(game_obj.data.get("fever_expire", 0) - now)) if game_obj.is_fever else 0
    )

    return {
        "summary": summary,
        "detail": message,
        "isFever": game_obj.is_fever,
        "averagePower": round(game_obj.average_power, 1),
        "currentFish": game_obj.current_fish.data if game_obj.current_fish else None,
        "currentFishIsShiny": game_obj.current_fish_is_shiny if game_obj.current_fish else False,
        "feverRemaining": fever_remaining,
        "glowBuffs": glow_info,
        "rarityBuffs": rarity_buffs,
        "fishLogCount": len(game_obj.data.get("fish_log", [])),
        "powerBoostFromPot": game_obj.big_pot.power_boost,
        "averagePowerBoostFromPot": game_obj.big_pot.average_power_boost,
        "lastUpdated": int(now),
    }


def _render_port_buff_description(template: str, level: int) -> str:
    if not template:
        return ""
    replacements = {
        "{level}": str(level),
        "{level * 5}": str(level * 5),
        "{level * 6}": str(level * 6),
        "{level * 10}": str(level * 10),
        "{level * 20}": str(level * 20),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def _build_port_item_options(player: FishPlayer) -> list[dict]:
    options = []
    for item_id in _PORT_LOADOUT_ITEM_IDS:
        item = FishItem.get(item_id)
        if not item:
            continue
        required = 10 if 33 <= item_id <= 40 else 1
        owned = player.bag.get_item_count(item_id)
        options.append(
            {
                "id": int(item_id),
                "name": item.name,
                "rarity": getattr(item, "rarity", 1),
                "required": required,
                "owned": owned,
                "description": getattr(item, "description", ""),
                "power": getattr(item, "power", 0),
            }
        )
    return options


def _build_battle_snapshot(game_obj, player: FishPlayer) -> dict | None:
    battle = getattr(game_obj, "oversea_battle", None)
    if not battle:
        return None
    data = battle.data
    loadouts = {str(k): v for k, v in data.get("loadouts", {}).items()}
    players_payload = []
    self_loadout_id = None
    for idx, member in enumerate(data.get("players", [])):
        qq_str = str(member)
        try:
            member_player = FishPlayer(qq_str)
            display_name = data.get("player_names", {}).get(qq_str) or member_player.name or qq_str
        except Exception:
            display_name = data.get("player_names", {}).get(qq_str) or qq_str
        item_id = loadouts.get(qq_str)
        if item_id is None:
            item_id = loadouts.get(member)
        item_meta = FishItem.get(item_id) if item_id else None
        entry = {
            "qq": qq_str,
            "name": display_name,
            "isLeader": idx == 0,
            "itemId": item_id,
            "itemName": item_meta.name if item_meta else None,
        }
        players_payload.append(entry)
        if qq_str == str(player.qq):
            self_loadout_id = item_id

    env_id = data.get("environment_buff") or 0
    env_meta = next((buff for buff in battle_buffs["environment"] if buff["id"] == env_id), None)

    monster_buff_payload = []
    for buff in data.get("monster_buffs", []):
        meta = next((entry for entry in battle_buffs["monster_negative"] if entry["id"] == buff.get("id")), None)
        if not meta:
            continue
        level = int(buff.get("level", 1) or 1)
        monster_buff_payload.append(
            {
                "id": buff.get("id"),
                "name": meta["name"],
                "level": level,
                "description": _render_port_buff_description(meta.get("description", ""), level),
            }
        )

    bonus_buff_payload = []
    for buff_id in data.get("bonus_buffs", []):
        meta = next((entry for entry in battle_buffs["bonus"] if entry["id"] == buff_id), None)
        if meta:
            bonus_buff_payload.append({"id": buff_id, "name": meta["name"], "description": meta.get("description", "")})

    monster_meta = Fish.get(data.get("monster_id")) if data.get("monster_id") else None
    monster_payload = None
    if monster_meta:
        monster_payload = {
            "id": monster_meta.id,
            "name": monster_meta.name,
            "rarity": monster_meta.rarity,
            "weakness": list(getattr(monster_meta, "weakness", [])),
        }

    return {
        "battleId": game_obj.data.get("current_oversea_id"),
        "status": data.get("status", "idle"),
        "difficulty": data.get("difficulty", 1),
        "round": {
            "current": data.get("current_round", 0),
            "max": data.get("max_rounds", 0),
        },
        "monster": monster_payload,
        "monsterHp": {
            "current": data.get("monster_hp", 0),
            "max": data.get("monster_max_hp", 0),
        },
        "ship": {
            "current": data.get("ship_hp", 0),
            "max": data.get("ship_max_hp", 0),
        },
        "players": players_payload,
        "playersCount": len(players_payload),
        "environmentBuff": env_meta,
        "monsterBuffs": monster_buff_payload,
        "bonusBuffs": bonus_buff_payload,
        "logs": data.get("logs", [])[-20:],
        "selfLoadoutId": self_loadout_id,
    }


def _build_port_payload(game_obj, player: FishPlayer) -> dict | None:
    port_building = getattr(game_obj, "port", None)
    if not port_building or port_building.level <= 0:
        return None
    today = time.strftime("%Y-%m-%d", time.localtime())
    raid_date = player.data.get("last_raid_date")
    attempts_used = player.data.get("raid_count", 0) if raid_date == today else 0
    attempts_used = int(attempts_used or 0)
    max_attempts = max(0, int(port_building.level))
    return {
        "level": port_building.level,
        "name": getattr(port_building, "name", "港口"),
        "description": getattr(port_building, "description", ""),
        "maxAttempts": max_attempts,
        "attemptsUsed": attempts_used,
        "attemptsRemaining": max(0, max_attempts - attempts_used),
        "teamSize": port_building.level + 1,
        "battle": _build_battle_snapshot(game_obj, player),
        "availableItems": _build_port_item_options(player),
    }


async def _broadcast_oversea_update(game_id: str, game_obj):
    battle = getattr(game_obj, "oversea_battle", None)
    if not battle:
        return
    data = battle.data
    await push_web_event(
        str(game_id),
        {
            "type": "oversea_battle_update",
            "status": data.get("status"),
            "round": data.get("current_round"),
            "monster": {
                "name": data.get("monster_name"),
                "hp": data.get("monster_hp"),
                "maxHp": data.get("monster_max_hp"),
            },
            "ship": {
                "hp": data.get("ship_hp"),
                "maxHp": data.get("ship_max_hp"),
            },
            "logs": data.get("logs", []),
        },
    )


def _json_error(message: str, status: int = 400):
    return jsonify({"code": status, "message": message}), status


async def _broadcast(game_id: str, message: dict):
    """Broadcast a JSON message to all connected websockets in the game group."""
    conns = _GROUP_CONNECTIONS.get(game_id, set()).copy()
    payload = _prepare_ws_payload(game_id, message)
    body = json.dumps(payload)
    for ws in list(conns):
        try:
            await ws.send(body)
        except Exception:
            logger.exception("Failed to send websocket message")
            try:
                _GROUP_CONNECTIONS.get(game_id, set()).discard(ws)
            except Exception:
                pass


@quart_app.route("/fishgame", methods=["GET"])
async def fishgame_entry():
    return await send_file(FISH_TEMPLATE)


@quart_app.route("/fishgame/api/session", methods=["POST"])
async def fishgame_session():
    payload = await request.get_json(force=True)
    if not payload:
        return _json_error("missing payload")
    game = str(payload.get("game", "")).strip()
    user = str(payload.get("user", "")).strip()
    if not game or not user:
        return _json_error("game 与 user 为必填")
    # no password required for web access; just report existence
    exists = FishPlayer.try_get(user) is not None
    return jsonify({"code": 0, "firstLogin": not exists})


@quart_app.route("/fishgame/api/player", methods=["POST"])  # POST for simplicity
async def fishgame_player_info():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("game 与 user 为必填")
    player = FishPlayer.try_get(user) or FishPlayer(user)
    # Return a compact view
    out = {
        "qq": user,
        "name": player.name,
        "level": player.level,
        "exp": player.exp,
        "nextExp": player.get_target_exp(player.level),
        "gold": player.gold,
        "score": player.score,
        "fishCount": len(player.fish_log),
        "power": player.power,
        "feverPower": player.fever_power,
        "bag": player.bag.items,
        "equipment": player.equipment.data if hasattr(player, 'equipment') else {"ids": {}, "details": {}},
        "skills": player.get_equipped_skills(),
        "buffs": player.buff,
    }
    return jsonify({"code": 0, "player": out})


@quart_app.route("/fishgame/api/player/rename", methods=["POST"])
async def fishgame_player_rename():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    new_name = str((payload or {}).get("name", "")).strip()
    if not game or not user:
        return _json_error("game 与 user 为必填")
    if not new_name:
        return _json_error("昵称不能为空")
    if len(new_name) > 20:
        return _json_error("昵称长度需在 1-20 个字符内")

    player = FishPlayer(user)
    player.data["name"] = new_name
    player.save()
    return jsonify({"code": 0, "message": "昵称更新成功", "name": new_name})


@quart_app.route("/fishgame/api/signin", methods=["POST"])
async def fishgame_sign_in():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.sign_in(player)
    return jsonify(res)


@quart_app.route("/fishgame/api/catch", methods=["POST"])
async def fishgame_catch_attempt():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    master_ball = bool((payload or {}).get("masterBall", False))
    if not game or not user:
        return _json_error("game 与 user 为必填")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    fish_before = game_obj.current_fish.data if game_obj.current_fish else None
    res = game_obj.catch_fish(player, master_ball)
    fish_still = game_obj.current_fish is not None

    if fish_before:
        display = player.name or user
        await push_web_event(
            str(game),
            {
                "type": "catch",
                "by": user,
                "display": display,
                "fish": fish_before,
                "code": res.get("code"),
                "message": res.get("message"),
                "success": res.get("code") == 0,
                "fishStillPresent": fish_still,
                "isFever": game_obj.is_fever,
                "source": "web",
            },
        )

    return jsonify(res)


@quart_app.route("/fishgame/api/shop/list", methods=["GET"])
async def fishgame_shop_list():
    # Return buyable items
    items = [it.data for it in fish_item.values() if it.buyable]
    return jsonify({"code": 0, "items": items})


@quart_app.route("/fishgame/api/dashboard", methods=["POST"])
async def fishgame_dashboard():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    game_obj.refresh_buff()
    try:
        game_obj.update_average_power([user])
    except Exception:
        pass

    pool_info = _build_pool_snapshot(game_obj)
    pot_info = _build_pot_snapshot(game_obj)
    buildings = _build_building_snapshot(game_obj)

    cooldown_seconds = 0
    try:
        last_build = float(player.data.get('last_build_time', 0) or 0)
        cooldown_window = game_obj.building_center.build_cooldown * 3600
        cooldown_seconds = max(0, int(last_build + cooldown_window - time.time()))
    except Exception:
        cooldown_seconds = 0

    dashboard = {
        "pool": pool_info,
        "pot": pot_info,
        "buildings": buildings,
        "buildCooldownSeconds": cooldown_seconds,
        "timestamp": int(time.time()),
    }
    return jsonify({"code": 0, "dashboard": dashboard})


@quart_app.route("/fishgame/api/pot/add", methods=["POST"])
async def fishgame_pot_add():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    item_id = int((payload or {}).get("item_id", 0))
    count = max(1, int((payload or {}).get("count", 1)))
    if not game or not user or item_id <= 0:
        return _json_error("缺少必要参数")

    item = FishItem.get(item_id)
    if item.rarity > 3:
        return _json_error("限制：只能添加稀有度不超过 3 的物品到大锅中")
    if not item:
        return _json_error("未找到该物品", status=404)

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.pot_add_item(player, item, count)
    return jsonify(res)


@quart_app.route("/fishgame/api/buildings/add", methods=["POST"])
async def fishgame_building_add():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    building_name = str((payload or {}).get("building", "")).strip()
    item_id = int((payload or {}).get("item_id", 0))
    if not game or not user or not building_name or item_id <= 0:
        return _json_error("缺少必要参数")

    if building_name not in building_name_map:
        building_name = _BUILDING_LABELS.get(building_name, building_name)
        if building_name not in building_name_map:
            return _json_error("未知的建筑")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.build(player, building_name, item_id)
    return jsonify(res)


@quart_app.route("/fishgame/api/buildings/upgrade", methods=["POST"])
async def fishgame_building_upgrade():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    building_name = str((payload or {}).get("building", "")).strip()
    if not game or not building_name:
        return _json_error("缺少必要参数")

    if building_name not in building_name_map:
        building_name = _BUILDING_LABELS.get(building_name, building_name)
        if building_name not in building_name_map:
            return _json_error("未知的建筑")

    game_obj = ensure_game(game)
    res = game_obj.building_level_up(building_name)
    return jsonify(res)


@quart_app.route("/fishgame/api/skills", methods=["GET"])
async def fishgame_skill_catalog():
    skill_payload = [sk.data for sk in fish_skills.values()]
    skill_payload.sort(key=lambda item: item.get("id", 0))
    return jsonify({"code": 0, "skills": skill_payload})


@quart_app.route("/fishgame/api/shop/buy", methods=["POST"])
async def fishgame_shop_buy():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    item_id = int((payload or {}).get("item_id", 0))
    if not game or not user or item_id <= 0:
        return _json_error("缺少 game、user 或 item_id")
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.shop_buy(player, item_id)
    return jsonify(res)


@quart_app.route("/fishgame/api/inventory/use", methods=["POST"])
async def fishgame_use_item():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    item_id = int((payload or {}).get("item_id", 0))
    force = bool((payload or {}).get("force", False))
    raw_params = payload.get("params", [])
    if not game or not user or item_id <= 0:
        return _json_error("缺少 game、user 或 item_id")
    if isinstance(raw_params, list):
        extra_args = raw_params
    elif isinstance(raw_params, str):
        extra_args = [raw_params]
    else:
        extra_args = []
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.use_item(player, item_id, force, extra_args)
    return jsonify(res)


@quart_app.route("/fishgame/api/gacha/draw", methods=["POST"])
async def fishgame_gacha_draw():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    mode = str((payload or {}).get("mode", "standard")).strip().lower()
    draw_type = (payload or {}).get("draw_type") or (payload or {}).get("type") or "single"
    if not game or not user:
        return _json_error("缺少 game 或 user")

    flags = _resolve_draw_flags(draw_type)
    if flags is None:
        return _json_error("未知的抽取次数类型")
    ten_time, hundred_time, thousand_time = flags

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    if mode in ("standard", "normal"):
        res = game_obj.gacha(player, ten_time=ten_time, hundred_time=hundred_time, thousand_time=thousand_time)
    elif mode == "mystery":
        res = game_obj.mystery_gacha(player, ten_time=ten_time, hundred_time=hundred_time, thousand_time=thousand_time)
    else:
        return _json_error("未知的抽取模式")
    return jsonify(res)


@quart_app.route("/fishgame/api/compose/list", methods=["POST"])
async def fishgame_compose_list():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    craftables = game_obj.get_craftable_items()
    eq_ids = getattr(player.equipment, "ids", [])
    items_payload = [_craftable_item_payload(item, player, game_obj, eq_ids) for item in craftables]
    items_payload.sort(key=lambda entry: str(entry["id"]))
    return jsonify({"code": 0, "items": items_payload})


@quart_app.route("/fishgame/api/compose", methods=["POST"])
async def fishgame_compose():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    raw_item_id = (payload or {}).get("item_id")
    if raw_item_id is None:
        raw_item_id = (payload or {}).get("target_id")
    try:
        item_id = int(raw_item_id)
    except (TypeError, ValueError):
        item_id = 0
    if not game or not user or item_id <= 0:
        return _json_error("缺少 game、user 或 item_id")

    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.craft_item(player, item_id)
    return jsonify(res)


@quart_app.route("/fishgame/api/port/status", methods=["POST"])
async def fishgame_port_status():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    port_payload = _build_port_payload(game_obj, player)
    return jsonify({"code": 0, "port": port_payload})


@quart_app.route("/fishgame/api/port/join", methods=["POST"])
async def fishgame_port_join():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    nickname = str((payload or {}).get("nickname", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    display_name = nickname or player.name or user
    res = game_obj.join_oversea(player, display_name)
    if res.get("code") == 0:
        await _broadcast_oversea_update(game, game_obj)
    return jsonify(res)


@quart_app.route("/fishgame/api/port/leave", methods=["POST"])
async def fishgame_port_leave():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.leave_oversea(player)
    if res.get("code") == 0:
        await _broadcast_oversea_update(game, game_obj)
    return jsonify(res)


@quart_app.route("/fishgame/api/port/equip", methods=["POST"])
async def fishgame_port_equip():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    item_id = (payload or {}).get("item_id")
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        item_id = 0
    if not game or not user or item_id <= 0:
        return _json_error("缺少 game、user 或 item_id")
    game_obj = ensure_game(game)
    player = FishPlayer(user)
    res = game_obj.equip_oversea_item(player, item_id)
    if res.get("code") == 0:
        await _broadcast_oversea_update(game, game_obj)
    return jsonify(res)


@quart_app.route("/fishgame/api/port/start", methods=["POST"])
async def fishgame_port_start():
    payload = await request.get_json(force=True)
    game = str((payload or {}).get("game", "")).strip()
    user = str((payload or {}).get("user", "")).strip()
    if not game or not user:
        return _json_error("缺少 game 或 user")
    game_obj = ensure_game(game)
    res = game_obj.start_oversea_battle()
    if res.get("code") == 0:
        await _broadcast_oversea_update(game, game_obj)
    return jsonify(res)


@quart_app.websocket("/fishgame/ws")
async def fishgame_ws():
    ws = websocket._get_current_object()
    try:
        # expect first message to be an identify payload
        raw = await ws.receive()
        data = json.loads(raw or "{}")
        if data.get("type") != "identify":
            await ws.send(json.dumps({"type": "error", "message": "must identify first"}))
            return
        game = str(data.get("game", "")).strip()
        user = str(data.get("user", "")).strip()
        if not game or not user:
            await ws.send(json.dumps({"type": "error", "message": "missing game/user"}))
            return

        try:
            history_messages = WsMessageStore(game).tail(200)
        except Exception:
            logger.exception("Failed to load websocket history for game %s", game)
            history_messages = []

        _GROUP_CONNECTIONS.setdefault(game, set()).add(ws)
        await ws.send(json.dumps({"type": "connected", "game": game, "user": user}))

        for entry in history_messages:
            try:
                history_payload = dict(entry)
                history_payload.setdefault("history", True)
                await ws.send(json.dumps(history_payload))
            except Exception:
                break

        while True:
            raw = await ws.receive()
            if raw is None:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "spawn":
                # broadcast spawn to this group
                await _broadcast(game, {"type": "spawn", "by": user, "fish": msg.get("fish")})
            elif mtype == "catch":
                await _broadcast(game, {"type": "catch", "by": user, "fish": msg.get("fish"), "result": msg.get("result")})
            elif mtype == "chat":
                text = str(msg.get("text", "")).strip()
                if not text:
                    continue
                text = text[:200]
                display = str(msg.get("name") or user).strip() or user
                payload = {
                    "type": "chat",
                    "user": user,
                    "display": display[:40],
                    "text": text,
                    "timestamp": int(time.time()),
                }
                await _broadcast(game, payload)
            elif mtype == "ping":
                await ws.send(json.dumps({"type": "pong"}))
    except Exception:
        logger.exception('error when connect ws:')
        pass
    finally:
        # cleanup
        try:
            for conns in _GROUP_CONNECTIONS.values():
                if ws in conns:
                    conns.remove(ws)
        except Exception:
            pass


def has_online_clients(game_id: str) -> bool:
    """Return True if the given fishgame (group) currently has active websocket clients."""
    return bool(_GROUP_CONNECTIONS.get(str(game_id), set()))

def online_clients_group_list() -> list[str]:
    """Return a list of game ids (groups) that currently have active websocket clients."""
    return [gid for gid, conns in _GROUP_CONNECTIONS.items() if conns]


async def push_web_event(game_id: str, payload: dict):
    """Public helper so other modules (cron jobs) can broadcast structured events."""
    await _broadcast(str(game_id), payload)
