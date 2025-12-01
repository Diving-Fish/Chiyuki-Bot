import json
import requests
from dataclasses import dataclass, field
from typing import Union, List, Dict
from src.libraries.pokemon_img import get_effectiveness_for_pokemon, type_tbl
    
fish_data: dict[int, 'Fish'] = {}
fish_item: dict[int, 'FishItem'] = {}
fish_skills: dict[int, 'FishSkill'] = {}
weekday_topic = ['', '', '', '', '', '', '']

pokedex_showdown = requests.get('https://www.diving-fish.com/api/pokemon-service/pokedex-showdown').json()
translation_dict = {v: k for k, v in requests.get('https://www.diving-fish.com/api/pokemon-service/translation/pokemon').json().items()}

def get_weakness(pokemon_name: str) -> List[str]:
    pokemon = pokedex_showdown.get(translation_dict[pokemon_name].lower().replace('-', ''), {})
    weaknesses = []
    for type in type_tbl:
        result = get_effectiveness_for_pokemon(pokemon, type)
        if result.get('default', 1) > 1:
            weaknesses.append(type.lower())
    return weaknesses


@dataclass
class Fish:
    id: int
    name: str
    detail: str
    rarity: str
    std_power: int
    base_probability: float
    exp: int
    spawn_at: tuple = ("common",)
    drops: list = field(default_factory=list)
    weakness: List[str] = field(default_factory=list)

    def __init__(self, obj: dict):
        self.id = obj['id']
        self.name = obj['name']
        self.detail = obj['detail']
        self.rarity = obj['rarity']
        self.std_power = obj['std_power']
        self.base_probability = obj['base_probability']
        self.exp = obj['exp']
        self.spawn_at = tuple(obj.get('spawn_at', ("common",)))
        self.drops = obj.get('drops', [])
        self.weakness = get_weakness(self.name)

    @staticmethod
    def get(obj: Union[int, dict]) -> 'Fish':
        if isinstance(obj, int):
            return fish_data.get(obj)
        elif isinstance(obj, dict):
            for fish in fish_data.values():
                if fish.name == obj.get('name') or (fish.exp == obj.get('exp') and fish.std_power == obj.get('std_power')):
                    return fish
            return None
        else:
            return None
        
    @property
    def data(self):
        return {
            "id": self.id,
            "name": self.name,
            "detail": self.detail,
            "rarity": self.rarity,
            "std_power": self.std_power,
            "base_probability": self.base_probability,
            "exp": self.exp,
            "spawn_at": self.spawn_at
        }
    

@dataclass
class FishItem:
    id: int
    name: str
    rarity: int
    description: str
    price: int = 0
    equipable: bool = False
    type: str = ""
    power: int = 0
    power_modifier: dict = field(default_factory=dict)
    craftby: list = field(default_factory=list)
    craft_score_cost: int = 0
    # 合成展示所需的神秘商店等级（默认 -1 不限制，判定为 mystic_shop.level >= craft_shop_level）
    craft_shop_level: int = -1
    # 配件专用字段
    stackable: bool = True
    id_range: int = 0  # 若为配件，表示可用的最大 id（闭区间）
    skill_point: int = 0  # 初始技能点
    skills: list = field(default_factory=list)  # [{id, level}]
    base_id: int = 0  # 若为实例化 accessory，记录其模板 base id
    batch_use: bool = False  # 是否支持批量使用
    batch_craft: bool = False  # 是否支持批量合成

    def __init__(self, obj: dict):
        self.id = obj['id']
        self.name = obj['name']
        self.rarity = obj['rarity']
        self.description = obj['description']
        self.price = obj.get('price', 0)
        self.equipable = obj.get('equipable', False)
        self.type = obj.get('type', "")
        self.power = obj.get('power', 0)
        self.power_modifier = obj.get('power_modifier', {})
        self.craftby = obj.get('craftby', [])
        self.craft_score_cost = obj.get('craft_score_cost', 0)
        self.craft_shop_level = obj.get('craft_shop_level', -1)
        self.stackable = obj.get('stackable', True)
        self.id_range = obj.get('id_range', 0)
        self.skill_point = obj.get('skill_point', obj.get('skill_point', 0))  # 兼容
        self.skills = obj.get('skills', [])
        self.base_id = obj.get('base_id', self.id)
        self.batch_use = obj.get('batch_use', False)
        self.batch_craft = obj.get('batch_craft', False)
    
    @staticmethod
    def get(obj: str) -> 'FishItem':
        try:
            id = int(obj)
            return fish_item.get(id)
        except ValueError:
            if isinstance(obj, str):
                for item in fish_item.values():
                    if item.name == obj:
                        return item
                return None
        return None
        
    @property
    def data(self):
        return {
            "id": self.id,
            "name": self.name,
            "rarity": self.rarity,
            "description": self.description,
            "price": self.price,
            "equipable": self.equipable,
            "type": self.type,
            "power": self.power,
            "power_modifier": self.power_modifier,
            "craftby": self.craftby,
            "craft_score_cost": self.craft_score_cost,
            "craft_shop_level": self.craft_shop_level,
            "stackable": self.stackable,
            "id_range": self.id_range,
            "skill_point": self.skill_point,
            "skills": self.skills,
            "base_id": self.base_id
        }
    
    @property
    def buyable(self):
        return self.id > 200 and self.id < 300 and self.price > 0
    
    @property
    def soldable(self):
        return self.price > 0
    
    @property
    def craftable(self):
        return len(self.craftby) > 0
    
    @property
    def giftable(self):
        return 299 <= self.id <= 400
    
    def is_feed(self):
        return self.id <= 3 or self.id == 404


