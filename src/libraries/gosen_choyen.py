# Author: Diving_Fish

from typing import Tuple, List
from PIL import Image, ImageDraw, ImageFont, ImageColor

# Define your font here.
__font_path = "./src/static/msyhbd.ttc"
__font = ImageFont.truetype(__font_path, 100, encoding='utf-8')


class VerticalColorGradient:
    def __init__(self):
        self.colors: List[Tuple[float, Tuple[int, int, int]]] = []

    def add_color_stop(self, ratio, color: Tuple[int, int, int]):
        self.colors.append((ratio, color))

    def get_color(self, ratio) -> Tuple[int, int, int]:
        if len(self.colors) == 0:
            return 0, 0, 0
        for i in range(len(self.colors)):
            if i + 1 >= len(self.colors):
                return self.colors[i][1]
            elif ratio <= self.colors[i + 1][0]:
                t = 1 - (self.colors[i + 1][0] - ratio) / (self.colors[i + 1][0] - self.colors[i][0])
                r = self.colors[i + 1][1][0] * t + self.colors[i][1][0] * (1 - t)
                g = self.colors[i + 1][1][1] * t + self.colors[i][1][1] * (1 - t)
                b = self.colors[i + 1][1][2] * t + self.colors[i][1][2] * (1 - t)
                return int(r + 0.5), int(g + 0.5), int(b + 0.5)


def get_vcg_bg(width, height, vcg: VerticalColorGradient, offset=0):
    im = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(im)
    for i in range(height):
        if i < offset:
            color = (0, 0, 0, 0)
        else:
            color = vcg.get_color((i - offset) / (height - offset))
        draw.line((0, i, width - 1, i), fill=(color[0], color[1], color[2], 255), width=1)
    return im


def canvas(text, stroke_width):
    im = Image.new('RGBA', (500, 500), (255, 255, 255, 255))
    draw = ImageDraw.Draw(im)
    size = draw.textsize(text, __font, stroke_width=stroke_width)
    im = im.resize(size)
    draw = ImageDraw.Draw(im)
    return im, draw


def get_text_mask(text):
    im, draw = canvas(text, 0)
    draw.text((0, 0), text, fill=(0, 0, 0, 0), font=__font)
    return im


def get_text_stroke_mask(text, stroke_width):
    im, draw = canvas(text, stroke_width)
    draw.text((0, 0), text, fill=(255, 255, 255, 255), font=__font, stroke_width=stroke_width, stroke_fill=(0, 0, 0, 0))
    return im


def vcg_text(text, vcg, stroke_width=0, offset=0):
    if stroke_width:
        im1 = get_text_stroke_mask(text, stroke_width)
        im2 = get_vcg_bg(im1.size[0], im1.size[1], vcg, offset)
        im3 = Image.new('RGBA', im2.size, (0, 0, 0, 0))
        im2.paste(im3, mask=im1)
        return im2
    else:
        im1 = get_text_mask(text)
        im2 = get_vcg_bg(im1.size[0], im1.size[1], vcg, offset)
        im3 = Image.new('RGBA', im2.size, (0, 0, 0, 0))
        im2.paste(im3, mask=im1)
        return im2


def red_text(text):
    uv1 = VerticalColorGradient()
    uv1.add_color_stop(0, (0, 0, 0))
    i1 = vcg_text(text, uv1, stroke_width=17, offset=20)
    i1 = i1.transform(i1.size, Image.AFFINE, (1, 0, -4, 0, 1, -3))

    uv2 = VerticalColorGradient()
    uv2.add_color_stop(0.0, (0,15,36))
    uv2.add_color_stop(0.10, (255,255,255))
    uv2.add_color_stop(0.18, (55,58,59))
    uv2.add_color_stop(0.25, (55,58,59))
    uv2.add_color_stop(0.5, (200,200,200))
    uv2.add_color_stop(0.75, (55,58,59))
    uv2.add_color_stop(0.85, (25,20,31))
    uv2.add_color_stop(0.91, (240,240,240))
    uv2.add_color_stop(0.95, (166,175,194))
    uv2.add_color_stop(1, (50,50,50))
    i2 = vcg_text(text, uv2, stroke_width=14, offset=20)
    i2 = i2.transform(i2.size, Image.AFFINE, (1, 0, -4, 0, 1, -3))

    uv3 = VerticalColorGradient()
    uv3.add_color_stop(0, (0, 0, 0))
    i3 = vcg_text(text, uv3, stroke_width=10, offset=20)

    uv4 = VerticalColorGradient()
    uv4.add_color_stop(0, (253,241,0))
    uv4.add_color_stop(0.25, (245,253,187))
    uv4.add_color_stop(0.4, (255,255,255))
    uv4.add_color_stop(0.75, (253,219,9))
    uv4.add_color_stop(0.9, (127,53,0))
    uv4.add_color_stop(1, (243,196,11))
    i4 = vcg_text(text, uv4, 8, 20)
    i4 = i4.transform(i4.size, Image.AFFINE, (1, 0, 0, 0, 1, 2))

    uv5 = VerticalColorGradient()
    uv5.add_color_stop(0, (0, 0, 0))
    i5 = vcg_text(text, uv5, stroke_width=4, offset=20)
    i5 = i5.transform(i5.size, Image.AFFINE, (1, 0, 0, 0, 1, 2))

    uv6 = VerticalColorGradient()
    uv6.add_color_stop(0, (255, 255, 255))
    i6 = vcg_text(text, uv6, stroke_width=4, offset=20)
    i6 = i6.transform(i6.size, Image.AFFINE, (1, 0, 0, 0, 1, 2))

    red_fill_vcg = VerticalColorGradient()
    red_fill_vcg.add_color_stop(0, (255, 100, 0))
    red_fill_vcg.add_color_stop(0.5, (123, 0, 0))
    red_fill_vcg.add_color_stop(0.51, (240, 0, 0))
    red_fill_vcg.add_color_stop(1, (5, 0, 0))
    im = vcg_text(text, red_fill_vcg, 0, 20)
    im = im.transform(im.size, Image.AFFINE, (1, 0, 4, 0, 1, 8))

    uv7 = VerticalColorGradient()
    uv7.add_color_stop(0, (230, 0, 0))
    uv7.add_color_stop(0.5, (230, 0, 0))
    uv7.add_color_stop(0.51, (240, 0, 0))
    uv7.add_color_stop(1, (5, 0, 0))
    i7 = vcg_text(text, red_fill_vcg, 1, 20)
    i7 = i7.transform(i7.size, Image.AFFINE, (1, 0, 4, 0, 1, 8))

    l = [i2, i3, i4, i5, i6, im, i7]
    for elem in l:
        x = i1.size[0] - elem.size[0]
        y = i1.size[1] - elem.size[1]
        i1.paste(elem, box=(int(x / 2), int(y / 2)), mask=elem)
    return i1.transform(i1.size, Image.AFFINE, (1, 0.4, 0, 0, 1, 0))


