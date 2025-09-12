from collections import defaultdict
from io import BytesIO
import os
import json
import re
from PIL import Image, ImageFont, ImageDraw
import requests

from src.libraries.poke_dmg_calc import get_accurate_name

# Const values

STATIC_FILE_DIR = "src/static/poke/"
SHOWDOWN_DATA_DIR = "data/poke/showdown/"
FILE_CACHE_DIR = "src/static/poke/imgcache/"
COVER_DIR = "src/static/poke/covers/"
FONT_PATH = STATIC_FILE_DIR + "LXGWWenKai-Regular.ttf"

title_style = ImageFont.truetype(FONT_PATH, 80, encoding="utf-8")
chapter_style = ImageFont.truetype(FONT_PATH, 56, encoding="utf-8")
subtitle_style = ImageFont.truetype(FONT_PATH, 40, encoding="utf-8")
type_style = ImageFont.truetype(FONT_PATH, 48, encoding="utf-8")
stat_style = ImageFont.truetype(FONT_PATH, 40, encoding="utf-8")
text_style = ImageFont.truetype(FONT_PATH, 32, encoding="utf-8")
comment_style = ImageFont.truetype(FONT_PATH, 28, encoding="utf-8")
small_style = ImageFont.truetype(FONT_PATH, 24, encoding="utf-8")
desc_style = ImageFont.truetype(FONT_PATH, 20, encoding="utf-8")

type_dmg_tbl = [
[1, 1, 1, 1, 1, 0.5, 1, 0, 0.5, 1, 1, 1, 1, 1, 1, 1, 1, 1],
[2, 1, 0.5, 0.5, 1, 2, 0.5, 0, 2, 1, 1, 1, 1, 0.5, 2, 1, 2, 0.5],
[1, 2, 1, 1, 1, 0.5, 2, 1, 0.5, 1, 1, 2, 0.5, 1, 1, 1, 1, 1],
[1, 1, 1, 0.5, 0.5, 0.5, 1, 0.5, 0, 1, 1, 2, 1, 1, 1, 1, 1, 2],
[1, 1, 0, 2, 1, 2, 0.5, 1, 2, 2, 1, 0.5, 2, 1, 1, 1, 1, 1],
[1, 0.5, 2, 1, 0.5, 1, 2, 1, 0.5, 2, 1, 1, 1, 1, 2, 1, 1, 1],
[1, 0.5, 0.5, 0.5, 1, 1, 1, 0.5, 0.5, 0.5, 1, 2, 1, 2, 1, 1, 2, 0.5],
[0, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 2, 1, 1, 0.5, 1],
[1, 1, 1, 1, 1, 2, 1, 1, 0.5, 0.5, 0.5, 1, 0.5, 1, 2, 1, 1, 2],
[1, 1, 1, 1, 1, 0.5, 2, 1, 2, 0.5, 0.5, 2, 1, 1, 2, 0.5, 1, 1],
[1, 1, 1, 1, 2, 2, 1, 1, 1, 2, 0.5, 0.5, 1, 1, 1, 0.5, 1, 1],
[1, 1, 0.5, 0.5, 2, 2, 0.5, 1, 0.5, 0.5, 2, 0.5, 1, 1, 1, 0.5, 1, 1],
[1, 1, 2, 1, 0, 1, 1, 1, 1, 1, 2, 0.5, 0.5, 1, 1, 0.5, 1, 1],
[1, 2, 1, 2, 1, 1, 1, 1, 0.5, 1, 1, 1, 1, 0.5, 1, 1, 0, 1],
[1, 1, 2, 1, 2, 1, 1, 1, 0.5, 0.5, 0.5, 2, 1, 1, 0.5, 2, 1, 1],
[1, 1, 1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 1, 1, 1, 2, 1, 0],
[1, 0.5, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 2, 1, 1, 0.5, 0.5],
[1, 2, 1, 0.5, 1, 1, 1, 1, 0.5, 0.5, 1, 1, 1, 1, 1, 2, 2, 1]]
type_tbl = {
    "Normal": ["一般", "#BBBBAA", "#E7E7D8", "普"],
    "Fighting": ["格斗", "#BB5544", "#DD9988", "斗"],
    "Flying": ["飞行", "#6699FF", "#99BBFF", "飞"],
    "Poison": ["毒", "#AA5599", "#C689BA", "毒"],
    "Ground": ["地面", "#DDBB55", "#F1DDA0", "地"],
    "Rock": ["岩石", "#BBAA66", "#E1D08C", "岩"],
    "Bug": ["虫", "#AABB22", "#DAEC44", "虫"],
    "Ghost": ["幽灵", "#6666BB", "#9F9FEC", "鬼"],
    "Steel": ["钢", "#AAAABB", "#DFDFE1", "钢"],
    "Fire": ["火", "#FF4422", "#FF927D", "火"],
    "Water": ["水", "#3399FF", "#77BBFF", "水"],
    "Grass": ["草", "#77CC55", "#BDFFA3", "草"],
    "Electric": ["电", "#FFCC33", "#FAE078", "电"],
    "Psychic": ["超能力", "#FF5599", "#FF9CC4", "超"],
    "Ice": ["冰", "#77DDFF", "#DBF6FF", "冰"],
    "Dragon": ["龙", "#7766EE", "#A194FF", "龙"],
    "Dark": ["恶", "#775544", "#BDA396", "恶"],
    "Fairy": ["妖精", "#FFAAFF", "#FBCBFB", "妖"],
}