@dataclass
class FishSkill:
    id: int
    name: str
    desc: str
    effect: dict
    score: int
    max_level: int
    detail: str = ''

    def __init__(self, obj: dict):
        self.id = obj['id']
        self.name = obj['name']
        self.desc = obj.get('desc', '')
        self.effect = obj.get('effect', {})
        self.score = obj.get('score', 0)
        self.max_level = obj.get('max_level', 1)
        self.detail = obj.get('detail', '')

    @property
    def data(self):
        return {
            'id': self.id,
            'name': self.name,
            'desc': self.desc,
            'effect': self.effect,
            'score': self.score,
            'max_level': self.max_level,
            'detail': self.detail
        }
    
    def get_detail_for_level(self, level: int):
        """获取指定等级的技能描述"""
        if level < 1 or level > self.max_level:
            return ""
        effect = {}
        for key, value in self.effect.items():
            effect[key] = value[level-1]
        return self.detail.format(**effect)


def get_skill(skill_id: int) -> 'FishSkill':
    return fish_skills.get(skill_id)

with open('data/fishgame/fish_data_poke_ver.json', 'r', encoding='utf-8') as f:
    for index, fish in enumerate(json.load(f)):
        fish['id'] = index + 1
        fish_obj = Fish(fish)
        fish_data[fish_obj.id] = fish_obj

with open('data/fishgame/fish_data_group.json', 'r', encoding='utf-8') as f:
    index = len(fish_data)
    for event in json.load(f):
        topic = event.get('topic', '')
        weekday_topic[event.get('weekday', 1) - 1] = topic
        for fish in event['fish']:
            fish['id'] = index + 1
            fish['spawn_at'] = (topic,) if topic else ("common",)
            index += 1
            fish_obj = Fish(fish)
            fish_data[fish_obj.id] = fish_obj

with open('data/fishgame/fish_item.json', 'r', encoding='utf-8') as f:
    for fish in json.load(f):
        fish_item_obj = FishItem(fish)
        fish_item[fish_item_obj.id] = fish_item_obj

# 读取技能
try:
    with open('data/fishgame/fish_skill.json', 'r', encoding='utf-8') as f:
        for sk in json.load(f):
            fish_skills[sk['id']] = FishSkill(sk)
except FileNotFoundError:
    pass


