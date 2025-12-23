class ItemRequest:
    def __init__(self, require_lists: list[str], desc: str, count: int = 0):
        self.require_lists = require_lists
        self.desc = desc
        self.count = count

    @staticmethod
    def with_count(request: 'ItemRequest', count):
        return ItemRequest(request.require_lists, request.desc, count)

_big_gold = ItemRequest(['298'], '一箱金币')
_gold = ItemRequest(['299'], '一袋金币')
_ssr_r3_drop = ItemRequest(['301', '303', '305', '307', '309', '311', '313'], '普通SSR通常掉落物')
_ssr_r4_drop = ItemRequest(['302', '304', '306', '308', '310', '312'], '普通SSR稀有掉落物')
_kyogre_drop = ItemRequest(['314'], '海皇玉')
_sand_r3_drop = ItemRequest(['315', '316', '317', '318'], '沙漠SSR通常掉落物')
_sand_r4_drop = ItemRequest(['319'], '沙漠SSR稀有掉落物')
_forest_r3_drop = ItemRequest(['320', '321', '322', '323'], '森林SSR通常掉落物')
_forest_r4_drop = ItemRequest(['324'], '森林SSR稀有掉落物')
_volcano_r3_drop = ItemRequest(['325', '326', '327', '328'], '火山SSR通常掉落物')
_volcano_r4_drop = ItemRequest(['329'], '火山SSR稀有掉落物')
_sky_r3_drop = ItemRequest(['330', '331', '332', '333'], '天空SSR通常掉落物')
_sky_r4_drop = ItemRequest(['334'], '天空SSR稀有掉落物')
_ice_r3_drop = ItemRequest(['335', '336', '337', '338'], '雪山SSR通常掉落物')
_ice_r4_drop = ItemRequest(['339'], '雪山SSR稀有掉落物')
_steel_r3_drop = ItemRequest(['340', '341', '342', '343'], '金属SSR通常掉落物')
_steel_r4_drop = ItemRequest(['344'], '金属SSR稀有掉落物')
_mystic_r3_drop = ItemRequest(['345', '346', '347', '348'], '神秘SSR通常掉落物')
_mystic_r4_drop = ItemRequest(['349'], '神秘SSR稀有掉落物')
_sea_token = ItemRequest(['30'], '海洋之证')
_hurricane_token = ItemRequest(['31'], '风暴之证')
_strongest_token = ItemRequest(['32'], '最强之证')

building_name_map = {
    '大锅': 'big_pot',
    '渔获加工厂': 'fish_factory',
    '建筑中心': 'building_center',
    '鱼研所': 'fish_lab',
    '冰洞': 'ice_hole',
    '神秘商店': 'mystic_shop',
    '七天神像': 'seven_statue',
    '熔炉工坊': 'forge_shop',
    '港口': 'port'
}

class BuildingBase:
    def __init__(self, data, id):
        self._data = data
        if 'id' not in self._data:
            self._data['id'] = id
        if 'current_materials' not in self._data:
            self._data['current_materials'] = {}
        if 'level' not in self._data:
            self.level = 0

    @property
    def level(self) -> int:
        return self._data.get('level', 0)
    
    @level.setter
    def level(self, value: int):
        self._data['level'] = value

    @property
    def max_level(self) -> int:
        ...

    @property
    def id(self) -> str:
        return self._data.get('id', '')
    
    @property
    def current_materials(self) -> list[ItemRequest]:
        return self._data['current_materials']

    def get_level_materials(self, int) -> list[ItemRequest]:
        ...

    def get_level_prerequisites(self, int) -> list[ItemRequest]:
        ...

    # 返回实际消耗了几个材料
    def add_materials(self, material_id: int, count: int) -> int:
        str_id = str(material_id)
        require_count = 0
        for request in self.get_level_materials(self.level + 1):
            if str_id in request.require_lists:
                require_count += request.count
                break
        current_count = 0
        for str_id2 in request.require_lists:
            current_count += self.current_materials.get(str_id2, 0)
        if current_count >= require_count:
            return 0
        add_count = min(count, require_count - current_count)
        if str_id not in self.current_materials:
            self.current_materials[str_id] = 0
        self.current_materials[str_id] += add_count
        return add_count
    
    def get_materials_status(self) -> list[tuple[ItemRequest, int]]:
        status = []
        for request in self.get_level_materials(self.level + 1):
            current_count = 0
            for str_id in request.require_lists:
                current_count += self.current_materials.get(str_id, 0)
            status.append((request, current_count))
        return status
    
    def can_upgrade(self) -> bool:
        if self.level >= self.max_level:
            return False
        for request in self.get_level_materials(self.level + 1):
            current_count = 0
            for str_id in request.require_lists:
                current_count += self.current_materials.get(str_id, 0)
            if current_count < request.count:
                return False
        return True
    
    def upgrade(self) -> bool:
        if not self.can_upgrade():
            return False
        self.level += 1
        self._data['current_materials'] = {}
        return True

