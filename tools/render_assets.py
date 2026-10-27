"""Render Zizo World's Android icons, splash screens and Play Store graphics.

The icon is "Zizo and the blocks": Zizo peeking over three blocks (أ, A, ١) on sun yellow.
Usage: python3 render_assets.py <project_dir>
Writes android-overlay/app/src/main/res/... and store/ inside the project.
"""
import sys, asyncio, math, pathlib
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

PROJ = pathlib.Path(sys.argv[1]).resolve()
RES = PROJ / "android-overlay/app/src/main/res"
STORE = PROJ / "store"
FONTS = (PROJ / "www/fonts").as_uri()
ICON_BG = "#FFC83D"      # sun yellow, also the adaptive icon background
SPLASH_BG = "#FFF3D1"    # warm cream
NAVY, ORANGE_TEXT = "#22304D", "#D9650A"

# The decorations that sit on the yellow (full icon only)
DOTS = """<circle cx="72" cy="84" r="16" fill="#FFE08A"/><circle cx="446" cy="96" r="22" fill="#FFE08A"/><circle cx="418" cy="168" r="10" fill="#FFE08A"/>"""

# Zizo and the blocks, on a transparent 512 x 512 board
ART = """
<defs><clipPath id="hc"><circle cx="256" cy="206" r="110"/></clipPath></defs>
<g transform="rotate(-10 150 200)"><ellipse cx="150" cy="200" rx="70" ry="86" fill="#8E9DB8"/><ellipse cx="156" cy="206" rx="44" ry="58" fill="#F4A3B7"/></g>
<g transform="rotate(10 362 200)"><ellipse cx="362" cy="200" rx="70" ry="86" fill="#8E9DB8"/><ellipse cx="356" cy="206" rx="44" ry="58" fill="#F4A3B7"/></g>
<circle cx="256" cy="206" r="110" fill="#A7B4CB"/>
<circle cx="242" cy="190" r="104" fill="#BAC6DA" clip-path="url(#hc)"/>
<ellipse cx="218" cy="198" rx="18" ry="23" fill="#22304D"/><ellipse cx="294" cy="198" rx="18" ry="23" fill="#22304D"/>
<circle cx="225" cy="188" r="7" fill="#fff"/><circle cx="301" cy="188" r="7" fill="#fff"/>
<circle cx="213" cy="209" r="3.5" fill="#fff"/><circle cx="289" cy="209" r="3.5" fill="#fff"/>
<ellipse cx="180" cy="236" rx="18" ry="11" fill="#F4A3B7"/><ellipse cx="332" cy="236" rx="18" ry="11" fill="#F4A3B7"/>
<path d="M202 254 Q220 272 238 258" fill="none" stroke="#22304D" stroke-width="7" stroke-linecap="round"/>
<path d="M256 222 L256 330" fill="none" stroke="#BAC6DA" stroke-width="40" stroke-linecap="round"/>
<path d="M242 266 h28 M243 288 h26" fill="none" stroke="#8E9DB8" stroke-width="5" stroke-linecap="round"/>
<g transform="rotate(-9 128 390)">
<rect x="66" y="340" width="124" height="118" rx="26" fill="#C95F0B"/><rect x="66" y="328" width="124" height="118" rx="26" fill="#F07C1F"/>
<text x="128" y="414" text-anchor="middle" font-family="'Baloo Bhaijaan 2', sans-serif" font-weight="800" font-size="84" fill="#fff">أ</text></g>
<g transform="rotate(10 384 390)">
<rect x="322" y="340" width="124" height="118" rx="26" fill="#21803F"/><rect x="322" y="328" width="124" height="118" rx="26" fill="#2FA65C"/>
<text x="384" y="414" text-anchor="middle" font-family="'Baloo Bhaijaan 2', sans-serif" font-weight="800" font-size="84" fill="#fff">٢</text></g>
<g transform="rotate(3 256 372)">
<rect x="194" y="324" width="124" height="118" rx="26" fill="#2A6BB8"/><rect x="194" y="312" width="124" height="118" rx="26" fill="#3D8BE0"/>
<text x="256" y="400" text-anchor="middle" font-family="'Baloo Bhaijaan 2', sans-serif" font-weight="800" font-size="84" fill="#fff">A</text></g>
"""


