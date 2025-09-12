from PIL import Image, ImageDraw, ImageFont
import textwrap
from src.libraries.fishgame.data import FishItem, Fish, Backpack
from src.libraries.fishgame.fishgame import FishPlayer, FishGame
import math
from io import BytesIO
import aiohttp

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

def create_character_panel(player: FishPlayer, avatar_img: Image.Image, game=None):
    # 创建一个800x800的图像 (增加高度以容纳图鉴)
    width, height = 800, 800
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
    avatar_img = avatar_img.resize((avatar_size, avatar_size))
    image.paste(avatar_img, (60, 70))
    
    # 基本信息
    draw.text((150, 67), player.name, fill=(248, 248, 242), font=header_font)
    
    # fever期间显示fever_power，否则显示普通power
    if game and game.is_fever:
        draw.text((150, 92), f"渔力: {player.fever_power} (鱼群状态)", fill=(255, 215, 0), font=regular_font)
    else:
        draw.text((150, 92), f"渔力: {player.power}", fill=(248, 248, 242), font=regular_font)
    
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
    draw.rectangle([(50, 170), (width-50, 300)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    draw.text((60, 180), "当前装备", fill=(189, 147, 249), font=header_font)
    
    # 定义装备栏位置
    equipment_slots = [
        {"name": "渔具", "x": 70, "y": 210, "item": player.equipment.rod},
        {"name": "工具", "x": 70, "y": 250, "item": player.equipment.tool}
    ]
    
    # 绘制装备栏
    for slot in equipment_slots:
        # 装备名称
        draw.text((slot["x"], slot["y"]), f"{slot['name']}:", fill=(248, 248, 242), font=regular_font)
        
        item: FishItem = slot["item"]
        if item:
            # 获取稀有度对应的颜色
            rarity_color = (255, 255, 255)  # 默认白色
            if item.rarity == 2:
                rarity_color = (139, 233, 253)  # 稀有 - 蓝色
            elif item.rarity == 3:
                rarity_color = (255, 121, 198)  # 史诗 - 紫色
            elif item.rarity == 4:
                rarity_color = (241, 250, 140)  # 传说 - 黄色
                
            # 绘制装备信息
            item_text = f"{item.name} (渔力+{item.power})"
            draw.text((slot["x"]+60, slot["y"]), item_text, fill=rarity_color, font=regular_font)
            
            # 显示装备描述
            desc = item.description
            wrapped_desc = textwrap.wrap(desc, width=60)
            if wrapped_desc:
                draw.text((slot["x"]+60, slot["y"]+20), wrapped_desc[0], fill=(248, 248, 242), font=small_font)
        else:
            draw.text((slot["x"]+60, slot["y"]), "未装备", fill=(98, 114, 164), font=regular_font)
    
    # 图鉴区域
    draw.rectangle([(50, 310), (width-50, height-50)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    draw.text((60, 320), "图鉴", fill=(189, 147, 249), font=header_font)
    
    # 创建图鉴内容
    create_pokedex_content(draw, player, game, font_dict={
        'header': header_font,
        'regular': regular_font,
        'small': small_font
    })
    
    # 底部提示信息
    # draw.line([(50, height-50), (width-50, height-50)], fill=(98, 114, 164), width=2)
    draw.text((width/2, height-25), "捕鱼达人 v0.1", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image


def create_pokedex_content(draw, player: FishPlayer, game: FishGame, font_dict):
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
    caught_fish_ids = set(player.fish_log._FishLog__data)
    
    # 基础鱼 (ID 1-32)
    base_fish_caught = len([fish_id for fish_id in caught_fish_ids if 1 <= fish_id <= base_fish_count])
    
    # 鱼群鱼 (ID 33+)
    group_fish_caught = len([fish_id for fish_id in caught_fish_ids if fish_id > base_fish_count])
    
    total_caught = base_fish_caught + group_fish_caught
    
    # 显示完成率
    completion_rate = (total_caught / total_fish_count) * 100
    draw.text((60, 350), f"图鉴完成度: {total_caught}/{total_fish_count} ({completion_rate:.1f}%)", 
             fill=(241, 250, 140), font=regular_font)
    draw.text((60, 375), f"基础鱼: {base_fish_caught}/{base_fish_count}  鱼群鱼: {group_fish_caught}/{group_fish_count}", 
             fill=(248, 248, 242), font=small_font)
    
    # 获取今日鱼群主题
    current_weekday = time.localtime().tm_wday
    today_topic = weekday_topic[current_weekday] if current_weekday < len(weekday_topic) else ""
    
    # 绘制基础鱼图鉴 (4列显示)
    y_start = 410
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


def create_inventory_panel(items_data, page, max_page, equipped_item_ids):
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
    
    def get_rarity_color(rarity):
        if rarity == 1:
            return (255, 255, 255)  # 普通 - 白色
        elif rarity == 2:
            return (139, 233, 253)  # 稀有 - 蓝色
        elif rarity == 3:
            return (255, 121, 198)  # 史诗 - 紫色
        elif rarity == 4:
            return (241, 250, 140)  # 传说 - 黄色
        return (255, 255, 255)
    
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
        is_equipable = item.equipable
        
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
            if item_type == "tool":
                type_text = "工具"
            elif item_type == "rod":
                type_text = "渔具"
            else:
                type_text = item_type

            if item.id in equipped_item_ids:
                equip_text = f"[已装备] 类型: {type_text} | 渔力: {power}"
                draw.text((name_x, current_y), equip_text, fill=(250, 250, 70), font=small_font)
            else:
                equip_text = f"[可装备] 类型: {type_text} | 渔力: {power}"
                draw.text((name_x, current_y), equip_text, fill=(80, 250, 123), font=small_font)
            current_y += 18
        
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

def create_craft_panel(craftable_items: list[FishItem], player_bag: Backpack, player_score: int = 0):
    """创建合成面板"""
    # 基本设置
    padding = 20
    item_width = 300
    item_height = 280
    items_per_row = 2
    
    # 计算面板尺寸
    items_count = len(craftable_items)
    rows = math.ceil(items_count / items_per_row)
    width = padding + (item_width + padding) * min(items_count, items_per_row)
    height = 100 + (item_height + padding) * rows + 80
    
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
    draw.text((width/2, 40), "合成工坊", fill=(248, 248, 242), font=title_font, anchor="mm")
    draw.line([(padding, 80), (width-padding, 80)], fill=(98, 114, 164), width=2)
    
    # 获取稀有度对应的颜色
    def get_rarity_color(rarity):
        if rarity == 1:
            return (255, 255, 255)   # 白色 - 普通
        elif rarity == 2:
            return (80, 250, 123)    # 绿色 - 稀有
        elif rarity == 3:
            return (189, 147, 249)   # 紫色 - 史诗
        elif rarity == 4:
            return (255, 184, 108)   # 橙色 - 传说
        return (255, 255, 255)
    
    # 手动文本换行函数
    def wrap_text(text, font, max_width):
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            line_width = draw.textlength(test_line, font=font)
            
            if line_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        if current_line:  # 添加最后一行
            lines.append(current_line)
            
        return lines
    
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
            if item_type == "tool":
                type_text = "工具"
            elif item_type == "rod":
                type_text = "渔具"
            else:
                type_text = item_type

            equip_text = f"类型: {type_text} | 渔力: +{power}"
            draw.text((x + 80, current_text_y), equip_text, fill=(80, 250, 123), font=small_font)
            current_text_y += 20
        
        # 物品描述（使用手动换行函数）
        max_desc_width = item_width - 90
        wrapped_desc = wrap_text(item.description, small_font, max_desc_width)
        
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
                if material_y - y > 250:
                    draw.text((x + 15, material_y), "...", 
                             fill=(248, 248, 242), font=small_font)
                    break
        
        # 显示积分消耗（如果需要）
        if item.craft_score_cost > 0:
            # 添加一些间隔
            material_y += 10
            
            # 积分消耗标题
            draw.text((x + 10, material_y), "积分消耗:", fill=(255, 184, 108), font=regular_font)
            material_y += 25
            
            # 显示积分消耗和玩家当前积分
            score_text = f"需要积分: {item.craft_score_cost}"
            current_score_text = f"当前: {player_score}"
            
            # 根据积分是否充足选择颜色
            if player_score >= item.craft_score_cost:
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
             "Usage: 合成 <物品编号>", 
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
        return (255, 255, 255)      # 默认 - 白色
    
    # 手动文本换行函数
    def wrap_text(text, font, max_width):
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            line_width = draw.textlength(test_line, font=font)
            
            if line_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        if current_line:  # 添加最后一行
            lines.append(current_line)
            
        return lines
    
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
            if item_type == "tool":
                type_text = "工具"
            elif item_type == "rod":
                type_text = "渔具"
            else:
                type_text = item_type
                
            equip_text = f"{type_text} | 渔力+{power}"
            draw.text((x+item_width//2, name_y+25), equip_text, 
                     fill=(80, 250, 123), font=small_font, anchor="mm")
        
        # 物品描述（使用自定义换行函数）
        desc_y = name_y + (45 if is_equipable else 25)
        
        # 设置最大文本宽度略小于项目宽度
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width)
        
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
        return (255, 255, 255)      # 默认 - 白色
    
    # 手动文本换行函数
    def wrap_text(text, font, max_width):
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            line_width = draw.textlength(test_line, font=font)
            
            if line_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        if current_line:  # 添加最后一行
            lines.append(current_line)
            
        return lines
    
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
            if item_type == "tool":
                type_text = "工具"
            elif item_type == "rod":
                type_text = "渔具"
            else:
                type_text = item_type
                
            equip_text = f"{type_text} | 渔力+{power}"
            draw.text((x+item_width//2, name_y+20), equip_text, 
                     fill=(80, 250, 123), font=small_font, anchor="mm")
        
        # 物品描述
        desc_y = name_y + (40 if is_equipable else 20)
        
        # 设置最大文本宽度略小于项目宽度
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width)
        
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