def type_cn_to_eng(type):
    for k, v in type_tbl.items():
        if v[0] == type:
            return k
    return ""


def get_type_scale(target1, target2, attacker):
    result = 1
    at = list(type_tbl.keys()).index(attacker)
    ta1 = list(type_tbl.keys()).index(target1)
    result *= type_dmg_tbl[at][ta1]
    if target2 is not None:
        result *= type_dmg_tbl[at][list(type_tbl.keys()).index(target2)]
    return result


def get_type(name):
    for type_eng, type_v in type_tbl.items():
        if type_eng.lower() == name.lower() or type_v[0].lower() == name.lower() or type_v[1].lower() == name.lower():
            return type_eng, type_v
    return "Normal", type_tbl["Normal"]


def get_type_scale_s(target1, target2, attacker):
    color_tbl = {
        "4": "#D32F2F",
        "2": "#F44336",
        "1": "#333333",
        "1/2": "#4CAF50",
        "1/4": "#A5D6A7",
        "0": "#888888"
    }
    r = get_type_scale(target1, target2, attacker)
    if r == 1.0:
        r = "1"
    elif r == 0.5:
        r = "1/2"
    elif r == 0.25:
        r = "1/4"
    elif r == 0.0:
        r = "0"
    else:
        r = str(r)
    return r + "×", color_tbl[r]


def tc(type):
    return type_tbl[type][1]


def tc2(type):
    return type_tbl[type][2]


def tn(type):
    return type_tbl[type][0]


with open(SHOWDOWN_DATA_DIR + "move_list.json") as f:
    move_dict: dict[str, dict] = json.load(f)

with open(SHOWDOWN_DATA_DIR + "move.json") as f:
    pokemon_move_dict: dict[str, dict] = json.load(f)

with open(SHOWDOWN_DATA_DIR + "ability_list.json") as f:
    ability_dict_raw: dict[str, dict] = json.load(f)
    ability_dict = {}
    for k, v in ability_dict_raw.items():
        ability_dict[v['name']] = v

with open(SHOWDOWN_DATA_DIR + "pokedex.json") as f:
    pokedex: dict[str, dict] = json.load(f)

with open(SHOWDOWN_DATA_DIR + "translations.json", 'r', encoding='utf-8') as f:
    eng2zh: dict[str, str] = json.load(f)

with open(SHOWDOWN_DATA_DIR + "move_cn.txt", 'r', encoding='utf-8') as f:
    move_cn = f.read().splitlines()
    move_cn_dict = {}
    for line in move_cn:
        args = line.split('\t')
        if args[3] in move_cn_dict and "Ｚ" not in args[1]:
            raise KeyError(f"{args[3]} duplicate in move")
        move_cn_dict[args[3]] = {
            "name": args[1],
            "description": args[-1]
        }

with open(SHOWDOWN_DATA_DIR + "ability_cn.txt", 'r', encoding='utf-8') as f:
    ability_cn = f.read().splitlines()
    ability_cn_dict = {}
    for line in ability_cn:
        args = line.split('\t')
        if args[3] in ability_cn_dict:
            raise KeyError(f"{args[3]} duplicate in ability")
        ability_cn_dict[args[3]] = {
            "name": args[1],
            "description": args[-3]
        }

