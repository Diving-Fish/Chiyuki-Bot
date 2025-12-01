from typing import Optional
from src.data_access.redis import DictRedisData, redis_global
from src.libraries.fishgame.data import *
from src.libraries.fishgame.buildings import *
import hashlib
import json
import random
import string
import time
import string

def generate_mixed_gibberish(length=10):
    # 中文字符的 Unicode 范围：常用汉字范围大约在 0x4E00-0x9FFF
    result = []
    
    for _ in range(length):
        # 随机决定是生成中文还是英文字符
        if random.random() < 0.5:  # 50% 的概率生成中文
            # 随机选择一个 Unicode 编码点，生成一个中文字符
            char_code = random.randint(0x4E00, 0x9FFF)
            result.append(chr(char_code))
        else:  # 50% 的概率生成英文
            # 随机选择英文字母（大小写）或数字
            choices = string.ascii_letters + string.digits
            result.append(random.choice(choices))
    
    return ''.join(result)

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def buff_available(buff):
    expire = buff.get('expire', 0)
    times = buff.get('time', 999)
    return times > 0 and (expire == 0 or expire > time.time())

with open('data/fishgame/fish_data_poke_ver.json', 'r', encoding='utf-8') as f:
    fish_data_poke_ver = json.load(f)

with open('data/fishgame/gacha.json', 'r', encoding='utf-8') as f:
    gacha_data = json.load(f)

with open('data/fishgame/fish_talent.json', 'r', encoding='utf-8') as f:
    talent_data = json.load(f)

# 神秘抽卡与宝玉转换数据
try:
    with open('data/fishgame/mystery.json', 'r', encoding='utf-8') as f:
        _mystery_raw = json.load(f)
        mystery_gacha_data = _mystery_raw.get('gacha', [])
        mystery_jewel_table = _mystery_raw.get('jewel', {})  # { source_item_id(str): {target_id(str): weight(float)} }
except FileNotFoundError:
    mystery_gacha_data = []
    mystery_jewel_table = {}


