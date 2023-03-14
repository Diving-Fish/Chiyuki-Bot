from io import BytesIO
import os
import json
import re
from PIL import Image, ImageFont, ImageDraw

# Const values

STATIC_FILE_DIR = "src/static/poke/"
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

ability_cn = {}
pokemon_dict = {}
pokemon_cn = {}
pokemon_cn_to_eng = {}
move_cn = {}
pm_move_dict = {}
move_list = {}
pic_dict = {}
item_list = []
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


with open(STATIC_FILE_DIR + "MoveList.txt", encoding='utf-8') as f:
    for line in f.read().split('\n'):
        arr = line.split('\t')
        move_cn[arr[3]] = arr
        try:
            move_list[int(arr[0])] = arr
        except ValueError:
            pass

with open(STATIC_FILE_DIR + "AbilityList.txt", encoding='utf-8') as f:
    for line in f.read().split('\n'):
        arr = line.split('\t')
        ability_cn[arr[3]] = arr

with open(STATIC_FILE_DIR + "PokeList.txt", encoding='utf-8') as f:
    for line in f.read().split('\n'):
        arr = line.split('\t')
        pokemon_cn[arr[3]] = arr
        pokemon_cn_to_eng[arr[1]] = arr[3]

with open(STATIC_FILE_DIR + "ItemList.txt", encoding='utf-8') as f:
    for line in f.read().split('\n'):
        arr = line.split('\t')
        item_list.append(arr)

with open(STATIC_FILE_DIR + "move_list.json", encoding='utf-8') as f:
    pm_move_dict = json.load(f)

with open(STATIC_FILE_DIR + "pokemon_dict.json", encoding='utf-8') as f:
    pokemon_dict = json.load(f)

with open(STATIC_FILE_DIR + "pic_dict.json", encoding='utf-8') as f:
    pic_dict = json.load(f)


def get_move(id):
    move = move_list[id]
    return {
        "id": id,
        "name": move[1].strip(),
        "type": type_cn_to_eng(move[4].strip()),
        "genre": move[5].strip(),
        "power": move[6].strip(),
        "acc": move[7].strip(),
        "pp": move[8].strip(),
        "desc": move[9].strip(),
        "usual": len(move) > 10
    }


def get_item(name):
    for item in item_list:
        for v in item:
            if name == v:
                return item
    return None


def get_pokemon(pokename, index=0):
    if pokename in pokemon_cn_to_eng:
        name = pokemon_cn_to_eng[pokename]
    else:
        name = pokename
    if name not in pokemon_dict:
        return None, None
    poke = pokemon_dict[name][index]
    res = {
        "name": pokemon_cn[name][1],
        "jpname": pokemon_cn[name][2],
        "engname": pokemon_cn[name][3],
        "ability_list": [],
        "moves": {
            "by_leveling_up": [],
            "all": [],
        },
        "type": [],
        "stats": []
    }
    for ab in poke["ability"]:
        ab_cn = ability_cn[ab]
        res["ability_list"].append({
            "name": ab_cn[1],
            "hidden": False,
            "description": ab_cn[4]
        })
    if poke["hiddenability"] != "":
        ab = poke["hiddenability"]
        ab_cn = ability_cn[ab]
        res["ability_list"].append({
            "name": ab_cn[1],
            "hidden": True,
            "description": ab_cn[4]
        })
    res["type"] = poke["type"]
    res["stats"] = poke["stats"]
    moves = pm_move_dict[name]
    for move in moves["byLevelingUp"]:
        res["moves"]["by_leveling_up"].append({
            "level": move[0],
            "move": get_move(move[1])
        })
    for move in moves["all"]:
        if get_move(move) not in res["moves"]["all"]:
            res["moves"]["all"].append(get_move(move))
            res["moves"]["all"].sort(key=lambda elem: elem["id"])
    return res, pokemon_dict[name]


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

def get_image(pokename, index=0, force_generate=False):
    data, others = get_pokemon(pokename, index)
    if data is None:
        return None, None

    filepath = FILE_CACHE_DIR + data['engname'] + (f"_{index}" if index > 0 else "") + ".png"
    if os.path.exists(filepath) and not force_generate:
        return filepath, others

    cover = Image.open(f"{COVER_DIR}{data['engname']}.png")
    cover = cover.resize((500, 500), Image.Resampling.BILINEAR)

    im = Image.new("RGBA", (1200, 4000))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1200, 4000), tc(data["type"][0]))
    draw.rounded_rectangle((16, 16, 1200 - 16, 4000 - 16), 20, tc2(data["type"][0]))
    draw.text((40, 24), data["name"], fill="#333333", font=title_style)
    draw.text((52 + len(data["name"] * 80), 64), data["jpname"] + " " + data["engname"], fill="#333333", font=subtitle_style)
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

    return im2, others


