from collections import defaultdict
from typing import Optional
from src.data_access.redis import DictRedisData, redis_global
from src.libraries.fishgame.data import *
from src.libraries.fishgame.buildings import *
from src.libraries.fishgame.player import FishPlayer
import random
import time


class FishGame(DictRedisData):
    def __init__(self, group_id=0):
        self.group_id = group_id
        token = f'fishgame_group_data_{group_id}'
        super().__init__(token, default=FishGame.default_group_data())
        self.fish_log = FishLog(self.data["fish_log"])
        self.__average_power = 0
        self.current_fish: Fish = None
        self.current_fish_is_shiny: bool = False  # 当前鱼是否为异色
        self.try_list = []
        self.leave_time = 0
        self.init_buildings()
        
        # Load Oversea Battle if exists
        if 'current_oversea_id' in self.data:
            from src.libraries.fishgame.oversea import OverseaBattle
            self.oversea_battle = OverseaBattle(self.group_id, self.data['current_oversea_id'])
        else:
            self.oversea_battle = None

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

        if 'port' not in self.data:
            self.data['port'] = {}
        self.port = Port(self.data['port'])

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
            ret = []
            for i in range(1, len(fish_data_poke_ver) + 1):
                fish = Fish.get(i)
                if fish is not None and fish.base_probability > 0:
                    ret.append(fish)
            return ret

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
            if player is None or time.time() - player.updated_at > 86400:
                continue
            # fever期间使用fever_power，否则使用普通power
            if self.is_fever:
                p += player.fever_power
            else:
                p += player.power
            count += 1
        if count == 0:
            self.__average_power = self.big_pot.power_boost
        else:
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
            self.current_fish_is_shiny = False
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
                # 异色判定：根据七天神像等级
                shiny_rate = self.seven_statue.shiny_rate
                self.current_fish_is_shiny = random.random() < shiny_rate
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
        self.current_fish_is_shiny = False  # 强制刷鱼默认非异色
        self.try_list = []
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
            if self.current_fish.rarity == 'UR':
                return {
                    "code": -4,
                    "message": "大师球被弹开了！！"
                }
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
        player_power += player.get_skill29_power_bonus()
        player_power += self.big_pot.power_boost + topic_power_bonus
        diff = player_power - fish.std_power

        if master_ball:
            success_rate = 100
        else:
            if diff > 0:
                success_rate += (40 - 40 * 0.9 ** (diff / 5))
            else:
                success_rate *= 0.9 ** (-diff / 5)
            
            # 技能17: 强行 (增加成功率)
            success_rate_bonus = skill_ctx.get('success_rate', 0)
            if success_rate_bonus > 0:
                success_rate = min(100, success_rate * (1 + success_rate_bonus / 100))

        fail_prob = max(0.0, 1 - min(success_rate, 100) / 100.0)

        for i, buff in enumerate(player.data['buff']):
            if buff.get('time', 0) > 0:
                player.data['buff'][i]['time'] -= 1

        if random.random() < success_rate / 100:
            # 异色判定：如果刷出来就是异色，直接使用；否则再次判定
            if self.current_fish_is_shiny:
                is_shiny = True
            else:
                shiny_rate = self.seven_statue.shiny_rate
                is_shiny = random.random() < shiny_rate
            
            player.fish_log.add_log(fish.id, is_shiny=is_shiny)
            fishing_bonus = 1
            for buff in player.buff:
                fishing_bonus += buff.get('fishing_bonus', 0)
            fishing_bonus *= 1 + self.fish_factory.fishing_bonus
            if self.is_fever:
                fishing_bonus *= 1 + self.ice_hole.fever_fishing_bonus
            value = int(fish.exp * fishing_bonus)
            add_line = ''
            if skill_ctx.get('fail_rate_reward_bonus'):
                extra_value = int(value * fail_prob)
                if extra_value > 0:
                    value += extra_value
                    add_line += f"\n【绝处逢生】发动，额外提升 {fail_prob * 100:.2f}% 渔获"
            crit_percent = player.get_crit_percent(fish, diff)
            convert_ratio = skill_ctx.get('over_100_crit_to_reward', 0)
            if convert_ratio > 0 and crit_percent > 100:
                extra_reward_percent = (crit_percent - 100) * convert_ratio / 100.0
                if extra_reward_percent > 0:
                    value = int(value * (1 + extra_reward_percent / 100.0))
                    add_line += f"\n【雀跃之舞】发动，额外获得 {extra_reward_percent:.2f}% 渔获"

            # 经验/金币技能加成
            exp_multiplier = 1 + player.equipment.exp_bonus + skill_ctx.get('exp_rate', 0)/100
            gold_multiplier = 1 + player.equipment.gold_bonus + skill_ctx.get('gold_rate', 0)/100
            exp = int(value * exp_multiplier)
            gold = int(value * gold_multiplier)

            # 看破（额外渔获）与超幸运倍率

            effective_crit_percent = max(0.0, min(crit_percent, 100))
            is_crit = random.random() < effective_crit_percent / 100
            if is_crit:
                crit_rate = max(skill_ctx.get('crit_rate', 0), 150)  # 默认 150%
                extra = int(value * (crit_rate/100 - 1))
                exp += int(extra * exp_multiplier)
                gold += int(extra * gold_multiplier)
                add_line += f"\n会心触发（概率{crit_percent:.2f}%）！额外获得渔获倍率 {crit_rate}%"

            # 异色宝可梦：经验和金币翻4倍
            if is_shiny:
                exp *= 4
                gold *= 4

            player.data['exp'] += exp
            player.data['gold'] += gold
            
            # 构建捕获消息
            shiny_mark = "✨异色✨" if is_shiny else ""
            if exp == gold:
                msg = f"捕获 {shiny_mark}{fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和金币"
            else:
                msg = f"捕获 {shiny_mark}{fish.name}【{fish.rarity}】 成功（成功率{success_rate:.2f}%），获得了 {exp} 经验和 {gold} 金币"
            if is_shiny:
                msg += "\n🎉恭喜！你捕获了异色宝可梦！经验和金币翻4倍！"
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
            if skill_ctx.get('power_on_success_gain', 0) > 0 and skill_ctx.get('max_power_on_success', 0) > 0:
                new_stack = player.add_skill29_power_bonus(skill_ctx['power_on_success_gain'], skill_ctx['max_power_on_success'])
                if new_stack > 0:
                    msg += f"\n【力量吸收】蓄能提升至 +{new_stack} 渔力（30 分钟）"
            msg += player.handle_level_up()
            player.save()
            
            # fever期间鱼不会被清除，非fever期间捕获成功后清除
            if not self.is_fever:
                regenerate_percent = skill_ctx.get('regenerate_percent', 0)
                keep_current_fish = False
                if is_crit and skill_ctx.get('keep_fish_on_non_fever_crit'):
                    keep_current_fish = True
                    msg += f"\n由于【精准手术】的效果，{fish.name} 留了下来！"
                elif random.random() < regenerate_percent / 100:
                    keep_current_fish = True
                    msg += f"\n由于【再生力】的效果，{fish.name} 留了下来！"
                if not keep_current_fish:
                    self.current_fish = None
                    self.current_fish_is_shiny = False
                    self.try_list = []
            
            return {
                "code": 0,
                "message": msg,
                "is_shiny": is_shiny
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
            
            # 技能12: 不屈 (失败后可再次尝试)
            # 冷却时间逻辑暂未实现，这里简化为本次不计入尝试列表
            cool_down = skill_ctx.get('cool_down', 0)
            # 检查冷却时间 (使用 player.data['last_unyielding_time'])
            can_retry = False
            if cool_down > 0:
                last_time = player.data.get('last_unyielding_time', 0)
                if time.time() - last_time > cool_down * 60:
                    can_retry = True
                    player.data['last_unyielding_time'] = time.time()
                    player.save()
            
            if can_retry:
                self.try_list.remove(player.qq)
                msg += f"\n由于【不屈】的效果，你可以再次尝试捕获！"

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
                    self.current_fish_is_shiny = False
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
    
    def check_requirements(self, item: FishItem):
        for building_name in item.require:
            building: BuildingBase = getattr(self, building_name, None)
            if building is None or not isinstance(building, BuildingBase):
                continue
            if building.level < item.require[building_name]:
                return False, f"{building.name} 等级不足，无法购买或合成该物品（需要 {building.name} {item.require[building_name]} 级）"
        return True, ""

    def can_buy(self, id):
        good: FishItem = FishItem.get(id)
        ret, msg = self.check_requirements(good)
        if ret is False:
            return {
                "code": -3,
                "message": msg
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
        if good.id == 209 and len(player.fish_log.caught_set) < 100:
            return {
                "code": -4,
                "message": "购买此道具需要至少捕获100种不同的鱼"
            }
        if good.id == 210 and len(player.fish_log.caught_set) < 32 + 84:
            return {
                "code": -4,
                "message": "购买此道具需要解锁所有图鉴"
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
            shiny_mark = "✨异色✨" if self.current_fish_is_shiny else ""
            s += f'\n当前池子中有{'一群' if self.is_fever else '一条'} {shiny_mark}{self.current_fish.name}【{self.current_fish.rarity}】！'
        
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
        
        elif item.id in (31, 32):
            player.bag.pop_item(item.id)
            player.bag.add_item(item.id - 1, 2)
            player.save()
            return {
                "code": 0,
                "message": f"成功将 {item.name} 分解为 2 个 {FishItem.get(str(item.id - 1)).name}！"
            }

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
        elif self.forge_shop.level >= 1:
            if item.id in (301, 303, 305, 307, 309, 311):
                player.bag.pop_item(item.id)
                player.bag.add_item(33)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 精良鱼叉！"
                }
            elif 315 <= item.id <= 318:
                player.bag.pop_item(item.id)
                player.bag.add_item(34)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 沙漠鱼叉！"
                }
            elif 320 <= item.id <= 323:
                player.bag.pop_item(item.id)
                player.bag.add_item(35)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 森林鱼叉！"
                }
            elif 325 <= item.id <= 328:
                player.bag.pop_item(item.id)
                player.bag.add_item(36)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 火山鱼叉！"
                }
            elif 330 <= item.id <= 333:
                player.bag.pop_item(item.id)
                player.bag.add_item(37)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 天空鱼叉！"
                }
            elif 335 <= item.id <= 338:
                player.bag.pop_item(item.id)
                player.bag.add_item(38)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 雪山鱼叉！"
                }
            elif 340 <= item.id <= 343:
                player.bag.pop_item(item.id)
                player.bag.add_item(39)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 金属鱼叉！"
                }
            elif 345 <= item.id <= 348:
                player.bag.pop_item(item.id)
                player.bag.add_item(40)
                player.save()
                return {
                    "code": 0,
                    "message": f"成功将 {item.name} 制作为 神秘鱼叉！"
                }
            elif item.id == 310 or (33 <= item.id <= 40):
                return {
                    "code": -2,
                    "message": f"请使用【港口 物品 {item.id}】指令来携带该物品参加港口战斗"
                }
            else:
                return {
                    "code": -2,
                    "message": "该物品无法使用，或效果暂未实装！"
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
        return [item for item in fish_item.values() if item.craftable and self.check_requirements(item)[0]]
    
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

        # 检查条件
        can_craft, msg = self.check_requirements(item)
        if not can_craft:
            return {
                "code": -2,
                "message": msg
            }

        prerequisite_id = getattr(item, 'prerequisite_item', 0)
        if prerequisite_id:
            owned_count = player.bag.get_item_count(prerequisite_id)
            equipped_count = player.equipment.ids.count(prerequisite_id)
            if max(owned_count, equipped_count) <= 0:
                prereq_item = FishItem.get(str(prerequisite_id))
                prereq_name = prereq_item.name if prereq_item else f"物品{prerequisite_id}"
                return {
                    "code": -7,
                    "message": f"缺少前置装备：需要先获得 {prereq_name}"
                }
        
        # 统计需要的材料
        material_requirements = {}
        for material_id in item.craftby:
            material_requirements[material_id] = material_requirements.get(material_id, 0) + 1
        
        # 检查材料是否充足
        for material_id, required_count in material_requirements.items():
            current_count = player.bag.get_item_count(material_id)
            # 扣除已装备的物品
            equipped_count = player.equipment.ids.count(material_id)
            current_count -= equipped_count
            
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
        if count <= 0:
            return {
                "code": "-1",
                "message": "添加数量必须大于0"
            }

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

    def sign_in(self, player: FishPlayer):
        # 检查建筑
        if self.seven_statue.level < 1:
            return {
                "code": "-1",
                "message": "你没有【七天神像】，无法签到"
            }
        
        # 检查是否已签到
        today = time.strftime("%Y-%m-%d", time.localtime())
        if 'sign_in_record' not in self.data:
            self.data['sign_in_record'] = {}
        
        record = self.data['sign_in_record']
        if record.get('date') != today:
            record['date'] = today
            record['players'] = []
        
        if player.qq in record['players']:
            return {
                "code": "-1",
                "message": "你今天已经签到过了"
            }
        
        # 签到逻辑
        record['players'].append(player.qq)
        self.save()
        
        # 奖励逻辑
        rewards = []
        msg = "签到成功！获得奖励：\n"
        
        # 1. 第一个签到的人
        if len(record['players']) == 1:
            player.bag.add_item(408, 1)
            rewards.append("神秘之涎 x1")
        
        # 获取今日主题
        current_topic = weekday_topic[time.localtime().tm_wday]
        
        topic_item_map = {
            "沙漠": (315, 319),
            "森林": (320, 324),
            "洞穴": (325, 329),
            "海洋": (330, 334),
            "雪山": (335, 339),
            "火山": (340, 344),
            "遗迹": (345, 349)
        }
        
        topic_range = topic_item_map.get(current_topic)
        
        pool = []
        
        if topic_range:
            theme_r3 = list(range(topic_range[0], topic_range[0] + 3))
            theme_r4 = list(range(topic_range[0] + 3, topic_range[1] + 1))
        else:
            theme_r3 = []
            theme_r4 = []
            
        if self.seven_statue.level == 1:
            # 301-313 + Theme R3
            pool = list(range(301, 314)) + theme_r3
        elif self.seven_statue.level == 2:
            # 301-314 + Theme R3
            pool = list(range(301, 315)) + theme_r3
        elif self.seven_statue.level >= 3:
            # 301-314 + Theme R3 + Theme R4
            pool = list(range(301, 315)) + theme_r3 + theme_r4
            
        # Randomly pick one
        if pool:
            reward_id = random.choice(pool)
            player.bag.add_item(reward_id, 1)
            item_name = fish_item[reward_id].name if reward_id in fish_item else f"Item {reward_id}"
            rewards.append(f"{item_name} x1")

        if self.port.level >= 1:
            if player.bag.get_item_count(49) < 1:
                player.bag.add_item(49, 1)
                rewards.append("港口通行证 x1")
            
        player.save()
        
        return {
            "code": 0,
            "message": msg + "\n".join(rewards)
        }

    # ---------------- Oversea Battle ----------------
    def check_oversea_spawn(self):
        """检查是否生成港口怪物"""
        if self.port.level < 1:
            return False
        
        # 检查时间 8:00 - 24:00
        hour = time.localtime().tm_hour
        if hour < 8:
            return False
        
        # 检查是否已有战斗
        if self.oversea_battle and self.oversea_battle.data['status'] in ['fighting']:
            return False
        
        # 检查本小时是否已经生成过
        current_hour_str = time.strftime("%Y-%m-%d-%H")
        if self.data.get('last_oversea_hour') == current_hour_str:
            return False
            
        self.spawn_oversea_monster()
        return True

    def spawn_oversea_monster(self):
        from src.libraries.fishgame.oversea import OverseaBattle
        
        # 增加计数
        self.data['oversea_count'] = self.data.get('oversea_count', 0) + 1
        battle_id = self.data['oversea_count']
        self.data['current_oversea_id'] = battle_id
        self.data['last_oversea_hour'] = time.strftime("%Y-%m-%d-%H")
        # 难度 = 1 ~ 港口等级
        difficulty = random.randint(1, self.port.level)
        
        self.oversea_battle = OverseaBattle(self.group_id, battle_id, difficulty, self.port.level)
        self.save()
        return self.oversea_battle

    def _settle_oversea_rewards(self, success: bool):
        battle = self.oversea_battle
        diff = battle.data['difficulty']
        
        # Base rewards
        base_exp = [20000, 40000, 60000][diff - 1]
        base_gold = [20000, 40000, 60000][diff - 1]
        base_drop_count = [6, 12, 20][diff - 1]
        
        # Bonus Buffs
        bonus_gold_pct = 0.0
        bonus_exp_pct = 0.0
        bonus_drop_pct = 0.0
        bonus_token = 0
        
        for buff_id in battle.data.get('bonus_buffs', []):
            if buff_id == 201: # 稀有: +20% Gold
                bonus_gold_pct += 0.2
            elif buff_id == 202: # 超级稀有: +50% Gold
                bonus_gold_pct += 0.5
            elif buff_id == 203: # 强者: +1 Token
                bonus_token += 1
            elif buff_id == 204: # 大体型: +50% Drop
                bonus_drop_pct += 0.5
            elif buff_id == 205:
                bonus_exp_pct += 0.2
                
        logs = []
        
        monster_id = battle.data['monster_id']
        monster_drops = []
        if monster_id in fish_data:
            monster_drops = fish_data[monster_id].drops
        player_damage_map = battle.data.get('player_damage', {})
        
        for qq in battle.data['players']:
            player = FishPlayer(qq)
            player_name = battle.data.get('player_names', {}).get(str(qq), player.name)
            player_skill_ctx = player.get_skill_context()
            
            # Variance 0.9 - 1.1
            variance = random.uniform(0.9, 1.1)
            
            if success:
                player_bonus_drop_pct = 0
                player_bonus_exp_pct = 0
                player_bonus_gold_pct = 0
                if battle.data.get('loadouts', {}).get(str(qq)) == 49:
                    player_bonus_drop_pct = 1
                    player_bonus_exp_pct = 1
                    player_bonus_gold_pct = 1

                exp = int(base_exp * (1 + bonus_exp_pct + player_bonus_exp_pct) * variance)
                gold = int(base_gold * (1 + bonus_gold_pct + player_bonus_gold_pct) * variance)
                extra_gold = 0
                dmg_rate = player_skill_ctx.get('oversea_dmg_gold_rate', 0)
                if dmg_rate > 0:
                    player_total_damage = player_damage_map.get(str(qq), 0)
                    extra_gold = int(player_total_damage * dmg_rate / 100)
                total_gold = gold + extra_gold
                drop_count = round(base_drop_count * (1 + bonus_drop_pct + player_bonus_drop_pct) * variance)
                
                player.data['exp'] += exp
                player.data['gold'] += total_gold
                
                # Drops
                got_drops = {}
                if monster_drops:
                    items = [d['item_id'] for d in monster_drops]
                    weights = [d['probability'] for d in monster_drops]
                    
                    for _ in range(drop_count):
                        item_id = random.choices(items, weights=weights, k=1)[0]
                        player.bag.add_item(item_id, 1)
                        got_drops[item_id] = got_drops.get(item_id, 0) + 1

                if 206 in battle.data.get('bonus_buffs', []):
                    gems = []
                    for gem in [314, 319, 324, 329, 334, 339, 344, 349]:
                        if gem != monster_drops[-1].get('item_id', 0):
                            gems.append(gem)
                    jewel_id = random.choice(gems)
                    player.bag.add_item(jewel_id, diff)
                    got_drops[jewel_id] = got_drops.get(jewel_id, 0) + diff
                
                msg = f"获得 {exp} 经验, {total_gold} 金币"
                if extra_gold > 0:
                    msg += f"（点石成金额外 +{extra_gold}）"
                for i in range(diff):
                    # Tokens
                    # 30: 海洋之证, 31: 风暴之证, 32: 最强之证
                    token_name = FishItem.get(30 + i).name
                    if i == diff - 1 and bonus_token > 0:
                        token_count = 2
                    else:
                        token_count = 1
                    msg += f", {token_name} x{token_count}"
                    player.bag.add_item(30 + i, token_count)
                if got_drops:
                    drop_msg = []
                    for iid, count in got_drops.items():
                        item = FishItem.get(iid)
                        drop_msg.append(f"{item.name} x{count}")
                    msg += ", " + ", ".join(drop_msg)
                msg += player.handle_level_up()
                logs.append(f"{player_name} {msg}")
                
            else:
                # Fail
                # Exp = Base * (Max - Current) / Max
                progress = (battle.data['monster_max_hp'] - battle.data['monster_hp']) / battle.data['monster_max_hp']
                exp = int(base_exp * progress * variance)
                player.data['exp'] += exp
                logs.append(f"{player_name} 获得 {exp} 经验 (进度 {progress*100:.1f}%){player.handle_level_up()}")
            
            # 扣除道具
            is_deduct = 205 not in battle.data.get('bonus_buffs', [])
            item_id = battle.data['loadouts'].get(str(qq)) or battle.data['loadouts'].get(int(qq))
            if item_id:
                item_id = int(item_id)
                deduct_count = 0
                if item_id == 310:
                    deduct_count = 1 if is_deduct else 0
                elif 33 <= item_id <= 40:
                    deduct_count = 10 if is_deduct else 0
                elif item_id == 49:
                    deduct_count = 1
                
                if deduct_count > 0:
                    player.bag.pop_item(item_id, deduct_count)

            player.save()
            
        battle.data['logs'].extend(logs)
        battle.save()
        return logs

    def process_oversea_turn(self):
        """推进战斗回合"""
        if not self.oversea_battle:
            return None
        
        if self.oversea_battle.data['status'] != 'fighting':
            return None
            
        # 检查是否有人参战
        if not self.oversea_battle.data['players']:
            # 无人参战，不推进回合，或者自动失败？
            # 需求：每3分钟会前进一轮
            pass
            
        res = self.oversea_battle.process_round()
        
        if res['status'] == 'success':
            res['logs'].extend(self._settle_oversea_rewards(True))
        elif res['status'] == 'fail':
            res['logs'].extend(self._settle_oversea_rewards(False))
            
        return res

    def join_oversea(self, player: FishPlayer, nickname: str = None):
        if not self.oversea_battle:
            return {"code": -1, "message": "当前没有海怪袭击"}
        
        if self.oversea_battle.data['status'] != 'idle':
            return {"code": -2, "message": "战斗已经开始或已结束，无法加入"}
            
        # 检查每日次数
        # 每日次数限制 = 港口等级
        today = time.strftime("%Y-%m-%d")
        if player.data.get('last_raid_date') != today:
            player.data['last_raid_date'] = today
            player.data['raid_count'] = 0
            player.save()
            
        max_count = self.port.level
        # if self.group_id in (663516277,):
        #     max_count += 1

        if player.data.get('raid_count', 0) >= max_count:
            return {"code": -3, "message": f"今日讨伐次数已耗尽（上限 {max_count} 次）"}
            
        if player.qq in self.oversea_battle.data['players']:
            return {"code": -4, "message": "你已经加入了讨伐队伍"}
            
        if len(self.oversea_battle.data['players']) >= self.port.level + 1:
            return {"code": -5, "message": "讨伐队伍人数已达上限"}
        
        self.oversea_battle.data['players'].append(player.qq)
        if nickname:
            self.oversea_battle.data['player_names'][str(player.qq)] = nickname
        self.oversea_battle.save()
        return {"code": 0, "message": "成功加入讨伐队伍"}

    def leave_oversea(self, player: FishPlayer):
        if not self.oversea_battle:
            return {"code": -1, "message": "当前没有海怪袭击"}
            
        if self.oversea_battle.data['status'] != 'idle':
            return {"code": -2, "message": "战斗已经开始，无法退出"}
            
        if player.qq not in self.oversea_battle.data['players']:
            return {"code": -3, "message": "你不在讨伐队伍中"}
            
        self.oversea_battle.data['players'].remove(player.qq)
        # 移除装备配置
        if player.qq in self.oversea_battle.data['loadouts']:
            del self.oversea_battle.data['loadouts'][player.qq]
            
        self.oversea_battle.save()
        return {"code": 0, "message": "已退出讨伐队伍"}

    def equip_oversea_item(self, player: FishPlayer, item_id: str):
        if not self.oversea_battle:
            return {"code": -1, "message": "当前没有海怪袭击"}
            
        if self.oversea_battle.data['status'] != 'idle':
            return {"code": -6, "message": "战斗已经开始，无法更换装备"}

        if player.qq not in self.oversea_battle.data['players']:
            return {"code": -2, "message": "请先加入讨伐队伍"}
            
        # 检查物品
        item = FishItem.get(item_id)
        if not item:
            return {"code": -3, "message": "物品不存在"}
            
        # 检查类型 (鱼叉 33-40, 尾鳍 310)
        valid_ids = [33, 34, 35, 36, 37, 38, 39, 40, 310, 49]
        if item.id not in valid_ids:
            return {"code": -5, "message": "该物品无法在讨伐中使用"}
            
        # 检查是否拥有
        required_count = 1
        if item.id in [33, 34, 35, 36, 37, 38, 39, 40]: # Harpoons
            required_count = 10
        
        if player.bag.get_item_count(item.id) < required_count:
            return {"code": -4, "message": f"你没有足够的该物品（需要 {required_count} 个）"}
            
        self.oversea_battle.data['loadouts'][player.qq] = item.id
        self.oversea_battle.save()
        return {"code": 0, "message": f"已装备 {item.name}"}

    def start_oversea_battle(self):
        if not self.oversea_battle:
            return {"code": -1, "message": "当前没有海怪袭击"}
            
        if self.oversea_battle.data['status'] != 'idle':
            return {"code": -2, "message": "战斗状态不正确"}
            
        if not self.oversea_battle.data['players']:
            return {"code": -3, "message": "队伍中没有玩家"}
            
        # 扣除次数
        players_obj = []
        for qq in self.oversea_battle.data['players']:
            p = FishPlayer(qq)
            p.data['raid_count'] = p.data.get('raid_count', 0) + 1
            p.save()
            players_obj.append(p)
            
        self.oversea_battle.start_battle(players_obj, self.oversea_battle.data['loadouts'])
        return {"code": 0, "message": "战斗开始！"}