pokemon_cn_to_eng = {}
for poke in pokedex.values():
    name = poke['name']
    if name in eng2zh:
        pokemon_cn_to_eng[eng2zh[name].lower()] = name.lower()
    else:
        name_tags = name.split('-')
        if len(name_tags) > 1:
            name = eng2zh[name_tags[0]]
            for tag in name_tags[1:]:
                name += eng2zh['-' + tag]
        pokemon_cn_to_eng[name.lower()] = poke['name'].lower()

pokemon_eng_to_key = {}
for key, poke in pokedex.items():
    pokemon_eng_to_key[poke['name'].lower()] = key

def get_move(pokemon, name):
    move = move_dict[name]
    genre = {
        'Physical': '物理',
        'Special': '特殊',
        'Status': '变化'
    }
    return {
        "name": move_cn_dict[move["name"]]["name"],
        "type": move["type"],
        "genre": genre[move["category"]],
        "power": str(move['basePower']) if move['basePower'] > 0 else "—",
        "acc": str(move["accuracy"]) if type(move["accuracy"]) == type(0) else "—",
        "pp": str(move["pp"]),
        "desc": move_cn_dict[move["name"]]["description"],
        "usual": name in pokemon_move_dict[pokemon]['overused']
    }


def get_pokemon(pokename):
    pokename = pokename.lower()
    if pokename in pokemon_cn_to_eng:
        name = pokemon_cn_to_eng[pokename]
    else:
        name = pokename
    if name not in pokemon_eng_to_key:
        return None, None
    poke_key = pokemon_eng_to_key[name]
    poke = pokedex[poke_key]
    res = {
        "key": poke_key,
        "name": eng2zh[poke['name']],
        # "jpname": pokemon_cn[name][2],
        "engname": poke['name'],
        "ability_list": [],
        "moves": pokemon_move_dict[poke_key]['overused'] + pokemon_move_dict[poke_key]['useless'],
        "type": [],
        "stats": []
    }
    if len(res["moves"]) == 0:
        print(f"Warn: {poke['name']} has no moves, try find base")
        species = poke['baseSpecies'] if 'baseSpecies' in poke else poke['name']
        if species.lower() in pokemon_move_dict:
            new_moves = pokemon_move_dict[species.lower()]['overused'] + pokemon_move_dict[species.lower()]['useless']
            if len(new_moves) > 0 or species.lower() == "unown":
                res["moves"] = new_moves
            else:
                raise Exception(f"Error: {poke['name']} has no moves")
            
    for ab_index in ["0", "1"]:
        if ab_index in poke["abilities"]:
            ab = poke["abilities"][ab_index]
            res["ability_list"].append({
                "name": ability_cn_dict[ab]["name"],
                "hidden": False,
                "description": ability_cn_dict[ab]["description"]
            })
    if "H" in poke["abilities"]:
        ab = poke["abilities"]["H"]
        res["ability_list"].append({
            "name": ability_cn_dict[ab]["name"],
            "hidden": True,
            "description": ability_cn_dict[ab]["description"]
        })
    res["type"] = poke["types"]
    res["stats"] = list(poke["baseStats"].values())
    res["moves"] = {
        "all": [get_move(poke_key, move) for move in res["moves"] if move != '' and move in move_dict]
    }
    return res


def get_image_url(pokemon, base=False):
    name = pokemon['baseSpecies'] if 'baseSpecies' in pokemon else pokemon['name']
    name = name.replace(" ", "").replace("-", "").replace("’", "").lower()
    if not base and pokemon.get('forme', '') != '':
        forme = pokemon['forme'].replace(" ", "").replace("-", "").replace("’", "").lower()
        name += f"-{forme}"
    return f"https://play.pokemonshowdown.com/sprites/home-centered/{name}.png"


def get_length_of_val(val):
    return min(val * 2, 450)

def calc_stat(ev, level, iv, bp, modifier, is_hp=False):
    if is_hp:
        return int((int(ev * 2 + iv + bp / 4) * level) / 100 + 10 + level)
    else:
        return int(((int(ev * 2 + iv + bp / 4) * level) / 100 + 5) * modifier)

def get_min_max(pokedata, level):
    minv = [0, 0, 0, 0, 0, 0]
    maxv = [0, 0, 0, 0, 0, 0]
    if pokedata["name"] == "脱壳忍者":
        minv[0] = 1
        maxv[0] = 1
    else:
        minv[0] = calc_stat(pokedata["stats"][0], level, 0, 0, 1, True)
        maxv[0] = calc_stat(pokedata["stats"][0], level, 31, 252, 1, True)
    for i in range(1, 6):
        minv[i] = calc_stat(pokedata["stats"][i], level, 0, 0, 0.9)
        maxv[i] = calc_stat(pokedata["stats"][i], level, 31, 252, 1.1)
    return minv, maxv