class BigPot(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'big_pot')
        self.name = '大锅'

    @property
    def description(self):
        return "一口神秘的大锅，不仅可以提升平均渔力，还可以加入燃料获得全员的渔力提升。\n不仅如此，这个大锅似乎连接着周边的地脉，别的建筑也依赖大锅才能发挥作用。"

    def level_effect_desc(self, level):
        return f"大锅最大容量：{level * 100}\n平均渔力加成：{level * 10}"

    @property
    def capacity(self) -> int:
        return self.level * 100
    
    @property
    def current(self) -> int:
        return self._data.get('current_count', 0)
    
    @current.setter
    def current(self, value: int):
        self._data['current_count'] = value

    @property
    def power_boost(self):
        return self.current // 10
    
    @property
    def average_power_boost(self):
        return self.level * 10
    
    @property
    def consume_speed(self) -> int:
        power = max(0, self.current / 100 - 1)
        return int(10 * (1.6 ** power))

    @property
    def max_level(self) -> int:
        return 5
    
    def consume(self):
        self.current = max(0, self.current - self.consume_speed)
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 5),
                ItemRequest.with_count(_ssr_r4_drop, 2)
            ],
            2: [
                ItemRequest.with_count(_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_kyogre_drop, 1)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 15),
                ItemRequest.with_count(_ssr_r4_drop, 8),
                ItemRequest.with_count(_kyogre_drop, 2),
            ],
            4: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_kyogre_drop, 3),
                ItemRequest.with_count(_forest_r3_drop, 5),
                ItemRequest.with_count(_volcano_r3_drop, 5),
            ],
            5: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_ssr_r3_drop, 25),
                ItemRequest.with_count(_ssr_r4_drop, 15),
                ItemRequest.with_count(_kyogre_drop, 5),
                ItemRequest.with_count(_forest_r4_drop, 2),
                ItemRequest.with_count(_volcano_r4_drop, 2),
            ]
        }
        return materials.get(level, [])
    
    def get_level_prerequisites(self, int):
        return {}
    
# Steel
class FishFactory(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'fish_factory')
        self.name = '渔获加工厂'

    @property
    def fishing_bonus(self):
        return self.level * 0.1
    
    @property
    def description(self):
        return "加工鱼的工厂，可以提升捕捉到的鱼的渔获量。"
    
    def level_effect_desc(self, level):
        return f"渔获量加成：+{level * 10}%"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 2),
                ItemRequest.with_count(_ssr_r3_drop, 5),
                ItemRequest.with_count(_ssr_r4_drop, 2),
                ItemRequest.with_count(_steel_r3_drop, 5)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 5),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_steel_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_steel_r3_drop, 20),
                ItemRequest.with_count(_steel_r4_drop, 2)
            ],
            4: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_steel_r3_drop, 30),
                ItemRequest.with_count(_steel_r4_drop, 5),
                ItemRequest.with_count(_mystic_r3_drop, 10)
            ],
            5: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_steel_r4_drop, 10),
                ItemRequest.with_count(_mystic_r4_drop, 5)
            ]
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 1},
            2: {'big_pot': 2},
            3: {'big_pot': 3},
            4: {'big_pot': 4},
            5: {'big_pot': 5}
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 5

# Sand
class BuildingCenter(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'building_center')
        self.name = '建筑中心'

    @property
    def description(self):
        return "建筑中心，提升该建筑的等级后，会减少两次建筑之间需要的冷却时间。"

    @property
    def build_cooldown(self):
        return [24, 12, 6, 4, 2, 1][self.level]
    
    def level_effect_desc(self, level):
        cooldown_hours = [24, 12, 6, 4, 2, 1][level]
        return f"建筑冷却时间：{cooldown_hours}小时"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 2),
                ItemRequest.with_count(_ssr_r3_drop, 5),
                ItemRequest.with_count(_ssr_r4_drop, 2),
                ItemRequest.with_count(_sand_r3_drop, 5)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 5),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_sand_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_sand_r3_drop, 20),
                ItemRequest.with_count(_sand_r4_drop, 2)
            ],
            4: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_sand_r3_drop, 30),
                ItemRequest.with_count(_sand_r4_drop, 5),
                ItemRequest.with_count(_forest_r3_drop, 10)
            ],
            5: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_sand_r4_drop, 10),
                ItemRequest.with_count(_forest_r4_drop, 5)
            ]
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 1},
            2: {'big_pot': 2},
            3: {'big_pot': 3},
            4: {'big_pot': 4},
            5: {'big_pot': 5}
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 5
    