def generate_cache():
    j = 0
    for name, poke_datas in pokemon_dict.items():
        j += 1
        for i in range(len(poke_datas)):
            filepath = FILE_CACHE_DIR + name + (f"_{i}" if i > 0 else "") + ".png"
            try:
                get_image(name, i, True)[0].save(filepath)
                print(f"{j}-{i}")
            except Exception as e:
                print(f"err: {j}-{i}, {str(e)}")


def get_token(text, index):
    s = ""
    for i in range(index, len(text)):
        if text[i] == " ":
            return s, i+1
        s += text[i]
    return s, i+1


def parse_pokemon(text, index):
    result = {
        "pokemon": None,
        "item": [],
        "ability": [],
        "bps": [0, 0, 0, 0, 0, 0],
        "ivs": [31, 31, 31, 31, 31, 31],
        "high": 0, # 性格修正+
        "low": 0, # 性格修正-
        "tera": None,
        "mods": 0, # 能力变化
        "percent": 100 # 能力变化百分比
    }
    while True:
        token, index = get_token(text, index)
        if token == "":
            return result, index
        item = get_item(token)
        # parse item
        if item is not None:
            result["item"] = item
            continue
        # parse ability
        pass
        # parse mods
        reg = "([+|-][0-6])"
        grp = re.match(reg, token)
        if grp:
            result["mods"] = int(grp.group(0))
            continue
        # parse mods percent
        reg = "([0-9]+)%"
        grp = re.match(reg, token)
        if grp:
            result["percent"] = float(grp.group(1))
            continue
        
        flag = False
        # parse ivs
        tbl = ['ivhp', 'ivatk', 'ivdef', 'ivspa', 'ivspd', 'ivspe',
        'ivh', 'iva', 'ivb', 'ivc', 'ivd', 'ivs',
        'ivhp', '攻', 'ivdef', 'ivspa', 'ivspd', '速']
        for i, t in enumerate(tbl):
            if t in token.lower():
                t_re = token.lower().replace(t, "")
                result["ivs"][i % 6] = max(0, min(31, int(t_re)))
                flag = True
                break
        if flag:
            continue
        # parse bps
        tbl = ['hp', 'atk', 'def', 'spa', 'spd', 'spe',
        'h', 'a', 'b', 'c', 'd', 's',
        '生命', '攻击', '防御', '特攻', '特防', '速度']
        for i, t in enumerate(tbl):
            if t in token.lower():
                t_re = token.lower().replace(t, "")
                if "+" in t_re:
                    t_re = t_re.replace("+", "")
                    if i % 6 != 0:
                        result["high"] = i % 6
                elif "-" in t_re:
                    t_re = t_re.replace("-", "")
                    if i % 6 != 0:
                        result["low"] = i % 6
                result["bps"][i % 6] = max(0, min(252, int(t_re)))
                flag = True
                break
        if flag:
            continue
        # parse tera
        if "太晶" in token:
            tera_type, _ = get_type(token.replace("太晶", ""))
            if tera_type != None:
                result["tera"] = tera_type
                continue
        # parse pokemon
        for poke in pokemon_cn.values():
            for value in poke:
                s = f"{value}([0-9]?)"
                regex = re.match(s, token)
                if regex:
                    pmi = regex.group(1)
                    if pmi == "":
                        pmi = 0
                    else:
                        pmi = int(pmi) - 1
                    pokemon, _ = get_pokemon(poke[1], pmi)
                    result["pokemon"] = {
                        "name": pokemon["name"],
                        "stats": pokemon["stats"],
                        "type": pokemon["type"]
                    }
                    return result, index


def parse_move(text, index):
    result = {
        "name": "",
        "bp": 0,
        "category": 0, # 0 for physical, 1 for special, 2 for ...
        "type": "Normal"
    }
    token, index = get_token(text, index)
    # parse existed move
    for move in move_list.values():
        if token.lower() == move[1].lower() or token.lower() == move[2].lower() or token.lower() == move[3].lower():
            result["name"] = move[1]
            try:
                result["bp"] = int(move[6])
            except Exception:
                result["bp"] = 0
            result["type"], _ = get_type(move[4])
            result["category"] = ["物理", "特殊", "变化"].index(move[5])
            return result, index
    # parse unexisted move
    result["name"] = "自定义"
    # parse type
    for type_eng, type_v in type_tbl.items():
        if type_eng in token:
            token = token.replace(type_eng, "")
            result["type"] = type_eng
            break
        if type_v[0] in token:
            token = token.replace(type_v[0], "")
            result["type"] = type_eng
            break
        if type_v[3] in token:
            token = token.replace(type_v[3], "")
            result["type"] = type_eng
            break
    if "物理" in token:
        token = token.replace("物理", "")
        result["category"] = 0
    elif "特殊" in token:
        token = token.replace("特殊", "")
        result["category"] = 1
    elif "变化" in token:
        token = token.replace("变化", "")
        result["category"] = 2
    try:
        result["bp"] = int(token)
    except Exception:
        result["bp"] = 0
    result["name"] += f'（{type_tbl[result["type"]][0]} {["物理", "特殊", "变化"][result["category"]]} {result["bp"]} BP）'
    return result, index


