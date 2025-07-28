import asyncio
from nonebot import on_command, on_notice, get_driver
from nonebot.params import CommandArg, EventMessage
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, Event, Bot, MessageSegment
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from src.libraries.image import *
from src.libraries.pokemon_img import get_image, get_not_every_effective_types, get_not_every_effective_list, pokedex
from src.libraries.showdown_data_fetch import get_tier_score
from src.libraries.poke_dmg_calc import DamageCalc, types_cn, types, species_en2zh, abilities_en2zh
from src.data_access.plugin_manager import plugin_manager
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

async def __group_checker(event: Event):
    if hasattr(event, 'message_type') and event.message_type == 'channel':
        return False
    elif not hasattr(event, 'group_id'):
        return True
    else:
        return plugin_manager.get_enable(event.group_id, __plugin_meta["name"])

pokemon = on_command('poke', rule=__group_checker)

@pokemon.handle()
async def _(event: Event, message: Message = CommandArg()):
    arg = str(message).strip()
    try:
        data = get_image(arg)
    except Exception as e:
        await pokemon.send("查询出错：" + str(e))
        return
    if type(data) == type(""):
        await pokemon.send(Message([
            MessageSegment("image", {
                "file": f"file://{os.getcwd()}/{data}"
            })
        ]))
    elif data is not None:
        await pokemon.send(Message([
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(data), encoding='utf-8')}"
            })
        ]))
    else:
        await pokemon.send(f"未找到名为【{arg}】的宝可梦~")
        return


dmgcalc = on_command("伤害计算", rule=__group_checker)

@dmgcalc.handle()
async def _(event: Event, message: Message = CommandArg()):
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

天气、场地、状态等参数可以直接写在宝可梦前面'''
        await dmgcalc.send(Message([
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(text_to_image(s)), encoding='utf-8')}"
            })
        ]))
        return
    try:
        result = await DamageCalc(argv).execute()
        await dmgcalc.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text(result)
        ]))
    except Exception as e:
        await dmgcalc.send(f"{e}\n格式错误，请使用 伤害计算 帮助 查看命令格式")
        return


nve = on_command('进攻盲点')
@nve.handle()
async def _(event: Event, message: Message = CommandArg()):
    args = str(message).strip().split()
    if str(message).strip() == '帮助':
        await nve.send("进攻盲点格式为：\n进攻盲点 [属性] [属性] ...\n以 . 头的宝可梦属性名表示非本系，从第四个属性开始也认为是非本系\n例如：\n进攻盲点 电 .冰 .岩石")
        return
    if len(args) == 0:
        await nve.send("请输入至少一个属性")
        return
    args_type = []
    for i, key in enumerate(args):
        stab = True
        if i >= 3:
            stab = False
        if key.startswith('.') or key.startswith('。'):
            key = key[1:]
            stab = False
        if key in types_cn:
            args_type.append((types[types_cn.index(key)], 1.5 if stab else 1))
        elif key in types:
            args_type.append((key, 1.5 if stab else 1))
        else:
            await nve.send(f"错误：未知属性 {key}，请使用【进攻盲点 帮助】查看命令格式")
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
    
    await nve.send(Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(output)
    ]))