def get_image(pokename, force_generate=False):
    pokename = get_accurate_name(pokename)
    data = get_pokemon(pokename)
    if data is None:
        return None, None

    filepath = FILE_CACHE_DIR + pokedex[data['key']]['name'].lower() + ".png"
    print(filepath)
    if os.path.exists(filepath) and not force_generate:
        print('Cached image found for', data['engname'])
        return filepath

    image_url = get_image_url(pokedex[data['key']])
    cover_url = f"{COVER_DIR}{data['engname']}.png"
    if not os.path.exists(cover_url):
        try:
            cover = Image.open(BytesIO(requests.get(image_url).content))
        except Exception as e:
            image_url = get_image_url(pokedex[data['key']], True)
            cover = Image.open(BytesIO(requests.get(image_url).content))
    else:
        cover = Image.open(cover_url)
    cover = cover.resize((500, 500), Image.Resampling.BILINEAR)

    im = Image.new("RGBA", (1200, 4000))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1200, 4000), tc(data["type"][0]))
    draw.rounded_rectangle((16, 16, 1200 - 16, 4000 - 16), 20, tc2(data["type"][0]))
    draw.text((40, 24), data["name"], fill="#333333", font=title_style)
    name_width = draw.textlength(data["name"], font=title_style)
    draw.text((52 + name_width, 64), data["engname"], fill="#333333", font=subtitle_style)
    draw.text((40, 128), tn(data["type"][0]), fill=tc(data["type"][0]), stroke_fill="#888888", stroke_width=2, font=type_style)
    if len(data["type"]) == 2:
        draw.text((56 + len(tn(data["type"][0])) * 48, 128), tn(data["type"][1]), fill=tc(data["type"][1]), stroke_fill="#888888", stroke_width=2, font=type_style)
    lst = ['HP', '攻击', '防御', '特攻', '特防', '速度', '总计']
    colors = ["#97C87A", "#FAE192", "#FBB977", "#A2D4DA", "#89A9CD", "#C39CD8", "#dddddd"]
    data["stats"].append(sum(data["stats"]))
    for i in range(len(data["stats"]) - 1):
        val = data["stats"][i]
        draw.text((40, 200 + i * 56), lst[i], stroke_fill="#888888", stroke_width=2, fill=colors[i], font=stat_style)
        draw.rectangle((135, 211 + i * 56, 145 + get_length_of_val(val), 233 + i * 56), "#888888")
        draw.rectangle((136, 212 + i * 56, 144 + get_length_of_val(val), 232 + i * 56), colors[i])
        draw.text((160 + get_length_of_val(val), 200 + i * 56), str(data["stats"][i]), stroke_fill="#888888", stroke_width=2, fill=colors[i], font=stat_style)
    
    i = 6
    val = data["stats"][i]
    draw.text((40, 200 + i * 56), lst[i], stroke_fill="#888888", stroke_width=2, fill=colors[i], font=stat_style)
    draw.rectangle((135, 211 + i * 56, 145 + int(val * 0.33), 233 + i * 56), "#888888")
    draw.rectangle((136, 212 + i * 56, 144 + int(val * 0.33), 232 + i * 56), colors[i])
    draw.text((160 + int(val * 0.33), 200 + i * 56), str(data["stats"][i]), stroke_fill="#888888", stroke_width=2, fill=colors[i], font=stat_style)
    
    minv, maxv = get_min_max(data, 50)
    minv100, maxv100 = get_min_max(data, 100)

    draw.text((40, 600), "能力值范围", fill="#333333", font=chapter_style)

    draw.rectangle((30, 670, 170 * 6 + 142 + 2, 672 + 104), "#333333")

    draw.rectangle((32, 672, 142, 672 + 50), fill=colors[6])
    draw.text((40, 680), "50级", fill="#333333", font=text_style)
    for i in range(6):
        length = draw.textlength(f"{minv[i]} - {maxv[i]}", font=text_style)
        draw.rectangle((170 * i + 142, 672, 170 * (i + 1) + 142, 672 + 50), fill=colors[i])
        draw.text((170 * i + 142 + 85 - int(length / 2), 680), f"{minv[i]} - {maxv[i]}", fill="#333333", font=text_style)

    draw.rectangle((32, 672 + 52, 142, 672 + 102), fill=colors[6])
    draw.text((40, 680 + 52), "100级", fill="#333333", font=text_style)
    for i in range(6):
        length = draw.textlength(f"{minv100[i]} - {maxv100[i]}", font=text_style)
        draw.rectangle((170 * i + 142, 672 + 52, 170 * (i + 1) + 142, 672 + 102), fill=colors[i])
        draw.text((170 * i + 142 + 85 - int(length / 2), 680 + 52), f"{minv100[i]} - {maxv100[i]}", fill="#333333", font=text_style)
    
    current_y = 790

    draw.text((40, current_y), "属性抗性", fill="#333333", font=chapter_style)
    
    current_y += 76

    current_x = 60

    for k in type_tbl:
        draw.rectangle((current_x, current_y, current_x + 60, current_y + 60), fill=type_tbl[k][1])
        draw.text((current_x + 30, current_y + 12), tn(k)[:2], anchor="ma", fill="#333333", font=comment_style)
        draw.rectangle((current_x, current_y + 60, current_x + 60, current_y + 120), fill=type_tbl[k][2])
        s, f = get_type_scale_s(data["type"][0], None if len(data["type"]) == 1 else data["type"][1], k)
        draw.text((current_x + 30, current_y + 76), s, anchor="ma", fill=f, font=small_style, stroke_fill="#888888", stroke_width=1)
        current_x += 60

    current_y += 132
    
    draw.text((40, current_y), "特性", fill="#333333", font=chapter_style)
    current_y += 76
    for i in range(len(data["ability_list"])):
        ab = data["ability_list"][i]
        draw.text((40, current_y), ab["name"], fill=("#3F51B5" if ab["hidden"] else "#333333"), font=text_style, stroke_fill="#888888", stroke_width=1)
        desc = ab["description"]
        current = ""
        while len(desc) != 0:
            current += desc[0]
            desc = desc[1:]
            if draw.textlength(current, font=text_style) > 920 and len(desc) > 0:
                draw.text((240, current_y), current, fill=("#3F51B5" if ab["hidden"] else "#333333"), font=text_style, stroke_fill="#888888", stroke_width=1)
                current_y += 50
                current = ""
        draw.text((240, current_y), current, fill=("#3F51B5" if ab["hidden"] else "#333333"), font=text_style, stroke_fill="#888888", stroke_width=1)
        current_y += 50
    
    draw.text((40, current_y), "招式列表", fill="#333333", font=chapter_style)
    current_y += 16 + 56
    draw.text((40, current_y), f"仅显示整体使用率较高的招式，如果需要完整招式请输入“完整招式 {data['name']}”", fill="#555555", font=comment_style)
    current_y += 16 + 32

    def draw_move(move, current_y, dark):
        desc = move["desc"]
        if len(desc) > 33:
            desc = desc[:32] + "..."
        draw.rectangle((48, current_y - 2, 1160, current_y + 30), fill=("#ffffffff" if dark else "#eeeeeeee"))
        draw.text((50 + 80, current_y), move["name"], fill="#333333", font=desc_style, anchor="ma")
        draw.text((200 + 30, current_y), tn(move["type"]), fill=tc(move["type"]), font=desc_style, anchor="ma")
        draw.text((270, current_y), move["genre"], fill="#333333", font=desc_style)
        draw.text((320 + 30, current_y), move["power"], fill="#333333", font=desc_style, anchor="ma")
        draw.text((380 + 30, current_y), move["acc"], fill="#333333", font=desc_style, anchor="ma")
        draw.text((440 + 30, current_y), move["pp"], fill="#333333", font=desc_style, anchor="ma")
        draw.text((500, current_y), desc, fill="#333333", font=desc_style)
        return current_y + 30

    dark = False
    draw.rectangle((48, current_y - 2, 1160, current_y + 30), fill=("#ffffffff" if dark else "#eeeeeeee"))
    draw.text((50 + 80, current_y), "名称", fill="#333333", font=desc_style, anchor="ma")
    draw.text((200 + 30, current_y), "属性", fill="#333333", font=desc_style, anchor="ma")
    draw.text((270, current_y), "分类", fill="#333333", font=desc_style)
    draw.text((320 + 30, current_y), "威力", fill="#333333", font=desc_style, anchor="ma")
    draw.text((380 + 30, current_y), "命中", fill="#333333", font=desc_style, anchor="ma")
    draw.text((440 + 30, current_y), "PP", fill="#333333", font=desc_style, anchor="ma")
    draw.text(((500 + 1160) / 2, current_y), "描述", fill="#333333", font=desc_style, anchor="ma")
     
    current_y += 30

    dark = True
    for move in data["moves"]["all"]:
        if move["usual"]:
            current_y = draw_move(move, current_y, dark)
            dark = not dark

    im.paste(cover, (640, 120), cover)

    im2 = Image.new("RGBA", (1200, current_y + 50))
    draw = ImageDraw.Draw(im2)
    draw.rectangle((0, 0, 1200, current_y + 50), tc(data["type"][0]))
    draw.rounded_rectangle((16, 16, 1200 - 16, current_y + 50 - 16), 20, tc2(data["type"][0]))

    im2.paste(im.crop((0, 0, 1200, current_y)), (0, 0))
    im2.save(filepath)

    return im2


