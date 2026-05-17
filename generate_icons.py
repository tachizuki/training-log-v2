#!/usr/bin/env python3
"""
TrainingLog アイコン生成スクリプト
使い方: python generate_icons.py <元画像のパス>
例: python generate_icons.py icon_source.png
"""
import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillowをインストールしてください: pip install Pillow")
    sys.exit(1)

# Androidの各解像度とサイズ
SIZES = {
    "mipmap-mdpi":    48,
    "mipmap-hdpi":    72,
    "mipmap-xhdpi":   96,
    "mipmap-xxhdpi":  144,
    "mipmap-xxxhdpi": 192,
}

def generate_icons(source_path: str):
    src = Path(source_path)
    if not src.exists():
        print(f"ファイルが見つかりません: {source_path}")
        sys.exit(1)

    img = Image.open(src).convert("RGBA")
    base = Path("app/src/main/res")

    for folder, size in SIZES.items():
        out_dir = base / folder
        out_dir.mkdir(parents=True, exist_ok=True)

        resized = img.resize((size, size), Image.LANCZOS)

        # 通常アイコン
        launcher = out_dir / "ic_launcher.png"
        resized.save(launcher, "PNG")

        # ラウンドアイコン（同じ画像を使用）
        launcher_round = out_dir / "ic_launcher_round.png"
        resized.save(launcher_round, "PNG")

        print(f"✅ {folder}/ic_launcher.png ({size}x{size})")

    print("\n🎉 アイコン生成完了！")
    print("Android Studioでプロジェクトをリビルドしてください。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python generate_icons.py <元画像のパス>")
        print("例:     python generate_icons.py icon_source.png")
        sys.exit(1)
    generate_icons(sys.argv[1])
