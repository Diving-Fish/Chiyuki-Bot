import asyncio
import random
import aiohttp
from io import BytesIO

from nonebot import on_command, on_notice, get_driver
from nonebot.params import CommandArg, EventMessage, Depends
from nonebot.typing import T_State
from nonebot.adapters import Message, Event, Bot
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from nonebot_plugin_alconna import UniMessage
from src.libraries.image import *
from src.libraries.pokemon_img import get_image, get_not_every_effective_types, get_not_every_effective_list, pokedex
from src.libraries.showdown_data_fetch import get_tier_score, parse_pokemon_showdown_user_html, format_player_ratings
from src.libraries.poke_dmg_calc import DamageCalc, types_cn, types, species_en2zh, abilities_en2zh
from src.data_access.plugin_manager import plugin_manager
from src.data_access.open_helper import RealContext, get_real_context
from src.data_access.redis import redis_global, RedisData
from private.libraries.poke_match.match10v1 import try_update_tricolor
import os
import requests

__plugin_meta = {
    "name": "宝可梦",
    "enable": True,
    "help_text": """可用命令列表：
- poke [宝可梦名]：查询宝可梦数据
- 伤害计算：请使用【伤害计算 帮助】查看命令格式
- 进攻盲点：请使用【进攻盲点 帮助】查看命令格式""",
}

plugin_manager.register_plugin(__plugin_meta)

async def __group_checker(bot: Bot, event: Event):
    if hasattr(event, 'group_openid') and bot.type == 'QQ' and bot.self_id != str(get_driver().config.pokemon_bot):
        return False
    elif not hasattr(event, 'group_id') or hasattr(event, 'group_openid'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])

def reply_text(ctx: RealContext, text: str) -> UniMessage:
    """Create a text reply that quotes the triggering message when possible."""
    message = UniMessage.text(text)
    if getattr(ctx, "message_id", None):
        return UniMessage.reply(ctx.message_id) + message
    return message


def reply_image(ctx: RealContext, image_data) -> UniMessage:
    """Create an image reply using raw bytes or in-memory images."""
    buffer = BytesIO()
    if hasattr(image_data, "save"):
        image_data.save(buffer, format="PNG")
    elif isinstance(image_data, (bytes, bytearray)):
        buffer.write(image_data)
    elif isinstance(image_data, str):
        path = image_data[7:] if image_data.startswith("file://") else image_data
        with open(path, "rb") as fp:
            buffer.write(fp.read())
    else:
        raise ValueError("Unsupported image data type for reply_image")
    buffer.seek(0)
    message = UniMessage.image(raw=buffer)
    if getattr(ctx, "message_id", None):
        return UniMessage.reply(ctx.message_id) + message
    return message

pokemon = on_command('poke', rule=__group_checker)

@pokemon.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    arg = str(message).strip()
    try:
        data = get_image(arg)
    except Exception as e:
        await reply_text(ctx, "查询出错：" + str(e)).send()
        return
    if isinstance(data, str):
        await reply_image(ctx, os.path.join(os.getcwd(), data)).send()
    elif data is not None:
        await reply_image(ctx, data).send()
    else:
        await reply_text(ctx, f"未找到名为【{arg}】的宝可梦~").send()
        return


dmgcalc = on_command("伤害计算", rule=__group_checker)

@dmgcalc.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    argv = str(message).strip()
    if argv == "帮助":
        s = '''伤害计算格式为
伤害计算 [攻击方宝可梦] [招式] [防御方宝可梦]
宝可梦均为 50 级

宝可梦可以设置如下参数，以空格隔开，最后一个参数为宝可梦：
252C/252+SpA/252-spa：设置努力值/性格修正
31ivatk/31iva：设置个体值
太晶火：设置太晶属性
-6~+6：设置能力变化

道具直接写道具名字在宝可梦前面
不会自动猜测特性，特性请写在宝可梦前面

天气、场地、状态等参数可以直接写在宝可梦前面

您可以使用 【伤害计算 vgc】或【伤害计算 singles】来快速切换对战模式'''
        await reply_image(ctx, text_to_image(s)).send()
        return
    try:
        key = f"grp{getattr(ctx, 'group_id')}" or str(ctx.user_id)
        mode = RedisData(f"dmgcalc_mode_{key}")
        if argv.strip() == "vgc":
            mode.data = "vgc"
            mode.save()
            await reply_text(ctx, "已切换至 VGC 模式").send()
            return
        elif argv.strip() == "singles":
            mode.data = "singles"
            mode.save()
            await reply_text(ctx, "已切换至 Singles 模式").send()
            return
        result = await DamageCalc(argv, preset=mode.data).execute()
        await reply_text(ctx, result).send()
    except Exception as e:
        await reply_text(ctx, f"{e}\n格式错误，请使用 伤害计算 帮助 查看命令格式").send()
        return