class FishPlayer(DictRedisData):
    def __init__(self, qq):
        self.qq = qq
        token = f'fishgame_user_data_{md5(str(qq))}'
        super().__init__(token, default=FishPlayer.default_user_data())
        self.bag = Backpack(self.data['bag'], self)
        self.fish_log = FishLog(self.data['fish_log'])
        self.equipment = Equipment(self.data['equipment'], self)
        # 配件实例数据： { item_id(str): {"skills": [{id, level}, ...], "base_id": int} }
        if 'accessory_meta' not in self.data:
            self.data['accessory_meta'] = {}

    @staticmethod
    def try_get(qq):
        token = f'fishgame_user_data_{md5(str(qq))}'
        if redis_global.get(token) == None:
            return None
        return FishPlayer(qq)

    @staticmethod
    def default_user_data():
        return {
            "name": "渔者",
            "level": 1,
            "exp": 0,
            "gold": 0,
            "score": 0,
            "fish_log": [],
            "bag": {"1": 1},  # 修改为字典格式: {item_id: count}
            "buff": [],
            "equipment": {},
            "last_gift_time": 0,
            "master_ball_crafts": 0,
            "accessory_meta": {},
            # 天赋经验：{ talent_id(str): total_exp(int) }
            "talent_exp": {}
        }

    def refresh_buff(self):
        self.data['buff'] = list(filter(buff_available, self.data['buff']))
    
    @property
    def name(self):
        return self.data.get('name', '渔者')
    
    @property
    def level(self):
        return self.data['level']
    
    @property
    def exp(self):
        return self.data['exp']
    
    @property
    def gold(self):
        return self.data['gold']
    
    @property
    def score(self):
        return self.data['score']
    
    # @property
    # def fish_log(self):
    #     return self.data['fish_log']
    
    # @property
    # def bag(self):
    #     return self.data['bag']
    
    @property
    def buff(self):
        return self.data['buff']
    
    @property
    def renew_accessory(self):
        now_date = time.strftime('%Y-%m-%d', time.localtime())
        date = self.data.get('accessory_renew_date', '')
        if date != now_date:
            return 0
        return self.data.get('accessory_renew', 0)
    
    @renew_accessory.setter
    def renew_accessory(self, value):
        now_date = time.strftime('%Y-%m-%d', time.localtime())
        self.data['accessory_renew_date'] = now_date
        self.data['accessory_renew'] = value
    
    @property
    def master_ball_crafts(self):
        return self.data.get('master_ball_crafts', 0)
    
    @master_ball_crafts.setter
    def master_ball_crafts(self, value):
        self.data['master_ball_crafts'] = value
    
    @property
    def power(self):
        # 基础：等级作微量基础值（原逻辑保留）
        base = self.level
        for item in self.equipment.items:
            if item:
                base += item.power
        for buff in self.buff:
            base += buff.get('power', 0)
        # 技能附加
        ctx = self.get_skill_context()
        base += ctx.get('flat_power', 0)
        return base
    
    @property
    def fever_power(self):
        # Fever 模式下原有的削减逻辑 + 技能
        base = self.level // 5
        for item in self.equipment.items:
            if item:
                if item.type == 'rod' and item.id not in [403, 405]:
                    base += item.power // 2
                elif item.id == 406:
                    base += item.power + 25
                else:
                    base += item.power
        for buff in self.buff:
            base += buff.get('power', 0)
        ctx = self.get_skill_context()
        base += ctx.get('flat_power', 0)
        return base
    
    @staticmethod
    def from_id(qq: str):
        token = f'fishgame_user_data_{md5(str(qq))}'
        if redis_global.exists(token):
            return FishPlayer(qq)
        return None
    
    @staticmethod
    def get_target_exp(level):
        base = level + 19
        return int(base * 1.1 ** (level / 10))

    def handle_level_up(self):
        level_up = False
        target_exp = self.get_target_exp(self.level)
        while self.exp >= target_exp:
            self.data['level'] += 1
            self.data['exp'] -= target_exp
            target_exp = self.get_target_exp(self.level)
            level_up = True
        if level_up:
            return f"\n等级提升至 {self.level} 级！"
        return ''

    # ---------------- Skill System Helpers ----------------
    def get_equipped_skills(self) -> list[dict]:
        skills = []
        meta = self.data.get('accessory_meta', {})
        acc = self.equipment.accessory
        if acc and str(acc.id) in meta:
            skills.extend(meta[str(acc.id)].get('skills', []))
        for it in [self.equipment.rod, self.equipment.tool]:
            if it and getattr(it, 'skills', []):
                skills.extend(it.skills)
        return skills

    def get_skill_context(self) -> dict:
        from src.libraries.fishgame.data import fish_skills
        ctx = {
            'flat_power': 0,
            'topic_power': {},
            'fail_reward': 0,
            'fail_item_percent': 0,
            'crit_percent': 0,
            'crit_rate': 0,
            'gold_rate': 0,
            'exp_rate': 0,
            'new_fish_power': 0,
            'old_fish_crit': 0
        }
        for inst in self.get_equipped_skills():
            sk = fish_skills.get(inst['id'])
            if not sk:
                continue
            lv = min(inst.get('level', 1), sk.max_level)
            eff = sk.effect
            if 'power' in eff:
                ctx['flat_power'] += eff['power'][lv-1]
            for key, val in eff.items():
                if key.startswith('power_') and isinstance(val, list):
                    topic = key.split('_',1)[1]
                    ctx['topic_power'][topic] = ctx['topic_power'].get(topic, 0) + val[lv-1]
            if 'fail_reward' in eff:
                ctx['fail_reward'] = max(ctx['fail_reward'], eff['fail_reward'][lv-1])
            if 'item_percent' in eff:
                ctx['fail_item_percent'] = max(ctx['fail_item_percent'], eff['item_percent'][lv-1])
            if 'crit_percent' in eff:
                ctx['crit_percent'] += eff['crit_percent'][lv-1]
            if 'crit_rate' in eff:
                ctx['crit_rate'] = max(ctx['crit_rate'], eff['crit_rate'][lv-1])
            if 'gold_rate' in eff:
                ctx['gold_rate'] += eff['gold_rate'][lv-1]
            if 'exp_rate' in eff:
                ctx['exp_rate'] += eff['exp_rate'][lv-1]
            if 'new_fish_power' in eff:
                ctx['new_fish_power'] += eff['new_fish_power'][lv-1]
            if 'old_fish_crit' in eff:
                ctx['old_fish_crit'] += eff['old_fish_crit'][lv-1]
        return ctx
    

    def get_talent_level(self, talent_id):
        """根据已累积的天赋经验，返回当前天赋等级（从0开始，满级为效果长度）。

        规则：get_talent_exp_level 返回的是每个等级的累计经验阈值数组，
        等级 = 满足 total_exp >= 阈值 的数量。
        """
        # 保护：初始化存储
        store = self.data.setdefault('talent_exp', {})
        total_exp = int(store.get(str(talent_id), 0))
        try:
            thresholds = self.get_talent_exp_level(talent_id)
        except Exception:
            return 0
        level = 0
        for th in thresholds:
            if total_exp >= th:
                level += 1
            else:
                break
        return level

    @staticmethod
    def get_talent_exp_level(talent_id):
        talent = talent_data[talent_id - 1]
        base_cost = talent.get('base_cost', 100)
        power_cost = talent.get('power_cost', 2)
        # 取效果数组长度作为最大等级
        max_level = 1
        for _key, v in talent.get('effect', {}).items():
            if isinstance(v, list):
                max_level = max(max_level, len(v))
        # 构造累计经验阈值：
        # L1 阈值 = base_cost * power_cost^0
        # L2 阈值 = L1 + base_cost * power_cost^1
        # ...
        thresholds = []
        cumulative = 0
        for i in range(max_level):
            cost_i = int(base_cost * (power_cost ** i))
            cumulative += cost_i
            thresholds.append(cumulative)
        return thresholds

    def add_talent_exp(self, talent_id, exp):
        """为指定天赋增加经验。

        返回：(new_level, level_up_count)
        - new_level: 增加经验后的最新等级
        - level_up_count: 本次增加带来的等级提升数量（可为 0）
        """
        if exp == 0:
            return self.get_talent_level(talent_id), 0
        if exp < 0:
            # 不允许负经验；如需支持可在此修改为回退逻辑
            exp = 0

        store = self.data.setdefault('talent_exp', {})
        key = str(talent_id)
        old_total = int(store.get(key, 0))
        old_level = self.get_talent_level(talent_id)
        thresholds = self.get_talent_exp_level(talent_id)
        max_total = thresholds[-1] if thresholds else 0

        new_total = old_total + int(exp)
        if max_total > 0:
            new_total = min(new_total, max_total)
        new_total = max(new_total, 0)
        store[key] = new_total

        new_level = self.get_talent_level(talent_id)
        level_up = max(0, new_level - old_level)
        # 自动保存
        self.save()
        return new_level, level_up

    # ---------------- Talent Status Interface ----------------
    def get_talent_status(self, talent_id: int, as_text: bool = False):
        """查看玩家在某个天赋上的当前经验与等级。

        返回：
        - as_text=False: dict
            {
              "talent_id": int,
              "name": str,
              "level": int,           # 当前等级（0..max_level）
              "max_level": int,
              "total_exp": int,       # 当前累计经验
              "current_need": int,    # 本级已累经验（相对上一级阈值）
              "current_total": int,   # 达到当前等级所需累计阈值
              "next_total": int,      # 下一级阈值（满级时等于最后阈值）
              "need_to_next": int     # 距离下一级还需经验（满级为0）
            }
        - as_text=True: str 友好提示文本
        """
        # 数据与阈值
        store = self.data.setdefault('talent_exp', {})
        total = int(store.get(str(talent_id), 0))
        thresholds = self.get_talent_exp_level(talent_id)
        max_level = len(thresholds)
        level = self.get_talent_level(talent_id)

        # 计算区间
        current_total = thresholds[level-1] if level > 0 else 0
        next_total = thresholds[level] if level < max_level else thresholds[-1] if thresholds else 0
        current_need = max(0, total - current_total)
        need_to_next = 0 if level >= max_level else max(0, next_total - total)

        # 名称
        try:
            name = talent_data[talent_id - 1].get('name', f'Talent {talent_id}')
        except Exception:
            name = f'Talent {talent_id}'

        info = {
            'talent_id': talent_id,
            'name': name,
            'level': level,
            'max_level': max_level,
            'total_exp': total,
            'current_need': current_need,
            'current_total': current_total,
            'next_total': next_total,
            'need_to_next': need_to_next
        }

        if not as_text:
            return info

        # 文本化
        if max_level == 0:
            return f"{name}：暂无等级信息"
        if level >= max_level:
            return f"{name} Lv.{level}/{max_level}（满级），累计经验 {total}"
        # 当前级进度与下一阈值
        seg_total = next_total - current_total if next_total > current_total else 1
        seg_cur = min(max(total - current_total, 0), seg_total)
        percent = int(seg_cur * 100 / seg_total)
        return (
            f"{name} Lv.{level}/{max_level} | 当前经验 {total} | 距离下一级还需 {need_to_next}\n"
            f"（本级进度：{seg_cur}/{seg_total}，{percent}%）"
        )


