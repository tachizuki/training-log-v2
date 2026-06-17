# -*- coding: utf-8 -*-
# icon_source.png（白タイル＋黒シルエット）をブランド配色に再配色してプレビュー生成。
# 黒は「人物」と「外側角」の両方に使われているため、白タイル領域(角丸)でマスクして人物だけ抽出する。
import sys
from PIL import Image, ImageDraw, ImageChops, ImageFilter

SRC = 'icon_source.png'
CHARCOAL = (16, 18, 20)      # #101214
LIME = (201, 240, 77)        # #c9f04d

im = Image.open(SRC).convert('L')
W, H = im.size

# 2値マスク
dark = im.point(lambda v: 255 if v <= 140 else 0)     # 黒（人物＋外側角）
light = im.point(lambda v: 255 if v > 140 else 0)     # 白（タイル）

# タイルのbbox
bbox = light.getbbox()
L, T, R, B = bbox
# 角丸半径を推定：タイル上端付近で白が始まるxからleftを引く
strip = light.crop((L, T + 3, R, T + 8))
sb = strip.getbbox()  # (x0,y0,x1,y1) within strip
radius = max(8, (sb[0]))  # 白が始まるxオフセット ≒ 角丸半径
# 念のため上限
radius = min(radius, int(0.28 * (R - L)))

# 角丸タイルマスク
tile = Image.new('L', (W, H), 0)
ImageDraw.Draw(tile).rounded_rectangle([L, T, R - 1, B - 1], radius=radius, fill=255)

# 人物マスク = 黒 AND タイル内
figure = ImageChops.multiply(dark, tile)

print(f'size={W}x{H} tile_bbox={bbox} radius={radius}')

OUT = 512

def render(bg, fig, glow=False, fname='out.png'):
    out = Image.new('RGBA', (W, H), bg + (255,))
    if glow:
        g = figure.filter(ImageFilter.GaussianBlur(W * 0.012))
        glowimg = Image.new('RGBA', (W, H), fig + (255,))
        out.paste(glowimg, (0, 0), g.point(lambda v: int(v * 0.55)))
    figimg = Image.new('RGBA', (W, H), fig + (255,))
    out.paste(figimg, (0, 0), figure)
    out = out.resize((OUT, OUT), Image.LANCZOS)
    out.convert('RGB').save(fname)
    print('wrote', fname)

render(CHARCOAL, LIME, glow=False, fname='tools/preview_case1.png')
render(CHARCOAL, LIME, glow=True,  fname='tools/preview_case1_glow.png')
render(LIME, CHARCOAL, glow=False, fname='tools/preview_case2.png')
