from typing import Optional
from src.data_access.redis import DictRedisData, redis_global
from src.libraries.fishgame.data import *
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


class FishPlayer(DictRedisData):
    def __init__(self, qq):
        self.qq = qq
        token = f'fishgame_user_data_{md5(str(qq))}'
        super().__init__(token, default=FishPlayer.default_user_data())
        self.bag = Backpack(self.data['bag'])
        self.fish_log = FishLog(self.data['fish_log'])
        self.equipment = Equipment(self.data['equipment'])

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
            "last_gift_time": 0
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
    def power(self):
        base_power = self.level
        for item in self.equipment.items:
            if item is not None:
                base_power += item.power
        for buff in self.buff:
            base_power += buff.get('power', 0)
        return base_power
    
    @property
    def fever_power(self):
        base_power = self.level // 5
        for item in self.equipment.items:
            if item is not None:
                item: FishItem
                if item.type == 'rod' and item.id not in [403, 405]:
                    base_power += item.power // 2
                elif item.id == 406:
                    base_power += item.power + 25
                else:
                    base_power += item.power
        for buff in self.buff:
            base_power += buff.get('power', 0)
        return base_power
    
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


class FishGame(DictRedisData):
    def __init__(self, group_id=0):
        token = f'fishgame_group_data_{group_id}'
        super().__init__(token, default=FishGame.default_group_data())
        self.fish_log = FishLog(self.data["fish_log"])
        self.average_power = 0
        self.current_fish: Fish = None
        self.try_list = []
        self.leave_time = 0

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
            "fever_fishes": []
        }
    
    @property
    def current_fish_pool(self) -> list[Fish]:
        if self.is_fever:
            return list(map(Fish.get, self.data['fever_fishes']))
        else:
            # 返回基础鱼池（来自fish_data_poke_ver.json的鱼，ID为1到len(fish_data_poke_ver)）
            return [Fish.get(i) for i in range(1, len(fish_data_poke_ver) + 1) if Fish.get(i) is not None]

    def refresh_buff(self):
        self.data['buff'] = list(filter(buff_available, self.data['buff']))
        if self.data.get('day', 0) != time.localtime().tm_mday:
            self.data['day'] = time.localtime().tm_mday
            self.data['feed_time'] = 0

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
        self.average_power = p / count

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
        prob_dist = list(map(lambda fish: fish.base_probability * (1 + self.get_buff_for_rarity(fish.rarity)), fish_data_local))
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
        prob_dist = list(map(lambda fish: fish.base_probability * (1 + self.get_buff_for_rarity(fish.rarity)), fish_data_local))
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

    def catch_fish(self, player: FishPlayer):
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
        self.try_list.append(player.qq)
        fish = self.current_fish
        success_rate = 60
        
        # fever期间使用fever_power，否则使用普通power
        player_power = player.fever_power if self.is_fever else player.power
        diff = player_power - fish.std_power
        
        if diff > 0:
            success_rate += (40 - 40 * 0.9 ** (diff / 5))
        else:
            success_rate *= 0.9 ** (-diff / 5)

        for i, buff in enumerate(player.data['buff']):
            if buff.get('time', 0) > 0:
                player.data['buff'][i]['time'] -= 1

        if random.random() < success_rate / 100:
            player.fish_log.add_log(fish.id)
            fishing_bonus = 1
            for buff in player.buff:
                fishing_bonus += buff.get('fishing_bonus', 0)
            value = int(fish.exp * fishing_bonus)
            exp = int(value * (1 + player.equipment.exp_bonus))
            gold = int(value * (1 + player.equipment.gold_bonus) )
            player.data['exp'] += exp
            player.data['gold'] += gold
            if exp == gold:
                msg = f"捕获 {fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和金币"
            else:
                msg = f"捕获 {fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和 {gold} 金币"
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
            
            # fever期间鱼不会被清除，非fever期间捕获成功后清除
            if not self.is_fever:
                self.current_fish = None
                self.try_list = []
            
            return {
                "code": 0,
                "message": msg
            }
        else:
            player.data['exp'] += 1
            player.save()
            msg = f"捕获 {fish.name}【{fish.rarity}】 失败（成功率{success_rate:.2f}%），但至少你获得了 1 经验"
            
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
        
    def gacha(self, player: FishPlayer, ten_time=False, hundred_time=False):
        if hundred_time:
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
        if hundred_time:
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
            for item_id, count in item_counts.items():
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

    def get_shop(self):
        return list(filter(lambda x: x.buyable, fish_item.values()))

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
            "message": f"成功将 {item.name} 赠送给 {receiver_qq}"
        }
    
    def get_status(self):
        self.refresh_buff()
        s = f'当前池子平均渔力 {self.average_power:.1f}，已经来过 {len(self.data['fish_log'])} 条鱼了'
        
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

    def use_item(self, player: FishPlayer, item_id, force=False):
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
                "time": 1
            })
        elif item.id == 5:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 20,
                "time": 2
            })
        elif item.id == 6:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 40,
                "time": 4
            })
        elif item.id == 7:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.25,
                "expire": time.time() + 1200
            })
        elif item.id == 8:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.5,
                "expire": time.time() + 1200
            })
        elif item.id == 9:
            player.bag.pop_item(item_id)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 1,
                "expire": time.time() + 1200
            })
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
        return {
            "code": 0,
            "message": f"使用 {item.name} 成功" + extra
        }
    
    def get_craftable_items(self):
        """获取所有可合成的物品"""
        return [item for item in fish_item.values() if item.craftable]
    
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
        
        # 检查积分是否充足
        if item.craft_score_cost > 0:
            if player.score < item.craft_score_cost:
                return {
                    "code": -4,
                    "message": f"积分不足：需要 {item.craft_score_cost} 积分，当前只有 {player.score} 积分"
                }
        
        # 消耗材料
        if not player.bag.consume_items(material_requirements):
            return {
                "code": -5,
                "message": "消耗材料失败"
            }
        
        # 消耗积分
        if item.craft_score_cost > 0:
            player.data['score'] -= item.craft_score_cost
        
        # 添加合成的物品
        player.bag.add_item(item_id, 1)
        player.save()
        
        success_message = f"成功合成 {item.name}！"
        if item.craft_score_cost > 0:
            success_message += f" 消耗了 {item.craft_score_cost} 积分"
        
        return {
            "code": 0,
            "message": success_message
        }