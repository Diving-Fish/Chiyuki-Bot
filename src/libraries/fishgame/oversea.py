# 战斗 Buff 共分为三类
# 1. 环境 Buff，影响子弹的威力
# 2. 怪物 Buff，纯负面 Buff，怪物从 1 - 3 级分别拥有 1 - 3 个 Buff，Buff 共分为 3 级：
# 2 级怪物 70% 概率拥有 1 级 Buff，30% 概率拥有 2 级 Buff
# 3 级怪物 50% 概率拥有 1 级 Buff，30% 概率拥有 2 级 Buff，20% 概率拥有 3 级 Buff
# 3. 奖励 Buff，纯正面 Buff：
# 1 级怪物 50% 概率有 1 个 Buff
# 2 级怪物 50% 概率只有 1 个 Buff，20% 概率有两个 Buff
# 3 级怪物 50% 概率只有 1 个 Buff，20% 概率有 2 个 Buff，10% 概率有 3 个 Buff

from typing import List, Dict, TYPE_CHECKING, Optional
from src.data_access.redis import DictRedisData
import random
from src.libraries.fishgame.data import Fish, fish_data, FishItem

if TYPE_CHECKING:
    from src.libraries.fishgame.fishgame import FishPlayer

class OverseaBattle(DictRedisData):
    def __init__(self, group_id: int, battle_id: int, difficulty: int = 1, port_level: int = 1):
        self.group_id = group_id
        self.battle_id = battle_id
        token = f'fishgame_oversea_battle_{group_id}_{battle_id}'
        default = {
            "status": "idle",  # idle, fighting, success, fail
            "players": [],     # List[str] (qq)
            "player_names": {}, # Dict[str, str] (qq -> name)
            "loadouts": {},    # Dict[str, int] (qq -> item_id)
            "monster_name": "",
            "monster_id": 0,
            "monster_weakness": [],
            "monster_hp": 0,
            "monster_max_hp": 0,
            "base_monster_hp": 0, # 基础血量 (单人, 含Buff)
            "monster_atk": 0,
            "port_level": port_level,
            "difficulty": difficulty,
            "environment_buff": 0,
            "monster_buffs": [], # List[Dict] {'id': int, 'level': int}
            "bonus_buffs": [],   # List[int]
            "ship_hp": 0,
            "ship_max_hp": 0,
            "current_round": 0,
            "max_rounds": 10,
            "logs": []
        }
        super().__init__(token, default=default)
        
        if self.data['monster_id'] == 0:
            self._init_monster()

    def _init_monster(self):
        # 随机选择怪物
        boss_candidates = []
        for id, fish in fish_data.items():
            if fish.std_power == 333:
                boss_candidates.append(fish)
        
        if not boss_candidates:
            return
            
        selected_fish = random.choice(boss_candidates)
        self.data['monster_name'] = selected_fish.name
        self.data['monster_id'] = selected_fish.id
        self.data['monster_weakness'] = selected_fish.weakness
        
        # 生成 Buff
        # 1. 环境 Buff
        self.data['environment_buff'] = random.randint(1, 7)
        
        # 2. 怪物 Buff
        diff = self.data['difficulty']
        monster_buff_pool = [101, 102, 103, 104, 105, 106, 107]
        selected_monster_buffs = random.sample(monster_buff_pool, diff)
        self.data['monster_buffs'] = []
        
        for bid in selected_monster_buffs:
            level = 1
            r = random.random()
            if diff == 2:
                if r >= 0.7: level = 2
            elif diff == 3:
                if r < 0.5: level = 1
                elif r < 0.8: level = 2
                else: level = 3
            
            self.data['monster_buffs'].append({'id': bid, 'level': level})
            
        # 3. 奖励 Buff
        bonus_buff_pool = [201, 202, 203, 204]
        bonus_count = 0
        r = random.random()
        if diff == 1:
            if r < 0.5: bonus_count = 1
        elif diff == 2:
            if r < 0.5: bonus_count = 1
            elif r < 0.7: bonus_count = 2
        elif diff == 3:
            if r < 0.5: bonus_count = 1
            elif r < 0.7: bonus_count = 2
            elif r < 0.8: bonus_count = 3
            
        self.data['bonus_buffs'] = random.sample(bonus_buff_pool, bonus_count)
        
        # 应用静态 Buff 效果
        hp_bonus_pct = 0.0
        atk_bonus_pct = 0.0
        max_rounds = 10
        
        for buff in self.data['monster_buffs']:
            if buff['id'] == 101:
                max_rounds -= buff['level']
            elif buff['id'] == 105:
                hp_bonus_pct += buff['level'] * 0.05
                atk_bonus_pct += buff['level'] * 0.05
        
        self.data['max_rounds'] = max(1, max_rounds)
        
        base_hp_raw = 10000 * [1, 1.5, 2][self.data['difficulty'] - 1] * random.uniform(0.85, 1.15)
        self.data['base_monster_hp'] = int(base_hp_raw * (1 + hp_bonus_pct))
        self.data['monster_atk'] = [333, 500, 666][self.data['difficulty'] - 1] * random.uniform(0.85, 1.15) * (1 + atk_bonus_pct)
        self.save()

    def start_battle(self, players: List['FishPlayer'], loadouts: Dict[str, int]):
        """
        初始化战斗
        players: 参与玩家列表
        loadouts: 玩家携带的道具ID (鱼叉 或 310洛奇亚尾鳍)
        """
        player_count = len(players)
        if player_count == 0:
            return False
            
        if self.data['monster_id'] == 0:
            return False

        # 验证玩家携带物品
        qq_to_player = {str(p.qq): p for p in players}
        validated_loadouts = {}
        
        for qq, item_id in loadouts.items():
            qq = str(qq)
            if qq not in qq_to_player:
                continue
            
            player = qq_to_player[qq]
            valid = True
            
            if str(item_id) == '310' or item_id == 310:
                if player.bag.get_item_count(310) < 1:
                    valid = False
            elif item_id:
                try:
                    iid = int(item_id)
                    # 鱼叉 ID 范围 33-40
                    if 33 <= iid <= 40:
                        if player.bag.get_item_count(iid) < 10:
                            valid = False
                except:
                    pass
            
            if valid:
                validated_loadouts[qq] = item_id
            else:
                validated_loadouts[qq] = 0 

        self.data['loadouts'] = validated_loadouts
        loadouts = validated_loadouts

        # 怪物血量倍率: 1人100%，2人170%，3人240%，4人300%
        hp_multipliers = {1: 1.0, 2: 1.7, 3: 2.4, 4: 3.0}
        multiplier = hp_multipliers.get(player_count, 3.0)
        
        self.data['monster_max_hp'] = int(self.data['base_monster_hp'] * multiplier)
        self.data['monster_hp'] = self.data['monster_max_hp']
        
        # 船体耐久
        base_ship_hp = 3000 * [1, 1.25, 1.5][self.data['port_level'] - 1]
        bonus_ship_hp_percent = 0.0
        
        self.data['players'] = [p.qq for p in players]
        self.data['loadouts'] = loadouts
        
        for qq, item_id in loadouts.items():
            if str(item_id) == '310' or item_id == 310: # 洛奇亚的尾鳍
                bonus_ship_hp_percent += 0.5
        
        self.data['ship_max_hp'] = int(base_ship_hp * (1 + bonus_ship_hp_percent))
        self.data['ship_hp'] = self.data['ship_max_hp']
        
        # 应用螺旋加速效果
        extra_rounds = 0
        for p in players:
            ctx = p.get_skill_context()
            extra_rounds += ctx.get('oversea_extra_round', 0)
        
        self.data['max_rounds'] += extra_rounds

        self.data['current_round'] = 0
        self.data['status'] = "fighting"
        self.data['logs'] = []
        self.save()
        return True

    def process_round(self) -> Dict:
        """
        结算一轮战斗
        """
        if self.data['status'] != "fighting":
            return {"code": -1, "message": "战斗未开始或已结束"}
        
        # 避免循环引用，在方法内部导入
        from src.libraries.fishgame.fishgame import FishPlayer
        
        self.data['current_round'] += 1
        round_num = self.data['current_round']
        round_log = []
        
        # 1. 玩家攻击
        total_damage = 0
        player_names = self.data.get('player_names', {})
        
        # 技能效果统计变量
        max_defeatist_reduce = 0
        total_member_reduce = 0
        max_regen_percent = 0
        max_revive_percent = 0
        max_heal_reduce = 0
        
        # 计算队长全队增伤 (Skill 15)
        team_damage_bonus = 0.0
        if self.data['players']:
            captain_qq = self.data['players'][0]
            captain = FishPlayer(captain_qq)
            captain_ctx = captain.get_skill_context()
            team_damage_bonus = captain_ctx.get('oversea_1st_damage_boost', 0) / 100.0

        for i, qq in enumerate(self.data['players']):
            player = FishPlayer(qq)
            player_name = player_names.get(str(qq), player.name)
            item_id = self.data['loadouts'].get(str(qq)) or self.data['loadouts'].get(int(qq))
            
            # 收集技能上下文
            skill_ctx = player.get_skill_context()
            
            # 统计防御和恢复类技能
            max_defeatist_reduce = max(max_defeatist_reduce, skill_ctx.get('oversea_damage_reduce', 0))
            max_regen_percent = max(max_regen_percent, skill_ctx.get('oversea_heal_percent', 0))
            max_revive_percent = max(max_revive_percent, skill_ctx.get('oversea_revive_percent', 0))
            heal_reduce = skill_ctx.get('oversea_heal_reduce', 0)
            if int(item_id) == 38: # 雪山鱼叉
                heal_reduce *= 2
            max_heal_reduce = max(max_heal_reduce, heal_reduce)
            
            if i != 0: # 非队长
                total_member_reduce += skill_ctx.get('oversea_member_damage_reduce', 0)

            # 基础攻击力计算 (需要斟酌)
            # 暂时使用 player.power 作为基础
            damage = player.power 
            
            # 鱼叉加成
            # 鱼叉 ID 范围 33-40 (根据 fish_item.json)
            # 33: 精良鱼叉 (+30%)
            # 34: 沙漠鱼叉 (+50%)
            # 35: 森林鱼叉 (+50%)
            # 36: 火山鱼叉 (+50%)
            # 37: 天空鱼叉 (+50%)
            # 38: 雪山鱼叉 (+50%)
            # 39: 金属鱼叉 (+70%)
            # 40: 神秘鱼叉 (+50%)
            
            bonus = 0.0
            if item_id:
                iid = int(item_id)
                if iid == 33: bonus = 0.3
                elif iid in [34, 35, 36, 37, 38, 40]: bonus = 0.5
                elif iid == 39: bonus = 0.7
                
                # 亲和力技能加成
                if iid == 34: bonus += skill_ctx.get('oversea_沙漠', 0) / 100.0
                elif iid == 35: bonus += skill_ctx.get('oversea_森林', 0) / 100.0
                elif iid == 36: bonus += skill_ctx.get('oversea_火山', 0) / 100.0
                elif iid == 37: bonus += skill_ctx.get('oversea_天空', 0) / 100.0
                elif iid == 38: bonus += skill_ctx.get('oversea_雪山', 0) / 100.0
                elif iid == 39: bonus += skill_ctx.get('oversea_金属', 0) / 100.0
                elif iid == 40: bonus += skill_ctx.get('oversea_神秘', 0) / 100.0
            
            # Skill 15: 队长全队增伤
            bonus += team_damage_bonus
            
            # 环境 Buff 加成
            env_buff = self.data.get('environment_buff', 0)
            env_bonus = 0.0
            if env_buff == 1: # 晴天
                env_bonus += 0.1
            elif env_buff == 7: # 大雾
                env_bonus -= 0.1
            
            if item_id:
                iid = int(item_id)
                if env_buff == 2 and iid == 34: env_bonus += 0.5
                elif env_buff == 3 and iid == 35: env_bonus += 0.5
                elif env_buff == 4 and iid == 36: env_bonus += 0.5
                elif env_buff == 5 and iid == 37: env_bonus += 0.5
                elif env_buff == 6 and iid == 38: env_bonus += 0.5
                elif env_buff == 7 and iid == 40: env_bonus += 1.0
            
            # 暴击逻辑
            skill_ctx = player.get_skill_context()
            crit_percent = player.get_crit_percent(Fish.get(self.data['monster_id']), diff=player.power - self.data['monster_atk'])

            # 怪物 Buff: 106 反会心
            for buff in self.data.get('monster_buffs', []):
                if buff['id'] == 106:
                    crit_percent -= buff['level'] * 20
            
            is_crit = False
            crit_dmg_multiplier = 1.0
            
            if random.random() < min(crit_percent, 100) / 100:
                is_crit = True
                crit_rate = max(skill_ctx.get('crit_rate', 0), 150)
                crit_dmg_multiplier = crit_rate / 100.0

            # 伤害浮动 0.9 - 1.1
            damage = int(damage * (1 + bonus + env_bonus) * random.uniform(0.9, 1.1))
            
            if is_crit:
                damage = int(damage * crit_dmg_multiplier)
            
            # Skill 17: 强行 (增伤)，乘算
            damage = int(damage * (1 + skill_ctx.get('oversea_damage_boost', 0) / 100.0))

            # 怪物 Buff: 102 坚韧 (减伤)
            damage_reduction_pct = 0.0
            for buff in self.data.get('monster_buffs', []):
                if buff['id'] == 102:
                    damage_reduction_pct += buff['level'] * 0.1
            
            damage = int(damage * (1 - damage_reduction_pct))
            damage = max(1, damage)
            
            total_damage += damage
            
            weapon_name = "【鱼叉】"
            if item_id:
                iid = int(item_id)
                if 33 <= iid <= 40:
                    item = FishItem.get(iid)
                    if item:
                        weapon_name = f"【{item.name}】"

            log_msg = f"{player_name} 使用 {weapon_name} "
            if is_crit:
                log_msg += f"触发会心一击（概率{crit_percent:.2f}%）！"
            log_msg += f"造成了 {damage} 点伤害"
            round_log.append(log_msg)
            
            # 怪物 Buff: 107 荆棘 (反伤)
            for buff in self.data.get('monster_buffs', []):
                if buff['id'] == 107:
                    thorns_dmg = int(damage * buff['level'] * 0.1)
                    if thorns_dmg > 0:
                        self.data['ship_hp'] -= thorns_dmg
                        round_log.append(f"受到荆棘反伤，船体扣除 {thorns_dmg} 点耐久")
            
        self.data['monster_hp'] -= total_damage
        round_log.append(f"本轮玩家共造成 {total_damage} 点伤害")

        # 检查怪物是否死亡
        if self.data['monster_hp'] <= 0:
            self.data['monster_hp'] = 0
            self.data['status'] = "success"        
            self.data['logs'] += round_log
            self.save()
            return {
                "code": 1, 
                "message": f"战斗胜利！{self.data['monster_name']}已被击败！", 
                "logs": round_log,
                "status": "success"
            }
            
        # 2. 怪物攻击
        # 怪物 Buff: 103 狂暴 (增伤)
        atk_bonus_pct = 0.0
        for buff in self.data.get('monster_buffs', []):
            if buff['id'] == 103:
                atk_bonus_pct += buff['level'] * 0.1
                
        monster_damage = int(self.data['monster_atk'] * (1 + atk_bonus_pct) * random.uniform(0.9, 1.1))
        
        # 玩家技能减伤 (Skill 9 & 15)
        total_reduce_pct = min(100, max_defeatist_reduce + total_member_reduce) / 100.0
        if total_reduce_pct > 0:
            reduced = int(monster_damage * total_reduce_pct)
            monster_damage -= reduced
            
        self.data['ship_hp'] -= monster_damage
        round_log.append(f"{self.data['monster_name']}发起反击！船体受到了 {monster_damage} 点伤害，剩余耐久 {max(0, self.data['ship_hp'])}")

        if total_reduce_pct > 0:
            round_log.append(f"玩家技能减免了 {reduced} 点伤害")
        
        # 怪物 Buff: 104 再生
        for buff in self.data.get('monster_buffs', []):
            if buff['id'] == 104:
                heal = int(self.data['monster_max_hp'] * buff['level'] * 0.05)
                if heal > 0:
                    self.data['monster_hp'] = min(self.data['monster_max_hp'], self.data['monster_hp'] + heal)
                    round_log.append(f"{self.data['monster_name']} 触发再生，恢复了 {heal} 点生命值")
        
        # Skill 12: 不屈 (复活)
        if self.data['ship_hp'] <= 0:
            if not self.data.get('revive_used', False) and max_revive_percent > 0:
                self.data['revive_used'] = True
                recover_hp = int(self.data['ship_max_hp'] * max_revive_percent / 100.0)
                self.data['ship_hp'] = recover_hp
                round_log.append(f"【不屈】发动！船体在被破坏前坚持住了，恢复了 {recover_hp} 点耐久！")
            else:
                self.data['ship_hp'] = 0
                self.data['status'] = "fail"        
                self.data['logs'] += round_log
                self.save()
                return {
                    "code": 0, 
                    "message": "船体被破坏，战斗失败...", 
                    "logs": round_log,
                    "status": "fail"
                }
            
        # Skill 18: 再生力 (回血)
        if max_regen_percent > 0 and self.data['ship_hp'] > 0:
            regen_hp = int(self.data['ship_max_hp'] * max_regen_percent / 100.0)
            if regen_hp > 0:
                self.data['ship_hp'] = min(self.data['ship_max_hp'], self.data['ship_hp'] + regen_hp)
                round_log.append(f"【再生力】发动，船体恢复了 {regen_hp} 点耐久")
            
        # 3. 检查回合数
        if self.data['current_round'] >= self.data['max_rounds']:
            self.data['status'] = "fail"        
            self.data['logs'] += round_log
            self.save()
            return {
                "code": 0, 
                "message": f"回合数耗尽，未能击败{self.data['monster_name']}，战斗失败...", 
                "logs": round_log,
                "status": "fail"
            }
                    
        self.data['logs'] += round_log
        self.save()
        return {
            "code": 2,
            "message": f"第 {round_num} 轮结束",
            "logs": round_log,
            "status": "fighting",
            "monster_hp": self.data['monster_hp'],
            "ship_hp": self.data['ship_hp']
        }

    def get_info(self):
        return {
            "status": self.data['status'],
            "monster_name": self.data.get('monster_name', '未知巨兽'),
            "round": f"{self.data['current_round']}/{self.data['max_rounds']}",
            "monster_hp": f"{self.data['monster_hp']}/{self.data['monster_max_hp']}",
            "ship_hp": f"{self.data['ship_hp']}/{self.data['ship_max_hp']}",
            "players_count": len(self.data['players']),
            "environment_buff": self.data.get('environment_buff', 0),
            "monster_buffs": self.data.get('monster_buffs', []),
            "bonus_buffs": self.data.get('bonus_buffs', [])
        }

