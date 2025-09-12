import requests
import subprocess
import json
import tempfile
import os
import re
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

def js_to_json_via_node(js_obj_str):
    """
    通过 Node.js 子进程转换（需要安装 Node.js）
    """
    # 创建临时 JS 文件
    js_code = f"""
    const obj = {js_obj_str};
    console.log(JSON.stringify(obj));
    """
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_file = f.name
    
    try:
        # 执行 Node.js
        result = subprocess.run(['node', temp_file], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        
        json_str = result.stdout.strip()
        return json.loads(json_str)
    
    finally:
        # 清理临时文件
        os.unlink(temp_file)

battle_formats_data = requests.get('https://play.pokemonshowdown.com/data/formats-data.js').text
battle_formats_data = battle_formats_data[len('exports.BattleFormatsData = '):]
battle_formats_data = js_to_json_via_node(battle_formats_data)

def get_tier_score(key):
    natTier = battle_formats_data.get(key, {}).get('natDexTier', 'Illegal')
    score = 0
    if natTier == 'RU':
        score += 1
    elif natTier == 'RUBL':
        score += 2
    elif natTier == 'Uber':
        score += 3
    elif natTier == 'AG':
        score += 4
    elif natTier == 'UU':
        score += 5
    elif natTier == 'UUBL':
        score += 6
    elif natTier == 'OU':
        score += 7
    return score

@dataclass
class LadderEntry:
    """表示一个天梯条目的数据"""
    format_name: str
    elo: int
    gxe: Optional[float] = None
    glicko_rating: Optional[float] = None
    glicko_deviation: Optional[float] = None
    needs_more_games: bool = False


@dataclass
class PlayerRatings:
    """表示玩家的完整天梯数据"""
    username: str
    join_date: str
    official_ladder: List[LadderEntry]
    unofficial_ladder: List[LadderEntry]


def parse_pokemon_showdown_user_html(html_content: str) -> PlayerRatings:
    """
    解析 Pokémon Showdown 用户页面的 HTML 内容，提取天梯数据
    
    Args:
        html_content (str): HTML 页面内容
        
    Returns:
        PlayerRatings: 包含用户名、加入日期和天梯数据的对象
    """
    # 提取用户名
    username_match = re.search(r'<h1>(.+?)</h1>', html_content)
    username = username_match.group(1) if username_match else "Unknown"
    
    # 提取加入日期
    join_date_match = re.search(r'<em>Joined:</em> (.+?)</small>', html_content)
    join_date = join_date_match.group(1) if join_date_match else "Unknown"
    
    # 提取表格数据
    official_ladder = []
    unofficial_ladder = []
    
    # 找到所有的数据行（不包括表头）
    # 使用更精确的正则表达式匹配整个表格行
    data_rows = re.findall(r'<tr><td>([^<]+)</td><td[^>]*><strong>(\d+)</strong></td>(.*?)</tr>', html_content, re.DOTALL)
    
    # 确定哪些行属于 official 还是 unofficial
    # 通过查找表头来分割
    official_start = html_content.find('Official ladder')
    unofficial_start = html_content.find('Unofficial ladder')
    
    for format_name, elo, rest_of_row in data_rows:
        # 找到这个条目在 HTML 中的位置
        row_text = f'<tr><td>{format_name}</td>'
        row_position = html_content.find(row_text)
        
        # 根据位置判断属于哪个部分
        is_official = (row_position > official_start and 
                      (unofficial_start == -1 or row_position < unofficial_start))
        
        entry = _parse_data_row(format_name, elo, rest_of_row)
        if entry:
            if is_official:
                official_ladder.append(entry)
            else:
                unofficial_ladder.append(entry)
    
    return PlayerRatings(
        username=username,
        join_date=join_date,
        official_ladder=official_ladder,
        unofficial_ladder=unofficial_ladder
    )


def _parse_data_row(format_name: str, elo: str, rest_of_row: str) -> Optional[LadderEntry]:
    """
    解析提取出的数据行
    
    Args:
        format_name (str): 格式名称
        elo (str): Elo 分数字符串
        rest_of_row (str): 行的其余部分
        
    Returns:
        Optional[LadderEntry]: 解析出的天梯条目，如果解析失败返回 None
    """
    elo_int = int(elo)
    
    # 检查是否需要更多游戏
    if 'more games needed' in rest_of_row:
        return LadderEntry(
            format_name=format_name,
            elo=elo_int,
            needs_more_games=True
        )
    
    # 提取 GXE
    gxe = None
    gxe_match = re.search(r'>(\d+\.?\d*)<small>%</small>', rest_of_row)
    if gxe_match:
        gxe = float(gxe_match.group(1))
    
    # 提取 Glicko-1 评分和偏差
    glicko_rating = None
    glicko_deviation = None
    glicko_match = re.search(r'<em>(\d+)<small> &#177; (\d+)</small></em>', rest_of_row)
    if glicko_match:
        glicko_rating = float(glicko_match.group(1))
        glicko_deviation = float(glicko_match.group(2))
    
    return LadderEntry(
        format_name=format_name,
        elo=elo_int,
        gxe=gxe,
        glicko_rating=glicko_rating,
        glicko_deviation=glicko_deviation
    )

def format_player_ratings(ratings: PlayerRatings) -> str:
    """
    格式化输出玩家天梯数据
    
    Args:
        ratings (PlayerRatings): 玩家天梯数据
        
    Returns:
        str: 格式化后的字符串
    """
    result = []
    result.append(f"玩家: {ratings.username}")
    result.append(f"加入日期: {ratings.join_date}")
    result.append("")
    
    result.append("=== Official Ladder ===")
    for entry in ratings.official_ladder:
        result.append(f"{entry.format_name}: {entry.elo}")
        # if entry.needs_more_games:
        #     result.append(f"{entry.format_name}: Elo={entry.elo} (需要更多游戏)")
        # else:
        #     glicko_str = ""
        #     if entry.glicko_rating and entry.glicko_deviation:
        #         glicko_str = f", Glicko-1={entry.glicko_rating}±{entry.glicko_deviation}"
            
        #     gxe_str = f", GXE={entry.gxe}%" if entry.gxe else ""
        #     result.append(f"{entry.format_name}: Elo={entry.elo}{gxe_str}{glicko_str}")
    
    result.append("")
    result.append("=== Unofficial Ladder ===")
    for entry in ratings.unofficial_ladder:
        result.append(f"{entry.format_name}: {entry.elo}")
        # if entry.needs_more_games:
        #     result.append(f"{entry.format_name}: Elo={entry.elo} (需要更多游戏)")
        # else:
        #     glicko_str = ""
        #     if entry.glicko_rating and entry.glicko_deviation:
        #         glicko_str = f", Glicko-1={entry.glicko_rating}±{entry.glicko_deviation}"
            
        #     gxe_str = f", GXE={entry.gxe}%" if entry.gxe else ""
        #     result.append(f"{entry.format_name}: Elo={entry.elo}{gxe_str}{glicko_str}")
    
    return "\n".join(result)
