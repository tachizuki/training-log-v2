# -*- coding: utf-8 -*-
# Play フィーチャーグラフィック 1024x500 をブランド配色で生成。
# 左: ライム人物シルエット / 右: PhysiqueLog ワードマーク + 日本語タグライン / 背景: 微かな上昇グラフ。
from PIL import Image, ImageDraw, ImageChops, ImageFont

CHARCOAL = (16, 18, 20)
LIME = (201, 240, 77)
WHITE = (237, 240, 242)
SUB = (150, 158, 166)
Wd, Ht = 1024, 500

# ---- 人物シルエット抽出（ライム・透過、外周の細枠は内側マスクで除去） ----
im = Image.open('icon_source.png').convert('L')
W, H = im.size
dark = im.point(lambda v: 255 if v <= 140 else 0)
# 円形マスクで外周の枠線・角を除去（中央の人物は完全に収まる）
circ = Image.new('L', (W, H), 0)
ImageDraw.Draw(circ).ellipse([0, 0, W - 1, H - 1], fill=255)
figure = ImageChops.multiply(dark, circ)
fig_rgba = Image.new('RGBA', (W, H), LIME + (255,))
fig_rgba.putalpha(figure)
fig_rgba = fig_rgba.crop(figure.getbbox())

# ---- キャンバス ----
img = Image.new('RGB', (Wd, Ht), CHARCOAL)
d = ImageDraw.Draw(img, 'RGBA')

# 背景: 微かな上昇ライングラフ（右下、低不透明度）
pts = [(560, 430), (650, 392), (725, 408), (805, 330), (885, 352), (975, 250)]
d.line(pts, fill=LIME + (34,), width=6, joint='curve')
for x, y in pts:
    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=LIME + (55,))

# ---- 人物（左） ----
fig_h = 384
fw, fh = fig_rgba.size
fig = fig_rgba.resize((int(fw * fig_h / fh), fig_h), Image.LANCZOS)
fx, fy = 56, (Ht - fig_h) // 2
img.paste(fig, (fx, fy), fig)

# ---- ワードマーク（右・幅に合わせて自動サイズ） ----
tx = fx + fig.width + 56
avail = (Wd - 40) - tx

def brandfont(size):
    f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', size)
    try: f.set_variation_by_name('Bold')
    except Exception: pass
    return f

size = 150
while size > 40:
    if d.textlength('PhysiqueLog', font=brandfont(size)) <= avail:
        break
    size -= 2
f_brand = brandfont(size)
f_tag = ImageFont.truetype('C:/Windows/Fonts/YuGothB.ttc', int(size * 0.30))

s1, s2 = 'Physique', 'Log'
w1 = d.textlength(s1, font=f_brand)
w2 = d.textlength(s2, font=f_brand)
asc, desc = f_brand.getmetrics()
th = asc + desc
tagh = int(size * 0.30) + 8
gap_ul, gap_tag = 12, 26
block_h = th + gap_ul + 8 + gap_tag + tagh
ty = (Ht - block_h) // 2

d.text((tx, ty), s1, font=f_brand, fill=WHITE)
d.text((tx + w1, ty), s2, font=f_brand, fill=LIME)
# アクセント下線
uy = ty + th + gap_ul
d.rounded_rectangle([tx, uy, tx + w1 + w2, uy + 8], radius=4, fill=LIME)
# タグライン
d.text((tx + 2, uy + 8 + gap_tag), '体重とトレーニングを、まとめて記録。', font=f_tag, fill=SUB)

img.save('docs/store-assets/feature-graphic-1024x500.png')
print(f'wrote feature graphic  brand_size={size} brand_w={int(w1+w2)} tx={tx} avail={int(avail)} fig_w={fig.width}')
