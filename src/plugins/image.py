from src.libraries.image import *
from nonebot import on_command, on_message, on_notice, on_regex
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot
from nonebot.adapters.cqhttp import Message


high_eq = on_regex('低情商.+高情商.+')


@high_eq.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = '低情商(.+)高情商(.+)'
    groups = re.match(regex, str(event.get_message())).groups()
    left = groups[0].strip()
    right = groups[1].strip()
    if len(left) > 15 or len(right) > 15:
        await high_eq.send("为了图片质量，请不要多于15个字符")
        return
    img_p = Image.open(path)
    draw_text(img_p, left, 0)
    draw_text(img_p, right, 400)
    await high_eq.send(Message([{
        "type": "image",
        "data": {
            "file": f"base64://{str(image_to_base64(img_p), encoding='utf-8')}"
        }
    }]))


jlpx = on_command('金龙盘旋')


@jlpx.handle()
async def jlpx(bot: Bot, event: Event, state: T_State):
    argv = str(event.get_message()).strip().split(' ')
    if len(argv) != 3:
        await jlpx.send("金龙盘旋需要三个参数")
    url = await get_jlpx(argv[0], argv[1], argv[2])
    await jlpx.send(Message([{
        "type": "image",
        "data": {
            "file": f"{url}"
        }
    }]))