def parse_other(text, index):
    res = [[], [], [], 1]
    while index != len(text):
        value, index = get_token(text, index)
        if 'hit' in value and value[-3:] == 'hit':
            res[3] = int(value[:-3])
            continue
        elif 'bp' in value and value[-2:] == 'bp':
            res[0].append(float(value[:-2]))
            continue
        elif value[-1] == 'p':
            res[1].append(float(value[:-1]))
            continue
        else:
            res[2].append(float(value))
            continue
    return res


def calculate_damage(text):
    
    def poke_round(val):
        if val % 1 > 0.5:
            return int(val + 1)
        return int(val)

    result = {
        "percent": [],
        "int": [],
        "range": [],
        "hp": 0
    }
    text = text.strip()
    attacker, index = parse_pokemon(text, 0)
    move, index = parse_move(text, index)
    target, index = parse_pokemon(text, index)
    mods = parse_other(text, index)
    print(mods)
    
    cat_addition = move["category"] * 2
    if cat_addition == 4:
        return result
    modifier = 1.0
    if attacker["high"] == 1 + cat_addition:
        modifier = 1.1
    elif attacker["low"] == 1 + cat_addition:
        modifier = 0.9
    attack = calc_stat(attacker["pokemon"]["stats"][1 + cat_addition], 50, attacker["ivs"][1 + cat_addition], attacker["bps"][1 + cat_addition], modifier)
    attack = poke_round(attack * attacker["percent"] / 100)
    stat_mod = attacker["mods"]
    if stat_mod >= 0:
        attack = int(attack * (2 + stat_mod) / 2)
    else:
        attack = int(attack * 2 / (2 - stat_mod))

    modifier = 1.0
    if target["high"] == 2 + cat_addition:
        modifier = 1.1
    elif target["low"] == 2 + cat_addition:
        modifier = 0.9
    defense = calc_stat(target["pokemon"]["stats"][2 + cat_addition], 50, target["ivs"][2 + cat_addition], target["bps"][2 + cat_addition], modifier)
    defense = poke_round(defense * target["percent"] / 100)
    stat_mod = target["mods"]
    if stat_mod >= 0:
        defense = int(defense * (2 + stat_mod) / 2)
    else:
        defense = int(defense * 2 / (2 - stat_mod))

    target_hp = calc_stat(target["pokemon"]["stats"][0], 50, target["ivs"][0], target["bps"][0], 1, True)
    result["hp"] = target_hp

    base_power = move["bp"]
    for mod in mods[0]:
        base_power *= int(mod * 4096) / 4096
    base_power = int(base_power)

    damage = int(int(((int((2 * 50) / 5 + 2) * base_power) * attack) / defense) / 50 + 2)
    attack_type = json.loads(json.dumps(attacker["pokemon"]["type"]))
    attack_type.append(attacker["tera"])

    if target["tera"] is not None:
        defend_type1 = target["tera"]
        defend_type2 = None
    else:
        defend_type1 = target["pokemon"]["type"][0]
        defend_type2 = None if len(target["pokemon"]["type"]) == 1 else target["pokemon"]["type"][1]

    for mod in mods[1]:
        damage *= int(mod * 4096) / 4096
    
    damage_tbl = []
    for i in range(16):
        new_dmg = int(damage * (85 + i) / 100)
        effectiveness = get_type_scale(defend_type1, defend_type2, move["type"])
        stab = 4096
        for a in attack_type:
            if a == move["type"]:
                stab += 2048
        new_dmg = new_dmg * stab / 4096
        new_dmg = int(poke_round(new_dmg) * effectiveness)
        for mod in mods[2]:
            new_dmg *= int(mod * 4096) / 4096
        new_dmg = poke_round(max(1, new_dmg))
        damage_tbl.append(new_dmg)

    result["int"] = damage_tbl
    if mods[3] != 1:
        result["range"] = [damage_tbl[0] * mods[3], damage_tbl[15] * mods[3]]
        for dmg in result["range"]:
            result["percent"].append(int(dmg * 1000 / target_hp) / 10)
    else:
        for dmg in result["int"]:
            result["percent"].append(int(dmg * 1000 / target_hp) / 10)

    return result
