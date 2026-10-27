"""Play Store phone screenshots (1080x2160) of Huroof Zizo.

Uses example data (a child called سارة, some stars and journey progress) so each screen
shows what it does. Usage: python3 store_shots.py <project_dir>
"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright
from screenshots import FAKE_BRIDGE

EXAMPLE = """
try {
  if (!sessionStorage.getItem('seeded')) {
    localStorage.setItem('zizo-kid', JSON.stringify({ name: 'سارة', g: 'f' }));
    localStorage.setItem('zizo-stars', '9');
    localStorage.setItem('zizo-owned', JSON.stringify(['cap', 'orange', 'none', 'crown', 'party', 'blue', 'glasses']));
    localStorage.setItem('zizo-journey', JSON.stringify([3, 3, 2, 3, 3, 2, 3]));
    sessionStorage.setItem('seeded', '1');
  }
} catch (e) {}
"""


async def main(proj):
    out = proj / "store"
    for old in out.glob("screen-*.png"):
        old.unlink()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2.7, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        await page.add_init_script(FAKE_BRIDGE + EXAMPLE)
        await page.goto((proj / "www/index.html").as_uri())
        await page.evaluate("document.fonts.ready")

        async def shot(name, wait=900):
            await page.wait_for_timeout(wait)
            await page.screenshot(path=str(out / f"screen-{name}.png"))

        await shot("1-welcome", 1400)
        await page.click("#goLearn")
        await page.click("#grid .tile >> nth=1")
        await shot("2-letter")
        await page.click(".lchip[data-lang=en]")
        await page.click("#grid .tile >> nth=0")
        await shot("3-english")
        await page.click(".lchip[data-lang=ar]")
        await page.click(".tab[data-v=numbers]")
        await page.click("#ngrid .tile >> nth=2")
        await page.click("#nBox .obj >> nth=0")
        await page.click("#nBox .obj >> nth=1")
        await shot("4-number")
        await page.click(".tab[data-v=play]")
        await page.click(".journey-card")
        await page.wait_for_timeout(400)
        # show the current stage with the start of the journey below it
        await page.evaluate("window.scrollBy(0, 160)")
        await shot("5-journey")
        await page.click("#mapBack")
        await shot("6-games")
        await page.click(".tab[data-v=trace]")
        await page.click("#nextT")
        box = await page.locator("#cv").bounding_box()
        cx, cy, s = box["x"], box["y"], box["width"]
        pts = [(0.67, 0.31), (0.68, 0.42), (0.62, 0.50), (0.50, 0.53), (0.38, 0.52), (0.31, 0.46), (0.30, 0.39)]
        await page.mouse.move(cx + pts[0][0] * s, cy + pts[0][1] * s)
        await page.mouse.down()
        for x, y in pts[1:]:
            await page.mouse.move(cx + x * s, cy + y * s, steps=5)
        await page.mouse.up()
        await shot("7-trace")
        await page.evaluate("localStorage.setItem('zizo-outfit', JSON.stringify({hat:'party', scarf:'blue', extra:'glasses'}))")
        await page.reload()
        await page.evaluate("document.fonts.ready")
        await page.click("#goLearn")
        await page.click("#starPill")
        await shot("8-shop")
        await b.close()
    print(sorted(x.name for x in out.glob("screen-*.png")))


if __name__ == "__main__":
    asyncio.run(main(pathlib.Path(sys.argv[1]).resolve()))