def svg(inner, size, bg=None):
    rect = f'<rect width="512" height="512" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}" style="display:block">{rect}{inner}</svg>'


FONT_CSS = f"""
@font-face{{font-family:"Baloo Bhaijaan 2";src:url("{FONTS}/BalooBhaijaan2.ttf");font-weight:400 800}}
html,body{{margin:0;padding:0}}
"""


async def shot(page, html, w, h, path, transparent=False):
    # Loaded from a file (not set_content) so the page may use the local font and images
    await page.set_viewport_size({"width": w, "height": h})
    src = pathlib.Path(path).with_suffix(".html")
    src.write_text(f"<!doctype html><html dir='rtl' lang='ar'><head><meta charset='utf-8'><style>{FONT_CSS}</style></head><body>{html}</body></html>", encoding="utf-8")
    await page.goto(src.as_uri())
    await page.evaluate("document.fonts.load('800 40px \"Baloo Bhaijaan 2\"', 'أA٢Zizo')")
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(150)
    await page.screenshot(path=str(path), omit_background=transparent, clip={"x": 0, "y": 0, "width": w, "height": h})


def mask(img, shape, radius_frac=0.22):
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    if shape == "circle":
        d.ellipse([0, 0, img.width - 1, img.height - 1], fill=255)
    else:
        d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=int(img.width * radius_frac), fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    return out


