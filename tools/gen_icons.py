# -*- coding: utf-8 -*-
# 確定案（案1: チャコール背景 #101214 + ライム人物 #c9f04d, ライム枠あり）で
# 全密度 mipmap（ic_launcher / ic_launcher_round）＋ Play512 ＋ Twitter用 を書き出す。
import os
from PIL import Image, ImageDraw, ImageChops

SRC = 'icon_source.png'
CHARCOAL = (16, 18, 20)
LIME = (201, 240, 77)

im = Image.open(SRC).convert('L')
W, H = im.size
dark = im.point(lambda v: 255 if v <= 140 else 0)
light = im.point(lambda v: 255 if v > 140 else 0)
L, T, R, B = light.getbbox()
strip = light.crop((L, T + 3, R, T + 8))
radius = min(max(8, strip.getbbox()[0]), int(0.28 * (R - L)))
tile = Image.new('L', (W, H), 0)
ImageDraw.Draw(tile).rounded_rectangle([L, T, R - 1, B - 1], radius=radius, fill=255)
figure = ImageChops.multiply(dark, tile)
figimg = Image.new('RGBA', (W, H), LIME + (255,))

# 正方形マスター（枠あり・角チャコール）
master = Image.new('RGBA', (W, H), CHARCOAL + (255,))
master.paste(figimg, (0, 0), figure)
master = master.convert('RGB')

# 円形マスター（端末で円形マスクされる ic_launcher_round 用・枠なし）
circ = Image.new('L', (W, H), 0)
ImageDraw.Draw(circ).ellipse([0, 0, W - 1, H - 1], fill=255)
roundm = Image.new('RGBA', (W, H), (0, 0, 0, 0))
roundm.paste(Image.new('RGBA', (W, H), CHARCOAL + (255,)), (0, 0), circ)
roundm.paste(figimg, (0, 0), figure)
roundm.putalpha(ImageChops.multiply(roundm.split()[3], circ))

densities = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
for name, sz in densities.items():
    d = f'app/src/main/res/mipmap-{name}'
    master.resize((sz, sz), Image.LANCZOS).save(f'{d}/ic_launcher.png')
    roundm.resize((sz, sz), Image.LANCZOS).save(f'{d}/ic_launcher_round.png')
    print('wrote', d, sz)

os.makedirs('docs/store-assets', exist_ok=True)
master.resize((512, 512), Image.LANCZOS).save('docs/store-assets/icon-512-play.png')
master.resize((512, 512), Image.LANCZOS).save('docs/store-assets/icon-512-twitter.png')
master.save('icon_source_v2.png')
print('wrote docs/store-assets/icon-512-play.png, icon-512-twitter.png, icon_source_v2.png')
