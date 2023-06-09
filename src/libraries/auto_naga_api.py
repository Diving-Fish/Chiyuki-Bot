from datetime import datetime
from src.data_access.redis import redis_global
import json
from typing import Dict, List, Optional, Union
import aiohttp
from src.data_access.redis import *

BASE_URL = "https://www.diving-fish.com/api/auto_naga"
NAGA_SECRET = "" # will be set then

def set_naga_secret(secret):
    global NAGA_SECRET
    NAGA_SECRET = secret

class AutoNaga:
    def __init__(self) -> None:
        self.majsoul_analyze_queue = []
        self.majsoul_url_map = {}
        self.majsoul_data_map = {}

    async def cost_np(self, user_id, np) -> bool:
        cache_data = NumberRedisData(f'naga_np_{user_id}')
        if cache_data.data > np:
            cache_data.save(cache_data.data - np)
            return True, cache_data.data, np
        return False, cache_data.data, np

    async def get_np(self, user_id) -> int:
        cache_data = NumberRedisData(f'naga_np_{user_id}')
        return cache_data.data

    async def add_np(self, user_id, np) -> None:
        cache_data = NumberRedisData(f'naga_np_{user_id}')
        cache_data.save(cache_data.data + np)

    async def order(self, custom: bool, data: Union[str, List]) -> Dict:
        body = {
            "secret": NAGA_SECRET,
            "custom": custom,
        }
        if custom:
            body['haihus']: List = data
        else:
            body['tenhou_url']: str = data
        
        print(data)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/order", json=body) as resp:
                return json.loads(await resp.text())
            
    # 雀魂需要做缓存
    async def convert_majsoul(self, majsoul_url: str) -> Dict:
        body = {
            "secret": NAGA_SECRET,
            "majsoul_url": majsoul_url
        }

        prefixes = ['https://game.maj-soul.com/1/?paipu=', 'https://game.maj-soul.net/1/?paipu='] # 暂时只考虑支持国服

        haihu_id = ''

        for prefix in prefixes:
            if majsoul_url.startswith(prefix):
                haihu_id = majsoul_url[len(prefix):]
                break

        if haihu_id == '':
            return {"status": 400, "message": "majsoul_url is not valid"}

        cache_data = DictRedisData(f'convert_cache_{haihu_id}')

        index_data = DictRedisData('majsoul_convert_index_map')

        if len(cache_data.data) == 0:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{BASE_URL}/convert_majsoul", json=body) as resp:
                    print(await resp.text())
                    data = json.loads(await resp.text())
                    if data['status'] == 200:
                        majsoul_convert_index = redis_global.incr('majsoul_convert_index')
                        cache_data.save({
                            'majsoul_convert_index': majsoul_convert_index,
                            'message': data['message']
                        }, ex=30 * 24 * 60 * 60) # 1 month
                        index_data.data[majsoul_convert_index] = f'convert_cache_{haihu_id}'
                        index_data.save()
        
        return {"status": 200, "message": cache_data.data['message'], "index": cache_data.data['majsoul_convert_index']}
            
    async def order_report_list(self) -> Dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/order_report_list") as resp:
                return json.loads(await resp.text())
            
    async def get_tenhou_custom_url(self, custom_no, index):
        index_data = DictRedisData('majsoul_convert_index_map')
        cache_data = DictRedisData(index_data.data[str(custom_no)])
        return cache_data.data['message'][index]
    
    async def find_paipu(self, custom: bool, data: str) -> (int, str, str): # code, link, message
        # data will be a time format if custom, or a tenhou url
        if custom:
            ts = datetime.strptime(data, '%Y-%m-%dT%H:%M:%S').timestamp()
            json_data = await self.order_report_list()
            orders = list(filter(lambda e: e[0][:6] == "custom", json_data['order']))
            reports = list(filter(lambda e: e[0][:6] == "custom", json_data['report']))
            min_time = 10
            url = ''
            haihu = ["", 0, [2, 2, 2], 0]
            # 首先检测 order 是否成功
            for o in orders:
                ts2 = datetime.strptime(o[0].split('_')[2], '%Y-%m-%dT%H:%M:%S').timestamp()
                if abs(ts - ts2) < min_time:
                    haihu = o
                    min_time = abs(ts - ts2)
            
            print(haihu)
            if haihu[0] != "":
                if haihu[1] == 3:
                    return 2, "", "牌谱解析失败"
                elif haihu[1] == 0:
                    for r in reports:
                        if r[0] == haihu[0]:
                            break
                    return 0, f'https://naga.dmv.nico/htmls/{r[2]}.html', ""
                else:
                    return 1, "", "牌谱正在解析中"
            return -1, "", "未找到牌谱"
            
        else:
            query_str = data[data.index('?')+1:]
            query = [a.split('=') for a in query_str.split('&')]
            json_data = await self.order_report_list()
            orders = list(filter(lambda e: e[0][:6] != "custom", json_data['order']))
            reports = list(filter(lambda e: e[0][:6] != "custom", json_data['report']))
            haihu = ["", 0, [2, 2, 2], 0]
            for o in orders:
                if o[0] == query[0][1]:
                    haihu = o
                    break

            print(haihu)
            if haihu[0] != "":
                if haihu[1] == 3:
                    return 2, "", "牌谱解析失败"
                elif haihu[1] == 0:
                    for r in reports:
                        if r[0] == haihu[0]:
                            break
                    return 0, f'https://naga.dmv.nico/htmls/{r[2]}.html', ""
                else:
                    return 1, "", "牌谱正在解析中"
            return -1, "", "未找到牌谱"

        return -1, "", "未找到牌谱"

auto_naga = AutoNaga()
