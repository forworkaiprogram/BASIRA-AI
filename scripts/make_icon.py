#!/usr/bin/env python3
"""Generate the BASIRA application icon (PNG + ICO)."""
from PIL import Image, ImageDraw

def main():
    size = 256
    img = Image.new("RGBA", (size, size), (18, 20, 26, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([28, 78, 228, 178], outline=(47, 111, 237, 255), width=14)
    d.ellipse([98, 98, 158, 158], fill=(47, 111, 237, 255))
    d.ellipse([118, 118, 138, 138], fill=(232, 234, 240, 255))
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "desktop_assets")
    os.makedirs(base, exist_ok=True)
    img.save(os.path.join(base, "basira.png"))
    img.save(os.path.join(base, "basira.ico"), sizes=[(16, 16), (32, 32),
                                                      (64, 64), (256, 256)])
    print("icons written to desktop_assets/")

if __name__ == "__main__":
    main()
