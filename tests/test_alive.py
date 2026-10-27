"""Phone simulation: Zizo blinks, reacts to taps, encourages after a wrong answer; screens and tiles move in."""
import asyncio, pathlib
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out

async def main():
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)).new_page()
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        await page.add_init_script(BRIDGE + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(900)
        # blinking eyes in the header and on the welcome screen
        n = await page.evaluate("document.querySelectorAll('.zizo .zblink, #heroZizo .zblink').length")
        if n < 2: problems.append(f"blinking eyes missing ({n})")
        # tapping Zizo on the welcome screen
        await page.click("#heroZizo", force=True); await page.wait_for_timeout(200)
        if not await page.evaluate("!!document.querySelector('#heroZizo .ztap.go')"): problems.append("welcome Zizo did not wiggle")
        await page.wait_for_timeout(1500)
        if await page.evaluate("!!document.querySelector('#heroZizo .ztap')"): problems.append("welcome Zizo stuck in the tap look")
        await page.click("#goLearn"); await page.wait_for_timeout(150)
        # the letters screen came in and its tiles were numbered for the stagger
        i = await page.evaluate("getComputedStyle(document.querySelector('#grid .tile:nth-child(10)')).getPropertyValue('--i').trim()")
        if i != "9": problems.append(f"tiles not staggered ({i!r})")
        await page.wait_for_timeout(900)
        await page.screenshot(path=str(HERE / "alive-grid.png"))
        # tapping the header Zizo: a funny line in the bubble, then the old text again
        before = await page.text_content("#bubble")
        await page.click(".host .zizo", force=True); await page.wait_for_timeout(250)
        line = await page.text_content("#bubble")
        if line == before: problems.append("tapping Zizo did not change the bubble")
        await page.screenshot(path=str(HERE / "alive-tap.png"))
        await page.wait_for_timeout(1600)
        if await page.text_content("#bubble") != before: problems.append("bubble did not go back after the tap")
        await page.click(".host .zizo", force=True); await page.wait_for_timeout(1700); await page.click(".host .zizo", force=True); await page.wait_for_timeout(100)
        taps = await page.evaluate("window.__zizoTest.taps")
        if len(taps) < 3 or any(a == b for a, b in zip(taps, taps[1:])): problems.append(f"tap lines repeat: {taps}")
        # a wrong answer: Zizo comes in thinking, not from the bottom
        await page.click(".tab[data-v=play]"); await page.click(".gamecard[data-mode=listen]")
        for r in range(3):
            await page.wait_for_timeout(400)
            st = await page.evaluate("window.__zizoTest.target()")
            await page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first.click()
            await page.wait_for_timeout(450)
            if r == 0: await page.screenshot(path=str(HERE / "alive-oops.png"))
            await page.wait_for_timeout(1300)
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')"); await page.click(f"#choices .choice[data-o='{st['target']}']")
            await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden || !document.getElementById('stageEnd').hidden", timeout=20000)
        cheers = await page.evaluate("window.__zizoTest.cheers")
        oops = [c for c in cheers if c.split(':')[1] in ('think', 'cheerup')]
        if len(oops) != 3: problems.append(f"wrong answers: {cheers}")
        if any(c.startswith('bottom:') for c in oops): problems.append("encouragement came from the bottom")
        print("jump-ins:", cheers)
        await b.close()
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))
asyncio.run(main())