types_ability_modifier = {
    "Fire": {
        "Flash Fire": 0,
        "Well-Baked Body": 0,
        "Water Bubble": 0.5,
        "Thick Fat": 0.5,
        "Heatproof": 0.5,
        "Dry Skin": 1.25,
        "Fluffy": 2,
    },
    "Water": {
        "Water Absorb": 0,
        "Dry Skin": 0,
        "Storm Drain": 0,
    },
    "Electric": {
        "Volt Absorb": 0,
        "Lighting Rod": 0,
        "Motor Drive": 0,
    },
    "Ground": {
        "Levitate": 0,
        "Earth Eater": 0,
    },
    "Ice": {
        "Thick Fat": 0.5
    },
    "Grass": {
        "Sap Sipper": 0
    },
    "Ghost": {
        "Purifying Salt": 0.5
    }
}

for key in type_tbl:
    if key not in ["Flying", "Rock", "Ghost", "Fire", "Dark"]:
        types_ability_modifier.setdefault(key, {})["Wonder Guard"] = 0

def get_effectiveness_for_pokemon(poke, type, effectiveness=1):
    attack_type_index = list(type_tbl.keys()).index(type)
    defender_types = poke.get('types', [])
    for poke_type in defender_types:
        poke_type_index = list(type_tbl.keys()).index(poke_type)
        effectiveness *= type_dmg_tbl[attack_type_index][poke_type_index]
    result = {
        "default": effectiveness
    }
    for ability in poke.get('abilities', {}).values():
        if ability in types_ability_modifier.get(type, {}):
            modifier = types_ability_modifier[type][ability]
            result[ability] = effectiveness * modifier
        else:
            result[ability] = effectiveness
    return result

