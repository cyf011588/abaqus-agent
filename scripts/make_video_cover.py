# -*- coding: utf-8 -*-
"""把生图底图 + 中文字体排成 1920×1080 视频封面。"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

BASE = Path("docs/voice/cover_base.png")
OUT = Path("docs/video_cover.png")
BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
REG = r"C:\Windows\Fonts\msyh.ttc"

W, H = 1920, 1080
img = Image.open(BASE).convert("RGB")
# 铺满 16:9：等比放大后居中裁切
ratio = max(W / img.width, H / img.height)
img = img.resize((int(img.width * ratio) + 1, int(img.height * ratio) + 1), Image.LANCZOS)
left = (img.width - W) // 2
top = (img.height - H) // 2
img = img.crop((left, top, left + W, top + H))

# 左侧压暗，让白字有对比（淡淡的横向渐变）
shade = Image.new("L", (W, 1))
for x in range(W):
    t = max(0.0, 1.0 - x / (W * 0.62))
    shade.putpixel((x, 0), int(150 * (t ** 1.4)))
shade = shade.resize((W, H))
black = Image.new("RGB", (W, H), (8, 16, 26))
img = Image.composite(black, img, shade)

d = ImageDraw.Draw(img)
f_title = ImageFont.truetype(BOLD, 118)
f_sub = ImageFont.truetype(REG, 46)
f_tag = ImageFont.truetype(REG, 30)

x0 = 132
d.text((x0, 340), "对话即建模", font=f_title, fill=(255, 255, 255))
d.text((x0 + 4, 500), "Abaqus 参数化建模智能体", font=f_sub, fill=(168, 214, 230))

# 细分割线
d.line([(x0 + 4, 590), (x0 + 520, 590)], fill=(120, 168, 190), width=2)

d.text((x0 + 4, 626), "23 个案例  ·  23/23 真机跑通  ·  21 条诊断规则",
       font=f_tag, fill=(196, 208, 218))

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, "PNG")
print("saved", OUT, img.size)
