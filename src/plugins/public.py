from typing import Optional
from nonebot import on_command, on_notice, get_driver, get_bot
from nonebot.log import logger
from nonebot.params import CommandArg, EventMessage, Arg, ArgPlainText
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Message, Event, Bot, MessageSegment
from nonebot.exception import IgnoredException
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.message import event_preprocessor, run_postprocessor
from src.libraries.image import *
from src.data_access.redis import NumberRedisData
import time
import os
import uuid
import aiohttp
import random
import asyncio

from src.data_access.plugin_manager import plugin_manager


def is_channel_message(event: Event):
    return hasattr(event, 'message_type') and event.message_type == 'guild'

@event_preprocessor
async def preprocessor(bot, event, state):
    # if is_channel_message(event):
    #     qq = NumberRedisData(f'channel_bind_{event.user_id}')
    #     setattr(event, 'converted', qq.data != 0)       
    #     setattr(event, 'sender_id', qq.data if qq.data != 0 else event.user_id)
    # elif hasattr(event, 'user_id'):
    #     setattr(event, 'sender_id', event.user_id)
    #print(event.__dict__)
            
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")
    pass


last_call_time = 0
last_fail_time = 0
failed_count = 0

@run_postprocessor
async def _(bot: Bot, event, matcher: Matcher, exception: Optional[Exception]):
    pass

cuid = on_command('cuid')
@cuid.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if is_channel_message(event):
        await cuid.send('您的频道 ID 为： ' + str(event.user_id))

rdm = on_command('random')

@rdm.handle()
async def _(bot: Bot, event: Event, message: Message = CommandArg()):
    try:
        arg = int(str(message).strip())
    except Exception:
        await rdm.send('error')
        return
    if arg <= 0:
        await rdm.send('error')
        return
    await rdm.send(str(random.randint(1, arg)))


help = on_command('help')


@help.handle()
async def _(bot: Bot, event: Event, state: T_State, message: Message = CommandArg()):
    arg = str(message).strip()
    if arg == '':
        s = '可用插件帮助列表：'
        for name, value in plugin_manager.get_all(event.group_id).items():
            if value:
                s += f'\nhelp {name}'
        await help.send(s)
        return

    try:
        if not plugin_manager.get_enable(event.group_id, arg):
            raise Exception("插件已禁用")
        meta = plugin_manager.metadata[arg]
        await help.send(Message([
            MessageSegment("image", {
                "file": f"base64://{str(image_to_base64(text_to_image(meta['help_text'])), encoding='utf-8')}"
            })
        ]))
    except Exception:
        await help.send("未找到插件或插件未启用")


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
    is_superuser = str(event.user_id) in get_driver().config.superusers
    if not hasattr(event, 'group_id'):
        if not is_superuser:
            return
        argv = str(message).strip()
        args = argv.split(' ')
        if argv == "":
            await plugin_manage.send("用法：插件管理 <群号> 或 插件管理 <群号> 启用/禁用 [插件名]")
        else:
            group_id = int(args[0])
            if len(args) == 1:
                s = '\n'.join([f"{'√' if v else '×'}{k}" for k, v in plugin_manager.get_all(group_id).items()])
                await plugin_manage.send("当前插件列表：\n" + s)
                return
            else:
                try:
                    if len(args) != 3:
                        raise Exception
                    if args[1] not in ["启用", "禁用"]:
                        raise Exception
                    if args[2] not in plugin_manager.get_all(group_id):
                        await plugin_manage.send(f"未找到名为{args[2]}的插件")
                        return
                    if args[1] == "启用":
                        plugin_manager.set_enable(group_id, args[2], True)
                    elif args[1] == "禁用":
                        plugin_manager.set_enable(group_id, args[2], False)
                    s = '\n'.join([f"{'√' if v else '×'}{k}" for k, v in plugin_manager.get_all(group_id).items()])
                    await plugin_manage.send("修改成功，当前插件列表：\n" + s)
                except Exception:
                    await plugin_manage.send("格式错误，正确格式为：插件管理 <群号> 启用/禁用 [插件名]")
        return
    is_group_admin = (await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id))['role'] != "member"
    argv = str(message).strip()
    print(argv)
    if argv == "":
        s = '\n'.join([f"{'√' if v else '×'}{k}" for k, v in plugin_manager.get_all(event.group_id).items()])
        await plugin_manage.send("当前插件列表：\n" + s)
        return
    if not is_superuser: # and not is_group_admin:
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