class Equipment:
    def __init__(self, data, player=None):
        self.__data = data
        self._player = player
        if 'rod' not in self.__data:
            self.__data['rod'] = 0
        if 'tool' not in self.__data:
            self.__data['tool'] = 0
        if 'accessory' not in self.__data:
            self.__data['accessory'] = 0

    def equip(self, item: FishItem):
        # 支持 rod/tool/accessory 三类
        slot = item.type
        if slot not in ['rod', 'tool', 'accessory']:
            return False
        if item.id == self.__data.get(slot, 0):
            # 再次装备则卸下
            self.__data[slot] = 0
            return False
        else:
            self.__data[slot] = item.id
            return True
    
    @property
    def rod(self) -> FishItem:
        return FishItem.get(self.__data.get('rod', 0))
    
    @property
    def tool(self) -> FishItem:
        return FishItem.get(self.__data.get('tool', 0))
    
    @property
    def accessory(self) -> FishItem:
        acc_id = self.__data.get('accessory', 0)
        if acc_id == 0:
            return None
        # base = FishItem.get(acc_id)
        # if base:
        #     return base
        if self._player:
            meta = self._player.data.get('accessory_meta', {}).get(str(acc_id))
            if meta:
                base_item = FishItem.get(meta['base_id'])
                if base_item:
                    raw = base_item.data.copy()
                    raw['id'] = acc_id
                    raw['skills'] = meta.get('skills', [])
                    return FishItem(raw)
        return None
    
    @property
    def accessory_id(self) -> int:
        return self.__data.get('accessory', 0)
    
    @property
    def ids(self) -> list[int]:
        return [self.__data.get('rod', 0), self.__data.get('tool', 0), self.__data.get('accessory', 0)]
    
    @property
    def items(self) -> list[FishItem]:
        return [self.rod, self.tool, self.accessory]
    
    @property
    def exp_bonus(self) -> float:
        ret = 0
        for item in self.items:
            if item is not None and item.id == 402:
                ret += 0.1
        return ret

    @property
    def gold_bonus(self) -> float:
        return 0


# 背包
class Backpack:
    def __init__(self, data, player=None):
        self.__data: dict[str, int] = data
        self._player = player

    @property
    def items(self) -> list[dict]:
        result = []
        for key, value in self.__data.items():
            item_obj = FishItem.get(key)
            if (not item_obj or not item_obj.stackable) and self._player:
                meta = self._player.data.get('accessory_meta', {}).get(str(key))
                if meta:
                    base_item = FishItem.get(meta['base_id'])
                    if base_item:
                        raw = base_item.data.copy()
                        raw['id'] = int(key)
                        raw['skills'] = meta.get('skills', [])
                        item_obj = FishItem(raw)
            result.append({'item': item_obj, 'count': value})
        return result
    
    def get_item(self, item_id: int) -> Union[FishItem, None]:
        if str(item_id) in self.__data:
            fi = FishItem.get(str(item_id))
            if fi and fi.stackable:
                return fi
            if self._player:
                meta = self._player.data.get('accessory_meta', {}).get(str(item_id))
                if meta:
                    base_item = FishItem.get(meta['base_id'])
                    if base_item:
                        raw = base_item.data.copy()
                        raw['id'] = item_id
                        raw['skills'] = meta.get('skills', [])
                        return FishItem(raw)
        return None
    
    def add_item(self, item_id: int, count: int = 1):
        if str(item_id) in self.__data:
            self.__data[str(item_id)] += count
        else:
            self.__data[str(item_id)] = count

    def pop_item(self, item_id: int, count: int = 1) -> bool:
        if str(item_id) in self.__data:
            if self.__data[str(item_id)] >= count:
                self.__data[str(item_id)] -= count
                if self.__data[str(item_id)] == 0:
                    del self.__data[str(item_id)]
                return True
        return False
    
    def get_item_count(self, item_id: int) -> int:
        """获取指定物品的数量"""
        return self.__data.get(str(item_id), 0)
    
    def consume_items(self, requirements: dict) -> bool:
        """消耗物品，requirements格式: {item_id: count}"""
        # 先检查是否有足够的物品
        for item_id, required_count in requirements.items():
            if self.get_item_count(item_id) < required_count:
                return False
        
        # 执行消耗
        for item_id, required_count in requirements.items():
            self.pop_item(item_id, required_count)
        
        return True


# 记录以及图鉴功能
class FishLog:
    def __init__(self, data):
        self.__data: list[int] = data

    def add_log(self, fish_id: int):
        self.__data.append(fish_id)

    def __len__(self):
        return len(self.__data)
    
    def __iter__(self):
        return iter(self.__data)
    
    def __getitem__(self, index):
        return Fish.get(self.__data[index])
    
    def caught(self, fish_id: int):
        return fish_id in self.__data

    # def __setitem__(self, index, value):
    #     self.__data[index] = value

    @property
    def items(self) -> list[Fish]:
        return [Fish.get(fish_id) for fish_id in self.__data]
    

