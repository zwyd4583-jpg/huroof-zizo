"""Phone simulation of the letter stories: list, reading with pages turning by themselves, the question, the end."""
import asyncio, json, pathlib
from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
OUT = str(out("stories") / "stories")


async def main():
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        await page.add_init_script(BRIDGE + """try { if (!sessionStorage.getItem('seeded')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'سارة', g:'f'})); sessionStorage.setItem('seeded','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(900)
        await page.click("#goLearn")
        await page.click(".tab[data-v=stories]"); await page.wait_for_timeout(300)
        n = await page.locator("#sgrid .stile").count()
        if n != 28: problems.append(f"{n} stories listed")
        await page.screenshot(path=OUT + "-grid.png")
        over = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        if over: problems.append("sideways scroll on the stories list")
        # story of ب: the phone voice stands in for the recordings; pages turn by themselves
        played0 = len(await page.evaluate("window.__zizoTest.played || []"))
        await page.click("#sgrid .stile >> nth=1"); await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + "-page1.png")
        hl = await page.locator("#sCard .stext .hl").all_text_contents()
        if "بَطَّةٌ" not in hl: problems.append(f"highlighted words: {hl}")
        for k in range(40):  # Zizo's recorded voice reads slowly: up to about a minute
            if await page.locator("#sCard .sask").count(): break
            await page.wait_for_timeout(1400)
        spoken = await page.evaluate("window.__spoken")
        played = (await page.evaluate("window.__zizoTest.played || []"))[played0:]
        if not await page.locator("#sCard .choices .choice").count():
            problems.append(f"no question after the last page; said: {spoken} {played}")
        read = len([x for x in spoken if 'بَطْبُوطَة' in x or 'البَطّات' in x]) + len(played)
        if read < 5: problems.append(f"pages not all read: {spoken} {played}")
        print("story read with", len(played), "recordings and", len(spoken), "phone-voice lines")
        await page.screenshot(path=OUT + "-ask.png")
        # a wrong answer, then the right one
        target = "🦆"
        wrong = page.locator(f"#sCard .choice:not(:text-is('{target}'))").first
        await wrong.click(); await page.wait_for_timeout(200)
        await page.locator(f"#sCard .choice:text-is('{target}')").click()
        await page.wait_for_timeout(4000)
        if not await page.locator("#sNext").count(): problems.append("no end card")
        await page.screenshot(path=OUT + "-end.png")
        done = await page.evaluate("JSON.parse(localStorage.getItem('zizo-stories'))")
        if done != [1]: problems.append(f"finished stories saved as {done}")
        # leaving mid-story stops it: no more pages are read
        await page.click("#sNext"); await page.wait_for_timeout(200)
        await page.click(".tab[data-v=letters]")
        before = len(await page.evaluate("window.__spoken")); await page.wait_for_timeout(4000)
        after = len(await page.evaluate("window.__spoken"))
        if after != before: problems.append("story kept reading after leaving it")
        # from a letter: its story
        await page.click("#grid .tile >> nth=11")
        txt = await page.text_content("#toStoryText")
        if txt != "قصة حرف السين": problems.append(f"letter button says {txt}")
        await page.click("#toStory"); await page.wait_for_timeout(300)
        if "سمسمة" not in (await page.text_content("#sCard")): problems.append("letter button opened the wrong story")
        await page.screenshot(path=OUT + "-sin.png")
        # every page of every story fits the phone without sideways scroll
        for i in range(28):
            await page.evaluate(f"window.__back && 0")
            await page.click(".tab[data-v=stories]"); await page.click(f"#sgrid .stile >> nth={i}")
            for k in range(5):
                if k: await page.click("#nextS")
                ow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                h = await page.evaluate("document.querySelector('#sCard .stext').getBoundingClientRect().height")
                if ow: problems.append(f"story {i} page {k}: sideways scroll")
                if h > 190: problems.append(f"story {i} page {k}: text {h:.0f}px tall")
        # tabs still fit
        tw = await page.evaluate("Array.from(document.querySelectorAll('.tab span')).map(s => s.scrollWidth > s.clientWidth + 1)")
        if any(tw): problems.append("a tab label is cut")
        await page.screenshot(path=OUT + "-tabs.png", clip={"x": 0, "y": 760, "width": 390, "height": 84})
        await b.close()
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))

asyncio.run(main())