# Forest
class FishLab(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'fish_lab')
        self.name = '鱼研所'

    @property
    def description(self):
        return "研究鱼的实验室，可以提升渔力强化剂的使用次数，和渔获加成卡的持续时间。"

    @property
    def extra_power_boost_times(self):
        return self.level

    @property
    def extra_fishing_bonus_second(self):
        return self.level * 600
    
    def level_effect_desc(self, level):
        return f"渔力强化剂额外使用次数：+{level}次\n渔获加成卡额外持续时间：+{level * 10}分钟"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 2),
                ItemRequest.with_count(_ssr_r3_drop, 5),
                ItemRequest.with_count(_ssr_r4_drop, 2),
                ItemRequest.with_count(_forest_r3_drop, 5)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 5),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_forest_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_forest_r3_drop, 20),
                ItemRequest.with_count(_forest_r4_drop, 2)
            ],
            4: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_forest_r3_drop, 30),
                ItemRequest.with_count(_forest_r4_drop, 5),
                ItemRequest.with_count(_volcano_r3_drop, 10)
            ],
            5: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_forest_r4_drop, 10),
                ItemRequest.with_count(_volcano_r4_drop, 5)
            ]
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 1},
            2: {'big_pot': 2},
            3: {'big_pot': 3},
            4: {'big_pot': 4},
            5: {'big_pot': 5}
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 5
    
# Ice - L2
class IceHole(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'ice_hole')
        self.name = '冰洞'

    @property
    def description(self):
        return "冰封的渔场，可以吸引更新鲜的鱼群。\n提升鱼群时获得的渔获量，并且降低鱼群中普通鱼的比例，提高鱼群中限定鱼的比例。"

    @property
    def fever_fishing_bonus(self):
        return self.level * 0.15
    
    @property
    def common_rate_down(self):
        return self.level * 0.1
    
    @property
    def special_rate_up(self):
        return self.level * 0.3
    
    def level_effect_desc(self, level):
        return f"鱼群渔获量加成：+{level * 15}%\n普通/限定鱼比例降低/提升：-{level * 10}%/+{level * 30}%"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 5),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_ice_r3_drop, 5)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_ice_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_ice_r3_drop, 20),
                ItemRequest.with_count(_ice_r4_drop, 5),
                ItemRequest.with_count(_steel_r3_drop, 10)
            ],
            4: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_ice_r3_drop, 30),
                ItemRequest.with_count(_ice_r4_drop, 10),
                ItemRequest.with_count(_steel_r4_drop, 5)
            ],
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 2},
            2: {'big_pot': 3},
            3: {'big_pot': 4},
            4: {'big_pot': 5},
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 4

# Mystic - L2
class MysticShop(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'mystic_shop')    
        self.name = '神秘商店'
        
    @property
    def description(self):
        return "神秘的商店，升级后可以在商店和合成中追加新的物品。"
    
    def level_effect_desc(self, level):
        return f"解锁新商品和合成配方：第{level}阶段"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 5),
                ItemRequest.with_count(_ssr_r3_drop, 10),
                ItemRequest.with_count(_ssr_r4_drop, 5),
                ItemRequest.with_count(_mystic_r3_drop, 5)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 10),
                ItemRequest.with_count(_ssr_r3_drop, 20),
                ItemRequest.with_count(_ssr_r4_drop, 10),
                ItemRequest.with_count(_mystic_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_mystic_r3_drop, 20),
                ItemRequest.with_count(_mystic_r4_drop, 5),
                ItemRequest.with_count(_sand_r3_drop, 10)
            ],
            4: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_mystic_r3_drop, 30),
                ItemRequest.with_count(_mystic_r4_drop, 10),
                ItemRequest.with_count(_sand_r4_drop, 5)
            ],
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 2},
            2: {'big_pot': 3},
            3: {'big_pot': 4},
            4: {'big_pot': 5},
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 4

