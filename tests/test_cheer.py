"""Phone simulation: on every right answer Zizo jumps in with a new look, from a different side, with the praise."""
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
          localStorage.setItem('zizo-kid', JSON.stringify({name:'زينب', g:'f'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(900)
        await page.click("#goLearn"); await page.click(".tab[data-v=play]")
        for mode in ["listen", "animal"]:
            await page.click(f".gamecard[data-mode={mode}]")
            for r in range(5):
                await page.wait_for_timeout(300)
                st = await page.evaluate("window.__zizoTest.target()")
                if r == 1:  # a wrong answer first: Zizo comes to encourage, with his thinking or cheering-up look
                    await page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first.click()
                    await page.wait_for_timeout(200)
                    last = (await page.evaluate("window.__zizoTest.cheers || []"))[-1:]
                    if not last or last[0].split(':')[1] not in ('think', 'cheerup'): problems.append(f"wrong answer: {last}")
                    await page.wait_for_timeout(1500)
                await page.evaluate("window.__oldc = document.querySelector('#choices .choice')"); await page.click(f"#choices .choice[data-o='{st['target']}']")
                await page.wait_for_timeout(500)
                if mode == "listen": await page.screenshot(path=str(HERE / f"cheer-{r}.png"))
                vis = await page.evaluate("!document.getElementById('cheer').hidden")
                if not vis: problems.append("Zizo did not jump in")
                ow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                if ow: problems.append("sideways scroll while Zizo jumps in")
                # the bubble and Zizo are inside the screen at the peak
                box = await page.evaluate("(() => { const r = document.querySelector('.cheer-in').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })()")
                if box[0] < -2 or box[1] > 392 or box[2] < 0 or box[3] > 844: problems.append(f"Zizo partly off screen: {box}")
                await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden || !document.getElementById('stageEnd').hidden", timeout=20000)
                try: await page.wait_for_function("() => document.getElementById('cheer').hidden", timeout=2500)
                except Exception: problems.append("Zizo stayed on screen")
            await page.click("#gamesBack")
        every = await page.evaluate("window.__zizoTest.cheers")
        cheers = [c for c in every if c.split(':')[1] not in ('think', 'cheerup')]
        sides = [c.split(':')[0] for c in every]; poses = [c.split(':')[1] for c in cheers]
        if any(a == b for a, b in zip(sides, sides[1:])): problems.append(f"same side twice: {sides}")
        if any(a == b for a, b in zip(poses, poses[1:])): problems.append(f"same look twice: {poses}")
        if len(set(sides)) < 3 or len(set(poses)) < 4: problems.append(f"little variety: {sides} {poses}")
        print(len(cheers), "jump-ins:", ", ".join(cheers))
        await b.close()
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))
asyncio.run(main())
