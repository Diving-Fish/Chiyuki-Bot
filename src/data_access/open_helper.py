from dataclasses import dataclass
from typing import Optional, Union
from nonebot import logger
from nonebot.adapters import Event, Bot
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.adapters.qq import GroupAtMessageCreateEvent as QQGroupEvent
from nonebot.adapters.onebot.v11 import GroupMessageEvent as OneBotGroupEvent

from src.data_access.redis import DictRedisData

# --- 1. 定义一个数据模型，用来给 Handler 传参 ---
@dataclass
class RealContext:
    group_id: int
    user_id: int
    message_id: Union[str, int]
    is_official: bool  # 标记一下来源，方便业务区分

# --- 2. 模拟你的本地映射表 (实际使用时换成数据库查询) ---

def db_get_real_group(openid: str) -> Optional[int]:
    return DictRedisData("open_helper_group_map").data.get(openid)

def db_get_real_user(openid: str) -> Optional[int]:
    return DictRedisData("open_helper_user_map").data.get(openid)

async def get_real_context(bot: Bot, event: Event, matcher: Matcher) -> RealContext:
    """
    依赖注入函数：
    1. 判断平台
    2. 如果是官方Bot，查表转换 ID
    3. 如果查不到，报错或拦截
    """
    
    # === 情况 A: 如果是 OneBot (NapCat) ===
    # 本身就是真实的 ID，直接透传，不做多余操作
    if isinstance(event, OneBotGroupEvent):
        return RealContext(
            group_id=event.group_id,
            user_id=event.user_id,
            message_id=event.message_id,
            is_official=False
        )

    # === 情况 B: 如果是 官方Bot (QQ Adapter) ===
    # 包含了 消息事件 和 交互事件(/指令)
    if isinstance(event, QQGroupEvent):
        # 1. 获取 OpenID
        # 注意：不同事件获取 group_openid 的属性可能略有不同，建议用 getattr 安全获取
        group_openid = getattr(event, "group_openid", None)
        user_openid = event.get_user_id() # 官方适配器通用方法

        # --- 逻辑 1: 检查群映射 ---
        if not group_openid:
            # 理论上群事件一定有 OpenID，如果没有，说明可能是私聊触发了群指令
            logger.error("【严重】检测到来自官方Bot的事件没有 group_openid，忽略处理。")
            await matcher.finish() # 直接结束
            
        real_group_id = db_get_real_group(group_openid)

        # --- 逻辑 2: 检查用户映射 ---
        real_user_id = db_get_real_user(user_openid)
        
        if not real_user_id:
            # 【需求实现】如果是用户的表没找到，则 finish 一条指令给用户
            logger.warning(f"【用户未绑定】User OpenID [{user_openid}] 未找到绑定记录。")
            # 这里可以发一段指引文本，或者卡片
            # await matcher.finish("当前没有鱼")
            if real_group_id:
                await matcher.finish("您的QQ账号还未绑定，请at我使用“绑定用户”命令进行绑定后重试。")
            real_user_id = int(user_openid, 16)
        
        if not real_group_id:
            # 【需求实现】如果没有查到群信息，logger 报错，不给用户反馈
            logger.warning(f"【映射失败】未找到 Group OpenID [{group_openid}] 对应的真实群号！请检查数据库。")
            # 这里必须 finish 或者抛出异常停止，否则业务逻辑拿到 None 会崩
            # await matcher.finish('当前没有鱼') 
            real_group_id = int(group_openid, 16)

        # --- 全部成功，返回注入对象 ---
        return RealContext(
            group_id=real_group_id,
            user_id=real_user_id,
            message_id=event.id,
            is_official=True
        )

    # === 情况 C: 其他未知情况 ===
    logger.warning("收到未知适配器事件，跳过处理")
    await matcher.finish()