def get_effectiveness_for_all_type(attack_type, effectiveness=1):
    result = []
    types = list(type_tbl.keys())
    attack_index = types.index(attack_type)
    for i in range(len(types)):
        for j in range(i, len(types)):
            if i == j:
                rate = effectiveness * type_dmg_tbl[attack_index][i]
                if rate < 1.49:
                    result.append([types[i]])
            else:
                rate = effectiveness * type_dmg_tbl[attack_index][i] * type_dmg_tbl[attack_index][j]
                if rate < 1.49:
                    result.append([types[i], types[j]])
    return result


def get_not_every_effective_types(attack_types):
    result = None
    for (attack_type, eff) in attack_types:
        if result is None:
            result = get_effectiveness_for_all_type(attack_type, eff)
        else:
            new_result = get_effectiveness_for_all_type(attack_type, eff)
            result = [key for key in result if key in new_result]
    return result

def get_not_every_effective_list(attack_types):
    result = defaultdict(lambda: {})
    for key, poke in pokedex.items():
        if key.endswith('totem') or key.endswith('gmax'):
            continue
        one_result = defaultdict(lambda: 0)
        for (t, eff) in attack_types:
            result2 = get_effectiveness_for_pokemon(poke, t, eff)
            for ability in result2:
                one_result[ability] = max(one_result[ability], result2[ability])
        for ability in one_result:
            if one_result[ability] < 1.49:
                result[key][ability] = one_result[ability]
    for value in result.values():
        del_l = []
        for key in value:
            if key != 'default' and value[key] == value.get('default', -1):
                del_l.append(key)
        for key in del_l:
            del value[key]
    return dict(result)
