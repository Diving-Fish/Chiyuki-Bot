import asyncio
from quart import request, Quart
import aiohttp

__lock = asyncio.Lock()
with open('wahlap_data.txt') as fr:
    __ult = fr.readline().strip()
    __user_id = fr.readline().strip()


app = Quart(__name__)


@app.route('/maimai-mobile/<path:url>')
async def get_page(url: str) -> str:
    query = str(request.query_string, encoding='utf-8')
    if query != "":
        url += f'?{query}'
    global __ult
    global __user_id
    async with __lock:
        url = "https://maimai.wahlap.com/maimai-mobile/" + url
        cookies = {'_t': __ult, 'userId': __user_id}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                text = await resp.text()
                __ult = resp.cookies['_t'].value
                __user_id = resp.cookies['userId'].value
        with open('wahlap_data.txt', 'w') as fw:
            fw.write(f'{__ult}\n{__user_id}')
    return text


app.run(port=8080)