class FishGame(DictRedisData):
    def __init__(self, group_id=0):
        token = f'fishgame_group_data_{group_id}'
        super().__init__(token, default=FishGame.default_group_data())
        self.fish_log = FishLog(self.data["fish_log"])
        self.__average_power = 0
        self.current_fish: Fish = None
        self.try_list = []
        self.leave_time = 0
        self.init_buildings()

    def init_buildings(self):
        # Buildings
        if 'big_pot' not in self.data:
            self.data['big_pot'] = {}
        self.big_pot = BigPot(self.data['big_pot'])

        if 'fish_factory' not in self.data:
            self.data['fish_factory'] = {}
        self.fish_factory = FishFactory(self.data['fish_factory'])

        if 'building_center' not in self.data:
            self.data['building_center'] = {}
        self.building_center = BuildingCenter(self.data['building_center'])

        if 'fish_lab' not in self.data:
            self.data['fish_lab'] = {}
        self.fish_lab = FishLab(self.data['fish_lab'])

        if 'ice_hole' not in self.data:
            self.data['ice_hole'] = {}
        self.ice_hole = IceHole(self.data['ice_hole'])

        if 'mystic_shop' not in self.data:
            self.data['mystic_shop'] = {}
        self.mystic_shop = MysticShop(self.data['mystic_shop'])

        if 'seven_statue' not in self.data:
            self.data['seven_statue'] = {}
        self.seven_statue = SevenStatue(self.data['seven_statue'])

        if 'forge_shop' not in self.data:
            self.data['forge_shop'] = {}
        self.forge_shop = ForgeShop(self.data['forge_shop'])

    @property
    def is_fever(self):
        return time.time() < self.data.get('fever_expire', 0)

    @staticmethod
    def default_group_data():
        return {
            "fish_log": [],
            "buff": [],
            "day": 0,
            "feed_time": 0,
            "fever_expire": 0,
            "fever_fishes": [],
            "pot_consume_time": 0,
        }
    
    @property
    def current_fish_pool(self) -> list[Fish]:
        if self.is_fever:
            return list(map(Fish.get, self.data['fever_fishes']))
        else:
            # 返回基础鱼池（来自fish_data_poke_ver.json的鱼，ID为1到len(fish_data_poke_ver)）
            return [Fish.get(i) for i in range(1, len(fish_data_poke_ver) + 1) if Fish.get(i) is not None]

    def refresh_buff(self):
        for buff_key in ['buff', 'avgp_buff']:
            self.data[buff_key] = list(filter(buff_available, self.data.get(buff_key, [])))
        if self.data.get('day', 0) != time.localtime().tm_mday:
            self.data['day'] = time.localtime().tm_mday
            self.data['feed_time'] = 0
        if self.big_pot.level > 0:
            current_time = time.time()
            pot_consume_time = self.data.get('pot_consume_time', 0)
            if pot_consume_time == 0:
                pot_consume_time = current_time + 600
            while pot_consume_time < current_time:
                pot_consume_time += 600
                self.big_pot.consume()
            self.data['pot_consume_time'] = pot_consume_time
            self.save()


    def unlock_all(self):
        self.data['fish_log'] += list(fish_data.keys())
        self.save()
    
    def trigger_fever(self):
        minutes = random.randint(60, 120)
        self.data['fever_expire'] = time.time() + minutes * 60
        common_last_fish_id = len(fish_data_poke_ver)
        current_topic: str = weekday_topic[time.localtime().tm_wday]
        all_range = range(1, len(fish_data) + 1)
        r_common = [i for i in all_range if i <= common_last_fish_id and Fish.get(i).rarity == 'R']
        sr_common = [i for i in all_range if i <= common_last_fish_id and Fish.get(i).rarity == 'SR']
        ssr_common = [i for i in all_range if i <= common_last_fish_id and Fish.get(i).rarity == 'SSR']
        sr_fever = [i for i in all_range if Fish.get(i).rarity == 'SR' and current_topic in Fish.get(i).spawn_at]
        ssr_fever = [i for i in all_range if Fish.get(i).rarity == 'SSR' and current_topic in Fish.get(i).spawn_at]
        r_samples = random.sample(r_common, len(r_common) // 2)
        sr_samples = random.sample(sr_common, len(sr_common) // 2) + random.sample(sr_fever, len(sr_fever) // 2) 
        ssr_samples = random.sample(ssr_common, len(ssr_common) // 2) + random.sample(ssr_fever, len(ssr_fever) // 2) 
        self.data['fever_fishes'] = r_samples + sr_samples + ssr_samples
        self.data['fever_fishes'].sort(key=lambda x: {"R": 1000, "SR": 2000, "SSR": 3000}[Fish.get(x).rarity] + Fish.get(x).std_power)
        self.save()

    def get_buff_for_rarity(self, rarity):
        # fever期间始终拥有黄金鱼料等级的buff
        if self.is_fever:
            fever_buff = {
                "SSR": 200,
                "SR": 120,
                "R": 60
            }
            return fever_buff[rarity]
        

        value = 0
        for buff in self.data['buff']:
            if rarity == buff.get('rarity', ''):
                value += buff.get('bonus', 0)
        return value

    def update_average_power(self, qq_list):
        p = 0
        count = 0
        for qq in qq_list:
            player = FishPlayer.try_get(qq)
            if player is None:
                continue
            # fever期间使用fever_power，否则使用普通power
            if self.is_fever:
                p += player.fever_power
            else:
                p += player.power
            count += 1
        self.__average_power = p / count + self.big_pot.power_boost

    @property
    def average_power(self):
        power = self.__average_power
        for buff in self.data.get('avgp_buff', []):
            power += buff.get('power', 0)
        power += self.big_pot.average_power_boost
        return power

    def count_down(self):
        if self.current_fish is None:
            return False
        self.leave_time -= 1
        if self.leave_time == 0:
            self.current_fish = None
            self.try_list = []
            return True
        return False

    def simulate_spawn_fish(self):
        self.refresh_buff()
        # calculate base probability
        fish_data_local = self.current_fish_pool
        prob_dist = []
        for fish in fish_data_local:
            prob = fish.base_probability * (1 + self.get_buff_for_rarity(fish.rarity))
            if self.is_fever:
                if 'common' in fish.spawn_at:
                    prob *= (1 - self.ice_hole.common_rate_down)
                else:
                    prob *= (1 + self.ice_hole.special_rate_up)
            prob_dist.append(prob)

        all_prob = sum(prob_dist)
        for i in range(len(prob_dist)):
            power = fish_data_local[i].std_power
            # 平均 power 每低于 std_power 5 点，概率乘 0.9
            prob_dist[i] *= 0.9 ** max(0, (power - self.average_power) / 5)
            # print(prob_dist[i])
        # normalize
        all_prob2 = sum(prob_dist)
        prob_dist = list(map(lambda x: x * all_prob / all_prob2, prob_dist))
        s = ''
        for i in range(len(fish_data_local)):
            fish: Fish = fish_data_local[i]
            # check this fish has been caught before
            if self.fish_log.caught(fish.id):
                s += f'{fish.name}【{fish.rarity}】（难度{fish.std_power}）: {prob_dist[i]*100:.4f}%\n'
            else:
                s += f'？？？？？？【{fish.rarity}】: {prob_dist[i]*100:.4f}%\n'
        return s

    def spawn_fish(self):
        fish_data_local = self.current_fish_pool
        self.refresh_buff()
        if self.current_fish is not None:
            return self.current_fish
        # calculate base probability
        prob_dist = []
        for fish in fish_data_local:
            prob = fish.base_probability * (1 + self.get_buff_for_rarity(fish.rarity))
            if self.is_fever:
                if 'common' in fish.spawn_at:
                    prob *= (1 - self.ice_hole.common_rate_down)
                else:
                    prob *= (1 + self.ice_hole.special_rate_up)
            prob_dist.append(prob)

        all_prob = sum(prob_dist)
        for i in range(len(prob_dist)):
            power = fish_data_local[i].std_power
            # 平均 power 每低于 std_power 5 点，概率乘 0.9
            prob_dist[i] *= 0.9 ** max(0, (power - self.average_power) / 15)
        # normalize
        all_prob2 = sum(prob_dist)
        prob_dist = list(map(lambda x: x * all_prob / all_prob2, prob_dist))
        # random 0 - 1
        r = random.random()
        # print(f'random: {r}, target: {all_prob}')
        for i in range(len(prob_dist)):
            if r < prob_dist[i]:
                self.current_fish = fish_data_local[i]
                self.fish_log.add_log(self.current_fish.id)
                self.save()
                self.leave_time = 2 if self.is_fever else 5
                return self.current_fish
            r -= prob_dist[i]
        return None
    
    def force_spawn_fish(self, fish_id_or_name: str):
        # 尝试通过ID获取鱼
        try:
            fish_id = int(fish_id_or_name)
            fish = Fish.get(fish_id)
        except ValueError:
            # 如果不是数字，则通过名字查找
            fish = None
            for fish1 in fish_data.values():
                if fish1.name == fish_id_or_name:
                    fish = fish1
        if fish is None:
            return None
        self.current_fish = fish
        self.fish_log.add_log(self.current_fish.id)
        self.save()
        self.leave_time = 5
        return self.current_fish

    def catch_fish(self, player: FishPlayer, master_ball=False):
        player.refresh_buff()
        if self.current_fish is None:
            return {
                "code": -1,
                "message": "当前没有鱼"
            }
        
        if player.qq in self.try_list:
            return {
                "code": -2,
                "message": "你已经尝试过捕捉这条鱼了"
            }
        fish = self.current_fish

        if master_ball and player.bag.get_item(14):
            player.bag.pop_item(14)
        elif master_ball:
            return {
                "code": -3,
                "message": "你没有大师球"
            }

        self.try_list.append(player.qq)
        success_rate = 60
        skill_ctx = player.get_skill_context()
        # 主题渔力加成
        topic_power_bonus = 0
        current_topics = list(fish.spawn_at)
        for tp in current_topics:
            topic_power_bonus += skill_ctx['topic_power'].get(tp, 0)

        # 新鱼额外渔力
        if not player.fish_log.caught(fish.id):
            topic_power_bonus += skill_ctx.get('new_fish_power', 0)

        # fever期间使用fever_power，否则使用普通power
        player_power = player.fever_power if self.is_fever else player.power
        player_power += self.big_pot.power_boost + topic_power_bonus
        diff = player_power - fish.std_power

        if master_ball:
            success_rate = 100
        else:
            if diff > 0:
                success_rate += (40 - 40 * 0.9 ** (diff / 5))
            else:
                success_rate *= 0.9 ** (-diff / 5)
            # 看破触发相当于额外一次收益机会，不改变成功率（若想影响可在此调整）

        for i, buff in enumerate(player.data['buff']):
            if buff.get('time', 0) > 0:
                player.data['buff'][i]['time'] -= 1

        if random.random() < success_rate / 100:
            player.fish_log.add_log(fish.id)
            fishing_bonus = 1
            for buff in player.buff:
                fishing_bonus += buff.get('fishing_bonus', 0)
            fishing_bonus *= 1 + self.fish_factory.fishing_bonus
            if self.is_fever:
                fishing_bonus *= 1 + self.ice_hole.fever_fishing_bonus
            value = int(fish.exp * fishing_bonus)
            # 经验/金币技能加成
            exp_multiplier = 1 + player.equipment.exp_bonus + skill_ctx.get('exp_rate', 0)/100
            gold_multiplier = 1 + player.equipment.gold_bonus + skill_ctx.get('gold_rate', 0)/100
            exp = int(value * exp_multiplier)
            gold = int(value * gold_multiplier)

            # 看破（额外渔获）与超幸运倍率
            add_line = ''
            crit_percent = skill_ctx.get('crit_percent', 0)
            if player.fish_log.caught(fish.id):
                crit_percent += skill_ctx.get('old_fish_crit', 0)
            talent_types = ['fire', 'water', 'grass', 'ice', 'electric', 'ghost', 'ground']
            for weak in fish.weakness:
                if weak in talent_types:
                    talent_id = talent_types.index(weak) + 1
                    talent_level = player.get_talent_level(talent_id)
                    if talent_level > 0:
                        crit_percent += 5 * talent_level  # 每级增加 5% 几率
            
            talent_8_level = player.get_talent_level(8)
            if talent_8_level > 0:
                crit_percent += 0.01 * talent_8_level * max(0, diff)

            is_crit = random.random() < min(crit_percent, 100) / 100
            if is_crit:
                crit_rate = max(skill_ctx.get('crit_rate', 0), 150)  # 默认 150%
                extra = int(value * (crit_rate/100 - 1))
                exp += int(extra * exp_multiplier)
                gold += int(extra * gold_multiplier)
                add_line += f"\n会心触发（概率{crit_percent:.2f}%）！额外获得渔获倍率 {crit_rate}%"

            player.data['exp'] += exp
            player.data['gold'] += gold
            if exp == gold:
                msg = f"捕获 {fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和金币"
            else:
                msg = f"捕获 {fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和 {gold} 金币"
            msg += add_line
            if len(fish.drops) > 0:
                rd = random.random()
                for drop in fish.drops:
                    rd -= drop['probability'] * (0.75 if is_crit else 1)
                    if rd < 0:
                        break
                item = FishItem.get(drop['item_id'])
                player.bag.add_item(item.id)
                msg += f"\n获得了物品【{item.name}】"
            msg += player.handle_level_up()
            player.save()
            
            # fever期间鱼不会被清除，非fever期间捕获成功后清除
            if not self.is_fever:
                self.current_fish = None
                self.try_list = []
            
            return {
                "code": 0,
                "message": msg
            }
        else:
            fail_base_exp = 1
            fail_base_gold = 0
            # 失败收益技能：失败主义 fail_reward 百分比转换为基础渔获（用 fish.exp * 百分比）
            if skill_ctx.get('fail_reward', 0) > 0:
                add_gold = add_exp = int(fish.exp * skill_ctx['fail_reward'] / 100)
                fail_base_exp = max(fail_base_exp, add_exp)
                fail_base_gold = max(fail_base_gold, add_gold)
            player.data['exp'] += fail_base_exp
            player.data['gold'] += fail_base_gold
            msg = f"捕获 {fish.name}【{fish.rarity}】 失败（成功率{success_rate:.2f}%），获得了 {fail_base_exp} 经验"
            # 失败额外掉道具概率
            if skill_ctx.get('fail_item_percent',0) > 0 and random.random() < skill_ctx['fail_item_percent']/100:
                if len(fish.drops) > 0:
                    rd = random.random()
                    for drop in fish.drops:
                        rd -= drop['probability']
                        if rd < 0:
                            break
                    item = FishItem.get(drop['item_id'])
                    player.bag.add_item(item.id)
                    msg += f"\n获得了物品【{item.name}】"
            msg += player.handle_level_up()
            player.save()
            
            # fever期间失败不会逃跑，只有非fever期间才会逃跑
            if not self.is_fever:
                flee_rate = {
                    'R': 0.2,
                    'SR': 0.5,
                    'SSR': 0.8,
                    'UR': 0
                }
                if random.random() < flee_rate[fish.rarity] + len(self.try_list) * 0.1:
                    self.current_fish = None
                    self.try_list = []
                    msg += f"\n{fish.name}【{fish.rarity}】逃走了..."
            
            return {
                "code": 1,
                "message": msg
            }
        
    def gacha(self, player: FishPlayer, ten_time=False, hundred_time=False, thousand_time=False):
        if thousand_time:
            need_gold = 10000
            draw_count = 1100
        elif hundred_time:
            need_gold = 1000
            draw_count = 110
        elif ten_time:
            need_gold = 100
            draw_count = 11
        else:
            need_gold = 10
            draw_count = 1
            
        if player.gold < need_gold:
            return {
                "code": -1,
                "message": "金币不足"
            }
        player.data['gold'] -= need_gold
        result = []
        
        # 如果是百连，使用堆叠显示
        if hundred_time or thousand_time:
            # 用于堆叠显示的字典
            item_counts = {}  # {item_id: count}
            score_total = 0
            
            for i in range(draw_count):
                res = self.gacha_pick()
                if res['type'] == 'score':
                    player.data['score'] += res['value']
                    score_total += res['value']
                elif res['type'] == 'item':
                    item_id = res['value']
                    player.bag.add_item(item_id)
                    item_counts[item_id] = item_counts.get(item_id, 0) + 1
            
            # 添加积分到结果（如果有）
            if score_total > 0:
                result.append({
                    "name": f"{score_total} 积分", 
                    "description": "可以使用积分在积分商城兑换奖励",
                    "count": 1,
                    "is_score": True
                })
            
            # 添加物品到结果（堆叠显示）
            for item_id, count in sorted(list(item_counts.items()), key=lambda x: x[0]):
                item_data = FishItem.get(str(item_id)).data
                item_data["count"] = count
                item_data["is_score"] = False
                result.append(item_data)
        else:
            # 普通单抽/十连，不堆叠显示
            for i in range(draw_count):
                res = self.gacha_pick()
                if res['type'] == 'score':
                    player.data['score'] += res['value']
                    result.append({
                        "name": f"{res['value']} 积分", 
                        "description": "可以使用积分在积分商城兑换奖励",
                        "count": 1,
                        "is_score": True
                    })
                elif res['type'] == 'item':
                    player.bag.add_item(FishItem.get(res['value']).id)
                    item_data = FishItem.get(res['value']).data
                    item_data["count"] = 1
                    item_data["is_score"] = False
                    result.append(item_data)
        
        player.save()
        return {
            "code": 0,
            "message": result
        }
    
    def gacha_pick(self):
        all_weight = sum(map(lambda x: x['weight'], gacha_data))
        r = random.random() * all_weight
        for item in gacha_data:
            if r < item['weight']:
                return item
            r -= item['weight']
        return None

    # ---------------- Mystery Gacha ----------------
    def mystery_gacha(self, player: FishPlayer, ten_time=False, hundred_time=False, thousand_time=False):
        """神秘抽卡（使用 mystery.json 中的 gacha 表）

        费用: 单抽100 / 十连1000 / 百连10000 金币
        次数: 1 / 11 / 110
        展示: 单抽、十连逐条显示；百连为堆叠显示
        """
        if self.mystic_shop.level < 1:
            return {"code": -1, "message": "神秘商店未解锁"}

        if thousand_time:
            need_gold = 100000
            draw_count = 1100
        elif hundred_time:
            need_gold = 10000
            draw_count = 110
        elif ten_time:
            need_gold = 1000
            draw_count = 11
        else:
            need_gold = 100
            draw_count = 1

        if player.gold < need_gold:
            return {"code": -1, "message": "金币不足"}
        player.data['gold'] -= need_gold

        result = []
        if hundred_time or thousand_time:
            item_counts = {}
            score_total = 0
            for _ in range(draw_count):
                res = self.mystery_gacha_pick()
                if res['type'] == 'score':
                    player.data['score'] += res['value']
                    score_total += res['value']
                else:  # item
                    iid = res['value']
                    player.bag.add_item(iid)
                    item_counts[iid] = item_counts.get(iid, 0) + 1
            if score_total > 0:
                result.append({
                    "name": f"{score_total} 积分",
                    "description": "可以使用积分在积分商城兑换奖励",
                    "count": 1,
                    "is_score": True
                })
            for iid, cnt in sorted(item_counts.items(), key=lambda x: x[0]):
                data = FishItem.get(str(iid)).data
                data['count'] = cnt
                data['is_score'] = False
                result.append(data)
        else:
            for _ in range(draw_count):
                res = self.mystery_gacha_pick()
                if res['type'] == 'score':
                    player.data['score'] += res['value']
                    result.append({
                        "name": f"{res['value']} 积分",
                        "description": "可以使用积分在积分商城兑换奖励",
                        "count": 1,
                        "is_score": True
                    })
                else:
                    iid = res['value']
                    player.bag.add_item(iid)
                    data = FishItem.get(str(iid)).data
                    data['count'] = 1
                    data['is_score'] = False
                    result.append(data)
        player.save()
        return {"code": 0, "message": result}

    def mystery_gacha_pick(self):
        all_weight = sum(map(lambda x: x['weight'], mystery_gacha_data))
        if all_weight <= 0:
            return None
        r = random.random() * all_weight
        for item in mystery_gacha_data:
            if r < item['weight']:
                return item
            r -= item['weight']
        return None

    def get_shop(self):
        return list(filter(lambda x: x.buyable and self.can_buy(x.id)['code'] == 0, fish_item.values()))
    
    def can_buy(self, id):
        good: FishItem = FishItem.get(id)
        if good.craft_shop_level > self.mystic_shop.level:
            return {
                "code": -3,
                "message": f"神秘商店等级不足，无法购买该物品（需要神秘商店 {good.craft_shop_level} 级）"
            }
        return {
            "code": 0,
            "message": "可以购买"
        }

    def shop_buy(self, player: FishPlayer, id):
        good: FishItem = FishItem.get(id)
        if good is None or good.price == 0:
            return {
                "code": -2,
                "message": "未找到该商品"
            }
        if player.gold < good.price:
            return {
                "code": -1,
                "message": "金币不足"
            }
        can_buy = self.can_buy(id)
        if can_buy['code'] != 0:
            return can_buy
        player.data['gold'] -= good.price
        player.bag.add_item(good.id, 1)
        player.save()
        return {
            "code": 0,
            "message": f"购买 {good.name} 成功"
        }
    
    def gift_item(self, giver: FishPlayer, receiver_qq: str, item_id: str):
        """
        赠送物品给其他玩家
        Args:
            giver: 赠送者
            receiver_qq: 接收者QQ号
            item_id: 物品ID
        """
        # 检查冷却时间
        current_time = time.time()
        if current_time - giver.data.get('last_gift_time', 0) < 24 * 60 * 60:  # 24小时
            remaining_time = 24 * 60 * 60 - (current_time - giver.data['last_gift_time'])
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            return {
                "code": -1,
                "message": f"赠送功能冷却中，还需等待 {hours} 小时 {minutes} 分钟"
            }
        
        # 检查物品是否存在
        item = FishItem.get(item_id)
        if item is None:
            return {
                "code": -2,
                "message": "未找到该物品"
            }
        
        # 检查物品是否可赠送
        if not item.giftable:
            return {
                "code": -3,
                "message": "该物品不可赠送"
            }
        
        # 检查赠送者是否拥有该物品
        if giver.bag.get_item_count(item_id) < 1:
            return {
                "code": -4,
                "message": "您没有该物品"
            }
        
        # 检查接收者是否存在
        receiver = FishPlayer.from_id(receiver_qq)
        if receiver is None:
            return {
                "code": -5,
                "message": "接收者未找到，请确保对方已开始游戏"
            }
        
        # 执行赠送
        giver.bag.consume_items({item_id: 1})
        receiver.bag.add_item(item_id, 1)
        giver.data['last_gift_time'] = current_time
        
        giver.save()
        receiver.save()
        
        return {
            "code": 0,
            "message": f"成功将 {item.name} 赠送给",
            "receiver": receiver_qq
        }
    
    def get_status(self):
        self.refresh_buff()
        s = f'当前池子平均渔力 {self.average_power:.1f}，已经来过 {len(self.data['fish_log'])} 条鱼了'

        for buff in self.data['avgp_buff']:
            remaining_time = buff['expire'] - time.time()
            glow_stick_name = {
                'glow_stick_normal': '普通荧光棒',
                'glow_stick_special': '海皇荧光棒'
            }[buff['key']]
            s += f'\n{glow_stick_name}剩余 {remaining_time:.0f} 秒'
        
        # fever期间显示特殊状态
        if self.is_fever:
            remaining_time = int(self.data.get('fever_expire', 0) - time.time())
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            s += f'\n🔥 当前处于鱼群状态！剩余时间 {hours}小时{minutes}分钟'
            s += '\n🔥 鱼群期间：等级和渔具提供的渔力削弱、鱼不会逃跑、可多人捕获、无法投放饵料'
        
        if self.current_fish is not None:
            s += f'\n当前池子中有{'一群' if self.is_fever else '一条'} {self.current_fish.name}【{self.current_fish.rarity}】！'
        
        # 非fever期间显示buff信息，fever期间自动拥有黄金鱼料buff
        if not self.is_fever:
            for buff in self.data['buff']:
                if buff.get('expire', 0) > 0:
                    s += f'\n【{buff["rarity"]}】种类鱼出现概率 +{100 * buff["bonus"]}% 效果剩余 {int(buff["expire"] - time.time())} 秒'
        else:
            s += '\n🔥 鱼群期间自动拥有黄金鱼料效果：【SSR】+20000% 【SR】+12000% 【R】+6000%'
        
        return {
            "code": 0,
            "message": s
        }

    def use_item(self, player: FishPlayer, item_id, force=False, extra_args=[]):
        self.refresh_buff()
        item: Optional[FishItem] = player.bag.get_item(item_id)
        if item is None:
            return {
                "code": -1,
                "message": "背包中没有该物品"
            }
        if item.equipable:
            equipped = player.equipment.equip(item)
            if not equipped:
                player.save()
                return {
                    "code": 0,
                    "message": f"卸下 {item.name} 成功"
                }
            else:
                player.save()
                return {
                    "code": 0,
                    "message": f"装备 {item.name} 成功"
                }
        
        # fever期间无法投放饵料
        if self.is_fever and item.is_feed():
            return {
                "code": -2,
                "message": "鱼群期间无法投放饵料！"
            }
        
        if self.data['feed_time'] >= 5 and item.is_feed():
            return {
                "code": -2,
                "message": "鱼已经吃饱了，明天再喂吧"
            }
        if not force and item.is_feed() and len(self.data['buff']) > 0:
            return {
                "code": -2,
                "message": f"当前已有食料效果，如果确定要覆盖，请输入【强制使用 {item_id}】"
            }
        if item.id == 1:
            player.bag.pop_item(item_id)
            self.data['buff'] = [
                {
                    "rarity": "R",
                    "bonus": 40,
                    "expire": time.time() + 1800
                }
            ]
            self.data['feed_time'] += 1
        elif item.id == 2:
            player.bag.pop_item(item_id)
            self.data['buff'] = [
                {
                    "rarity": "SR",
                    "bonus": 100,
                    "expire": time.time() + 3600
                },
                {
                    "rarity": "R",
                    "bonus": 60,
                    "expire": time.time() + 3600
                }
            ]
            self.data['feed_time'] += 1
        elif item.id == 3:
            player.bag.pop_item(item_id)
            self.data['buff'] = [
                {
                    "rarity": "SSR",
                    "bonus": 200,
                    "expire": time.time() + 7200
                },
                {
                    "rarity": "SR",
                    "bonus": 120,
                    "expire": time.time() + 7200
                },
                {
                    "rarity": "R",
                    "bonus": 60,
                    "expire": time.time() + 7200
                }
            ]
            self.data['feed_time'] += 1
        elif item.id == 404:
            player.bag.pop_item(item_id)
            self.data['buff'] = [
                {
                    "rarity": "SSR",
                    "bonus": 600,
                    "expire": time.time() + 7200
                }
            ]
            self.data['feed_time'] += 1
        elif item.id == 4:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 10,
                "time": 1 + self.fish_lab.extra_power_boost_times
            })
        elif item.id == 5:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 20,
                "time": 2 + self.fish_lab.extra_power_boost_times
            })
        elif item.id == 6:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 40,
                "time": 4 + self.fish_lab.extra_power_boost_times
            })
        elif item.id == 7:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.25,
                "expire": time.time() + 1200 + self.fish_lab.extra_fishing_bonus_second
            })
        elif item.id == 8:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.5,
                "expire": time.time() + 1200 + self.fish_lab.extra_fishing_bonus_second
            })
        elif item.id == 9:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 1,
                "expire": time.time() + 1200 + self.fish_lab.extra_fishing_bonus_second
            })
        elif item.id == 10:
            player.bag.pop_item(item_id)
            self.refresh_buff()
            self.data['avgp_buff'] = list(filter(lambda x: x['key'] != 'glow_stick_normal', self.data.get('avgp_buff', [])))
            self.data['avgp_buff'].append({
                'key': 'glow_stick_normal',
                'power': 15,
                'expire': time.time() + 1800
            })
        elif item.id == 11:
            player.bag.pop_item(item_id)
            self.refresh_buff()
            self.data['avgp_buff'] = list(filter(lambda x: x['key'] != 'glow_stick_normal', self.data.get('avgp_buff', [])))
            self.data['avgp_buff'].append({
                'key': 'glow_stick_normal',
                'power': 30,
                'expire': time.time() + 1800
            })
        elif item.id == 12:
            player.bag.pop_item(item_id)
            self.refresh_buff()
            self.data['avgp_buff'] = list(filter(lambda x: x['key'] != 'glow_stick_normal', self.data.get('avgp_buff', [])))
            self.data['avgp_buff'].append({
                'key': 'glow_stick_normal',
                'power': 60,
                'expire': time.time() + 1800
            })
        elif item.id == 23:  # 钻石渔力强化剂
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 60,
                "time": 6 + self.fish_lab.extra_power_boost_times
            })
        elif item.id == 24:  # 钻石渔获加成卡
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 1.5,
                "expire": time.time() + 1200 + self.fish_lab.extra_fishing_bonus_second
            })
        # 天赋书：提升指定天赋经验
        elif item.id in [25, 26, 27, 28, 29]:
            # 解析参数：25/26/27/28: 使用 <ItemID> <天赋ID>
            # 29: 使用 29 <天赋ID> <经验>
            if self.seven_statue.level == 0:
                return {
                    "code": -2,
                    "message": "至少需要 1 级七天神像才能学习技能"
                }
            try:
                talent_id = int(extra_args.pop(0))
            except Exception:
                if item.id == 29:
                    return {
                        "code": -2,
                        "message": "使用格式错误：使用 29 <天赋ID> <经验>"
                    }
                else:
                    return {
                        "code": -2,
                        "message": "使用格式错误：使用 <25|26|27|28> <天赋ID>"
                    }
            # 校验天赋ID
            if talent_id <= 0 or talent_id > len(talent_data):
                return {"code": -2, "message": "无效的天赋ID"}

            # 计算经验与金币消耗
            if item.id == 25:
                gain = 10
                cost_gold = 0
            elif item.id == 26:
                gain = 100
                cost_gold = 0
            elif item.id == 27:
                gain = 400
                cost_gold = 0
            elif item.id == 28:
                gain = 1000
                cost_gold = 0
            else:  # 29
                try:
                    req_gain = int(extra_args.pop(0))
                except Exception:
                    return {
                        "code": -2,
                        "message": "使用格式错误：使用 29 <天赋ID> <经验>"
                    }
                if req_gain <= 0:
                    return {"code": -2, "message": "经验必须为正整数"}
                # 上限 2000
                gain = min(req_gain, 2000)
                cost_gold = gain * 10
                if player.data.get('gold', 0) < cost_gold:
                    return {"code": -3, "message": f"金币不足，需要 {cost_gold} 金币"}

            # 应用经验并消耗物品/金币
            # 记录使用前等级
            old_level = player.get_talent_level(talent_id)
            new_level, level_up = player.add_talent_exp(talent_id, gain)
            # 扣除物品
            player.bag.pop_item(item_id)
            # 29 需要扣金币
            if cost_gold > 0:
                player.data['gold'] -= cost_gold
                if player.data['gold'] < 0:
                    player.data['gold'] = 0
            # 保存
            player.save()

            talent_name = talent_data[talent_id - 1].get('name', f'Talent {talent_id}')
            msg = f"已为天赋【{talent_name}】增加 {gain} 点经验。Lv.{old_level} -> Lv.{new_level}"
            if level_up > 0:
                msg += f"（提升 {level_up} 级）"
            if cost_gold > 0:
                msg += f"，消耗金币 {cost_gold}"
            return {"code": 0, "message": msg}
        elif item.id == 208: # 饰品溶解液
            try:
                accessory_id = int(extra_args.pop(0))
            except Exception as e:
                return {
                    "code": -2,
                    "message": "使用溶解液时请输入【使用 208 需要溶解的饰品ID】，例如【使用 208 1201】"
                }
            meta_store = player.data.setdefault('accessory_meta', {})
            if str(accessory_id) not in meta_store:
                return {
                    "code": -3,
                    "message": "你没有这个饰品！"
                }
            if player.equipment.accessory_id == accessory_id:
                return {
                    "code": -4,
                    "message": "请先卸下该饰品！"
                }
            accessory_data = meta_store[str(accessory_id)]
            accessory_item_id = accessory_data['base_id']
            accessory_item = FishItem.get(str(accessory_item_id))
            gem = accessory_item.craftby[0]
            sub_gem = max(gem - 1, 20)
            fail_percent = player.renew_accessory * 0.05
            
            player.bag.pop_item(item_id)
            player.bag.pop_item(25)
            player.bag.pop_item(accessory_id)
            del player.data['accessory_meta'][str(accessory_id)]
            player.renew_accessory += 1

            r = random.random()
            if r < fail_percent:
                player.save()
                return {
                    "code": 0,
                    "message": "完蛋啦！溶解失败，饰品和宝石都没了！"
                }
            elif r < (fail_percent * 3):
                player.bag.add_item(sub_gem)
                player.save()
                return {
                    "code": 0,
                    "message": f"溶解成功，但只回收到了低级宝石 {FishItem.get(str(sub_gem)).name}！"
                }
            else:
                player.bag.add_item(gem)
                player.save()
                return {
                    "code": 0,
                    "message": f"溶解成功，回收到了宝石 {FishItem.get(str(gem)).name}！"
                }
        elif item.id == 299:
            player.bag.pop_item(299)
            player.data['gold'] += 1000
            player.save()
        elif item.id == 407:
            player.bag.pop_item(item_id)
            self.refresh_buff()
            self.data['avgp_buff'] = list(filter(lambda x: x['key'] != 'glow_stick_special', self.data.get('avgp_buff', [])))
            self.data['avgp_buff'].append({
                'key': 'glow_stick_special',
                'power': 100,
                'expire': time.time() + 3600
            })
        elif item.id == 408:
            player.bag.pop_item(item_id)
            self.trigger_fever()
        elif str(item.id) in mystery_jewel_table:  # 宝玉转换
            if self.mystic_shop.level < 1:
                return {"code": -1, "message": "神秘商店未解锁"}
            table = mystery_jewel_table[str(item.id)]
            player.bag.pop_item(item_id)
            total = sum(table.values())
            rnd = random.random() * total
            picked = None
            for target, weight in table.items():
                if rnd < weight:
                    picked = int(target)
                    break
                rnd -= weight
            if picked is None:
                picked = int(next(iter(table.keys())))
            player.bag.add_item(picked)
            self.save(); player.save()
            return {
                "code": 0,
                "message": f"神秘的气息包裹住了 {item.name}，它化作了 {FishItem.get(str(picked)).name}！"
            }
        else:
            return {
                "code": -2,
                "message": "该物品无法使用，或效果暂未实装！"
            }
        self.save()
        player.save()
        extra = ''
        if item.id <= 3:
            extra += f'\n今天还能投 {5 - self.data["feed_time"]} 次食料'
        if item.id == 408:
            minute = (self.data['fever_expire'] - time.time()) // 60
            extra += f"\n大量的鱼群聚集了起来！\n接下来{minute}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n但与此同时，你的等级和渔具的效果似乎受到了削弱……"
        return {
            "code": 0,
            "message": f"使用 {item.name} 成功" + extra
        }
    
    def get_craftable_items(self):
        """获取所有可合成的物品"""
    # 仅展示：可合成 且 神秘商店等级 >= 物品要求的 craft_shop_level
        mystic_level = getattr(self.mystic_shop, 'level', 0)
        return [item for item in fish_item.values() if item.craftable and mystic_level >= getattr(item, 'craft_shop_level', -1)]
    
    def craft_item(self, player: FishPlayer, item_id: int):
        """合成物品"""
        item: FishItem = FishItem.get(str(item_id))
        if item is None:
            return {
                "code": -1,
                "message": "未找到该物品"
            }
        
        if not item.craftable:
            return {
                "code": -2,
                "message": "该物品无法合成"
            }

    # 神秘商店等级 gating：需要 mystic_shop.level >= craft_shop_level
        mystic_level = getattr(self.mystic_shop, 'level', 0)
        required_level_threshold = getattr(item, 'craft_shop_level', -1)
        if mystic_level < required_level_threshold:
            return {
                "code": -4,
                "message": f"神秘商店等级不足，需要 >= {required_level_threshold}（当前 {mystic_level}）"
            }
        
        # 统计需要的材料
        material_requirements = {}
        for material_id in item.craftby:
            material_requirements[material_id] = material_requirements.get(material_id, 0) + 1
        
        # 检查材料是否充足
        for material_id, required_count in material_requirements.items():
            current_count = player.bag.get_item_count(material_id)
            if current_count < required_count:
                material_item = FishItem.get(str(material_id))
                material_name = material_item.name if material_item else f"物品{material_id}"
                return {
                    "code": -3,
                    "message": f"材料不足：{material_name} 需要 {required_count} 个，当前只有 {current_count} 个"
                }

        craft_score_cost = item.craft_score_cost
        if item_id == 14:
            craft_score_cost *= 2 ** player.master_ball_crafts
        # 检查积分是否充足
        if craft_score_cost > 0:
            if player.score < craft_score_cost:
                return {
                    "code": -4,
                    "message": f"积分不足：需要 {craft_score_cost} 积分，当前只有 {player.score} 积分"
                }
        
        # 消耗材料
        if not player.bag.consume_items(material_requirements):
            return {
                "code": -5,
                "message": "消耗材料失败"
            }
        
        # 消耗积分
        if craft_score_cost > 0:
            player.data['score'] -= craft_score_cost
        
        # 添加合成的物品 / 配件特殊处理
        if item_id == 14:
            player.master_ball_crafts += 1

        if item.type == 'accessory':
            meta_store = player.data.setdefault('accessory_meta', {})
            existing_for_base = [iid for iid, meta in meta_store.items() if meta.get('base_id') == item_id]
            if len(existing_for_base) >= 100:
                return {"code": -6, "message": "该配件已经达到可拥有的最大数量(100)"}
            used_ids = set(int(k) for k in meta_store.keys())
            allocated_id = None
            for cand in range(item.id, item.id_range + 1):
                if cand not in used_ids:
                    allocated_id = cand
                    break
            if not allocated_id:
                return {"code": -6, "message": "没有可用的配件实例ID，请联系管理员"}
            import random as _r
            remaining_sp = item.skill_point
            skill_pool = list(fish_skills.values())
            _r.shuffle(skill_pool)
            skills_list = []
            for sk in skill_pool:
                if sk.score == 0:
                    continue
                cost = sk.score or 1
                if cost > remaining_sp:
                    continue
                level = 1
                remaining_sp -= cost
                while level < sk.max_level and remaining_sp >= cost and _r.random() < 0.5:
                    remaining_sp -= cost
                    level += 1
                skills_list.append({'id': sk.id, 'level': level})
                if remaining_sp <= 0:
                    break
            meta_store[str(allocated_id)] = {'base_id': item_id, 'skills': skills_list}
            player.bag.add_item(str(allocated_id), 1)
        else:
            player.bag.add_item(item_id, 1)
        player.save()
        
        success_message = f"成功合成 {item.name}！"
        if craft_score_cost > 0:
            success_message += f" 消耗了 {craft_score_cost} 积分"
        if item.type == 'accessory':
            success_message += f"\n（配件实例ID {allocated_id}），技能列表："
            for sk in skills_list:
                skill_obj = fish_skills.get(sk['id'])
                if skill_obj:
                    success_message += f"\n- {skill_obj.name} Lv.{sk['level']}"
        
        return {
            "code": 0,
            "message": success_message
        }
    
    def build(self, player: FishPlayer, building_name: str, item_id: int):
        if building_name not in building_name_map:
            return {
                "code": "-1",
                "message": f'未找到名为 {building_name} 的建筑'
            }
        cd_time = self.building_center.build_cooldown * 3600 + player.data.get('last_build_time', 0)
        if time.time() < cd_time:
            return {
                "code": "-1",
                "message": f"建筑功能冷却中，剩余 {(cd_time - time.time()) // 60:.0f} 分钟"
            }
        building: BuildingBase = self.__getattribute__(building_name_map[building_name])
        # 先检测有没有
        if player.bag.get_item_count(item_id) <= 0:
            return {
                "code": "-1",
                "message": f'道具不足'
            }
        count = building.add_materials(item_id, 1)
        if count == 0:
            return {
                "code": "-1",
                "message": f'此建筑不需要此材料'
            }
        else:
            player.bag.pop_item(item_id)
            player.data['last_build_time'] = time.time()
            player.save()
            return {
                "code": 0,
                "message": f"添加建筑材料 {FishItem.get(item_id).name} 成功"
            }
        
    def building_level_up(self, building_name: str):
        if building_name not in building_name_map:
            return {
                "code": "-1",
                "message": f'未找到名为 {building_name} 的建筑'
            }
        building: BuildingBase = self.__getattribute__(building_name_map[building_name])
        # 已达上限
        if building.level >= building.max_level:
            return {
                "code": "-1",
                "message": f"{building.name} 已达到最高等级"
            }

        next_level = building.level + 1

        # 检查前置条件
        unmet_prerequisites = []
        prerequisites = building.get_level_prerequisites(next_level)
        for prereq_key, required_level in prerequisites.items():
            try:
                prereq_building: BuildingBase = getattr(self, prereq_key)
                current_level = prereq_building.level
                if current_level < required_level:
                    # 使用建筑显示名，如果没有则用key
                    prereq_name = getattr(prereq_building, 'name', prereq_key)
                    unmet_prerequisites.append((prereq_name, current_level, required_level))
            except AttributeError:
                # 该前置建筑不存在（理论上不会发生）
                unmet_prerequisites.append((prereq_key, 0, required_level))

        if unmet_prerequisites:
            lines = ["升级失败：前置条件未满足："]
            for name, cur, req in unmet_prerequisites:
                lines.append(f"- {name}: Lv.{cur}/{req}")
            return {
                "code": "-1",
                "message": "\n".join(lines)
            }

        # 检查材料是否足够
        if not building.can_upgrade():
            # 汇总缺少材料详情
            materials_status = building.get_materials_status()
            lack_lines = []
            for request, current_count in materials_status:
                if current_count < request.count:
                    lack_lines.append(f"- {request.desc}: {current_count}/{request.count}")
            if lack_lines:
                return {
                    "code": "-1",
                    "message": "升级失败：材料不足：\n" + "\n".join(lack_lines)
                }
            # 兜底（理论上不会到这里）
            return {
                "code": "-1",
                "message": "升级失败：条件未满足"
            }

        # 执行升级
        if building.upgrade():
            self.save()
            return {
                "code": 0,
                "message": f"{building.name} 已升级至 Lv.{building.level}"
            }
        else:
            return {
                "code": "-1",
                "message": "升级失败：未知原因"
            }

    def pot_add_item(self, player: FishPlayer, item: FishItem, count: int):
        pot = self.big_pot
        remain_capacity = pot.capacity - pot.current
        item_volume = [1, 2, 5, 10][item.rarity - 1]
        if 300 < item.id <= 400 or item.id == 104:
            item_volume *= 5
        item_consume = min(count, (remain_capacity - 1) // item_volume + 1)
        if item_consume == 0:
            return {
                "code": "-1",
                "message": "大锅容量已满，添加失败"
            }
        player_item_count = player.bag.get_item_count(item.id)
        if item.id in player.equipment.ids:
            player_item_count -= 1
        new_item_consume = min(player_item_count, item_consume)
        if new_item_consume == 0:
            return {
                "code": "-1",
                "message": f"你没有道具 {item.name}"
            }
        player.bag.pop_item(item.id, new_item_consume)
        player.save()
        vol = new_item_consume * item_volume
        pot.current = min(pot.current + vol, pot.capacity)
        self.save()
        msg = ''
        if new_item_consume < item_consume:
            msg += f'由于你的 { item.name } 不足，只添加了 {new_item_consume} 个'
        else:
            msg += f'添加了 { new_item_consume } 个 { item.name }'
        msg += f'，内容量增加了 {vol}\n当前内容量：{pot.current} / {pot.capacity} （消耗速度：{pot.consume_speed} / 10min）'
        return {
            "code": 0,
            "message": msg
        }

    def get_pot_status(self):
        pot = self.big_pot
        return f'当前大锅等级 { pot.level }\n内容量：{pot.current} / {pot.capacity} （消耗速度：{pot.consume_speed} / 10min）\n平均渔力加成：{pot.average_power_boost }\n玩家渔力加成：{pot.power_boost}'