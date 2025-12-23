from PIL import Image, ImageDraw, ImageFont
from src.libraries.fishgame.data import FishItem, Fish, Backpack, get_skill, fish_skills
from src.libraries.fishgame.fishgame import FishPlayer, FishGame, talent_data
from src.libraries.fishgame.buildings import *
import math
from io import BytesIO
import aiohttp
import time


def get_item_type_text(item_type):
    if item_type == "tool":
        type_text = "工具"
    elif item_type == "rod":
        type_text = "渔具"
    elif item_type == "accessory":
        type_text = "配件"
    else:
        type_text = item_type
    return type_text


def wrap_text(text, font, max_width, draw):
    """
    手动文本换行函数
    
    参数:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度（像素）
        draw: ImageDraw对象，用于计算文本宽度
    
    返回:
        list: 换行后的文本行列表
    """
    lines = []
    
    # 首先按照 \n 分割文本
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph:  # 空行
            lines.append("")
            continue
            
        current_line = ""
        
        for char in paragraph:
            test_line = current_line + char
            line_width = draw.textlength(test_line, font=font)
            
            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:  # 如果当前行不为空，添加到结果中
                    lines.append(current_line)
                current_line = char
        
        if current_line:  # 添加段落的最后一行
            lines.append(current_line)
        
    return lines

# 获取稀有度对应的颜色
def get_rarity_color(rarity):
    if rarity == 1:
        return (255, 255, 255)  # 普通 - 白色
    elif rarity == 2:
        return (139, 233, 253)  # 稀有 - 蓝色
    elif rarity == 3:
        return (255, 121, 198)  # 史诗 - 紫色
    elif rarity == 4:
        return (241, 250, 140)  # 传说 - 黄色
    elif rarity == 5:
        return (255, 85, 85)    # 神话 - 红色
    return (255, 255, 255)      # 默认 - 白色

async def get_qq_avatar(qq_number: int, size: int = 160) -> Image.Image:
    """
    异步获取QQ用户头像并转换为PIL Image对象
    
    参数:
        qq_number (int): QQ号码
        size (int): 头像尺寸，可选值为 40, 100, 140, 640 等，默认为 640
    
    返回:
        PIL.Image.Image: 头像图片的PIL对象
    
    异常:
        ValueError: 当QQ号无效时抛出
        aiohttp.ClientError: 网络请求失败时抛出
        IOError: 图片处理失败时抛出
    """
    
    # 构建QQ头像URL
    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={qq_number}&s={size}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"获取头像失败，状态码: {response.status}")
                
                # 读取图片数据
                image_data = await response.read()
                
                # 转换为PIL Image对象
                img = Image.open(BytesIO(image_data))
                # 确保图片完全加载
                img.load()
                return img
    
    except aiohttp.ClientError as e:
        raise aiohttp.ClientError(f"网络请求错误: {e}")
    except IOError as e:
        raise IOError(f"图片处理错误: {e}")