def sliver_text(text):
    uv1 = VerticalColorGradient()
    uv1.add_color_stop(0, (0, 0, 0))
    i1 = vcg_text(text, uv1, stroke_width=17, offset=20)
    i1 = i1.transform(i1.size, Image.AFFINE, (1, 0, -4, 0, 1, -3))

    uv2 = VerticalColorGradient()
    uv2.add_color_stop(0, (0,15,36))
    uv2.add_color_stop(0.25, (250,250,250))
    uv2.add_color_stop(0.5, (150,150,150))
    uv2.add_color_stop(0.75, (55,58,59))
    uv2.add_color_stop(0.85, (25,20,31))
    uv2.add_color_stop(0.91, (240,240,240))
    uv2.add_color_stop(0.95, (166,175,194))
    uv2.add_color_stop(1, (50,50,50))
    i2 = vcg_text(text, uv2, stroke_width=14, offset=20)
    i2 = i2.transform(i2.size, Image.AFFINE, (1, 0, -4, 0, 1, -3))

    uv3 = VerticalColorGradient()
    uv3.add_color_stop(0, (16, 25, 58))
    i3 = vcg_text(text, uv3, stroke_width=12, offset=20)

    uv4 = VerticalColorGradient()
    uv4.add_color_stop(0, (221, 221, 221))
    i4 = vcg_text(text, uv4, stroke_width=7, offset=20)
    i4 = i4.transform(i4.size, Image.AFFINE, (1, 0, 0, 0, 1, 0))

    uv5 = VerticalColorGradient()
    uv5.add_color_stop(0, (16,25,58))
    uv5.add_color_stop(0.03, (255,255,255))
    uv5.add_color_stop(0.08, (16,25,58))
    uv5.add_color_stop(0.2, (16,25,58))
    uv5.add_color_stop(1, (16,25,58))
    i5 = vcg_text(text, uv5, stroke_width=6, offset=20)

    uv6 = VerticalColorGradient()
    uv6.add_color_stop(0, (245,246,248))
    uv6.add_color_stop(0.15, (255,255,255))
    uv6.add_color_stop(0.35, (195,213,220))
    uv6.add_color_stop(0.5, (160,190,201))
    uv6.add_color_stop(0.51, (160,190,201))
    uv6.add_color_stop(0.52, (196,215,222))
    uv6.add_color_stop(1.0, (255,255,255))
    i6 = vcg_text(text, uv6, offset=20)
    i6 = i6.transform(i6.size, Image.AFFINE, (1, 0, 6, 0, 1, 8))

    l = [i2, i3, i4, i5, i6]
    for elem in l:
        x = i1.size[0] - elem.size[0]
        y = i1.size[1] - elem.size[1]
        i1.paste(elem, box=(int(x / 2), int(y / 2)), mask=elem)
    return i1.transform(i1.size, Image.AFFINE, (1, 0.4, 0, 0, 1, 0))


def generate(red, sliver, offset=-1):
    r = red_text("  " + red)
    s = sliver_text("  " + sliver)
    if offset == -1:
        offset = max(0, int(r.size[0] - s.size[0] / 2 - 60))
    i = Image.new('RGB', (max(r.size[0], s.size[0] + offset), r.size[1] + s.size[1]), (255, 255, 255))
    i.paste(r, box=(0, 0), mask=r.split()[3])
    i.paste(s, box=(offset, r.size[1]), mask=s.split()[3])
    return i