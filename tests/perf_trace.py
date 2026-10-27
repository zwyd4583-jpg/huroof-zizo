"""Where the long frames come from: a performance trace of tab switching and a game, slowed 6x."""
import asyncio, json, pathlib, collections
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 6})
        await page.add_init_script(BRIDGE + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(1500)
        await page.click("#goLearn"); await page.wait_for_timeout(800)
        await b.start_tracing(page=page, path=str(HERE / "trace.json"), categories=["devtools.timeline", "disabled-by-default-devtools.timeline", "v8.execute", "blink.user_timing"])
        for t in ["numbers", "discover", "play", "trace", "stories", "letters"]:
            await page.click(f".tab[data-v={t}]"); await page.wait_for_timeout(700)
        await page.click(".tab[data-v=play]"); await page.wait_for_timeout(500)
        await page.click(".gamecard[data-mode=listen]"); await page.wait_for_timeout(2500)
        for r in range(2):
            st = await page.evaluate("window.__zizoTest.target()")
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')")
            await page.click(f"#choices .choice[data-o='{st['target']}']")
            await page.wait_for_function("() => !document.body.contains(window.__oldc)", timeout=20000)
            await page.wait_for_timeout(1500)
        await b.stop_tracing()
        await b.close()
    ev = json.load(open(HERE / "trace.json"))
    ev = ev["traceEvents"] if isinstance(ev, dict) else ev
    main_tid = None
    for e in ev:
        if e.get("name") == "thread_name" and e.get("args", {}).get("name") == "CrRendererMain": main_tid = (e["pid"], e["tid"])
    tasks = [e for e in ev if e.get("ph") == "X" and (e["pid"], e["tid"]) == main_tid and e.get("name") in ("RunTask", "ThreadControllerImpl::RunTask") and e.get("dur", 0) > 50000]
    print(len(tasks), "main-thread tasks over 50 ms")
    for t in sorted(tasks, key=lambda t: -t["dur"])[:8]:
        s, d = t["ts"], t["dur"]
        kids = [e for e in ev if e.get("ph") == "X" and (e["pid"], e["tid"]) == main_tid and s <= e["ts"] <= s + d and e is not t]
        agg = collections.Counter()
        for k in kids:
            if k["name"] in ("Layout", "UpdateLayoutTree", "Paint", "PrePaint", "Layerize", "FunctionCall", "EvaluateScript", "ParseHTML", "HitTest", "RecalculateStyles", "UpdateLayerTree", "CompositeLayers", "Decode Image", "ParseAuthorStyleSheet", "v8.compile", "TimerFire", "EventDispatch", "FireAnimationFrame", "Commit", "MarkDOMContent"):
                agg[k["name"]] += k.get("dur", 0)
        fn = [k.get("args", {}).get("data", {}).get("functionName") or k.get("args", {}).get("data", {}).get("type") for k in kids if k["name"] in ("FunctionCall", "EventDispatch", "TimerFire")]
        print(f"{d/1000:6.0f} ms:", ", ".join(f"{n} {v/1000:.0f}" for n, v in agg.most_common(6)), "| js:", [f for f in fn if f][:5])
asyncio.run(main())
