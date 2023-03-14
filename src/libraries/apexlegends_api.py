import aiohttp
from collections import defaultdict
from urllib.parse import quote
from bs4 import BeautifulSoup
import json

YOUR_API_KEY = "" # will be set then

def set_apex_token(token):
    global YOUR_API_KEY
    YOUR_API_KEY = token

class ApexLegendsAPI:
    @staticmethod
    async def player_statistics_uid(uid):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mozambiquehe.re/bridge?auth={YOUR_API_KEY}&uid={uid}&platform=PC") as resp:
                return await resp.text(), resp.status

    @staticmethod
    async def map_rotation():
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mozambiquehe.re/maprotation?auth={YOUR_API_KEY}") as resp:
                return await resp.text(), resp.status

    @staticmethod
    async def crafting():
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mozambiquehe.re/crafting?auth={YOUR_API_KEY}") as resp:
                return await resp.text(), resp.status

    @staticmethod
    async def search_player(player_name):
        res = defaultdict(lambda: {
            "name": "",
            "level": "",
            "selected": "",
            "RP": 0,
        })
        # 此函数将通过橘子 ID 和用户昵称查找可能的用户。
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mozambiquehe.re/bridge?auth={YOUR_API_KEY}&player={player_name}&platform=PC") as resp:
                try:
                    obj = json.loads(await resp.text(encoding='utf-8'))
                    if 'global' in obj:
                        uid = obj['global']['uid']
                        res[uid]['name'] = obj['global']['name']
                        res[uid]['level'] = obj['global']['level'] + obj['global']['levelPrestige'] * 500
                        res[uid]['selected'] = obj['legends']['selected']['LegendName']
                        res[uid]['rp'] = obj['global']['rank']['rankScore']
                except Exception:
                    pass
            async with session.get("https://apexlegendsstatus.com/profile/search/gnivid"):
                # get cookie, then:
                async with session.get(f"https://apexlegendsstatus.com/core/interface?token=HARDCODED&platform=search&player={quote(player_name)}") as resp2:
                    txt = await resp2.text()
                    with open('a.html', 'w', encoding='utf-8') as fw:
                        fw.write(txt)
                    soup = BeautifulSoup(txt, 'html.parser')
                    for o in soup.find_all(class_="col-lg-2 col-md-3 col-sm-4 col-xs-12"):
                        container = list(o.children)[0]
                        a = container.find('a')
                        uid: str = a.attrs['href']
                        platform = uid.split('/')[-2]
                        uid = uid.split('/')[-1]
                        if platform != 'PC':
                            continue
                        uid = int(uid)
                        if uid in res:
                            continue
                        try:
                            ps = list(a.find_all('p'))
                            res[uid]['name'] = ps[0].text
                            b1, b2 = list(ps[1].find_all('b'))
                            res[uid]['level'] = int(b1.text) + int(b2.text) * 500
                            res[uid]['selected'] = ps[2].find('b').text
                            res[uid]['rp'] = int(ps[3].find('b').text.replace(',', ''))
                        except ValueError:
                            # 说明用户没有在 apex legends status 平台上搜索过
                            # 如果它能化成 UID (origin or steam)，那就用 bridge 抓一下，然后返回数据，否则就算了
                            resp3, txt = await ApexLegendsAPI.player_statistics_uid(uid)
                            obj = json.loads(resp3)
                            if 'global' in obj:
                                uid = obj['global']['uid']
                                res[uid]['name'] = obj['global']['name']
                                res[uid]['level'] = obj['global']['level'] + obj['global']['levelPrestige'] * 500
                                res[uid]['selected'] = obj['legends']['selected']['LegendName']
                                res[uid]['rp'] = obj['global']['rank']['rankScore']
            return res