battle_buffs = {
    'environment': [
        {
            'id': 1,
            'name': '晴天',
            'description': '能见度很好，所有威力提升 10%'
        },
        {
            'id': 2,
            'name': '阳光直射',
            'description': '炽热的阳光，沙漠鱼叉额外提供 50% 的威力加成'
        },
        {
            'id': 3,
            'name': '潮湿闷热',
            'description': '潮湿的空气，森林鱼叉额外提供 50% 的威力加成'
        },
        {
            'id': 4,
            'name': '异常高温',
            'description': '炽热的温度，火山鱼叉额外提供 50% 的威力加成'
        },
        {
            'id': 5,
            'name': '清风徐徐',
            'description': '微风拂面，天空鱼叉额外提供 50% 的威力加成'
        },
        {
            'id': 6,
            'name': '冰河时代',
            'description': '寒冷的气温，冰川鱼叉额外提供 50% 的威力加成'
        },
        {
            'id': 7,
            'name': '大雾弥漫',
            'description': '能见度降低，所有威力下降 10%，但神秘鱼叉额外提供 100% 的威力加成'
        }
    ],
    'monster_negative': [
        {
            'id': 101,
            'name': '灵活',
            'description': '怪物较为灵活，出战时间减少 {level} 轮'
        },
        {
            'id': 102,
            'name': '坚韧',
            'description': '怪物较为坚韧，受到的伤害减少 {level * 10}%'
        },
        {
            'id': 103,
            'name': '狂暴',
            'description': '怪物进入狂暴状态，造成的伤害提升 {level * 10}%'
        },
        {
            'id': 104,
            'name': '再生',
            'description': '怪物拥有再生能力，每轮回复 {level * 5}% 的最大生命值'
        },
        {
            'id': 105,
            'name': '强壮',
            'description': '怪物体型强壮，战斗力提高 {level * 5}%'
        },
        {
            'id': 106,
            'name': '反会心',
            'description': '会心一击触发的概率降低 {level * 20}%（加算）'
        },
        {
            'id': 107,
            'name': '荆棘',
            'description': '攻击怪物时，会反弹 {level * 10}% 的伤害给船体'
        }
    ],
    'bonus': [
        {
            'id': 201,
            'name': '稀有',
            'description': '击败怪物后，获得额外 20% 金钱',
            'conflict': [202]
        },
        {
            'id': 202,
            'name': '超级稀有',
            'description': '击败怪物后，获得额外 50% 金钱',
            'conflict': [201]
        },
        {
            'id': 203,
            'name': '强者',
            'description': '击败怪物后，获得额外 1 个对应等级之证'
        },
        {
            'id': 204,
            'name': '大体型',
            'description': '击败怪物后，获得 1.5 倍的材料掉落'
        },
        {
            'id': 205,
            'name': '可捕获',
            'description': '若成功击败怪物，获得的经验提升 20%，并且可以拿回使用的鱼叉'
        },
        {
            'id': 206,
            'name': '变异体质',
            'description': '此怪物会额外掉落一些随机的其他宝玉'
        }
    ]
}