"""Phone simulation of the parents' corner and the daily play limit."""
import asyncio, json, datetime, re
from playwright.async_api import async_playwright
from common import BRIDGE, ROOT, OUT, out

URL = "http://127.0.0.1:8765/index.html"
OUT = str(out("parents") / "parents")


def today(d=0):
    t = datetime.date.today() - datetime.timedelta(days=d)
    return f"{t.year}-{t.month}-{t.day}"


def seed(extra):
    return """window.__zizoTest = {}; try { if (!sessionStorage.getItem('seeded')) { localStorage.clear();
      localStorage.setItem('zizo-kid', JSON.stringify({name:'سارة', g:'f'}));
      localStorage.setItem('zizo-stars', '12');
      %s
      sessionStorage.setItem('seeded','1'); } } catch(e){}""" % extra


def digits(s):
    return int(re.sub(r"\D", "", s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))) or 0)


async def gate(page, wrong_first=False):
    q = await page.text_content("#paQ")
    a, b = [digits(x) for x in q.split("×")]
    if wrong_first:
        await page.fill("#paA", "1"); await page.click("#paGate button[type=submit]")
        err = await page.text_content("#paErr")
        assert "غير صحيحة" in err, err
        assert await page.is_hidden("#paBody")
        q = await page.text_content("#paQ"); a, b = [digits(x) for x in q.split("×")]
    await page.fill("#paA", "".join("٠١٢٣٤٥٦٧٨٩"[int(c)] for c in str(a * b)))  # Arabic digits from a phone keyboard
    await page.click("#paGate button[type=submit]")
    assert await page.is_visible("#paBody")


async def main():
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        # 1) real play fills the stats: open letters, answer a game with mistakes, then look
        await page.add_init_script(seed(""))
        await page.goto(URL); await page.wait_for_timeout(800)
        await page.click("#goLearn")
        for k in range(4):
            await page.click(f"#grid .tile >> nth={k}"); await page.click("#backBtn")
        await page.click(".tab[data-v=play]")
        await page.click(".gamecard[data-mode=listen]")
        for rnd in range(5):
            await page.wait_for_timeout(250)
            st = await page.evaluate("window.__zizoTest ? window.__zizoTest.target() : null")
            if st is None:
                break
            w = page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first
            await w.click(); await page.wait_for_timeout(80)
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')"); await page.click(f"#choices .choice[data-o='{st['target']}']"); await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden || !document.getElementById('stageEnd').hidden", timeout=20000)
        stats = await page.evaluate("JSON.parse(localStorage.getItem('zizo-stats'))")
        assert len(stats["seen"]["ar"]) >= 4, stats["seen"]
        assert stats["games"].get("listen", {}).get("ok", 0) >= 1, stats["games"]
        assert stats["earned"] >= 1
        await page.evaluate("window.__back && window.__back()")
        await page.evaluate("document.getElementById('welcome').hidden = false")
        await page.click("#openParents")
        await gate(page, wrong_first=True)
        await page.screenshot(path=OUT + "-1.png", full_page=False)
        txt = await page.text_content("#paBody")
        assert "سارة تدرّبت" in txt, txt[:300]
        assert "اسمع واختر" in txt
        await page.click("#paClose")
        assert await page.is_hidden("#parents")
        await ctx.close()

        # 2) a full report with a week of play, and the daily limit stopping play
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        days = {today(i): s for i, s in enumerate([15 * 60 + 5, 1200, 0, 2400, 600, 1800, 300])}
        st = {"since": today(6), "days": days, "earned": 57, "games": {"listen": {"ok": 20, "bad": 6}, "math": {"ok": 8, "bad": 9}, "enWord": {"ok": 10, "bad": 1}},
              "seen": {"ar": {str(i): 2 for i in range(14)}, "en": {"0": 1, "1": 1}, "num": {str(i): 1 for i in range(10)}, "enNum": {}},
              "ok": {"ar": {str(i): 3 for i in range(9)}, "en": {}, "num": {"2": 4}, "enNum": {}},
              "bad": {"ar": {"3": 5, "16": 4}, "en": {}, "num": {"6": 3}, "enNum": {}},
              "traced": {"ar": {"0": 1, "1": 2}, "en": {}, "num": {}, "enNum": {}}}
        await page.add_init_script(seed("localStorage.setItem('zizo-stats', %s); localStorage.setItem('zizo-parent', '{\"limit\":15}');" % json.dumps(json.dumps(st, ensure_ascii=False), ensure_ascii=False)))
        await page.goto(URL); await page.wait_for_timeout(900)
        assert await page.is_visible("#rest"), "rest screen should show when today's time is used up"
        await page.screenshot(path=OUT + "-rest.png")
        await page.click("#restParents")
        await gate(page)
        await page.screenshot(path=OUT + "-2.png", full_page=False)
        body = await page.text_content("#paBody")
        assert "انتهى وقت اليوم" in body, body[:400]
        assert "حرف الثاء" in body  # 5 mistakes on letter 3
        await page.click("#paExtra")
        body = await page.text_content("#paBody")
        assert "بقي اليوم" in body, body[:400]
        h = await page.evaluate("document.getElementById('parents').scrollHeight")
        for y in range(0, h, 700):
            await page.evaluate(f"document.getElementById('parents').scrollTo(0,{y})")
            await page.screenshot(path=f"{OUT}-2-{y // 700}.png")
        await page.click("#paClose")
        assert await page.is_hidden("#rest"), "extra time should let play continue"
        # limit off
        await page.evaluate("document.getElementById('welcome').hidden = false")
        await page.click("#openParents"); await gate(page)
        await page.click("#paLimit button[data-m='0']")
        assert "لا يوجد حدّ" in await page.text_content("#paLimitNote")
        overflow = await page.evaluate("document.getElementById('parents').scrollWidth > document.getElementById('parents').clientWidth")
        assert not overflow, "sideways scroll in the parents' corner"
        await b.close()
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))


asyncio.run(main())
