from PIL import Image, ImageDraw, ImageFont
import textwrap
from src.libraries.fishgame import FishPlayer
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

def create_character_panel(player: FishPlayer, avatar_img: Image.Image):
    # 创建一个800x600的图像
    width, height = 800, 600
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
        {"name": "渔具", "x": 70, "y": 210, "item": player.equipment.get("rod")},
        {"name": "工具", "x": 70, "y": 250, "item": player.equipment.get("tool")}
    ]
    
    # 绘制装备栏
    for slot in equipment_slots:
        # 装备名称
        draw.text((slot["x"], slot["y"]), f"{slot['name']}:", fill=(248, 248, 242), font=regular_font)
        
        item = slot["item"]
        if item:
            # 获取稀有度对应的颜色
            rarity_color = (255, 255, 255)  # 默认白色
            if item.get("rarity") == 2:
                rarity_color = (139, 233, 253)  # 稀有 - 蓝色
            elif item.get("rarity") == 3:
                rarity_color = (255, 121, 198)  # 史诗 - 紫色
            elif item.get("rarity") == 4:
                rarity_color = (241, 250, 140)  # 传说 - 黄色
                
            # 绘制装备信息
            item_text = f"{item['name']} (渔力+{item.get('power', 0)})"
            draw.text((slot["x"]+60, slot["y"]), item_text, fill=rarity_color, font=regular_font)
            
            # 显示装备描述
            desc = item.get("description", "")
            wrapped_desc = textwrap.wrap(desc, width=60)
            if wrapped_desc:
                draw.text((slot["x"]+60, slot["y"]+20), wrapped_desc[0], fill=(248, 248, 242), font=small_font)
        else:
            draw.text((slot["x"]+60, slot["y"]), "未装备", fill=(98, 114, 164), font=regular_font)
    
    # 近期捕获鱼记录区域
    draw.rectangle([(50, 310), (width-50, 540)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
    draw.text((60, 320), "近期捕获鱼记录", fill=(189, 147, 249), font=header_font)
    
    # 绘制渔获记录
    y_pos = 350
    for i, fish in enumerate(player.fish_log[max(0, len(player.fish_log)-4):]):
        if i >= 4:  # 最多显示6条记录
            break
            
        # 获取鱼的稀有度对应的颜色
        fish_color = (255, 255, 255)  # 默认白色
        if fish["rarity"] == "R":
            fish_color = (139, 233, 253)  # R - 蓝色
        elif fish["rarity"] == "SR":
            fish_color = (255, 121, 198)  # SR - 紫色
        elif fish["rarity"] == "SSR":
            fish_color = (241, 250, 140)  # SSR - 黄色
        
        draw.text((60, y_pos), f"- {fish['name']} [{fish['rarity']}]", fill=fish_color, font=regular_font)
        
        # 显示鱼的描述(缩短版)
        desc = fish["detail"]
        desc_index = len(desc)
        while True:
            if draw.textlength(desc[:desc_index], font=small_font) < 680:
                break
            desc_index -= 1
        if desc_index == len(desc):
            draw.text((60, y_pos+20), desc, fill=(248, 48, 242), font=small_font)
        draw.text((60, y_pos+20), desc[:desc_index-1] + '...', fill=(248, 248, 242), font=small_font)
        
        # 显示经验值
        draw.text((width-60, y_pos), f"${fish['exp']}", fill=(80, 250, 123), font=regular_font, anchor="rt")
        
        y_pos += 45
    
    # 底部提示信息
    draw.line([(50, height-50), (width-50, height-50)], fill=(98, 114, 164), width=2)
    draw.text((width/2, height-25), "捕鱼达人 v0.1", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image


def create_inventory_panel(items_data, page, max_page):
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
    
    for i, item in enumerate(display_items):
        row = i // slots_per_row
        col = i % slots_per_row
        
        x1 = 50 + col * slot_width
        y1 = 70 + row * (slot_height + padding)
        x2 = x1 + slot_width - 10
        y2 = y1 + slot_height
        
        # 获取物品信息
        item_id = item["id"]
        count = item.get('count', 1)
        item_name = item["name"] + (f" ×{count}" if count > 1 else "")
        item_rarity = item["rarity"]
        item_desc = item["description"]
        is_equipable = item.get("equipable", False)
        
        # 绘制物品栏背景
        rarity_color = get_rarity_color(item_rarity)
        draw.rectangle([(x1, y1), (x2, y2)], fill=(68, 71, 90), outline=(98, 114, 164), width=2)
        
        # 左侧小图标区域
        icon_size = 50
        draw.rectangle([(x1+10, y1+15), (x1+10+icon_size, y1+15+icon_size)], 
                      fill=(50, 53, 70), outline=rarity_color)
        
        # 物品编号
        draw.text((x1+35, y1+40), f"{i + 1 + page * 10 - 10}", fill=(248, 248, 242), font=regular_font, anchor="mm")
        
        # 物品名称
        name_x = x1 + icon_size + 20
        draw.text((name_x, y1+12), item_name, fill=rarity_color, font=header_font)
        
        current_y = y1+12+22
        
        # 装备信息（如果可装备）
        if is_equipable:
            power = item.get("power", 0)
            item_type = item.get("type", "未知")
            
            # 装备类型中文转换
            if item_type == "tool":
                type_text = "工具"
            elif item_type == "rod":
                type_text = "渔具"
            else:
                type_text = item_type

            if item.get('equipped', False):
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
        is_points = "积分" in item_name
        
        # 绘制项目背景
        rarity_color = get_rarity_color(item_rarity) if not is_points else (255, 184, 108)  # 积分用橙色
        draw.rectangle([(x, y), (x+item_width, y+item_height)], 
                      fill=(68, 71, 90), outline=rarity_color, width=3)
        
        # 随机ID区域或者积分标识
        if is_points:
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
            
            # # 积分数量
            # points_amount = item_name.split()[0]
            # draw.text((x+item_width//2, icon_y+icon_size+20), 
            #         f"{points_amount}", fill=(255, 184, 108), 
            #         font=title_font, anchor="mm")
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
        draw.text((x+item_width//2, name_y), item_name, 
                 fill=rarity_color, font=header_font, anchor="mm")
        
        # 装备信息（如果可装备）
        if is_equipable:
            power = item.get("power", 0)
            item_type = item.get("type", "未知")
            
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
    draw.text((width/2, height-25), 
             f"抽取了 {items_count} 件物品", 
             fill=(98, 114, 164), font=regular_font, anchor="mm")
    
    return image

def create_shop_panel(shop_items):
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
        item_id = item.get("id", "")
        item_name = item.get("name", "未知")
        item_rarity = item.get("rarity", 1)
        item_desc = item.get("description", "")
        item_price = item.get("price", 0)
        item_stock = item.get("stock", "无限")
        is_equipable = item.get("equipable", False)
        is_limited = item_stock != "无限"
        
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
            power = item.get("power", 0)
            item_type = item.get("type", "未知")
            
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
        if is_limited:
            stock_text = f"库存: {item_stock}"
            draw.text((x+item_width-20, price_y+10), stock_text, 
                     fill=(248, 248, 242), font=small_font, anchor="rm")
    
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
