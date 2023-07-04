from nonebot import on_command, on_notice, get_driver
from nonebot.params import CommandArg, EventMessage
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, Event, Bot, MessageSegment
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from src.libraries.image import *
from src.libraries.pokemon_img import get_image, calculate_damage
from src.data_access.plugin_manager import plugin_manager
import os

__plugin_meta = {
    "name": "宝可梦",
    "enable": True,
    "help_text": "",
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
    argv = str(message).strip().split(" ")
    flag = False
    if len(argv) == 1:
        flag = True
        argv.append(1)
    try:
        data, others = get_image(argv[0], int(argv[1]) - 1)
    except Exception as e:
        await pokemon.send("查询出错：" + str(e))
        return
    if type(data) == type(""):
        await pokemon.send(Message([
            MessageSegment("image", {
                "file": f"file:///{os.getcwd()}/{data}"
            })
        ]))
    elif data is not None:
        await pokemon.send(Message([
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(data), encoding='utf-8')}"
            })
        ]))
    else:
        await pokemon.send(f"未找到名为【{argv[0]}】的宝可梦~")
        return
    if len(others) > 1 and flag:
        s = f"""该宝可梦存在其他形态，如果需要查询对应形态请输入poke {argv[0]} <编号>，编号列表如下：\n"""
        for j, o in enumerate(others):
            s += f"{j+1}. {o['name']}\n"
        await pokemon.send(s.strip())


dmgcalc = on_command("伤害计算", rule=__group_checker)

@dmgcalc.handle()
async def _(event: Event, message: Message = CommandArg()):
    argv = str(message).strip()
    if argv == "帮助":
        s = '''伤害计算格式为
伤害计算 [攻击方宝可梦] [招式] [防御方宝可梦] [额外加成]
宝可梦均为 50 级

宝可梦可以设置如下参数，以空格隔开，最后一个参数为宝可梦：
252C/252+SpA/252-特攻：设置努力值/性格修正
31ivatk/31iva：设置个体值
太晶火：设置太晶属性
+0~6：设置能力变化
150%：设置对应项百分比的能力变化，例如

招式可以使用已存在的招式，也可以自由设定威力不同的招式，例如“150飞行物理”
欺诈、精神冲击、打草结、重磅冲撞等招式并未实现，请采用换算方式计算

由于物品、招式和特性均没有实现，所以引入额外加成的概念：
额外加成均为倍率，使用空格隔开，倍率后可以附加不同的字母代表不同的乘算方式，具体如下
无后缀：最终乘区内计算的加成，比如生命宝珠（1.3）
p后缀：代表在属性克制和本系加成之前、但是在技能威力之后计算的乘区，比如晴天（1.5p）
bp后缀：代表直接计算在威力区的加成，例如沙暴下岩石系精灵的特防，讲究眼镜、讲究头带
拍落（1.5bp），技术高手（1.5bp），妖精皮肤（1.2bp），双打对战（0.75bp），木炭（1.2bp）
hit后缀：代表多次攻击，例如种子机关枪（5hit），鼠数儿（10hit）

几个例子：
极限特攻的冰伊布携带讲究眼镜，对沙暴下的班基拉斯使用冰冻光束：
伤害计算 252+spa 150% 冰伊布 冰冻光束 150% 班基拉斯
晴天下双打对战，77%生命值、携带生命宝珠的极限特攻煤炭龟，对极限特耐的多龙巴鲁托使用喷火：
伤害计算 252+spa 煤炭龟 喷火 252hp 252+spd 多龙巴鲁托 0.77bp 0.75bp 1.3 1.5p
极限物攻、技师斗笠菇对无耐久吃吼霸使用五段种子机关枪：
伤害计算 252+atk 斗笠菇 种子机关枪 吃吼霸 1.5bp 5hit'''
        await dmgcalc.send(Message([
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(text_to_image(s)), encoding='utf-8')}"
            })
        ]))
        return
    try:
        result = calculate_damage(argv)
    except Exception as e:
        await dmgcalc.send("格式错误，请使用 伤害计算 帮助 查看命令格式\n" + str(e))
        return
    if len(result['percent']) == 2:
        s = f"> {message}: {result['range'][0]} - {result['range'][1]} ({result['percent'][0]}% - {result['percent'][1]}%)\n"
        s += "单次可能的伤害值：" + ", ".join([str(r) for r in result["int"]])
    else:
        s = f"> {message}: {result['int'][0]} - {result['int'][15]} ({result['percent'][0]}% - {result['percent'][15]}%)\n"
        s += "可能的伤害值：" + ", ".join([str(r) for r in result["int"]])
    await dmgcalc.send(s)

