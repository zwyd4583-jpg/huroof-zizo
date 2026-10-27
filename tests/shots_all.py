"""Pictures of every main screen, for reviewing the design. Usage: shots_all.py <prefix>"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
PRE = sys.argv[1] if len(sys.argv) > 1 else "before"
OUT = out("design")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await ctx.new_page()
        await page.add_init_script(BRIDGE + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); localStorage.setItem('zizo-stars','23'); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.emulate_media(reduced_motion="reduce")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(1200)
        async def shot(n): await page.wait_for_timeout(700); await page.screenshot(path=str(OUT / f"{PRE}_{n}.png"))
        await shot("01_welcome")
        await page.click("#goLearn"); await shot("02_letters")
        await page.click("#grid .tile >> nth=1"); await shot("03_letter")
        await page.click(".tab[data-v=numbers]"); await shot("04_numbers")
        await page.click("#ngrid .tile >> nth=4"); await shot("05_number")
        await page.click(".tab[data-v=discover]"); await shot("06_discover")
        await page.click("#dgrid .dtile >> nth=0"); await shot("07_discover_item")
        await page.click(".tab[data-v=play]"); await shot("08_games")
        await page.click(".gamecard[data-mode=listen]"); await shot("09_game")
        await page.click("#gamesBack"); await page.click(".journey-card:not(.daily-card)"); await shot("10_journey")
        await page.click(".tab[data-v=trace]"); await shot("11_trace")
        await page.click(".tab[data-v=stories]"); await shot("12_stories")
        await page.click("#sgrid .stile >> nth=1"); await shot("13_story")
        await page.click("#starPill"); await shot("14_shop")
        await b.close()
asyncio.run(main())
