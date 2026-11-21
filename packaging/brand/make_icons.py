"""Rebuild the app icon and splash logo from assets/brand/logo-dark.svg.

Needs Pillow and Playwright with Chromium (used to rasterise the SVG):

    python packaging/brand/make_icons.py

Writes ovc/app/static/ovc.ico, ovc-icon.png and splash-logo.png.
"""

import glob
import io
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SVG = (ROOT / "assets" / "brand" / "logo-dark.svg").read_text(encoding="utf-8")
STATIC = ROOT / "ovc" / "app" / "static"
INK = "#121417"

# The icon is the left of the wordmark: the "O" and the overlap with the "V".
ICON_HTML = f"""<body style="margin:0;background:transparent">
<div style="width:512px;height:512px;border-radius:96px;background:{INK};
            display:flex;align-items:center;justify-content:center;overflow:hidden">
  <div style="width:400px;height:400px;overflow:hidden;position:relative">
    <div style="position:absolute;left:8px;top:36px;width:760px">{SVG}</div>
  </div>
</div></body>"""
SPLASH_HTML = f"""<body style="margin:0;background:{INK}">
<div style="width:230px;padding:4px">{SVG}</div></body>"""


def shoot(page, html, width, height, transparent):
    page.set_viewport_size({"width": width, "height": height})
    page.set_content(html)
    return Image.open(io.BytesIO(page.screenshot(omit_background=transparent)))


def main():
    exe = os.environ.get("OVC_CHROMIUM")
    if not exe:
        found = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
        exe = found[0] if found else None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        page = browser.new_page()
        icon = shoot(page, ICON_HTML, 512, 512, True)
        splash = shoot(page, SPLASH_HTML, 238, 110, False)
        browser.close()
    icon.resize((256, 256), Image.LANCZOS).save(STATIC / "ovc-icon.png")
    icon.save(
        STATIC / "ovc.ico",
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    splash.convert("RGB").save(STATIC / "splash-logo.png")
    print("Wrote ovc.ico, ovc-icon.png, splash-logo.png")


if __name__ == "__main__":
    main()
