import requests
import subprocess
import json
import tempfile
import os

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