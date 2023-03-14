from typing import Optional
from nonebot import on_command, on_notice, get_driver
from nonebot.log import logger
from nonebot.params import CommandArg, EventMessage
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Message, Event, Bot, MessageSegment
from nonebot.exception import IgnoredException
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.message import event_preprocessor, run_postprocessor
from src.libraries.image import *
import time

from src.data_access.plugin_manager import plugin_manager


@event_preprocessor
async def preprocessor(bot, event, state):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")


last_call_time = 0
last_fail_time = 0
failed_count = 0

@run_postprocessor
async def _(bot: Bot, event, matcher: Matcher, exception: Optional[Exception]):
    global last_call_time
    global last_fail_time
    global failed_count
    if not exception:
        return
        
    try:
        raise exception
    except ActionFailed as err:
        print(err.__dict__)
        if err.info['msg'] == 'SEND_MSG_API_ERROR':
            if time.time() - last_fail_time < 180:
                logger.error(f"Send message error, count {failed_count}")
                last_fail_time = time.time()
                failed_count += 1
                if failed_count > 5 and time.time() - last_call_time > 300:
                    last_call_time = time.time()
                    await bot.send_msg(message_type="private", user_id=2300756578, message="爹，救我")
                    await bot.send_msg(message_type="private", user_id=1131604199, message="妈，救我")
                    return
            else:
                last_fail_time = time.time()
                failed_count = 0
        else:
            raise err

help = on_command('help')


@help.handle()
async def _(bot: Bot, event: Event, state: T_State):
    help_str = ''''''
    await help.send(Message([
        MessageSegment("image", {
            "file": f"base64://{str(image_to_base64(text_to_image(help_str)), encoding='utf-8')}"
        })
    ]))


async def _group_poke(bot: Bot, event: Event) -> bool:
    value = (event.notice_type == "notify" and event.sub_type == "poke" and event.target_id == int(bot.self_id))
    return value


poke = on_notice(rule=_group_poke, priority=10, block=True)


@poke.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if event.__getattribute__('group_id') is None:
        event.__delattr__('group_id')
    await poke.send(Message([
        MessageSegment("poke",  {
           "qq": f"{event.sender_id}"
       })
    ]))


plugin_manage = on_command("插件管理")


@plugin_manage.handle()
async def _(bot: Bot, event: Event, message: Message = CommandArg()):
    if not hasattr(event, 'group_id'):
        await plugin_manage.send("千雪私聊默认启用所有功能，请于群聊中使用此命令")
        return
    is_superuser = str(event.user_id) in get_driver().config.superusers
    print(is_superuser)
    is_group_admin = (await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id))['role'] != "member"
    argv = str(message).strip()
    print(argv)
    if argv == "":
        s = '\n'.join([f"{'√' if v else '×'}{k}" for k, v in plugin_manager.get_all(event.group_id).items()])
        await plugin_manage.send("当前插件列表：\n" + s)
        return
    if not is_superuser and not is_group_admin:
        await plugin_manage.send("权限不足，请检查权限后再试")
        return
    args = argv.split(' ')
    try:
        if len(args) != 2:
            raise Exception
        if args[1] not in plugin_manager.get_all(event.group_id):
            await plugin_manage.send(f"未找到名为{args[1]}的插件")
            return
        if args[0] == "启用":
            plugin_manager.set_enable(event.group_id, args[1], True)
        elif args[0] == "禁用":
            plugin_manager.set_enable(event.group_id, args[1], False)
        else:
            raise Exception
        s = '\n'.join([f"{'√' if v else '×'}{k}" for k, v in plugin_manager.get_all(event.group_id).items()])
        await plugin_manage.send("修改成功，当前插件列表：\n" + s)
        return
    except Exception:
        await plugin_manage.send("格式错误，正确格式为：插件管理 启用/禁用 [插件名]")


is_alive = on_command("千雪")


@is_alive.handle()
async def _(bot: Bot, message: Message = CommandArg()):
    print(str(message).strip())
    if str(message).strip() == "":
        await is_alive.finish("我在")


