import json
from dataclasses import dataclass, field
from typing import Union
    
fish_data: dict[int, 'Fish'] = {}
fish_item: dict[int, 'FishItem'] = {}
weekday_topic = ['', '', '', '', '', '', '']

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
            "craft_score_cost": self.craft_score_cost
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
        return 300 < self.id <= 400
    
    def is_feed(self):
        return self.id <= 3 or self.id == 404

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


class Equipment:
    def __init__(self, data):
        self.__data = data
        if 'rod' not in self.__data:
            self.__data['rod'] = 0
        if 'tool' not in self.__data:
            self.__data['tool'] = 0

    def equip(self, item: FishItem):
        if item.id == self.__data.get(item.type, 0):
            self.__data[item.type] = 0
            return False
        else:
            self.__data[item.type] = item.id
            return True
    
    @property
    def rod(self) -> FishItem:
        return FishItem.get(self.__data.get('rod', 0))
    
    @property
    def tool(self) -> FishItem:
        return FishItem.get(self.__data.get('tool', 0))
    
    @property
    def ids(self) -> list[int]:
        return [self.__data.get('rod', 0), self.__data.get('tool', 0)]
    
    @property
    def items(self) -> list[FishItem]:
        return [self.rod, self.tool]
    
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
    def __init__(self, data):
        self.__data: dict[str, int] = data

    @property
    def items(self) -> list[dict]:
        return [{
            'item': FishItem.get(key),
            'count': value
        } for key, value in self.__data.items()]
    
    def get_item(self, item_id: int) -> Union[FishItem, None]:
        if str(item_id) in self.__data:
            return FishItem.get(str(item_id))
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
    

