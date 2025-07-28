from collections import defaultdict
import re
import json
from typing import Optional
import aiohttp

calculate_service = 'http://localhost:9888/calculate'

with open('data/dmg-calc-translation/abilities.json', 'r', encoding='utf-8') as f:
    abilities: dict[str, str] = json.load(f)
    abilities_en2zh = {v: k for k, v in abilities.items()}
with open('data/dmg-calc-translation/items.json', 'r', encoding='utf-8') as f:
    items: dict[str, str] = json.load(f)
with open('data/dmg-calc-translation/moves.json', 'r', encoding='utf-8') as f:
    moves: dict[str, str] = json.load(f)
with open('data/dmg-calc-translation/species.json', 'r', encoding='utf-8') as f:
    species: dict[str, str] = json.load(f)
    species_en2zh = {v: k for k, v in species.items()}
with open('data/dmg-calc-translation/status.json', 'r', encoding='utf-8') as f:
    status: dict[str, str] = json.load(f)
with open('data/dmg-calc-translation/field.json', 'r', encoding='utf-8') as f:
    field = json.load(f)
    weathers: dict[str, str] = field['weathers']
    terrains: dict[str, str] = field['terrains']

def add_lower_case_map(m: dict[str, str]):
    lst = list(m.items())
    for k, v in lst:
        m[k.lower()] = v
    for k, v in lst:
        m[v.lower()] = v

add_lower_case_map(abilities)
add_lower_case_map(items)
add_lower_case_map(moves)
add_lower_case_map(species)
add_lower_case_map(status)
add_lower_case_map(weathers)
add_lower_case_map(terrains)


def check_ascii(s: str):
    for c in s:
        if ord(c) > 127:
            return False
    return True


def get_accurate_name(pokename):
    pokename = pokename.lower()
    if pokename in species:
        return species[pokename]
    mega = False
    x = False
    y = False
    if 'mega' in pokename:
        pokename = pokename.replace('mega', '').strip()
        mega = True
        if 'x' == pokename[0]:
            pokename = pokename[1:].strip()
            x = True
        elif 'y' == pokename[0]:
            pokename = pokename[1:].strip()
            y = True
        elif 'x' == pokename[-1]:
            pokename = pokename[:-1].strip()
            x = True
        elif 'y' == pokename[-1]:
            pokename = pokename[:-1].strip()
            y = True
    if pokename in species:
        name = species[pokename]
        if mega:
            if x:
                return name + '-Mega-X'
            elif y:
                return name + '-Mega-Y'
            else:
                return name + '-Mega'
        else:
            return name
    else:
        raise KeyError(f"错误：无法解析参数 '{pokename}'")
        

abilitie_vals = abilities.values()
item_vals = items.values()
move_vals = moves.values()
species_vals = species.values()
status_vals = status.values()
weather_vals = weathers.values()
terrain_vals = terrains.values()

types_cn = ['一般', '火', '水', '电', '草', '冰', '格斗', '毒', '地面', '飞行', '超能', '虫', '岩石', '幽灵', '龙', '恶', '钢', '妖精', '星晶']
types = ['Normal', 'Fire', 'Water', 'Electric', 'Grass', 'Ice', 'Fighting', 'Poison', 'Ground', 'Flying', 'Psychic', 'Bug', 'Rock', 'Ghost', 'Dragon', 'Dark', 'Steel', 'Fairy', 'Stellar']

HP = 5
ATK = 0
DEF = 1
SPA = 3
SPD = 4
SPE = 2
stat_map = {
    'hp': HP,
    'atk': ATK,
    'def': DEF,
    'spa': SPA,
    'spd': SPD,
    'spe': SPE,
    'h': HP,
    'a': ATK,
    'b': DEF,
    'c': SPA,
    'd': SPD,
    's': SPE
}
stat_text = ['atk', 'def', 'spe', 'spa', 'spd', 'hp']
natures = [
    ['Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty'],
    ['Bold', 'Docile', 'Relaxed', 'Impish', 'Lax'],
    ['Timid', 'Hasty', 'Serious', 'Jolly', 'Naive'],
    ['Modest', 'Mild', 'Quiet', 'Bashful', 'Rash'],
    ['Calm', 'Gentle', 'Sassy', 'Careful', 'Quirky']
]

