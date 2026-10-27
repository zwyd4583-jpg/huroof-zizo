"""Phone simulation of the opening: it plays, says hello, hands over to the welcome screen; a tap skips it."""
import asyncio, pathlib
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out

async def run(p, kid, shots, problems, skip=False):
    b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)).new_page()
    page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
    seed = "localStorage.clear();" + (f"localStorage.setItem('zizo-kid', JSON.stringify({kid}));" if kid else "")
    await page.add_init_script(BRIDGE + "window.__zizoTest.intro = true; try { if (!sessionStorage.getItem('s')) { " + seed + " sessionStorage.setItem('s','1'); } } catch(e){}")
    await page.goto("http://127.0.0.1:8765/index.html")
    if skip:
        await page.wait_for_timeout(700)
        await page.click("#intro")
        await page.wait_for_timeout(600)
        if not await page.is_hidden("#intro"): problems.append("tap did not skip the opening")
        played = await page.evaluate("window.__zizoTest.played || []")
        if not played and not await page.evaluate("window.__spoken.length"): problems.append("no hello after skipping")
    else:
        t = 0
        for ms in shots:
            await page.wait_for_timeout(ms - t); t = ms
            await page.screenshot(path=str(HERE / f"intro-{ms}.png"))
            ow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            if ow: problems.append(f"sideways scroll at {ms} ms")
        await page.wait_for_timeout(5000 - t)
        if not await page.is_hidden("#intro"): problems.append("opening did not end")
        if not await page.evaluate("window.__zizoTest.introDone()"): problems.append("opening not marked done")
        played = await page.evaluate("window.__zizoTest.played || []")
        if len(played) != 1: problems.append(f"hello said {len(played)} times: {played}")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(HERE / "intro-after.png"))
        # buttons work after the opening
        if kid:
            await page.click("#goLearn")
            if not await page.is_hidden("#welcome"): problems.append("welcome buttons blocked after the opening")
    await b.close()

async def main():
    problems = []
    async with async_playwright() as p:
        await run(p, "{name:'سارة', g:'f'}", [600, 1200, 1700, 2300, 2900, 3600, 4400], problems)
        await run(p, "{name:'سارة', g:'f'}", [], problems, skip=True)
        await run(p, None, [], problems, skip=True)
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))
asyncio.run(main())