nve = on_command('进攻盲点')
@nve.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    args = str(message).strip().split()
    if str(message).strip() == '帮助':
        await reply_text(ctx, "进攻盲点格式为：\n进攻盲点 [属性] [属性] ...\n以 . 头的宝可梦属性名表示非本系，从第四个属性开始也认为是非本系，如强制视为本系请以 * 开头\n例如：\n进攻盲点 电 .冰 .岩石").send()
        return
    if len(args) == 0:
        await reply_text(ctx, "请输入至少一个属性").send()
        return
    args_type = []
    for i, key in enumerate(args):
        stab = True
        if i >= 3:
            stab = False
        if key.startswith('.') or key.startswith('。'):
            key = key[1:]
            stab = False
        if key.startswith('*'):
            key = key[1:]
            stab = True
        if key in types_cn:
            args_type.append((types[types_cn.index(key)], 1.5 if stab else 1))
        elif key in types:
            args_type.append((key, 1.5 if stab else 1))
        else:
            await reply_text(ctx, f"错误：未知属性 {key}，请使用【进攻盲点 帮助】查看命令格式").send()
            return
    nve_types = get_not_every_effective_types(args_type)
    nve_pokes = get_not_every_effective_list(args_type)
    sorted_keys = sorted(nve_pokes.keys(), key=lambda x: get_tier_score(x), reverse=True)
    sorted_keys = list(filter(lambda x: get_tier_score(x) > 0, sorted_keys))
    sorted_keys = sorted_keys[:15]
    type_output_list = []
    for type in nve_types:
        type_output_list.append(f"{'+'.join([types_cn[types.index(t)] for t in type])}")

    poke_output_list2 = []
    poke_output_list = []
    for key in sorted_keys:
        value = nve_pokes[key]
        poke = pokedex[key]
        poke_name = species_en2zh[poke['name']]
        for item in value:
            if item == 'default':
                poke_output_list2.append(poke_name)
                break
            else:
                ability_name = abilities_en2zh[item]
                poke_output_list.append(f"{poke_name}（{ability_name}）")

    output = '进攻属性：'
    for type, eff in args_type:
        type_cn = types_cn[types.index(type)]
        if eff == 1.5:
            output += f"{type_cn}（本系）"
        else:
            output += f"{type_cn}（非本系）"
    output += '\n'
    if len(type_output_list) == 0:
        output += '该进攻属性组合没有任何属性盲点\n'
    if len(poke_output_list) == 0 and len(poke_output_list2) == 0:
        output += '没有任何能抵抗该进攻属性组合的宝可梦\n'
    if len(type_output_list) > 0:
        output += '属性盲点：' + '，'.join(type_output_list) + '\n'
    if len(poke_output_list2) > 0:
        output += '比如：' + '，'.join(poke_output_list2[:15]) + '\n'
        if len(poke_output_list2) > 15:
            output += f'（仅显示前 15 个）'
    if len(poke_output_list) > 0:
        output += '此外，有这些不符合该属性盲点，但是具有对应抵抗或免疫特性的宝可梦：' + '，'.join(poke_output_list[:15]) + '\n'
        if len(poke_output_list) > 15:
            output += f'（仅显示前 15 个）'
    
    await reply_text(ctx, output).send()


query_showdown = on_command("查ps", rule=__group_checker)

@query_showdown.handle()
async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
    gid = getattr(ctx, "group_id", 0)
    user_id = str(ctx.user_id)
    if gid != 0:
        if redis_global.exists(f'query_showdown_{gid}_{user_id}'):
            await reply_text(ctx, "为防止刷屏，60秒内只能查询一次").send()
            return
    
    username = str(message).strip().replace(' ', '').replace('-', '')
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://pokemonshowdown.com/users/{username}') as response:
            if response.status == 200:
                content = await response.text()
                results = parse_pokemon_showdown_user_html(content)
                await reply_text(ctx, format_player_ratings(results)).send()
            elif response.status == 404:
                await reply_text(ctx, f'未找到玩家：{username}').send()
            else:
                await reply_text(ctx, f"查询失败，状态码：{response.status}").send()
    redis_global.setex(f'query_showdown_{gid}_{user_id}', 60, 1)
    

# tricolor = on_command("抽三色")

# @tricolor.handle()
# async def _(ctx: RealContext = Depends(get_real_context), message: Message = CommandArg()):
#     result = random.sample(types_cn[:-1], 3)
#     result_en = [types[types_cn.index(t)] for t in result]
#     try_update_tricolor(str(event.user_id), result_en)
#     await tricolor.send(Message([
#         MessageSegment.reply(event.message_id),
#         MessageSegment.text('，'.join(result))
#     ]))