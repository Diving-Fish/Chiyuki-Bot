from io import BytesIO
from typing import Optional, List
from nonebot.adapters.cqhttp import Message, MessageSegment
from PIL import Image, ImageDraw, ImageFont
import aiohttp

from src.libraries.image import fontpath, image_to_base64


class ImgTemplateParseError(Exception):
    def __str__(self):
        return "解析命令失败"


class ImgParam:
    def __init__(self, url, param_str):
        self.url = url
        self.x: Optional[float] = 0
        self.y: Optional[float] = 0
        self.min_width: Optional[float] = None
        self.max_width: Optional[float] = None
        self.width: Optional[float] = None
        self.min_height: Optional[float] = None
        self.max_height: Optional[float] = None
        self.height: Optional[float] = None
        params = param_str.split(',')
        for param in params:
            arr = param.split("=")
            arr[0] = arr[0].strip()
            arr[1] = arr[1].strip()
            if arr[0] == "x":
                self.x = float(arr[1])
            elif arr[0] == "y":
                self.y = float(arr[1])
            elif arr[0] == "min_width":
                self.min_width = float(arr[1])
            elif arr[0] == "max_width":
                self.max_width = float(arr[1])
            elif arr[0] == "width":
                self.width = float(arr[1])
            elif arr[0] == "min_height":
                self.min_height = float(arr[1])
            elif arr[0] == "max_height":
                self.max_height = float(arr[1])
            elif arr[0] == "height":
                self.height = float(arr[1])


class TextParam:
    def __init__(self, text, param_str):
        self.text = text
        self.x: Optional[float] = 0
        self.y: Optional[float] = 0
        self.border_width: Optional[float] = None
        self.font_size: int = 18
        self.text_align: str = "left"
        self.color: str = "#000000"
        params = param_str.split(',')
        for param in params:
            arr = param.split("=")
            arr[0] = arr[0].strip()
            arr[1] = arr[1].strip()
            if arr[0] == "x":
                self.x = float(arr[1])
            elif arr[0] == "y":
                self.y = float(arr[1])
            elif arr[0] == "border_width":
                self.border_width = float(arr[1])
            elif arr[0] == "font_size":
                self.font_size = int(arr[1])
            elif arr[0] == "text_align":
                if arr[1] in ("left", "center", "right"):
                    self.text_align = arr[1]
            elif arr[0] == "color":
                self.color = arr[1]


async def get_image(url) -> Image.Image:
    async with aiohttp.request("GET", url) as resp:
        return Image.open(BytesIO(await resp.content.read()))


async def img_template_parser(msg: Message):
    for seg in msg:
        if seg.type == "text":
            seg.data["text"] = seg.data["text"].replace('\r', '').replace('\n', '')
    params = []
    if str(msg[0]) == "new":
        temp: MessageSegment = msg[1]
        base_img = await get_image(temp.data["url"])
    elif str(msg[0]) == "preset":
        # invoke preset
        base_img = None
        pass
    else:
        raise ImgTemplateParseError
    current_index = 2
    offset = 0

    def parse_next(param_index, arg_text_offset):
        seg: MessageSegment = msg[param_index]
        if seg.type == "image":
            url = seg.data["url"]
            param_index += 1
            arg_text_offset = 0
            next_seg: MessageSegment = msg[param_index]
            next_seg: str = str(next_seg)
            if next_seg[arg_text_offset] != "<":
                raise ImgTemplateParseError
            arg_text_offset += 1
            buff = ""
            while next_seg[arg_text_offset] != ">":
                buff += next_seg[arg_text_offset]
                arg_text_offset += 1
                if arg_text_offset == len(next_seg):
                    param_index += 1
                    arg_text_offset = 0
                    next_seg: MessageSegment = msg[param_index]
                    assert next_seg.type == "text"
                    next_seg: str = str(next_seg)
            arg_text_offset += 1
            return ImgParam(url, buff), param_index, arg_text_offset, False

        elif seg.type == "text":
            seg: str = str(seg)
            string = ""
            if arg_text_offset >= len(seg):
                param_index += 1
                arg_text_offset = 0
                if param_index == len(msg):
                    return None, param_index, arg_text_offset, True
            while seg[arg_text_offset] != " ":
                char = seg[arg_text_offset]
                if char == "<":
                    buff = ""
                    arg_text_offset += 1
                    while seg[arg_text_offset] != ">":
                        buff += seg[arg_text_offset]
                        arg_text_offset += 1
                        if arg_text_offset == len(seg):
                            param_index += 1
                            arg_text_offset = 0
                            seg: MessageSegment = msg[param_index]
                            assert seg.type == "text"
                            seg: str = str(seg)
                    arg_text_offset += 1
                    return TextParam(string, buff), param_index, arg_text_offset, False
                else:
                    string += char
                arg_text_offset += 1
            arg_text_offset += 1
            if arg_text_offset == len(seg):
                param_index += 1
                arg_text_offset = 0
                if param_index == len(msg):
                    return None, param_index, arg_text_offset, True
            return None, param_index, arg_text_offset, False

    while True:
        r, current_index, offset, f = parse_next(current_index, offset)
        if f:
            break
        if r:
            params.append(r)

    return base_img, params


async def edit_base_img(base_img: Image.Image, params):
    ips: List[ImgParam] = []
    tps: List[TextParam] = []
    for param in params:
        if isinstance(param, ImgParam):
            ips.append(param)
        if isinstance(param, TextParam):
            tps.append(param)
    for ip in ips:
        img = await get_image(ip.url)
        if ip.width:
            ip.width *= base_img.width
        if ip.height:
            ip.height *= base_img.height
        if ip.width and ip.height:
            img.resize((int(ip.width), int(ip.height)), Image.BILINEAR)
        elif ip.width:
            img.resize((int(ip.width), int(ip.width / img.width * img.height)), Image.BILINEAR)
        elif ip.height:
            img.resize((int(ip.height / img.height * img.width), int(img.height)), Image.BILINEAR)
        base_img.paste(img, (int(ip.x * base_img.width), int(ip.y * base_img.height)))
    draw = ImageDraw.Draw(base_img)
    for tp in tps:
        font = ImageFont.truetype(fontpath, tp.font_size)
        x = int(tp.x * base_img.width)
        y = int(tp.y * base_img.height)
        if not tp.border_width:
            draw.text((x, y), tp.text, font=font, fill=tp.color)
        else:
            width, _ = draw.textsize(tp.text, font)
            x1 = x
            x2 = x + int(base_img.width * tp.border_width)
            xc = int((x1 + x2) / 2)
            if tp.text_align == "center":
                x = int(xc - width / 2)
            elif tp.text_align == "left":
                x = x1
            elif tp.text_align == "right":
                x = x2 - width
            draw.text((x, y), tp.text, font=font, fill=tp.color)
    return image_to_base64(base_img)
