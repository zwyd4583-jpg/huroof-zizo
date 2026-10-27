"""Phone simulation with Zizo's recorded voice: every sentence the app says must have a recording.
Plays through all sections as a girl with a name, then as a boy without a name."""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright

PROJ = ROOT
from common import BRIDGE, ROOT, OUT, out


def seed(kid):
    return """
try {
  if (!sessionStorage.getItem('seeded')) {
    localStorage.clear();
    localStorage.setItem('zizo-kid', JSON.stringify(%s));
    localStorage.setItem('zizo-stars', '30');
    sessionStorage.setItem('seeded', '1');
  }
} catch (e) {}
""" % json.dumps(kid, ensure_ascii=False)


async def run(p, kid, problems):
    b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await b.new_context(viewport={"width": 400, "height": 800}, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    await page.add_init_script(BRIDGE + seed(kid))
    page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
    await page.goto("http://127.0.0.1:8765/index.html")
    await page.wait_for_timeout(800)

    async def answer(rounds, wrong=True):
        for rnd in range(rounds):
            await page.wait_for_timeout(200)
            st = await page.evaluate("window.__zizoTest.target()")
            if wrong and rnd < 2:
                w = page.locator(f"#choices .choice:not([data-o='{st['target']}']):not([disabled])").first
                if await w.count():
                    await w.click(); await page.wait_for_timeout(100)
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')"); await page.click(f"#choices .choice[data-o='{st['target']}']")
            await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden || !document.getElementById('stageEnd').hidden", timeout=20000)
        await page.wait_for_timeout(300)

    await page.click("#goLearn")
    # letters, Arabic and English
    for lang in ["ar", "en"]:
        await page.click(f".lchip[data-lang={lang}]")
        for k in range(0, 28 if lang == "ar" else 26, 1):
            if k >= (28 if lang == "ar" else 26): break
            await page.click(f"#grid .tile >> nth={k}")
            await page.click("#sayLetterBtn"); await page.click("#sayWordBtn")
            await page.click("#backBtn")
    await page.click(".lchip[data-lang=ar]")
    # numbers, Arabic and English: open each, count all
    await page.click(".tab[data-v=numbers]")
    for lang in ["ar", "en"]:
        await page.click(f".nchip[data-lang={lang}]")
        for k in range(10):
            await page.click(f"#ngrid .tile >> nth={k}")
            objs = page.locator("#nBox .obj")
            for j in range(await objs.count()):
                await objs.nth(j).click()
            await page.wait_for_timeout(50)
            await page.click(".tab[data-v=numbers]")
    # discover: every item of every topic
    await page.click(".tab[data-v=discover]")
    for topic in ["colors", "shapes", "animals", "foods", "body", "jobs"]:
        await page.click(f".dchip[data-topic={topic}]")
        n = await page.locator("#dgrid .dtile").count()
        await page.click("#dgrid .dtile >> nth=0")
        for _ in range(n):
            await page.click("#sayDBtn"); await page.click("#nextD")
        await page.click("#dbackBtn")
    # every game
    await page.click(".tab[data-v=play]")
    modes = await page.locator(".gamecard").evaluate_all("els => els.map(e => e.dataset.mode)")
    for m in modes:
        await page.click(f".gamecard[data-mode={m}]")
        await answer(5)
        await page.click("#gamesBack")
    # today's challenge, journey stage 1 and a locked stage
    await page.click(".daily-card"); await answer(5); await page.click("#gamesBack")
    await page.click(".journey-card:not(.daily-card)")
    await page.wait_for_timeout(300)
    await page.locator(".node[data-i='5']").click(force=True)
    await page.locator(".node[data-i='0']").click(force=True)
    await answer(5)
    await page.click("#stageMap")
    # tracing: a scribble, too little, and the four kinds
    await page.click(".tab[data-v=trace]")
    for kind in ["letters", "numbers", "en", "enNum"]:
        await page.click(f".tchip[data-kind={kind}]")
        await page.click("#doneT")
        await page.click("#tLabel")
        await page.click("#nextT")
    await page.click(".tchip[data-kind=letters]")
    await page.evaluate("""() => { const cv = document.getElementById('cv'), r = cv.getBoundingClientRect(), S = r.width;
      const ev = (t, x, y) => cv.dispatchEvent(new PointerEvent(t, { clientX: r.left + x, clientY: r.top + y, pointerId: 1, bubbles: true }));
      ev('pointerdown', 10, 10); for (let a = 0; a < 6.3; a += 0.1) ev('pointermove', S/2 + S*0.45*Math.cos(a), S/2 + S*0.45*Math.sin(a)); ev('pointerup', 10, 10); }""")
    await page.click("#doneT")
    # shop: buy, look at something too dear
    await page.click("#starPill")
    await page.wait_for_timeout(200)
    while await page.locator(".prize.can").count():
        await page.locator(".prize.can").first.click(); await page.click("#buyPrize"); await page.wait_for_timeout(80)
    if await page.locator(".prize.cant").count():
        await page.locator(".prize.cant").first.click(); await page.click("#laterPrize")
    await page.locator(".prize:not(.can):not(.cant)").first.click()
    # welcome again (back button) and first-run greeting
    await page.evaluate("window.__back && window.__back()")
    await page.evaluate("window.__back && window.__back()")
    res = await page.evaluate("({ missing: window.__zizoTest.missing || [], played: (window.__zizoTest.played || []).length })")
    spoken = await page.evaluate("window.__spoken.length")
    await page.evaluate("localStorage.removeItem('zizo-kid')")
    await page.reload(); await page.wait_for_timeout(800)
    r2 = await page.evaluate("({ missing: window.__zizoTest.missing || [], played: window.__zizoTest.played || [] })")
    res["missing"] += r2["missing"]; res["played"] += len(r2["played"]); spoken += await page.evaluate("window.__spoken.length")
    if not r2["played"]: problems.append("first-run greeting not played from a recording")
    await b.close()
    return res, spoken


async def main():
    problems = []
    async with async_playwright() as p:
        total_missing = set()
        for kid in [{"name": "سارة", "g": "f"}, {"name": "", "g": "m", "set": True}]:
            res, spoken = await run(p, kid, problems)
            total_missing |= set(res["missing"])
            print(f"{kid}: {res['played']} sentences played from recordings, {len(set(res['missing']))} without a recording, phone voice used {spoken} times")
        for m in sorted(total_missing):
            print("  MISSING:", m)
    print("PROBLEMS:" if problems else "no problems"); print("\n".join(problems[:20]))

asyncio.run(main())
