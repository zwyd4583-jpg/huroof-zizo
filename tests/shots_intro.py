import asyncio, pathlib
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
        page = await ctx.new_page()
        await page.add_init_script(BRIDGE + """window.__zizoTest.intro = true; try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html")
        await page.wait_for_function("performance.getEntriesByName('zizo-intro-run').length > 0", timeout=10000)
        t0 = await page.evaluate("performance.getEntriesByName('zizo-intro-run')[0].startTime")
        for k, ms in enumerate([300, 1200, 1700, 2300, 2900, 3700, 4900]):
            now = await page.evaluate("performance.now()")
            if t0 + ms > now: await page.wait_for_timeout(t0 + ms - now)
            await page.screenshot(path=str(out("intro") / f"intro_{k}.png"))
        await b.close()
asyncio.run(main())
