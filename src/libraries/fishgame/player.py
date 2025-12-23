from collections import defaultdict
from typing import Optional
from src.data_access.redis import DictRedisData, redis_global
from src.libraries.fishgame.data import *
from src.libraries.fishgame.buildings import *

class FishPlayer(DictRedisData):
    def __init__(self, qq, hash=''):
        self.qq = qq
        token = f'fishgame_user_data_{md5(str(qq)) if hash == "" else hash}'
        super().__init__(token, default=FishPlayer.default_user_data())
        self.bag = Backpack(self.data['bag'], self)
        self.fish_log = FishLog(self.data['fish_log'])
        self.equipment = Equipment(self.data['equipment'], self)
        # 配件实例数据： { item_id(str): {"skills": [{id, level}, ...], "base_id": int} }
        if 'accessory_meta' not in self.data:
            self.data['accessory_meta'] = {}

    @staticmethod
    def all_players():
        data = []
        for player in redis_global.scan_iter(f'fishgame_user_data_*'):
            hash = player.split('_')[-1]
            data.append(FishPlayer(-1, hash))
        return data

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
                if item.type == 'rod' and not item.ignore_fever:
                    base += item.power // 2
                elif item.id == 406:
                    base += item.power + 25
                else:
                    base += item.power
        for buff in self.buff:
            base += buff.get('power', 0)
        
        # 技能附加
        ctx = self.get_skill_context()
        base += ctx.get('flat_power', 0) + ctx.get('fever_power', 0)
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
    def get_equipped_skill_dict(self) -> dict[int, int]:
        skills = defaultdict(int)
        meta = self.data.get('accessory_meta', {})
        acc = self.equipment.accessory
        if acc and str(acc.id) in meta:
            for sk in meta[str(acc.id)].get('skills', []):
                skills[sk['id']] += sk.get('level', 1)
        for it in [self.equipment.rod, self.equipment.tool]:
            if it and getattr(it, 'skills', []):
                for sk in it.skills:
                    skills[sk['id']] += sk.get('level', 1)
        return skills

    def get_equipped_skills(self) -> list[dict]:
        from src.libraries.fishgame.data import fish_skills
        skills = self.get_equipped_skill_dict()
        return [{'id': k, 'level': min(v, fish_skills[k].max_level)} for k, v in skills.items()]

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
            'old_fish_crit': 0,
            'success_rate': 0,
            'regenerate_percent': 0,
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
                elif key.startswith('oversea_') and isinstance(val, list):
                    v = val[lv-1]
                    if key in ['oversea_damage_reduce', 'oversea_revive_percent', 'oversea_heal_percent', 'oversea_heal_reduce']:
                        ctx[key] = max(ctx.get(key, 0), v)
                    else:
                        ctx[key] = ctx.get(key, 0) + v

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
            if 'success_rate' in eff:
                ctx['success_rate'] += eff['success_rate'][lv-1]
            if 'regenerate_percent' in eff:
                ctx['regenerate_percent'] += eff['regenerate_percent'][lv-1]
            if 'fever_power' in eff:
                ctx['fever_power'] = ctx.get('fever_power', 0) + eff['fever_power'][lv-1]
            if 'cool_down' in eff:
                cd = eff['cool_down'][lv-1]
                if 'cool_down' not in ctx:
                    ctx['cool_down'] = cd
                else:
                    ctx['cool_down'] = min(ctx['cool_down'], cd)
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
    
    def get_crit_percent(self, fish: Fish, diff):
        skill_ctx = self.get_skill_context()
        crit_percent = skill_ctx.get('crit_percent', 0)
        if self.fish_log.caught(fish.id):
            crit_percent += skill_ctx.get('old_fish_crit', 0)
        talent_types = ['fire', 'water', 'grass', 'ice', 'electric', 'ghost', 'ground']
        for weak in fish.weakness:
            if weak == 'ice':
                continue
            if weak in talent_types:
                talent_id = talent_types.index(weak) + 1
                talent_level = self.get_talent_level(talent_id)
                if talent_level > 0:
                    crit_percent += 5 * talent_level  # 每级增加 5% 几率
        # 冰干单独判定
        talent_4_level = 0
        if 'freezedry' in fish.weakness and self.get_equipped_skill_dict().get(21, 0) > 0:
            talent_4_level = self.get_talent_level(4)
        elif 'ice' in fish.weakness:
            talent_4_level = self.get_talent_level(4)
        if talent_4_level > 0:
            crit_percent += 5 * talent_4_level
        
        talent_8_level = self.get_talent_level(8)
        if talent_8_level > 0:
            crit_percent += 0.01 * talent_8_level * max(0, diff)

        return crit_percent


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
