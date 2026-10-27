"""The opening, frame by frame, on a slow phone simulation (CPU slowed down).
Records a Chrome trace from page load to the end of the opening and reports what the main thread did,
how many times the page had to be repainted, and how many frames were late or dropped."""
import asyncio, json, pathlib, sys, collections
from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
RATE = float(sys.argv[1]) if len(sys.argv) > 1 else 6
CATS = ",".join(["devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.frame",
                 "blink", "cc", "benchmark", "loading", "v8.execute", "blink.user_timing"])


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2.75)
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": RATE})
        await page.add_init_script(BRIDGE + """window.__zizoTest.intro = true;
          window.__fr = []; (function loop(t0){ requestAnimationFrame(function(t){ if (t0) window.__fr.push([t, t - t0]); loop(t); }); })(0);
          try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        chunks = []
        done = asyncio.get_event_loop().create_future()
        cdp.on("Tracing.dataCollected", lambda e: chunks.extend(e["value"]))
        cdp.on("Tracing.tracingComplete", lambda e: done.set_result(True))
        await cdp.send("Tracing.start", {"categories": CATS, "transferMode": "ReportEvents"})
        await page.goto("http://127.0.0.1:8765/index.html")
        await page.wait_for_function("window.__zizoTest.introDone && window.__zizoTest.introDone()", timeout=30000)
        await page.wait_for_timeout(1500)
        fr = await page.evaluate("window.__fr.map(f => f[1])")
        frt = await page.evaluate("window.__fr")
        marks = await page.evaluate("Object.fromEntries(performance.getEntriesByType('mark').map(m => [m.name, m.startTime]))")
        fonts = await page.evaluate("performance.getEntriesByType('resource').filter(r => /ttf|index.json|mp3/.test(r.name)).map(r => [r.name.split('/').pop(), Math.round(r.startTime), Math.round(r.responseEnd)])")
        await cdp.send("Tracing.end")
        await done
        await b.close()

    ev = chunks
    # the renderer's main thread
    names = {(e["pid"], e["tid"]): e["args"]["name"] for e in ev if e.get("name") == "thread_name"}
    main_t = [k for k, v in names.items() if v == "CrRendererMain"]
    mains = set(main_t)
    tasks = [e for e in ev if (e["pid"], e["tid"]) in mains and e.get("ph") == "X" and e.get("name") in ("RunTask", "ThreadControllerImpl::RunTask")]
    tasks.sort(key=lambda e: -e.get("dur", 0))
    t0 = min(e["ts"] for e in ev if e.get("ts"))
    print(f"CPU slowed {RATE}x | rAF frames {len(fr)}, late >34ms: {sum(1 for x in fr if x > 34)}, >50ms: {sum(1 for x in fr if x > 50)}, worst {max(fr):.0f}ms")
    kinds = collections.Counter(); kdur = collections.Counter()
    for e in ev:
        if (e["pid"], e["tid"]) in mains and e.get("ph") == "X" and e.get("name") in (
                "UpdateLayoutTree", "Layout", "Paint", "PrePaint", "Layerize", "ParseHTML", "FunctionCall", "TimerFire",
                "FireAnimationFrame", "EvaluateScript", "v8.compile", "ParseAuthorStyleSheet", "HitTest", "Commit", "PaintImage", "Decode Image"):
            kinds[e["name"]] += 1; kdur[e["name"]] += e.get("dur", 0)
    run = marks.get('zizo-intro-run', 0)
    print("marks (ms from intro start):", {k: round(v - run) for k, v in marks.items()})
    print("files (start, end, ms from intro start):", [(n, a - run, e - run) for n, a, e in fonts][:12])
    print("late frames (ms from intro start, length):", [(round(t - run), round(d)) for t, d in frt if d > 34])
    # trace time of the intro start: the user-timing mark
    um = [e for e in ev if e.get("name") == "zizo-intro-run"]
    trun = um[0]["ts"] if um else t0
    print("main thread work:", ", ".join(f"{k} x{kinds[k]} {kdur[k]/1000:.0f}ms" for k in sorted(kdur, key=lambda k: -kdur[k])))
    print("longest main-thread tasks (start ms from intro start, length ms):")
    for e in tasks[:8]:
        st, en = e["ts"], e["ts"] + e["dur"]
        inner = collections.Counter()
        for x in ev:
            if (x["pid"], x["tid"]) == (e["pid"], e["tid"]) and x.get("ph") == "X" and st <= x["ts"] < en and x is not e and x.get("name") in kinds:
                inner[x["name"]] += x.get("dur", 0)
        print(f"  {(st - trun)/1000:7.0f} {e['dur']/1000:6.0f}  " + ", ".join(f"{k} {v/1000:.0f}" for k, v in inner.most_common(4)))
    # frames the compositor reported
    pr = [e for e in ev if e.get("name") == "PipelineReporter" and e.get("ph") in ("b", "X")]
    states = collections.Counter((e.get("args", {}).get("chrome_frame_reporter", {}) or {}).get("state", "?") for e in pr)
    print("compositor frames:", dict(states))
    anim = collections.Counter()
    for e in ev:
        if e.get("name") == "Animation" and e.get("ph") in ("n", "e", "b"):
            d = (e.get("args") or {}).get("data") or {}
            if "compositeFailed" in d or "unsupportedProperties" in d:
                anim[(d.get("compositeFailed"), tuple(d.get("unsupportedProperties") or []))] += 1
    print("animations not on the graphics chip (reason code, properties): count", dict(anim))


asyncio.run(main())
