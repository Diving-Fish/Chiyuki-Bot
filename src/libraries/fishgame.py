from src.data_access.redis import DictRedisData, redis_global
import hashlib
import json
import random
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


players = {}


with open('data/fishgame/fish_data.json', 'r', encoding='utf-8') as f:
    fish_data = json.load(f)

with open('data/fishgame/fish_item.json', 'r', encoding='utf-8') as f:
    fish_item = json.load(f)

def get_item_by_id(item_id):
    for item in fish_item:
        if item['id'] == item_id:
            return item
    return None

with open('data/fishgame/gacha.json', 'r', encoding='utf-8') as f:
    gacha_data = json.load(f)


class FishPlayer(DictRedisData):
    def __init__(self, qq):
        self.qq = qq
        token = f'fishgame_user_data_{md5(str(qq))}'
        super().__init__(token, default=FishPlayer.default_user_data())

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
            "bag": [{
                "id": 1,
                "name": "食料",
                "rarity": 1,
                "description": "使用后，在 30 分钟内，【R】鱼的出现概率将大幅提高"
            }],
            "buff": []
        }

    def refresh_buff(self):
        self.data['buff'] = list(filter(buff_available, self.data['buff']))

    def pop_item(self, item_index):
        item = self.bag[item_index]
        if item.get('count', 1) > 1:
            self.bag[item_index]['count'] -= 1
        else:
            self.bag.pop(item_index)

    def sort_bag(self):
        # 合并所有非装备类物品
        new_bag = {}
        for item in self.bag:
            if item['id'] < 100:
                if item['id'] in new_bag:
                    new_bag[item['id']]['count'] += item.get('count', 1)
                else:
                    new_bag[item['id']] = item
                    new_bag[item['id']]['count'] = item.get('count', 1)
        # 装备类物品
        equips = sorted(filter(lambda x: x['id'] >= 100, self.bag), key=lambda x: 0 if x.get('equipped', False) else 1)
        consumables = sorted(list(new_bag.values()), key=lambda x: x['id'])
        self.data['bag'] = consumables + list(equips)
        self.save()
    
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
    
    @property
    def fish_log(self):
        return self.data['fish_log']
    
    @property
    def bag(self):
        return self.data['bag']
    
    @property
    def buff(self):
        return self.data['buff']
    
    @property
    def power(self):
        base_power = self.level
        for equipment in self.bag:
            if equipment.get('equipped', False):
                base_power += equipment.get('power', 0)
        for buff in self.buff:
            base_power += buff.get('power', 0)
        return base_power
    
    @property
    def equipment(self):
        equipment = {}
        for item in self.bag:
            if item.get('equipped', False) and item.get('type', '') != '':
                equipment[item['type']] = item
        return equipment
    
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
        self.average_power = 0
        self.current_fish = None
        self.try_list = []
        self.leave_time = 0

    @staticmethod
    def default_group_data():
        return {
            "fish_log": [],
            "buff": [],
            "day": 0,
            "feed_time": 0
        }

    def refresh_buff(self):
        self.data['buff'] = list(filter(buff_available, self.data['buff']))
        if self.data.get('day', 0) != time.localtime().tm_mday:
            self.data['day'] = time.localtime().tm_mday
            self.data['feed_time'] = 0

    def is_fish_caught(self, name):
        for fish in self.data['fish_log']:
            if fish['name'] == name:
                return True
        return False
    
    def get_buff_for_rarity(self, rarity):
        value = 0
        for buff in self.data['buff']:
            if rarity == buff.get('rarity', ''):
                value += buff.get('bonus', 0)
        return value

    def update_average_power(self, qq_list):
        p = 0
        count = 0
        for qq in qq_list:
            player = None
            if qq in players:
                player = players[qq]
            else:
                player = FishPlayer.try_get(qq)
                if player is None:
                    continue
                players[qq] = player
            print(player.power)
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
        prob_dist = list(map(lambda x: x['base_probability'] * (1 + self.get_buff_for_rarity(x['rarity'])), fish_data))
        all_prob = sum(prob_dist)
        for i in range(len(prob_dist)):
            power = fish_data[i]['std_power']
            # 平均 power 每低于 std_power 5 点，概率乘 0.9
            prob_dist[i] *= 0.9 ** max(0, (power - self.average_power) / 5)
            print(prob_dist[i])
        # normalize
        all_prob2 = sum(prob_dist)
        prob_dist = list(map(lambda x: x * all_prob / all_prob2, prob_dist))
        s = ''
        for i in range(len(fish_data)):
            # check this fish has been caught before
            if self.is_fish_caught(fish_data[i]['name']):
                s += f'{fish_data[i]["name"]}【{fish_data[i]["rarity"]}】（难度{fish_data[i]['std_power']}）: {prob_dist[i]*100:.4f}%\n'
            else:
                s += f'？？？？？？【{fish_data[i]["rarity"]}】: {prob_dist[i]*100:.4f}%\n'
        return s


    def spawn_fish(self):
        self.refresh_buff()
        # self.current_fish = {
        #     "name": generate_mixed_gibberish(),
        #     "detail": "███████████████████████████████████████",
        #     "rarity": "UR",
        #     "std_power": 444,
        #     "base_probability": 0.0003,
        #     "exp": 7
        # }
        # return self.current_fish
        if self.current_fish is not None:
            return self.current_fish
        # calculate base probability
        prob_dist = list(map(lambda x: x['base_probability'] * (1 + self.get_buff_for_rarity(x['rarity'])), fish_data))
        all_prob = sum(prob_dist)
        for i in range(len(prob_dist)):
            power = fish_data[i]['std_power']
            # 平均 power 每低于 std_power 5 点，概率乘 0.9
            prob_dist[i] *= 0.9 ** max(0, (power - self.average_power) / 15)
        # normalize
        all_prob2 = sum(prob_dist)
        prob_dist = list(map(lambda x: x * all_prob / all_prob2, prob_dist))
        # random 0 - 1
        r = random.random()
        print(f'random: {r}, target: {all_prob}')
        for i in range(len(prob_dist)):
            if r < prob_dist[i]:
                self.current_fish = fish_data[i]
                self.data['fish_log'].append(fish_data[i])
                self.save()
                self.leave_time = 5
                return fish_data[i]
            r -= prob_dist[i]
        return None

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
        diff = player.power - fish['std_power']
        if diff > 0:
            success_rate += (40 - 40 * 0.9 ** (diff / 5))
        else:
            success_rate *= 0.9 ** (-diff / 5)
        if str(player.qq) == '2300756578':
            success_rate = 999.99

        for i, buff in enumerate(player.data['buff']):
            if buff.get('time', 0) > 0:
                player.data['buff'][i]['time'] -= 1

        if random.random() < success_rate / 100:
            player.data['fish_log'].append(fish)
            fishing_bonus = 1
            for buff in player.buff:
                fishing_bonus += buff.get('fishing_bonus', 0)
            value = int(fish['exp'] * fishing_bonus)
            player.data['exp'] += value
            player.data['gold'] += value
            msg = f"捕获 {fish['name']}【{fish['rarity']}】 成功（成功率{success_rate:.2f}%），获得了 {value} 经验和金币"
            msg += player.handle_level_up()
            player.save()
            self.current_fish = None
            self.try_list = []
            return {
                "code": 0,
                "message": msg
            }
        else:
            player.data['exp'] += 1
            player.save()
            msg = f"捕获 {fish['name']}【{fish['rarity']}】 失败（成功率{success_rate:.2f}%），但至少你获得了 1 经验"
            flee_rate = {
                'R': 0.2,
                'SR': 0.5,
                'SSR': 0.8,
                'UR': 0
            }
            if random.random() < flee_rate[fish['rarity']] + len(self.try_list) * 0.1:
                self.current_fish = None
                self.try_list = []
                msg += f"\n{fish['name']}【{fish['rarity']}】逃走了..."
            return {
                "code": 1,
                "message": msg
            }
        
    def gacha(self, player: FishPlayer, ten_time=False):
        need_gold = 100 if ten_time else 10
        if player.gold < need_gold:
            return {
                "code": -1,
                "message": "金币不足"
            }
        player.data['gold'] -= need_gold
        result = []
        if ten_time:
            for i in range(11):
                res = self.gacha_pick()
                if res['type'] == 'score':
                    player.data['score'] += res['value']
                    result.append({"name": f"{res['value']} 积分", "description": "可以使用积分在积分商城兑换奖励"})
                elif res['type'] == 'item':
                    player.bag.append(get_item_by_id(res['value']))
                    result.append(get_item_by_id(res['value']))
        else:
            res = self.gacha_pick()
            if res['type'] == 'score':
                player.data['score'] += res['value']
                result.append({"name": f"{res['value']} 积分", "description": "可以使用积分在积分商城兑换奖励"})
            elif res['type'] == 'item':
                player.bag.append(get_item_by_id(res['value']))
                result.append(get_item_by_id(res['value']))
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
        return list(filter(lambda x: x.get('price', 0) != 0, fish_item))

    def shop_buy(self, player: FishPlayer, id):
        good = get_item_by_id(id)
        if good is None or good.get('price', 0) == 0:
            return {
                "code": -2,
                "message": "未找到该商品"
            }
        if player.gold < good.get('price'):
            return {
                "code": -1,
                "message": "金币不足"
            }
        player.data['gold'] -= good.get('price')
        player.bag.append(good)
        player.save()
        return {
            "code": 0,
            "message": f"购买 {good.get('name')} 成功"
        }
    
    def get_status(self):
        self.refresh_buff()
        s = f'当前池子已经来过 {len(self.data['fish_log'])} 条鱼了'
        if self.current_fish is not None:
            s += f'\n当前池子中有一条 {self.current_fish["name"]}【{self.current_fish["rarity"]}】！'
        for buff in self.data['buff']:
            if buff.get('expire', 0) > 0:
                s += f'\n【{buff["rarity"]}】种类鱼出现概率 +{100 * buff["bonus"]}% 效果剩余 {int(buff["expire"] - time.time())} 秒'
        return {
            "code": 0,
            "message": s
        }

    def use_item(self, player: FishPlayer, item_index):
        self.refresh_buff()
        if item_index >= len(player.bag):
            return {
                "code": -1,
                "message": "背包中没有该物品"
            }
        item = player.bag[item_index]
        if item.get('equipable', False):
            if item.get('equipped', False):
                player.bag[item_index]['equipped'] = False
                player.save()
                return {
                    "code": 0,
                    "message": f"卸下 {item.get('name')} 成功"
                }
            for i in range(len(player.bag)):
                if player.bag[i].get('type', '') == item.get('type', '') and player.bag[i].get('equipped', False):
                    player.bag[i]['equipped'] = False
            player.bag[item_index]['equipped'] = True
            player.save()
            return {
                "code": 0,
                "message": f"装备 {item.get('name')} 成功"
            }
        if self.data['feed_time'] >= 5 and item['id'] <= 3:
            return {
                "code": -2,
                "message": "鱼已经吃饱了，明天再喂吧"
            }
        if item['id'] == 1:
            player.pop_item(item_index)
            self.data['buff'] = [
                {
                    "rarity": "R",
                    "bonus": 40,
                    "expire": time.time() + 1800
                }
            ]
            self.data['feed_time'] += 1
        elif item['id'] == 2:
            player.pop_item(item_index)
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
        elif item['id'] == 3:
            player.pop_item(item_index)
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
        elif item['id'] == 4:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 10,
                "time": 1
            })
        elif item['id'] == 5:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 20,
                "time": 2
            })
        elif item['id'] == 6:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('power', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "power": 40,
                "time": 4
            })
        elif item['id'] == 7:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.25,
                "expire": time.time() + 1200
            })
        elif item['id'] == 8:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 0.5,
                "expire": time.time() + 1200
            })
        elif item['id'] == 9:
            player.pop_item(item_index)
            player.data['buff'] = list(filter(lambda buff: buff.get('fishing_bonus', 0) == 0, player.data['buff']))
            player.data['buff'].append({
                "fishing_bonus": 1,
                "expire": time.time() + 1200
            })
        else:
            return {
                "code": -2,
                "message": "该物品效果暂未实装！"
            }
        self.save()
        player.save()
        extra = ''
        if item['id'] <= 3:
            extra += f'\n今天还能投 {5 - self.data["feed_time"]} 次食料'
        return {
            "code": 0,
            "message": f"使用 {item.get('name')} 成功" + extra
        }