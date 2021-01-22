import asyncio

from nonebot import get_driver
import aiohttp
from typing import Optional


driver = get_driver()

__lock = asyncio.Lock()
__ult = ""
__user_id = ""


class WahlapServerClosedError(Exception):
    pass


@driver.on_startup
def _():
    global __ult
    global __user_id
    with open('wahlap_data.txt') as fr:
        __ult = fr.readline().strip()
        __user_id = fr.readline().strip()


@driver.on_shutdown
def _():
    with open('wahlap_data.txt', 'w') as fw:
        fw.write(f'{__ult}\n{__user_id}')


async def get_page(url: str) -> str:
    global __ult
    global __user_id
    async with __lock:
        url = "https://maimai.wahlap.com" + url
        cookies = {'_t': __ult, 'userId': __user_id}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                text = await resp.text()
                __ult = resp.cookies['_t'].value
                __user_id = resp.cookies['userId'].value
    return text