# Sky - L3
class SevenStatue(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'seven_statue')
        self.name = '七天神像'
        
    @property
    def description(self):
        return "七天神像，传说可以带来好运，可以在这里学习捕鱼的技能。升级后可以提升获得异色鱼的概率。"

    @property
    def shiny_rate(self):
        return [0, 0.01, 0.02, 0.05][self.level]
    
    def level_effect_desc(self, level):
        rates = [0, 1, 2, 5]
        return f"异色鱼概率提升：+{rates[level]}%"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 15),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 15),
                ItemRequest.with_count(_sky_r3_drop, 15),
                ItemRequest.with_count(_sky_r4_drop, 2)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 40),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_sky_r3_drop, 20),
                ItemRequest.with_count(_sky_r4_drop, 5),
                ItemRequest.with_count(_ice_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_sky_r3_drop, 30),
                ItemRequest.with_count(_sky_r4_drop, 10),
                ItemRequest.with_count(_ice_r4_drop, 5)
            ],
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 3, 'ice_hole': 2},
            2: {'big_pot': 4, 'ice_hole': 3},
            3: {'big_pot': 5, 'ice_hole': 4},
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 3

# Volcano - L3
class ForgeShop(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'forge_shop')
        self.name = '熔炉工坊'
        
    @property
    def description(self):
        return "熔炉工坊，可以制造宝石，并且在渔具上镶嵌宝石，提升渔具的属性。"
    
    def level_effect_desc(self, level):
        return f"可制造宝石种类：第{level}阶段\n渔具镶嵌槽位：+{level}个"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_big_gold, 15),
                ItemRequest.with_count(_ssr_r3_drop, 30),
                ItemRequest.with_count(_ssr_r4_drop, 15),
                ItemRequest.with_count(_volcano_r3_drop, 15),
                ItemRequest.with_count(_volcano_r4_drop, 2)
            ],
            2: [
                ItemRequest.with_count(_big_gold, 20),
                ItemRequest.with_count(_ssr_r3_drop, 40),
                ItemRequest.with_count(_ssr_r4_drop, 20),
                ItemRequest.with_count(_volcano_r3_drop, 20),
                ItemRequest.with_count(_volcano_r4_drop, 5),
                ItemRequest.with_count(_sky_r3_drop, 10)
            ],
            3: [
                ItemRequest.with_count(_big_gold, 30),
                ItemRequest.with_count(_volcano_r3_drop, 30),
                ItemRequest.with_count(_volcano_r4_drop, 10),
                ItemRequest.with_count(_sky_r4_drop, 5)
            ],
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 3, 'mystic_shop': 2},
            2: {'big_pot': 4, 'mystic_shop': 3},
            3: {'big_pot': 5, 'mystic_shop': 4},
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 3


# Final - L3
class Port(BuildingBase):
    def __init__(self, data):
        super().__init__(data, 'port')
        self.name = '港口'

    @property
    def description(self):
        return "港口，可以用于出海捕鱼。"

    def level_effect_desc(self, level):
        return f"敌怪：第{level}阶段\n每日出海次数：{level}次 / 队伍最大人数：{level + 1}人"
    
    def get_level_materials(self, level: int) -> list[ItemRequest]:
        materials = {
            1: [
                ItemRequest.with_count(_kyogre_drop, 2),
                ItemRequest.with_count(_sand_r4_drop, 1),
                ItemRequest.with_count(_forest_r4_drop, 1),
                ItemRequest.with_count(_volcano_r4_drop, 1),
                ItemRequest.with_count(_sky_r4_drop, 1),
                ItemRequest.with_count(_ice_r4_drop, 1),
                ItemRequest.with_count(_steel_r4_drop, 1),
                ItemRequest.with_count(_mystic_r4_drop, 1),
            ],
            2: [
                ItemRequest.with_count(_sea_token, 10),
                ItemRequest.with_count(_sand_r4_drop, 2),
                ItemRequest.with_count(_forest_r4_drop, 2),
                ItemRequest.with_count(_volcano_r4_drop, 2),
                ItemRequest.with_count(_sky_r4_drop, 2),
                ItemRequest.with_count(_ice_r4_drop, 2),
                ItemRequest.with_count(_steel_r4_drop, 2),
                ItemRequest.with_count(_mystic_r4_drop, 2),
            ],
            3: [
                ItemRequest.with_count(_hurricane_token, 20),
                ItemRequest.with_count(_sand_r4_drop, 5),
                ItemRequest.with_count(_forest_r4_drop, 5),
                ItemRequest.with_count(_volcano_r4_drop, 5),
                ItemRequest.with_count(_sky_r4_drop, 5),
                ItemRequest.with_count(_ice_r4_drop, 5),
                ItemRequest.with_count(_steel_r4_drop, 5),
                ItemRequest.with_count(_mystic_r4_drop, 5),
            ],
        }
        return materials.get(level, {})
    
    def get_level_prerequisites(self, level):
        pre = {
            1: {'big_pot': 3, 'forge_shop': 1},
            2: {'big_pot': 4, 'forge_shop': 2},
            3: {'big_pot': 5, 'forge_shop': 3},
        }
        return pre.get(level, {})

    @property
    def max_level(self) -> int:
        return 3