def create_character_panel(player: FishPlayer, avatar_img: Image.Image, game: FishGame=None):
    # 创建一个800x800的图像 (增加高度以容纳图鉴)
    width, height = 800, 940
    image = Image.new("RGB", (width, height), (40, 42, 54))  # 深色背景
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 18)
    regular_font = ImageFont.truetype(font_path, 16)
    small_font = ImageFont.truetype(font_path, 14)
    
    # 绘制标题
    draw.text((width/2, 30), "钓鱼玩家信息", fill=(248, 248, 242), font=title_font, anchor="mm")
    
    # 绘制基本信息区域
    draw.rectangle([(50, 60), (width-50, 160)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    
    # 添加角色头像框
    avatar_size = 80
    draw.rectangle([(60, 70), (60+avatar_size, 70+avatar_size)], fill=(98, 114, 164), outline=(189, 147, 249), width=2)

    # bilt avatar
    if avatar_img:
        avatar_img = avatar_img.resize((avatar_size, avatar_size))
        image.paste(avatar_img, (60, 70))
        
    # 基本信息
    draw.text((150, 67), player.name, fill=(248, 248, 242), font=header_font)
    
    # fever期间显示fever_power，否则显示普通power
    if game and game.is_fever:
        draw.text((150, 92), f"渔力: {player.fever_power + game.big_pot.power_boost} (鱼群状态)", fill=(255, 215, 0), font=regular_font)
    else:
        draw.text((150, 92), f"渔力: {player.power + game.big_pot.power_boost}", fill=(248, 248, 242), font=regular_font)
    
    draw.text((150, 112), f"经验: {player.exp}/{player.get_target_exp(player.level)}", 
             fill=(248, 248, 242), font=regular_font)
    draw.text((150, 132), f"金币: {player.gold}", fill=(248, 248, 242), font=regular_font)
    
    # 绘制经验条
    # exp_bar_width = 200
    # exp_bar_height = 10
    # exp_ratio = min(character_data['exp'] / character_data['next_level_exp'], 1)
    # draw.rectangle([(250, 125), (250+exp_bar_width, 125+exp_bar_height)], fill=(68, 71, 90), outline=(98, 114, 164))
    # draw.rectangle([(250, 125), (250+exp_bar_width*exp_ratio, 125+exp_bar_height)], fill=(80, 250, 123))
    
    # 绘制称号
    draw.text((width-60, 75), f"Lv{player.level}", fill=(241, 250, 140), font=header_font, anchor="rt")
    draw.text((width-60, 100), f"总渔获: {len(player.fish_log)}条", fill=(248, 248, 242), font=regular_font, anchor="rt")
    draw.text((width-60, 125), f"积分: {player.score}", fill=(241, 250, 140), font=header_font, anchor="rt")
    
    # 装备区域
    draw.rectangle([(50, 170), (width-50, 420)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    draw.text((60, 180), "当前装备", fill=(189, 147, 249), font=header_font)
    
    # 定义装备栏位置
    equipment_slots = [
        {"name": "渔具", "x": 70, "y": 210, "item": player.equipment.rod},
        {"name": "工具", "x": 70, "y": 280, "item": player.equipment.tool},
        {"name": "配件", "x": 70, "y": 350, "item": player.equipment.accessory}
    ]
    
    # 绘制装备栏
    for slot in equipment_slots:
        # 装备名称
        draw.text((slot["x"], slot["y"]), f"{slot['name']}:", fill=(248, 248, 242), font=regular_font)
        
        item: FishItem = slot["item"]
        if item:
            # 获取稀有度对应的颜色
            rarity_color = get_rarity_color(item.rarity)
            # 绘制装备信息
            item_text = f"{item.name} (渔力+{item.power})"
            draw.text((slot["x"]+60, slot["y"]), item_text, fill=rarity_color, font=regular_font)
            
            # 显示装备描述
            desc = item.description
            wrapped_desc = wrap_text(desc, small_font, 400, draw)
            line_offset = 20
            if wrapped_desc:
                draw.text((slot["x"]+60, slot["y"]+line_offset), wrapped_desc[0], fill=(248, 248, 242), font=small_font)
                line_offset += 18
            # 显示技能
            xoffset = 0
            if getattr(item, 'skills', []):
                for sk in item.skills:
                    sk_obj = get_skill(sk['id'])
                    if sk_obj:
                        draw.text((slot["x"]+60+xoffset, slot["y"]+line_offset), f"{sk_obj.name} Lv{sk['level']}", fill=(189,147,249), font=small_font)
                        xoffset += 10 + draw.textlength(f"{sk_obj.name} Lv{sk['level']}", font=small_font)
        else:
            draw.text((slot["x"]+60, slot["y"]), "未装备", fill=(98, 114, 164), font=regular_font)
    
    # 若新增配件栏导致高度不足，向下平移图鉴起点
    pokedex_top = 430
    draw.rectangle([(50, pokedex_top), (width-50, height-50)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    draw.text((60, pokedex_top + 10), "图鉴", fill=(189, 147, 249), font=header_font)
    
    # 创建图鉴内容
    create_pokedex_content(draw, player, game, font_dict={
        'header': header_font,
        'regular': regular_font,
        'small': small_font
    }, y=pokedex_top)
    
    # 底部提示信息
    # draw.line([(50, height-50), (width-50, height-50)], fill=(98, 114, 164), width=2)
    draw.text((width/2, height-25), "捕鱼达人 v0.1", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image


def create_pokedex_content(draw, player: FishPlayer, game: FishGame, font_dict, y):
    """创建图鉴内容"""
    from src.libraries.fishgame.data import fish_data, weekday_topic
    import time
    
    # 获取字体
    header_font = font_dict['header']
    regular_font = font_dict['regular']
    small_font = font_dict['small']
    
    # 统计数据
    base_fish_count = 32  # 基础鱼数量
    group_fish_count = 7 * 12  # 鱼群模式鱼数量 (7天 * 12只)
    total_fish_count = base_fish_count + group_fish_count
    
    # 统计已捕获的鱼
    caught_fish_ids = player.fish_log.caught_set
    
    # 基础鱼 (ID 1-32)
    base_fish_caught = len([fish_id for fish_id in caught_fish_ids if 1 <= fish_id <= base_fish_count])
    
    # 鱼群鱼 (ID 33+)
    group_fish_caught = len([fish_id for fish_id in caught_fish_ids if fish_id > base_fish_count])
    
    total_caught = base_fish_caught + group_fish_caught
    
    # 显示完成率
    completion_rate = (total_caught / total_fish_count) * 100
    draw.text((60, y + 40), f"图鉴完成度: {total_caught}/{total_fish_count} ({completion_rate:.1f}%)", 
             fill=(241, 250, 140), font=regular_font)
    draw.text((60, y + 65), f"基础鱼: {base_fish_caught}/{base_fish_count}  鱼群鱼: {group_fish_caught}/{group_fish_count}", 
             fill=(248, 248, 242), font=small_font)
    
    # 获取今日鱼群主题
    current_weekday = time.localtime().tm_wday
    today_topic = weekday_topic[current_weekday] if current_weekday < len(weekday_topic) else ""
    
    # 绘制基础鱼图鉴 (4列显示)
    y_start = y + 90
    draw.text((60, y_start), "基础鱼:", fill=(189, 147, 249), font=header_font)
    
    # 显示基础鱼 (每排4个)
    for i in range(1, base_fish_count + 1):
        row = (i - 1) // 4
        col = (i - 1) % 4
        x = 60 + col * 170
        y = y_start + 30 + row * 25
        
        fish = fish_data.get(i)
        if fish:
            # 判断是否被捕获过
            is_caught = i in caught_fish_ids
            
            # 判断是否在当前群中被发现过
            group_fish_log = game.fish_log if game else None
            is_discovered = group_fish_log and group_fish_log.caught(fish.id) if group_fish_log else is_caught
            
            # 选择颜色
            if is_caught:
                # 已捕获：按稀有度显示颜色
                if fish.rarity == "R":
                    color = (139, 233, 253)  # 蓝色
                elif fish.rarity == "SR":
                    color = (255, 121, 198)  # 紫色
                elif fish.rarity == "SSR":
                    color = (241, 250, 140)  # 黄色
                else:
                    color = (248, 248, 242)  # 白色
            else:
                color = (128, 128, 128)
            
            # 显示鱼名或问号
            display_name = fish.name if is_discovered else "？？？"
            draw.text((x, y), f"{i:2d}. {display_name}", fill=color, font=small_font)
    
    # 绘制今日鱼群主题鱼图鉴
    if today_topic:
        group_y_start = y_start + 30 + ((base_fish_count - 1) // 4 + 1) * 25
        draw.text((60, group_y_start), f"今日鱼群主题: {today_topic}", fill=(189, 147, 249), font=header_font)
        
        # 获取今日主题的鱼
        today_theme_fish = []
        for fish_id, fish in fish_data.items():
            if fish_id > base_fish_count and today_topic in fish.spawn_at:
                today_theme_fish.append(fish)
        
        # 按ID排序
        today_theme_fish.sort(key=lambda f: f.id)
        
        # 显示今日主题鱼 (每排4个)
        for i, fish in enumerate(today_theme_fish):
            row = i // 4
            col = i % 4
            x = 60 + col * 170
            y = group_y_start + 30 + row * 25
            
            # 判断是否被捕获过
            is_caught = fish.id in caught_fish_ids
            
            # 判断是否在当前群中被发现过
            group_fish_log = game.fish_log if game else None
            is_discovered = group_fish_log and group_fish_log.caught(fish.id) if group_fish_log else is_caught
            
            # 选择颜色
            if is_caught:
                # 已捕获：按稀有度显示颜色
                if fish.rarity == "R":
                    color = (139, 233, 253)  # 蓝色
                elif fish.rarity == "SR":
                    color = (255, 121, 198)  # 紫色
                elif fish.rarity == "SSR":
                    color = (241, 250, 140)  # 黄色
                else:
                    color = (248, 248, 242)  # 白色
            else:
                color = (128, 128, 128)
            
            # 显示鱼名或问号
            display_name = fish.name if is_discovered else "？？？"
            draw.text((x, y), f"{fish.id}. {display_name}", fill=color, font=small_font)


def create_inventory_panel(items_data, page, max_page, equipped_item_ids, player: FishPlayer=None):
    width, height = 800, 600
    image = Image.new('RGB', (width, height), (40, 42, 54))  # 深色背景
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 18)
    regular_font = ImageFont.truetype(font_path, 16)
    small_font = ImageFont.truetype(font_path, 14)
    
    # 绘制标题和边框
    draw.text((width//2, 45), "背包", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.rectangle([(40, 10), (width-40, height-10)], outline=(98, 114, 164), width=2)
    
    # 绘制背包栏位
    slots_per_row = 2
    slot_width = (width - 100) // slots_per_row
    slot_height = 90
    padding = 15
    
    # 显示的物品数量（最多10个）
    display_items = items_data[:10]
    
    for i, bag_elem in enumerate(display_items):
        row = i // slots_per_row
        col = i % slots_per_row
        
        x1 = 50 + col * slot_width
        y1 = 70 + row * (slot_height + padding)
        x2 = x1 + slot_width - 10
        y2 = y1 + slot_height

        item: FishItem = bag_elem['item']
        count = bag_elem['count']
        
        # 获取物品信息
        item_id = item.id
        item_name = item.name + (f" ×{count}" if count > 1 else "")
        item_rarity = item.rarity
        item_desc = item.description
        if item.type == 'accessory':
            item_desc = ''
            skills = item.skills
            for skill in skills:
                skill_obj = fish_skills.get(skill['id'])
                if skill_obj:
                    item_desc += f"{skill_obj.name}({skill['level']}) "
        is_equipable = item.equipable
        # 配件特殊标记
        is_accessory = (item.type == 'accessory')
        
        # 绘制物品栏背景
        rarity_color = get_rarity_color(item_rarity)
        draw.rectangle([(x1, y1), (x2, y2)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
        
        # 左侧小图标区域
        icon_size = 50
        draw.rectangle([(x1+10, y1+15), (x1+10+icon_size, y1+15+icon_size)], 
                      fill=(50, 53, 70), outline=rarity_color)
        
        # 物品编号
        draw.text((x1+35, y1+40), f"{item_id}", fill=(248, 248, 242), font=regular_font, anchor="mm")
        
        # 物品名称
        name_x = x1 + icon_size + 20
        draw.text((name_x, y1+12), item_name, fill=rarity_color, font=header_font)
        
        current_y = y1+12+22
        
        # 装备信息（如果可装备）
        if is_equipable:
            power = item.power
            item_type = item.type
            
            # 装备类型中文转换
            type_text = get_item_type_text(item_type)

            if item.id in equipped_item_ids:
                equip_text = f"[已装备] 类型: {type_text} | 渔力: {power}"
                draw.text((name_x, current_y), equip_text, fill=(250, 250, 70), font=small_font)
            else:
                equip_text = f"[可装备] 类型: {type_text} | 渔力: {power}"
                draw.text((name_x, current_y), equip_text, fill=(80, 250, 123), font=small_font)
            current_y += 18
            # 显示配件技能
            if is_accessory and player is not None:
                meta = player.data.get('accessory_meta', {}).get(str(item.id), {})
                for sk in meta.get('skills', [])[:3]:
                    sk_obj = get_skill(sk.get('id'))
                    if not sk_obj:
                        continue
                    sk_level = sk.get('level')
                    draw.text((name_x, current_y), f"{sk_obj.name} Lv{sk_level}", fill=(189,147,249), font=small_font)
                    current_y += 16
        
        # 物品描述（处理换行）
        desc_width = x2 - name_x - 10  # 描述文本可用宽度
        desc_index = 0
        while desc_index < len(item_desc):
            if draw.textlength(item_desc[:desc_index], font=small_font) < desc_width:
                desc_index += 1
                continue
            desc_index -= 1
            draw.text((name_x, current_y), item_desc[:desc_index], fill=(248, 248, 242), font=small_font)
            current_y += 18
            item_desc = item_desc[desc_index:]
            desc_index = 0

        draw.text((name_x, current_y), item_desc, fill=(248, 248, 242), font=small_font)
    
    # 容量信息
    draw.text((width-50, 45), f"第 {page} 页 / 共 {max_page} 页", 
             fill=(248, 248, 242), font=regular_font, anchor="rt")

    # 容量信息
    draw.text((50, 45), f"Usage：使用 <道具编号>", 
             fill=(124, 124, 124), font=regular_font, anchor="lt")
    
    return image

def create_craft_panel(craftable_items: list[FishItem], player_bag: Backpack, player: FishPlayer = None, page: int = 1, total_pages: int = 1):
    """创建合成面板"""
    # 基本设置
    padding = 20
    item_width = 300
    item_height = 360
    items_per_row = 4
    
    # 计算面板尺寸
    items_count = len(craftable_items)
    # rows = math.ceil(items_count / items_per_row)
    # 固定显示 3 行的高度，或者根据实际行数（如果不足一页）
    # 但为了美观，通常固定宽度
    width = padding + (item_width + padding) * items_per_row
    # height = 100 + (item_height + padding) * rows + 80
    # 固定高度以容纳 3 行
    height = 100 + (item_height + padding) * 3 + 80
    
    # 创建图像和绘图对象
    image = Image.new('RGB', (width, height), color=(40, 42, 54))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 32)
    header_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 18)
    regular_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 16)
    small_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 14)
    tiny_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 12)
    
    # 绘制标题
    draw.text((width/2, 40), f"合成工坊 (第 {page}/{total_pages} 页)", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.line([(padding, 80), (width-padding, 80)], fill=(98, 114, 164), width=2)
    
    # 绘制合成物品
    for i, item in enumerate(craftable_items):
        row = i // items_per_row
        col = i % items_per_row
        
        x = padding + col * (item_width + padding)
        y = 100 + row * (item_height + padding)
        
        # 物品背景框
        rarity_color = get_rarity_color(item.rarity)
        draw.rectangle([(x, y), (x + item_width, y + item_height)], 
                      fill=(68, 71, 90), outline=rarity_color, width=2)
        
        # 物品图标区域
        icon_size = 60
        draw.rectangle([(x + 10, y + 10), (x + 10 + icon_size, y + 10 + icon_size)], 
                      fill=(50, 53, 70), outline=rarity_color)
        draw.text((x + 10 + icon_size/2, y + 10 + icon_size/2), 
                 str(item.id), fill=rarity_color, font=regular_font, anchor="mm")
        
        # 物品名称
        draw.text((x + 80, y + 15), item.name, fill=rarity_color, font=header_font)
        
        # 装备信息（如果可装备）
        current_text_y = y + 35
        if item.equipable:
            power = item.power
            item_type = item.type
            
            # 装备类型中文转换
            type_text = get_item_type_text(item_type)

            equip_text = f"类型: {type_text} | 渔力: +{power}"
            draw.text((x + 80, current_text_y), equip_text, fill=(80, 250, 123), font=small_font)
            current_text_y += 20
            
            # 显示技能
            if getattr(item, 'skills', []):
                skill_prefix = "技能: "
                current_line_text = skill_prefix
                max_skill_width = item_width - 90
                
                for sk in item.skills:
                    sk_obj = get_skill(sk['id'])
                    if sk_obj:
                        skill_part = f"{sk_obj.name} Lv{sk['level']} "
                        
                        # 检查是否需要换行
                        if draw.textlength(current_line_text + skill_part, font=small_font) > max_skill_width:
                            # 如果当前行仅有前缀，则不得不追加（避免死循环或空行）
                            if current_line_text == skill_prefix:
                                current_line_text += skill_part
                            else:
                                # 绘制当前行并换行
                                draw.text((x + 80, current_text_y), current_line_text, fill=(189, 147, 249), font=small_font)
                                current_text_y += 18
                                current_line_text = skill_part
                        else:
                            current_line_text += skill_part
                
                # 绘制最后一行
                if current_line_text:
                    draw.text((x + 80, current_text_y), current_line_text, fill=(189, 147, 249), font=small_font)
                    current_text_y += 20
        
        # 物品描述（使用手动换行函数）
        max_desc_width = item_width - 90
        wrapped_desc = wrap_text(item.description, small_font, max_desc_width, draw)
        
        # 最多显示2行描述
        for j, line in enumerate(wrapped_desc[:2]):
            draw.text((x + 80, current_text_y + j * 18), line, 
                     fill=(248, 248, 242), font=small_font)
        
        # 如果描述被截断，添加省略号
        if len(wrapped_desc) > 2:
            last_line = wrapped_desc[1]
            last_line_width = draw.textlength(last_line, font=small_font)
            ellipsis_width = draw.textlength("...", font=small_font)
            
            if last_line_width + ellipsis_width > max_desc_width:
                # 需要截断最后一行并添加省略号
                truncated_line = last_line
                while draw.textlength(truncated_line + "...", font=small_font) > max_desc_width:
                    truncated_line = truncated_line[:-1]
                
                draw.text((x + 80, current_text_y + 18), 
                         truncated_line + "...", fill=(248, 248, 242), font=small_font)
            else:
                # 直接添加省略号
                draw.text((x + 80, current_text_y + 18), 
                         last_line + "...", fill=(248, 248, 242), font=small_font)
        
        # 合成材料标题
        material_title_y = current_text_y + (40 if len(wrapped_desc) <= 2 else 60)
        draw.text((x + 10, material_title_y), "合成材料:", fill=(189, 147, 249), font=regular_font)
        
        # 统计所需材料
        material_requirements = {}
        for material_id in item.craftby:
            material_requirements[material_id] = material_requirements.get(material_id, 0) + 1
        
        # 显示材料需求
        material_y = material_title_y + 25
        for material_id, required_count in material_requirements.items():
            material_item = FishItem.get(str(material_id))
            if material_item:
                current_count = player_bag.get_item_count(material_id)
                
                # 材料名称和数量
                material_text = f"{material_item.name}"
                count_text = f"{current_count}/{required_count}"
                
                # 根据是否足够选择颜色
                if current_count >= required_count:
                    count_color = (80, 250, 123)  # 绿色 - 足够
                else:
                    count_color = (255, 85, 85)   # 红色 - 不足
                
                draw.text((x + 15, material_y), material_text, 
                         fill=(248, 248, 242), font=small_font)
                draw.text((x + item_width - 15, material_y), count_text, 
                         fill=count_color, font=small_font, anchor="rt")
                
                material_y += 20
                
                # 如果材料太多，显示省略号
                if material_y - y > 290:
                    draw.text((x + 15, material_y), "...", 
                             fill=(248, 248, 242), font=small_font)
                    break

        craft_score_cost = item.craft_score_cost
        if item.id == 14:
            craft_score_cost *= 2 ** player.master_ball_crafts
        
        # 显示积分消耗（如果需要）
        if item.craft_score_cost > 0:
            # 添加一些间隔
            material_y += 10
            
            # 积分消耗标题
            draw.text((x + 10, material_y), "积分消耗:", fill=(255, 184, 108), font=regular_font)
            material_y += 25
            
            # 显示积分消耗和玩家当前积分
            score_text = f"需要积分: {craft_score_cost}"
            current_score_text = f"当前: {player.score}"
            
            # 根据积分是否充足选择颜色
            if player.score >= craft_score_cost:
                score_color = (80, 250, 123)  # 绿色 - 足够
            else:
                score_color = (255, 85, 85)   # 红色 - 不足
            
            draw.text((x + 15, material_y), score_text, 
                     fill=(248, 248, 242), font=small_font)
            draw.text((x + item_width - 15, material_y), current_score_text, 
                     fill=score_color, font=small_font, anchor="rt")
    
    # 底部信息
    draw.line([(padding, height-60), (width-padding, height-60)], fill=(98, 114, 164), width=2)
    draw.text((width/2, height-35), 
             "Usage: 合成 <物品编号> | 合成#<页码>", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image

def create_gacha_panel(items_data):
    # 计算所需的面板尺寸
    items_count = len(items_data)
    items_per_row = 4  # 每行最多4个物品
    rows = math.ceil(items_count / items_per_row)
    
    # 设置面板大小
    padding = 20
    item_width = 170
    item_height = 210
    
    width = padding + (item_width + padding) * min(items_count, items_per_row)
    height = 150 + (item_height + padding) * rows + 50  # 标题高度 + 物品高度 + 底部信息
    
    # 创建画布
    image = Image.new("RGB", (width, height), (40, 42, 54))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 32)
    header_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 18)
    regular_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 16)
    small_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 14)
    tiny_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 12)
    
    # 绘制标题
    draw.text((width/2, 40), "抽卡结果", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.line([(padding, 80), (width-padding, 80)], fill=(98, 114, 164), width=2)
    
    # 绘制抽卡结果项目
    for i, item in enumerate(items_data):
        row = i // items_per_row
        col = i % items_per_row
        
        x = padding + col * (item_width + padding)
        y = 100 + row * (item_height + padding)
        
        # 获取物品信息
        item_id = item.get("id", "")
        item_name = item.get("name", "未知")
        item_rarity = item.get("rarity", 0)  # 积分项没有稀有度
        item_desc = item.get("description", "")
        is_equipable = item.get("equipable", False)
        item_count = item.get("count", 1)  # 物品数量，默认为1
        is_score = item.get("is_score", False)  # 是否为积分奖励
        
        # 绘制项目背景
        rarity_color = get_rarity_color(item_rarity) if not is_score else (255, 184, 108)  # 积分用橙色
        draw.rectangle([(x, y), (x+item_width, y+item_height)], 
                      fill=(68, 71, 90), outline=rarity_color, width=3)
        
        # 随机ID区域或者积分标识
        if is_score:
            # 如果是积分奖励
            icon_size = 60
            icon_x = x + (item_width - icon_size) // 2
            icon_y = y + 30
            # 绘制一个圆形或图标表示积分
            draw.ellipse([(icon_x, icon_y), (icon_x+icon_size, icon_y+icon_size)], 
                        fill=(255, 184, 108), outline=(255, 184, 108))
            
            # 修复：使用更小的字体来防止积分文字重叠
            draw.text((icon_x+icon_size//2, icon_y+icon_size//2), "积分", 
                     fill=(40, 42, 54), font=tiny_font, anchor="mm")
        else:
            # 普通物品
            icon_size = 60
            icon_x = x + (item_width - icon_size) // 2
            icon_y = y + 30
            # 绘制一个方形图标
            draw.rectangle([(icon_x, icon_y), (icon_x+icon_size, icon_y+icon_size)], 
                          fill=(50, 53, 70), outline=rarity_color)
            
            # 物品ID
            if item_id:
                draw.text((icon_x+icon_size//2, icon_y+icon_size//2), f"{item_id}", 
                         fill=(248, 248, 242), font=header_font, anchor="mm")
        
        # 物品名称
        name_y = y + 110
        display_name = item_name
        if item_count > 1 and not is_score:
            display_name = f"{item_name} ×{item_count}"
        draw.text((x+item_width//2, name_y), display_name, 
                 fill=rarity_color, font=header_font, anchor="mm")
        
        # 装备信息（如果可装备）
        if is_equipable:
            power = item['power']
            item_type = item['type']
            
            # 装备类型中文转换
            type_text = get_item_type_text(item_type)
                
            equip_text = f"{type_text} | 渔力+{power}"
            draw.text((x+item_width//2, name_y+25), equip_text, 
                     fill=(80, 250, 123), font=small_font, anchor="mm")
        
        # 物品描述（使用自定义换行函数）
        desc_y = name_y + (45 if is_equipable else 25)
        
        # 设置最大文本宽度略小于项目宽度
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width, draw)
        
        # 最多显示3行描述
        for j, line in enumerate(wrapped_text[:3]):
            draw.text((x+item_width//2, desc_y+j*20), line, 
                     fill=(248, 248, 242), font=small_font, anchor="mm")
            
        # 如果描述被截断，添加省略号
        if len(wrapped_text) > 3:
            last_line = wrapped_text[2]
            # 检查最后一行是否需要添加省略号
            if j == 2:  # 到达了第三行
                # 确保省略号不会导致文本溢出
                last_line_width = draw.textlength(last_line, font=small_font)
                ellipsis_width = draw.textlength("...", font=small_font)
                
                if last_line_width + ellipsis_width > max_text_width:
                    # 需要截断最后一行并添加省略号
                    truncated_line = last_line
                    while draw.textlength(truncated_line + "...", font=small_font) > max_text_width:
                        truncated_line = truncated_line[:-1]
                    
                    draw.text((x+item_width//2, desc_y+2*20), 
                             truncated_line + "...", fill=(248, 248, 242), 
                             font=small_font, anchor="mm")
                else:
                    # 直接添加省略号
                    draw.text((x+item_width//2, desc_y+2*20), 
                             last_line + "...", fill=(248, 248, 242), 
                             font=small_font, anchor="mm")
    
    # 底部信息
    draw.line([(padding, height-50), (width-padding, height-50)], fill=(98, 114, 164), width=2)
    
    # 计算总物品数量
    total_items = sum(item.get("count", 1) for item in items_data if not item.get("is_score", False))
    unique_items = len([item for item in items_data if not item.get("is_score", False)])
    
    if total_items != unique_items:
        # 如果有堆叠显示
        draw.text((width/2, height-25), 
                 f"获得 {total_items} 件物品 ({unique_items} 种)", 
                 fill=(98, 114, 164), font=regular_font, anchor="mm")
    else:
        # 普通显示
        draw.text((width/2, height-25), 
                 f"抽取了 {items_count} 件物品", 
                 fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image

def create_shop_panel(shop_items: list[FishItem]):
    # 基本设置
    padding = 20
    item_width = 200
    item_height = 220
    items_per_row = 4  # 每行最多4个商品
    
    # 计算面板尺寸
    items_count = len(shop_items)
    rows = math.ceil(items_count / items_per_row)
    width = padding + (item_width + padding) * min(items_count, items_per_row)
    height = 100 + (item_height + padding) * rows + 80  # 标题100px, 底部80px
    
    # 创建图像和绘图对象
    image = Image.new('RGB', (width, height), color=(40, 42, 54))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 32)
    header_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 18)
    price_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 20)
    regular_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 16)
    small_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 14)
    tiny_font = ImageFont.truetype("src/static/poke/LXGWWenKai-Regular.ttf", 12)
    
    # 绘制标题
    draw.text((width/2, 40), "金币商城", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.line([(padding, 80), (width-padding, 80)], fill=(98, 114, 164), width=2)
    
    # 绘制商品
    for i, item in enumerate(shop_items):
        row = i // items_per_row
        col = i % items_per_row
        
        x = padding + col * (item_width + padding)
        y = 100 + row * (item_height + padding)
        
        # 获取商品信息
        item_id = item.id
        item_name = item.name
        item_rarity = item.rarity
        item_desc = item.description
        item_price = item.price
        # item_stock = item.stock
        is_equipable = item.equipable
        # is_limited = item_stock != "无限"
        
        # 绘制商品背景
        rarity_color = get_rarity_color(item_rarity)
        draw.rectangle([(x, y), (x+item_width, y+item_height)], 
                      fill=(68, 71, 90), outline=rarity_color, width=3)
        
        # 商品图标
        icon_size = 60
        icon_x = x + (item_width - icon_size) // 2
        icon_y = y + 20
        
        # 绘制一个方形图标
        draw.rectangle([(icon_x, icon_y), (icon_x+icon_size, icon_y+icon_size)], 
                      fill=(50, 53, 70), outline=rarity_color)
        
        # 物品ID
        if item_id:
            draw.text((icon_x+icon_size//2, icon_y+icon_size//2), f"{item_id}", 
                     fill=(248, 248, 242), font=header_font, anchor="mm")
        
        # 物品名称
        name_y = y + 100
        draw.text((x+item_width//2, name_y), item_name, 
                 fill=rarity_color, font=header_font, anchor="mm")
        
        # 装备信息（如果可装备）
        if is_equipable:
            power = item.power
            item_type = item.type
            
            # 装备类型中文转换
            type_text = get_item_type_text(item_type)
                
            equip_text = f"{type_text} | 渔力+{power}"
            draw.text((x+item_width//2, name_y+20), equip_text, 
                     fill=(80, 250, 123), font=small_font, anchor="mm")
        
        # 物品描述
        desc_y = name_y + (40 if is_equipable else 20)
        
        # 设置最大文本宽度略小于项目宽度
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width, draw)
        
        # 最多显示2行描述（商店里需要给价格留位置）
        for j, line in enumerate(wrapped_text[:3]):
            draw.text((x+item_width//2, desc_y+j*20), line, 
                     fill=(248, 248, 242), font=small_font, anchor="mm")
            
        # 如果描述被截断，添加省略号
        if len(wrapped_text) > 3:
            last_line = wrapped_text[1]
            # 检查最后一行是否需要添加省略号
            if j == 1:  # 到达了第二行
                # 确保省略号不会导致文本溢出
                last_line_width = draw.textlength(last_line, font=small_font)
                ellipsis_width = draw.textlength("...", font=small_font)
                
                if last_line_width + ellipsis_width > max_text_width:
                    # 需要截断最后一行并添加省略号
                    truncated_line = last_line
                    while draw.textlength(truncated_line + "...", font=small_font) > max_text_width:
                        truncated_line = truncated_line[:-1]
                    
                    draw.text((x+item_width//2, desc_y+1*20), 
                             truncated_line + "...", fill=(248, 248, 242), 
                             font=small_font, anchor="mm")
                else:
                    # 直接添加省略号
                    draw.text((x+item_width//2, desc_y+1*20), 
                             last_line + "...", fill=(248, 248, 242), 
                             font=small_font, anchor="mm")
        
        # 绘制价格和库存信息
        price_y = y + item_height - 45
        
        # 价格区域
        price_bg_height = 30
        price_bg_y = price_y - 5
        draw.rectangle([(x+10, price_bg_y), (x+item_width-10, price_bg_y+price_bg_height)], 
                      fill=(60, 62, 80), outline=None)
        
        # 价格文字
        price_icon_color = (255, 184, 108)  # 积分颜色 - 橙色
        price_text = f"{item_price}"
        
        # 绘制积分图标
        draw.ellipse([(x+20, price_y), (x+20+20, price_y+20)], 
                    fill=price_icon_color)
        draw.text((x+20+10, price_y+10), "G", 
                 fill=(40, 42, 54), font=tiny_font, anchor="mm")
        
        # 绘制价格
        draw.text((x+50, price_y+10), price_text, 
                 fill=price_icon_color, font=price_font, anchor="lm")
        
        # 绘制库存信息（如果有限制）
        # if is_limited:
        #     stock_text = f"库存: {item_stock}"
        #     draw.text((x+item_width-20, price_y+10), stock_text, 
        #              fill=(248, 248, 242), font=small_font, anchor="rm")
    
    # 底部信息
    draw.line([(padding, height-60), (width-padding, height-60)], fill=(98, 114, 164), width=2)
    draw.text((width/2, height-35), 
             "Usage: 商店购买 <商品编号>", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    # 积分余额显示
    # balance_text = "当前金币: 150"
    # draw.text((width-padding, height-35), 
    #          balance_text, fill=(255, 184, 108), 
    #          font=regular_font, anchor="rm")
    
    return image


def create_buildings_panel(game: FishGame):
    """创建建筑面板"""
    # 初始化建筑
    game.init_buildings()
    
    # 获取所有建筑
    buildings: list[BuildingBase] = [
        game.big_pot,
        game.fish_factory,
        game.building_center,
        game.fish_lab,
        game.ice_hole,
        game.mystic_shop,
        game.seven_statue,
        game.forge_shop,
        game.port
    ]
    
    # 基本设置
    padding = 25
    building_width = 475  # 提升25%: 380 * 1.25 = 475
    building_height = 400  # 提升25%: 280 * 1.25 = 350
    buildings_per_row = 3
    
    # 计算面板尺寸
    rows = len(buildings) // buildings_per_row
    width = padding + (building_width + padding) * buildings_per_row
    height = 100 + (building_height + padding) * rows + 80
    
    # 创建图像和绘图对象
    image = Image.new('RGB', (width, height), color=(40, 42, 54))
    draw = ImageDraw.Draw(image)
    
    # 加载字体 (提升25%)
    font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
    title_font = ImageFont.truetype(font_path, 40)  # 32 * 1.25 = 40
    header_font = ImageFont.truetype(font_path, 23)  # 18 * 1.25 = 22.5 ≈ 23
    regular_font = ImageFont.truetype(font_path, 20)  # 16 * 1.25 = 20
    small_font = ImageFont.truetype(font_path, 18)  # 14 * 1.25 = 17.5 ≈ 18
    tiny_font = ImageFont.truetype(font_path, 15)  # 12 * 1.25 = 15
    
    # 绘制标题
    draw.text((width/2, 40), "建筑管理", fill=(248, 248, 242), font=title_font, anchor="mm")
    
    # 绘制建筑卡片
    for i, building in enumerate(buildings):
        row = i // buildings_per_row
        col = i % buildings_per_row
        
        x = padding + col * (building_width + padding)
        y = 80 + row * (building_height + padding)
        
        # 建筑卡片背景
        card_color = (68, 71, 90)
        if building.level >= building.max_level:
            card_color = (90, 90, 68)  # 已满级，金色背景
        elif building.can_upgrade():
            card_color = (68, 90, 71)  # 可升级，绿色背景
        
        draw.rectangle([(x, y), (x + building_width, y + building_height)], 
                      fill=card_color, outline=(98, 114, 164), width=2)
        
        # 建筑名称和等级
        level_text = f"Lv.{building.level}"
        if building.level >= building.max_level:
            level_text += " (MAX)"
        
        draw.text((x + 19, y + 19), building.name, fill=(189, 147, 249), font=header_font)  # 调整间距
        draw.text((x + building_width - 19, y + 19), level_text, 
                 fill=(241, 250, 140), font=header_font, anchor="rt")
        
        # 建筑描述
        description = building.description
        y_offset = y + 50  # 调整间距
        
        # 处理描述换行显示
        lines = wrap_text(description, tiny_font, building_width - 38, draw)  # 调整文本宽度
        for line in lines[:4]:  # 最多显示3行
            draw.text((x + 19, y_offset), line, fill=(150, 150, 150), font=tiny_font)
            y_offset += 16  # 调整行间距
        
        y_offset += 10  # 描述和效果之间的间距
        
        # 当前等级效果
        current_desc = ""
        if building.level > 0:
            current_desc = building.level_effect_desc(building.level)
        else:
            current_desc = "未建造"
        
        # 处理当前效果换行
        current_lines = wrap_text(f"当前效果：{current_desc}", small_font, building_width - 38, draw)
        for line in current_lines:
            draw.text((x + 19, y_offset), line, fill=(248, 248, 242), font=small_font)
            y_offset += 20  # 调整行间距
        
        # 下一级效果
        if building.level < building.max_level:
            next_desc = building.level_effect_desc(building.level + 1)
            next_lines = wrap_text(f"下级效果：{next_desc}", small_font, building_width - 38, draw)
            for line in next_lines:
                draw.text((x + 19, y_offset), line, fill=(150, 200, 255), font=small_font)
                y_offset += 20  # 调整行间距
        
        y_offset += 6  # 效果和条件之间的间距
        
        # 根据剩余空间判断是否显示详细信息
        remaining_space = y + building_height - y_offset - 30
        
        if building.level < building.max_level:
            # 前置建筑要求
            prerequisites = building.get_level_prerequisites(building.level + 1)
            if prerequisites and remaining_space > 60:  # 调整空间判断
                draw.text((x + 19, y_offset), "前置条件:", fill=(255, 184, 108), font=small_font)
                y_offset += 20  # 调整间距
                
                for prereq_building, required_level in prerequisites.items():
                    # 获取对应建筑的当前等级
                    current_prereq_level = 0
                    prereq_building_name = ""
                    if prereq_building == 'big_pot':
                        current_prereq_level = game.big_pot.level
                        prereq_building_name = "大锅"
                    elif prereq_building == 'ice_hole':
                        current_prereq_level = game.ice_hole.level
                        prereq_building_name = "冰洞"
                    elif prereq_building == 'mystic_shop':
                        current_prereq_level = game.mystic_shop.level
                        prereq_building_name = "神秘商店"
                    elif prereq_building == 'forge_shop':
                        current_prereq_level = game.forge_shop.level
                        prereq_building_name = "熔炉工坊"
                    
                    status_color = (80, 250, 123) if current_prereq_level >= required_level else (255, 85, 85)
                    prereq_text = f"{prereq_building_name}: Lv.{current_prereq_level}/{required_level}"
                    draw.text((x + 31, y_offset), prereq_text, 
                             fill=status_color, font=tiny_font)
                    y_offset += 18  # 调整行间距
                
                y_offset += 6  # 前置条件和材料之间的间距
            
            # 材料需求状态
            if y_offset + 25 < y + building_height - 38:  # 确保有足够空间显示材料
                materials_status = building.get_materials_status()
                
                draw.text((x + 19, y_offset), "升级材料:", fill=(189, 147, 249), font=small_font)
                y_offset += 20  # 调整间距
                
                for request, current_count in materials_status:
                    if y_offset + 16 > y + building_height - 19:  # 防止文本溢出
                        draw.text((x + 31, y_offset), "...", fill=(150, 150, 150), font=tiny_font)
                        break
                    
                    status_color = (80, 250, 123) if current_count >= request.count else (255, 85, 85)
                    material_text = f"{request.desc}: {current_count}/{request.count}"
                    draw.text((x + 31, y_offset), material_text, 
                             fill=status_color, font=tiny_font)
                    y_offset += 18  # 调整行间距
        else:
            draw.text((x + 19, y_offset), "建筑已达到最高等级", 
                     fill=(241, 250, 140), font=small_font)
    
    # 底部提示信息
    draw.text((width/2, height-31), "Usage: 建筑 <建筑名称> <材料编号> 或者 建筑 <建筑名称> 升级", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image

def create_oversea_panel(game: FishGame):
    """创建港口讨伐面板"""
    from src.libraries.fishgame.oversea import OverseaBattle, battle_buffs
    
    battle = game.oversea_battle
    if not battle:
        # 如果没有战斗，显示空面板或提示
        width, height = 600, 400
        image = Image.new('RGB', (width, height), color=(40, 42, 54))
        draw = ImageDraw.Draw(image)
        font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
        title_font = ImageFont.truetype(font_path, 32)
        draw.text((width/2, height/2), "当前海域风平浪静", fill=(248, 248, 242), font=title_font, anchor="mm")
        return image

    # print(battle.data)

    # 基本设置
    width = 800
    height = 1000
    padding = 20
    
    image = Image.new('RGB', (width, height), color=(40, 42, 54))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 24)
    regular_font = ImageFont.truetype(font_path, 18)
    small_font = ImageFont.truetype(font_path, 16)
    
    # 1. 标题区域
    draw.text((width/2, 40), f"海怪讨伐 - {battle.data['monster_name']}", fill=(255, 85, 85), font=title_font, anchor="mm")
    draw.text((width/2, 80), f"难度: {'★' * battle.data['difficulty']}", fill=(241, 250, 140), font=header_font, anchor="mm")
    
    # 2. 怪物 Buff 区域
    y_offset = 120
    draw.text((padding, y_offset), "环境与状态:", fill=(189, 147, 249), font=header_font)
    y_offset += 35
    
    # 环境 Buff
    env_id = battle.data.get('environment_buff', 0)
    if env_id > 0:
        env_info = next((b for b in battle_buffs['environment'] if b['id'] == env_id), None)
        if env_info:
            draw.text((padding + 20, y_offset), f"【环境】{env_info['name']}: {env_info['description']}", fill=(139, 233, 253), font=regular_font)
            y_offset += 25
            
    # 怪物 Buff
    for buff in battle.data.get('monster_buffs', []):
        buff_info = next((b for b in battle_buffs['monster_negative'] if b['id'] == buff['id']), None)
        if buff_info:
            desc = buff_info['description'].replace('{level}', str(buff['level'])).replace('{level * 10}', str(buff['level'] * 10)).replace('{level * 5}', str(buff['level'] * 5)).replace('{level * 20}', str(buff['level'] * 20))
            draw.text((padding + 20, y_offset), f"【特性】{buff_info['name']} Lv.{buff['level']}: {desc}", fill=(255, 121, 198), font=regular_font)
            y_offset += 25
            
    # 奖励 Buff
    for bid in battle.data.get('bonus_buffs', []):
        buff_info = next((b for b in battle_buffs['bonus'] if b['id'] == bid), None)
        if buff_info:
            draw.text((padding + 20, y_offset), f"【奖励】{buff_info['name']}: {buff_info['description']}", fill=(241, 250, 140), font=regular_font)
            y_offset += 25
            
    y_offset += 10
    draw.line([(padding, y_offset), (width-padding, y_offset)], fill=(98, 114, 164), width=2)
    y_offset += 20
    
    # 3. 战斗状态区域
    status_text = {
        "idle": "等待组队中...",
        "fighting": "战斗进行中",
        "success": "讨伐成功",
        "fail": "讨伐失败"
    }.get(battle.data['status'], "未知状态")
    
    draw.text((padding, y_offset), f"当前状态: {status_text}", fill=(80, 250, 123), font=header_font)
    
    # 船体耐久
    ship_hp = battle.data['ship_hp']
    ship_max = battle.data['ship_max_hp']
    ship_pct = ship_hp / ship_max if ship_max > 0 else 0
    draw.text((padding + 540, y_offset), f"船体耐久: {ship_hp}/{ship_max}", fill=(248, 248, 242), font=regular_font)
    
    y_offset += 40
    
    # 怪物血量 (隐藏数值，显示进度条或累计伤害)
    monster_hp = battle.data['monster_hp']
    monster_max = battle.data['monster_max_hp']
    damage_dealt = monster_max - monster_hp
    hp_pct = monster_hp / monster_max if monster_max > 0 else 0
    
    draw.text((padding, y_offset), f"怪物状态:", fill=(255, 85, 85), font=header_font)
    draw.text((padding + 540, y_offset), f"累计造成伤害: {damage_dealt}", fill=(248, 248, 242), font=regular_font)
    
    # 绘制怪物血条 (反向，显示剩余血量比例)
    bar_x = padding + 120
    bar_y = y_offset + 8
    draw.rectangle([(bar_x, bar_y), (bar_x + 400, bar_y + 15)], outline=(248, 248, 242))
    draw.rectangle([(bar_x, bar_y), (bar_x + 400 * hp_pct, bar_y + 15)], fill=(255, 85, 85))
    
    y_offset += 40
    draw.line([(padding, y_offset), (width-padding, y_offset)], fill=(98, 114, 164), width=2)
    y_offset += 20
    
    # 4. 队伍列表
    draw.text((padding, y_offset), "讨伐队伍:", fill=(189, 147, 249), font=header_font)
    y_offset += 35
    
    players = battle.data['players']
    if not players:
        draw.text((padding + 20, y_offset), "暂无玩家加入", fill=(98, 114, 164), font=regular_font)
        y_offset += 30
    else:
        # 分列显示
        col_width = width // 2
        for i, qq in enumerate(players):
            col = i % 2
            row = i // 2
            x = padding + 20 + col * col_width
            y = y_offset + row * 30
            
            # 获取玩家名字和装备
            from src.libraries.fishgame.fishgame import FishPlayer, FishItem
            p = FishPlayer(qq)
            
            # Use nickname if available
            player_name = battle.data.get('player_names', {}).get(str(qq), p.name)
            
            item_id = battle.data['loadouts'].get(str(qq)) or battle.data['loadouts'].get(int(qq))
            item_name = "无装备"
            if item_id:
                item = FishItem.get(item_id)
                if item:
                    item_name = item.name
            
            draw.text((x, y), f"{player_name} (装备: {item_name})", fill=(248, 248, 242), font=regular_font)
            
        y_offset += (len(players) + 1) // 2 * 30 + 10
        
    draw.line([(padding, y_offset), (width-padding, y_offset)], fill=(98, 114, 164), width=2)
    y_offset += 20
    
    # 5. 战斗日志 (最近几条)
    draw.text((padding, y_offset), "战斗日志:", fill=(139, 233, 253), font=header_font)
    y_offset += 35
    
    logs = battle.data.get('logs', [])
    # 取最后 10 条
    recent_logs = logs[-20:]
    for log in recent_logs:
        # 简单的自动换行处理
        wrapped_lines = wrap_text(log, small_font, width - 2 * padding - 20, draw)
        for line in wrapped_lines:
            if y_offset > height - 40:
                break
            draw.text((padding + 20, y_offset), '> ' + line, fill=(248, 248, 242), font=small_font)
            y_offset += 20
            
    return image


# ---------------- Talent Panel ----------------
def _format_talent_detail(talent_obj: dict, level: int) -> str:
    """Format talent detail string using effect values at given level.
    If key contains 'percent' and value <= 1, multiply by 100 for display.
    """
    detail_tpl = talent_obj.get('detail', '')
    eff = {}
    for k, arr in talent_obj.get('effect', {}).items():
        if not isinstance(arr, list) or level <= 0:
            continue
        idx = min(level - 1, len(arr) - 1)
        val = arr[idx]
        if ('percent' in k) and isinstance(val, (int, float)):
            # Special-case: 渔力会心( talent id == 8 ) uses absolute percent values per点
            # e.g., 0.01 means 0.01% (not 1%), so DO NOT multiply by 100 here
            if not (talent_obj.get('id') == 8 and k == 'crit_percent'):
                if val <= 1:
                    val = round(val * 100, 2)
        eff[k] = val
    try:
        return detail_tpl.format(**eff) if detail_tpl else ''
    except Exception:
        return detail_tpl


def create_talent_panel(player: FishPlayer, game: FishGame = None):
    """绘制天赋面板，仅显示当前等级与下一等级的 detail 效果，以及经验条。"""
    padding = 20
    card_w = 360
    card_h = 190
    gap = 16
    per_row = 2

    count = len(talent_data)
    rows = max(1, math.ceil(count / per_row))
    width = padding + (card_w + gap) * min(per_row, max(1, count)) - gap + padding
    height = 100 + (card_h + gap) * rows + padding

    image = Image.new('RGB', (width, height), (40, 42, 54))
    draw = ImageDraw.Draw(image)

    # Fonts
    font_path = "src/static/poke/LXGWWenKai-Regular.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 18)
    regular_font = ImageFont.truetype(font_path, 16)
    small_font = ImageFont.truetype(font_path, 14)

    # Title
    draw.text((width/2, 40), "天赋面板", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.line([(padding, 70), (width - padding, 70)], fill=(98, 114, 164), width=2)

    # Cards
    for idx, t in enumerate(talent_data):
        r = idx // per_row
        c = idx % per_row
        x0 = padding + c * (card_w + gap)
        y0 = 100 + r * (card_h + gap)
        x1 = x0 + card_w
        y1 = y0 + card_h
        draw.rectangle([(x0, y0), (x1, y1)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)

        tid = t.get('id')
        status = player.get_talent_status(tid)
        name = t.get('name', f'Talent {tid}')
        level_text = f"Lv.{status['level']}/{status['max_level']}"

        # Header
        draw.text((x0 + 10, y0 + 10), name, fill=(189, 147, 249), font=header_font)
        draw.text((x1 - 10, y0 + 10), level_text, fill=(241, 250, 140), font=header_font, anchor="rt")
        # Talent ID
        draw.text((x0 + 10, y0 + 30), f"ID: {tid}", fill=(200, 200, 200), font=small_font)

        # Only show current and next level detail (hide desc) with auto-wrap
        cur_lv = status['level']
        max_lv = status['max_level']
        # 当前等级的效果
        cur_detail = _format_talent_detail(t, cur_lv) if cur_lv > 0 else ''
        if not cur_detail:
            cur_detail = '无'
        # 下一等级的效果
        if cur_lv < max_lv:
            next_detail = _format_talent_detail(t, cur_lv + 1)
        else:
            next_detail = '已满级'

        max_text_width = card_w - 20
        base_y = y0 + 48
        line_h = 20
        progress_y = y1 - 40  # progress bar baseline; keep near bottom
        # 可用于两段文本的最大总行数
        max_lines_total = max(2, (progress_y - base_y - 10) // line_h)

        cur_text = f"当前 Lv.{cur_lv}：{cur_detail}"
        next_text = f"下一级 Lv.{min(cur_lv + 1, max_lv)}：{next_detail}"
        cur_lines = wrap_text(cur_text, regular_font, max_text_width, draw)
        next_lines = wrap_text(next_text, regular_font, max_text_width, draw)

        # 分配行数：尽量保证当前与下一级各至少两行（在空间允许时）
        base_min_each = 2 if max_lines_total >= 4 else 1
        cur_allow = max(base_min_each, min(len(cur_lines), max_lines_total - base_min_each))
        next_allow = max(base_min_each, min(len(next_lines), max_lines_total - cur_allow))
        if max_lines_total >= base_min_each * 2 and next_allow < base_min_each:
            # 将多余行数从当前段让给下一段，确保下一段至少 base_min_each 行
            need = base_min_each - next_allow
            cur_allow = max(base_min_each, cur_allow - need)
            next_allow = min(len(next_lines), max_lines_total - cur_allow)

        # 画当前段
        draw_y = base_y
        for j, line in enumerate(cur_lines[:cur_allow]):
            # 如果被截断，处理省略号
            txt = line
            if j == cur_allow - 1 and len(cur_lines) > cur_allow:
                while draw.textlength(txt + '...', font=regular_font) > max_text_width and len(txt) > 0:
                    txt = txt[:-1]
                txt = txt + '...'
            draw.text((x0 + 10, draw_y), txt, fill=(200, 220, 255), font=regular_font)
            draw_y += line_h

        # 画下一段
        for j, line in enumerate(next_lines[:next_allow]):
            txt = line
            if j == next_allow - 1 and len(next_lines) > next_allow:
                while draw.textlength(txt + '...', font=regular_font) > max_text_width and len(txt) > 0:
                    txt = txt[:-1]
                txt = txt + '...'
            draw.text((x0 + 10, draw_y), txt, fill=(160, 200, 255), font=regular_font)
            draw_y += line_h

        # Progress bar
        cur = status['current_need']
        seg_total = max(1, status['next_total'] - status['current_total'])
        bar_x, bar_y = x0 + 10, progress_y
        bar_w, bar_h = card_w - 20, 14
        pct = min(max(cur / seg_total, 0), 1)
        draw.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], fill=(54, 57, 70), outline=(98, 114, 164))
        fill_w = int(bar_w * pct)
        draw.rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h)], fill=(80, 250, 123))
        text = f"EXP {status['total_exp']} | +{cur}/{seg_total}"
        draw.text((bar_x + bar_w - 4, bar_y + bar_h + 4), text, fill=(200, 200, 200), font=small_font, anchor="rt")

    # Footer
    draw.text((width/2, height - 15), "天赋系统", fill=(98, 114, 164), font=regular_font, anchor="mm")
    return image