def fit_in_circle(art, size, radius_frac, bg=None):
    """Center the art on a size x size square so every painted pixel lies within radius_frac * size of the middle."""
    a = art.crop(art.getbbox())
    cx, cy = a.width / 2, a.height / 2
    px = a.getchannel("A").load()
    far = 0.0
    for y in range(0, a.height, 4):
        for x in range(0, a.width, 4):
            if px[x, y] > 40:
                far = max(far, math.hypot(x - cx, y - cy))
    k = radius_frac * size / far
    a = a.resize((max(1, int(a.width * k)), max(1, int(a.height * k))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    canvas.alpha_composite(a, ((size - a.width) // 2, (size - a.height) // 2))
    return canvas


async def main():
    tmp = PROJ.parent / "huroof-zizo-tools" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    STORE.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(device_scale_factor=1)

        # 1. The full icon (yellow, dots, Zizo and the blocks) and the art alone, at 1024
        full_p, art_p = tmp / "icon-full.png", tmp / "icon-art.png"
        await shot(page, svg(DOTS + ART, 1024, ICON_BG), 1024, 1024, full_p)
        await shot(page, svg(ART, 1024), 1024, 1024, art_p, transparent=True)
        full = Image.open(full_p).convert("RGBA")
        art = Image.open(art_p).convert("RGBA")

        # 2. Play Store icon (full bleed; Play rounds the corners itself)
        full.resize((512, 512), Image.LANCZOS).convert("RGB").save(STORE / "icon-512.png")

        # 3. Launcher icons: square and round for older phones, foreground layer for Android 8+
        round_master = fit_in_circle(art, 1024, 0.43, ICON_BG)
        fg_master = fit_in_circle(art, 1024, 0.30)
        sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
        for dpi, s in sizes.items():
            d = RES / f"mipmap-{dpi}"
            d.mkdir(parents=True, exist_ok=True)
            mask(full, "rounded").resize((s, s), Image.LANCZOS).save(d / "ic_launcher.png")
            mask(round_master, "circle").resize((s, s), Image.LANCZOS).save(d / "ic_launcher_round.png")
            fs = int(s * 108 / 48)
            fg_master.resize((fs, fs), Image.LANCZOS).save(d / "ic_launcher_foreground.png")

        # 4. Splash screens: the icon, then the name
        icon_uri = full_p.as_uri()
        splash = {
            "drawable": (480, 320),
            "drawable-port-mdpi": (320, 480), "drawable-port-hdpi": (480, 800), "drawable-port-xhdpi": (720, 1280),
            "drawable-port-xxhdpi": (960, 1600), "drawable-port-xxxhdpi": (1280, 1920),
            "drawable-land-mdpi": (480, 320), "drawable-land-hdpi": (800, 480), "drawable-land-xhdpi": (1280, 720),
            "drawable-land-xxhdpi": (1600, 960), "drawable-land-xxxhdpi": (1920, 1280),
        }
        for folder, (w, h) in splash.items():
            m = min(w, h)
            ic = int(m * 0.36)
            html = f"""
<div style="width:{w}px;height:{h}px;background:{SPLASH_BG};display:flex;flex-direction:column;align-items:center;justify-content:center;gap:{int(m * 0.035)}px;font-family:'Baloo Bhaijaan 2'">
  <img src="{icon_uri}" style="width:{ic}px;height:{ic}px;border-radius:{int(ic * 0.22)}px;box-shadow:0 {int(m * 0.012)}px {int(m * 0.03)}px rgba(34,48,77,.18)">
  <div dir="ltr" style="font-weight:800;font-size:{int(m * 0.1)}px;line-height:1;color:{NAVY}"><span style="color:{ORANGE_TEXT}">Zizo</span> World</div>
  <div style="font-weight:700;font-size:{int(m * 0.045)}px;line-height:1;color:#7A6A4F">عالم زيزو</div>
</div>"""
            d = RES / folder
            d.mkdir(parents=True, exist_ok=True)
            out = tmp / "splash.png"
            await shot(page, html, w, h, out)
            Image.open(out).convert("RGB").save(d / "splash.png")

        # 5. Play Store feature graphic 1024 x 500
        art_uri = art_p.as_uri()
        chips = "".join(
            f"<span style='display:inline-flex;align-items:center;height:56px;padding:0 20px;border-radius:999px;background:#fff;color:{c};font-weight:800;font-size:30px;box-shadow:0 5px 0 #EAD9AE;{dirs}'>{t}</span>"
            for t, c, dirs in [("أ ب ت", "#D9650A", ""), ("A B C", "#2A6BB8", "direction:ltr;"), ("١ ٢ ٣", "#21803F", "")]
        )
        fg_html = f"""
<div style="position:relative;width:1024px;height:500px;overflow:hidden;background:{SPLASH_BG};font-family:'Baloo Bhaijaan 2'">
  <div style="position:absolute;left:-70px;top:-60px;width:620px;height:620px;border-radius:50%;background:{ICON_BG}"></div>
  <div style="position:absolute;left:96px;top:92px;width:26px;height:26px;border-radius:50%;background:#FFE08A"></div>
  <div style="position:absolute;left:470px;top:58px;width:18px;height:18px;border-radius:50%;background:{ICON_BG}"></div>
  <img src="{art_uri}" style="position:absolute;left:20px;top:10px;width:480px;height:480px">
  <div style="position:absolute;right:60px;top:0;bottom:0;width:500px;display:flex;flex-direction:column;justify-content:center;gap:18px">
    <div dir="ltr" style="font-weight:800;font-size:96px;line-height:1;color:{NAVY};text-align:right;white-space:nowrap"><span style="color:{ORANGE_TEXT}">Zizo</span> World</div>
    <div style="font-weight:700;font-size:36px;line-height:1.35;color:{NAVY}">حروف وأرقام بالعربي والإنجليزي</div>
    <div style="display:flex;gap:12px;margin-top:8px">{chips}</div>
  </div>
</div>"""
        out = tmp / "fg.png"
        await shot(page, fg_html, 1024, 500, out)
        Image.open(out).convert("RGB").save(STORE / "feature-graphic.png")
        await b.close()


asyncio.run(main())
print("done")
