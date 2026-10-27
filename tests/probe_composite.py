"""Which animations in the whole app cannot be handed to the graphics chip, and why."""
import asyncio, pathlib, collections
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = await ctx.new_page(); cdp = await ctx.new_cdp_session(page)
        await page.add_init_script(BRIDGE + """window.__zizoTest.intro = true; try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); localStorage.setItem('zizo-stars','40'); sessionStorage.setItem('s','1'); } } catch(e){}""")
        chunks = []; done = asyncio.get_event_loop().create_future()
        cdp.on("Tracing.dataCollected", lambda e: chunks.extend(e["value"])); cdp.on("Tracing.tracingComplete", lambda e: done.set_result(1))
        await cdp.send("Tracing.start", {"categories": "devtools.timeline,blink.animations,disabled-by-default-devtools.timeline", "transferMode": "ReportEvents"})
        await page.goto("http://127.0.0.1:8765/index.html")
        await page.wait_for_function("window.__zizoTest.introDone()", timeout=20000); await page.wait_for_timeout(1500)
        await page.click("#heroZizo", force=True); await page.wait_for_timeout(1700)
        await page.click("#goLearn"); await page.wait_for_timeout(800)
        await page.click("#grid .tile >> nth=2"); await page.wait_for_timeout(800); await page.click("#nextL"); await page.wait_for_timeout(800); await page.click("#backBtn")
        for t in ["numbers", "discover", "play", "trace", "stories", "letters"]:
            await page.click(f".tab[data-v={t}]"); await page.wait_for_timeout(600)
        await page.click(".tab[data-v=play]"); await page.click(".gamecard[data-mode=listen]")
        for r in range(3):
            await page.wait_for_timeout(300)
            st = await page.evaluate("window.__zizoTest.target()")
            w = page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first
            if r == 0: await w.click(); await page.wait_for_timeout(1200)
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')")
            await page.click(f"#choices .choice[data-o='{st['target']}']")
            await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden", timeout=20000)
        await page.click("#gamesBack"); await page.click(".tab[data-v=stories]"); await page.click("#sgrid .stile >> nth=0"); await page.wait_for_timeout(1500)
        await page.click("#nextS"); await page.wait_for_timeout(1000)
        await page.click("#starPill"); await page.wait_for_timeout(800); await page.click(".zizo", force=True); await page.wait_for_timeout(1600)
        await cdp.send("Tracing.end"); await done; await b.close()
    import json
    an = [e for e in chunks if e.get("name") == "Animation"]
    names = {}
    bad = collections.Counter(); ok = collections.Counter()
    for e in chunks:
        if e.get("name") != "Animation": continue
        d = (e.get("args") or {}).get("data") or {}
        if "displayName" in d: names[e.get("id2", {}).get("local") or e.get("id")] = d["displayName"] + " @ " + d.get("nodeName", "")[:40]
    for e in chunks:
        if e.get("name") != "Animation": continue
        d = (e.get("args") or {}).get("data") or {}
        if "compositeFailed" in d:
            n = names.get(e.get("id2", {}).get("local") or e.get("id"), "?")
            (bad if d["compositeFailed"] else ok)[(n, d["compositeFailed"], tuple(d.get("unsupportedProperties") or []))] += 1
    print("ON the graphics chip:", sorted(set(k[0] for k in ok)))
    print("NOT on the graphics chip:")
    for k, v in bad.most_common(): print("  ", k, v)
asyncio.run(main())