class Pokemon:
    def __init__(self, generation=9, level=100):
        self.generation = generation
        self.level = level
        self.attributes = defaultdict(lambda: {})
        self.name = ''
        self.plus_stat = None
        self.minus_stat = None

    def json(self):
        return {
            'generation': self.generation,
            'level': self.level,
            'name': self.name,
            'attributes': self.attributes
        }
    
    def set_ev(self, stat: int, value: int):
        self.attributes['evs'][stat_text[stat]] = value

    def set_iv(self, stat: int, value: int):
        self.attributes['ivs'][stat_text[stat]] = value

    def set_boost(self, value: int, stats: list[int]=[]):
        for stat in stats:
            self.attributes['boosts'][stat_text[stat]] = value
    
class Move:
    def __init__(self, name, generation=9):
        self.name = name
        self.generation = generation

    def json(self):
        return {
            'name': self.name,
            'generation': self.generation
        }

class Field:
    def __init__(self):
        self.weather: Optional[str] = None
        self.terrain: Optional[str] = None

    def json(self):
        body = {}
        if self.weather:
            body['weather'] = self.weather
        if self.terrain:
            body['terrain'] = self.terrain.replace(' ter', '')
        return body

class DamageCalc:
    def __init__(self, message):
        self.message = message
        self.args = self.parse_arguments(message)
        self.attacker = Pokemon()
        self.defender = Pokemon()
        self.current = self.attacker
        self.field = Field()
        self.move = ''
        self.z_move = False
        self.move_crit = False
        self.parse()

    def parse_crit(self, text):
        text = text.lower()
        if text in ('ct', 'crit', 'critical', '要害', '击中要害'):
            self.move_crit = True
            return True
        return False

    def parse_boost(self, text):
        boost = r'(\+|-)([0-9]+)(H|A|B|C|D|S|hp|atk|def|spa|spd|spe)?\b'
        regex = re.compile(boost, re.IGNORECASE)
        groups = regex.findall(text)
        if len(groups) == 0:
            return False
        for group in groups:
            value = int(group[0] + group[1])
            stat: str = group[2].lower() if group[2] else ''
            if stat != '':
                stats = [stat]
            else:
                stats = ['atk', 'spa'] if self.attacker == self.current else ['def', 'spd']
            self.current.set_boost(value, [stat_map[s] for s in stats])
        return True

    def parse_iv(self, text):
        iv = r'([0-9]+)iv(H|A|B|C|D|S|hp|atk|def|spa|spd|spe)\b'
        regex = re.compile(iv, re.IGNORECASE)
        groups = regex.findall(text)
        if len(groups) == 0:
            return False
        for group in groups:
            value = int(group[0])
            stat = group[1].lower()
            if stat in stat_map:
                stat = stat_map[stat]
            self.current.set_iv(stat, value)
        return True

    def parse_ev(self, text):
        ev = r'([0-9]+)(\+|-)?(H|A|B|C|D|S|hp|atk|def|spa|spd|spe)\b(\+|-)?'
        regex = re.compile(ev, re.IGNORECASE)
        groups = regex.findall(text)
        if len(groups) == 0:
            return False
        for group in groups:
            value = int(group[0])
            stat = group[2].lower()
            if stat in stat_map:
                stat = stat_map[stat]
            if group[1] == '+' or group[3] == '+':
                self.current.plus_stat = stat
            elif group[1] == '-' or group[3] == '-':
                self.current.minus_stat = stat
            self.current.attributes['evs'][stat_text[stat]] = value
        return True
    
    def parse_word(self, text: str):
        text_lower = text.lower()
        if text in abilitie_vals:
            self.current.attributes['ability'] = text
            return True
        elif text in item_vals:
            self.current.attributes['item'] = text
            return True
        elif text in species_vals:
            self.current.name = text
            if self.current == self.attacker:
                self.current = self.defender
                return True
            elif self.current == self.defender:
                self.current = None
                return True
            else:
                raise Exception(f"解析参数 {text} 时出现错误：已定义攻击方宝可梦和防御方宝可梦")
        elif text in status_vals:
            self.current.attributes['status'] = text
            return True
        elif text in weather_vals:
            self.field.weather = text
            return True
        elif text in terrain_vals:
            self.field.terrain = text
            return True
        elif text in move_vals:
            self.move = Move(text)
            return True
        elif text_lower in abilities:
            return self.parse_word(abilities[text_lower])
        elif text_lower in items:
            return self.parse_word(items[text_lower])
        elif text_lower in species:
            return self.parse_word(species[text_lower])
        elif text_lower in status:
            return self.parse_word(status[text_lower])
        elif text_lower in weathers:
            return self.parse_word(weathers[text_lower])
        elif text_lower in terrains:
            return self.parse_word(terrains[text_lower])
        elif text_lower in moves:
            return self.parse_word(moves[text_lower])
        elif text_lower[-1] == 'z' and text_lower[:-1] in moves:
            self.z_move = True
            return self.parse_word(moves[text_lower[:-1]])
        try:
            if get_accurate_name(text_lower):
                return self.parse_word(get_accurate_name(text_lower))
        except KeyError:
            return False
        return False
    
    def parse_level(self, text):
        level_cn = r'(\d+)级'
        level_en = r'L(\d+)'
        regex_cn = re.compile(level_cn)
        regex_en = re.compile(level_en)
        match_cn = regex_cn.match(text)
        match_en = regex_en.match(text)
        if match_cn:
            level = int(match_cn.group(1))
            if 1 <= level <= 100:
                self.current.level = level
                return True
            else:
                raise Exception(f"错误：级别 {level} 超出范围 (1-100)")
        elif match_en:
            level = int(match_en.group(1))
            if 1 <= level <= 100:
                self.current.level = level
                return True
            else:
                raise Exception(f"错误：级别 {level} 超出范围 (1-100)")
        return False
    
    def parse_tera(self, text):
        tera = r'太晶(.+)'
        regex = re.compile(tera, re.IGNORECASE)
        match = regex.match(text)
        if match:
            tera_type = match.group(1)
            if tera_type in types:
                self.current.attributes['teraType'] = tera_type
                return True
            elif tera_type in types_cn:
                self.current.attributes['teraType'] = types[types_cn.index(tera_type)]
                return True
            else:
                raise Exception(f"错误：未知的太晶类型 '{tera_type}'")
        return False

    def parse(self):
        for arg in self.args:
            success = self.parse_crit(arg) or self.parse_boost(arg) or self.parse_ev(arg) or self.parse_iv(arg) or self.parse_level(arg) or self.parse_word(arg) or self.parse_tera(arg) 
            if not success:
                raise Exception(f"错误：无法解析参数 '{arg}'")
        if self.attacker.name == '':
            raise Exception("错误：攻击方宝可梦未定义")
        if self.defender.name == '':
            raise Exception("错误：防御方宝可梦未定义")
        if self.move == '':
            raise Exception("错误：未定义招式")
        if self.attacker.minus_stat is None:
            self.attacker.minus_stat = SPD
        if self.attacker.plus_stat is None:
            self.attacker.plus_stat = self.attacker.minus_stat
        if self.defender.minus_stat is None:
            self.defender.minus_stat = SPA
        if self.defender.plus_stat is None:
            self.defender.plus_stat = self.defender.minus_stat
        self.attacker.attributes['nature'] = natures[self.attacker.plus_stat][self.attacker.minus_stat]
        self.defender.attributes['nature'] = natures[self.defender.plus_stat][self.defender.minus_stat]

    async def execute(self):
        attacker = self.attacker.json()
        defender = self.defender.json()
        move = self.move.json()
        move['isZ'] = self.z_move
        move['crit'] = self.move_crit
        field = self.field.json()
        data = {
            'attacker': attacker,
            'defender': defender,
            'move': move,
            'field': field
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(calculate_service, json=data) as response:
                if response.status != 200:
                    raise Exception(f"错误：计算服务返回状态码 {response.status}")
                result = await response.json()
                # print(json.dumps(result, indent=4))
                return self.pretty_print(result)
            
    def pretty_print(self, result):
        raw_desc = result['rawDesc']
        attacker = []
        attackBoost = raw_desc.get('attackBoost', 0)
        if attackBoost != 0:
            attacker.append(f"{attackBoost:+d}")
        attackEVs = raw_desc.get('attackEVs', 0)
        attacker.append(attackEVs)
        attackerAbility = raw_desc.get('attackerAbility', '')
        if attackerAbility:
            attacker.append(attackerAbility)
        attackerItem = raw_desc.get('attackerItem', '')
        if attackerItem:
            attacker.append(attackerItem)
        attackTera = raw_desc.get('attackerTera', '')
        if attackTera:
            attacker.append(f"Tera {attackTera}")
        attacker.append(raw_desc.get('attackerName', ''))
        move = []
        move.append(raw_desc.get('moveName', ''))
        if raw_desc.get('moveBP', 0):
            move.append(f"({raw_desc['moveBP']} BP)")
        if raw_desc.get('hits', 1) > 1:
            move.append(f"({raw_desc['hits']} hits)")
        defender = []
        defenseBoost = raw_desc.get('defenseBoost', 0)
        if defenseBoost != 0:
            defender.append(f"{defenseBoost:+d}")
        hpEVS = raw_desc.get('HPEVs', 0)
        if hpEVS != 0:
            defender.append(hpEVS + ' /')
        defenseEVs = raw_desc.get('defenseEVs', 0)
        defender.append(defenseEVs)
        defenderAbility = raw_desc.get('defenderAbility', '')
        if defenderAbility:
            defender.append(defenderAbility)
        defenderItem = raw_desc.get('defenderItem', '')
        if defenderItem:
            defender.append(defenderItem)
        defenseTera = raw_desc.get('defenderTera', '')
        if defenseTera:
            defender.append(f"Tera {defenseTera}")
        defender.append(raw_desc.get('defenderName', ''))
        field = []
        weather = raw_desc.get('weather', '')
        terrain = raw_desc.get('terrain', '')
        if weather or terrain:
            field.append(' in')
        if weather:
            field.append(weather)
        if terrain:
            field.append(terrain + ' Terrain')
        dmg = result['damage']
        defender_hp = result['defender']['rawStats']['hp']
        crit_text = ''
        if raw_desc.get('isCritical', False):
            crit_text = ' on a critial hit'
        return ' '.join(attacker) + ' ' + ' '.join(move) + ' vs. ' + ' '.join(defender) + ' '.join(field) + crit_text + f': {dmg[0]}-{dmg[-1]} ({dmg[0] / defender_hp*100:.1f}% - {dmg[-1] / defender_hp*100:.1f}%)'
        

    def parse_arguments(self, text):
        args = []
        current_arg = ""
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            if not in_quotes:
                if char in ['"', "'"]:
                    in_quotes = True
                    quote_char = char
                elif char == ' ':
                    if current_arg:
                        args.append(current_arg)
                        current_arg = ""
                else:
                    current_arg += char
            else:
                if char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current_arg += char
            
            i += 1
        
        if current_arg:
            args.append(current_arg)
        
        return args