shuffle = on_command('shuffle')

@shuffle.handle()
async def _(event: Event, message: Message = CommandArg()):
    try:
        num = int(str(message).strip())
    except Exception:
        await shuffle.send("Usage: shuffle <number>")
    if num > 200:
        await shuffle.send("number should be lower than 200")
    else:
        a = list(range(1, num + 1))
        random.shuffle(a)
        await shuffle.send(', '.join([str(b) for b in a]))


channel_bind = on_command('qq绑定')

@channel_bind.handle()
async def _(event: Event, message: Message = CommandArg()):
    if not is_channel_message(event):
        return
    try:
        val = int(str(message).strip())
        qq = NumberRedisData(f'channel_bind_{event.user_id}')
        qq.save(val)
        await channel_bind.send(f'已绑定频道用户 ID {event.user_id} 到 QQ 号 {val}')
    except Exception:
        await channel_bind.send('绑定的 qq 格式错误，请重试')


get_group_members_by_gid = on_command('获取群成员')

@get_group_members_by_gid.handle()
async def get_group_members_by_gid_impl(event: Event, message: Message = CommandArg()):
    # 如果发送者不是 super user 则返回
    if str(event.user_id) not in get_driver().config.superusers:
        await get_group_members_by_gid.send("您没有权限使用此命令")
        return

    try:
        group_id = int(str(message).strip())
        qq_list = await get_bot().get_group_member_list(group_id=group_id)
        qq_list = [str(qq['user_id']) for qq in qq_list]
        await get_group_members_by_gid.send(f"群成员列表：\n{'\n'.join(qq_list)}")
    except Exception as e:
        await get_group_members_by_gid.send(f"获取群成员失败：{str(e)}")
        logger.error(f"获取群成员失败：{str(e)}")
        raise e


async def pic_convert_helper(image_url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image: HTTP {response.status}")
            
            image_data = await response.read()
            
            # 使用 BytesIO 来处理图片数据
            image_buffer = BytesIO(image_data)
            
            # 使用 PIL 打开图片，自动识别格式
            img = Image.open(image_buffer)
            
            # 确定文件扩展名
            format_map = {
                'JPEG': 'jpg',
                'PNG': 'png',
                'WEBP': 'webp',
                'GIF': 'gif'
            }
            
            # 创建 imgcache 目录
            cache_dir = os.path.join(os.getcwd(), 'imgcache')
            os.makedirs(cache_dir, exist_ok=True)
            
            # 如果是 GIF 动图，取第一帧并转换为 PNG
            if img.format == 'GIF':
                filename = f"{uuid.uuid4()}.gif"
                filepath = os.path.join(cache_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                return filepath
            else:
                file_ext = format_map.get(img.format, 'png')
            
            # 如果图片有透明通道但不是 PNG，转换为 PNG
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                if file_ext != 'png':
                    img = img.convert('RGBA')
                    file_ext = 'png'
            else:
                # 没有透明通道，可以保持原格式或转换为 RGB
                if img.mode != 'RGB' and file_ext in ['jpg', 'jpeg']:
                    img = img.convert('RGB')
            
            # 生成唯一文件名
            filename = f"{uuid.uuid4()}.{file_ext}"
            filepath = os.path.join(cache_dir, filename)
            
            # 保存图片
            if file_ext == 'jpg':
                img.save(filepath, format='JPEG', quality=95)
            else:
                img.save(filepath, format=file_ext.upper())
            
            return filepath

get_pic = on_command('获取图片', aliases={'转图'})
@get_pic.handle()
async def handle_function(args: Message = CommandArg()):
    if location := args.extract_plain_text():
        await get_pic.finish(f"错误")

@get_pic.got("location", prompt="请发送表情包")
async def got_location(location: str = ArgPlainText(), args: Message = EventMessage()):
    pic: MessageSegment = args[0]
    image_url = ''
    if pic.type == "image":
        image_url = pic.data['file']
    elif pic.type == "mface":
        image_url = pic.data['url']
    if not image_url:
        await get_pic.finish(f"错误")
    try:
        image_path = await pic_convert_helper(image_url)
        if image_path.endswith('.gif'):
            await get_pic.send(f"http://122.51.105.173:8000/web/image/{image_path.split('/')[-1]}")
        await get_pic.finish(Message([
            MessageSegment.image(f"file://{image_path}", cache=False, proxy=False)
        ]))
    except Exception as e:
        raise e
        # await get_pic.finish(f"转换图片失败：{str(e)}")
        return