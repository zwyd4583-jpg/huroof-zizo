"""Tab switching and next-letter, traced on the slow phone simulation: what the main thread spends time on."""
import asyncio, pathlib, collections, sys
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await ctx.new_page(); cdp = await ctx.new_cdp_session(page)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 6})
        await page.add_init_script(BRIDGE + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(1500)
        await page.click("#goLearn"); await page.wait_for_timeout(1000)
        chunks = []; done = asyncio.get_event_loop().create_future()
        cdp.on("Tracing.dataCollected", lambda e: chunks.extend(e["value"])); cdp.on("Tracing.tracingComplete", lambda e: done.set_result(1))
        await cdp.send("Tracing.start", {"categories": "devtools.timeline,disabled-by-default-devtools.timeline,cc,blink", "transferMode": "ReportEvents"})
        for t in ["numbers", "discover", "play", "trace", "stories", "letters"]:
            await page.click(f".tab[data-v={t}]"); await page.wait_for_timeout(700)
        await page.click("#grid .tile >> nth=2"); await page.wait_for_timeout(600)
        for _ in range(3): await page.click("#nextL"); await page.wait_for_timeout(600)
        await cdp.send("Tracing.end"); await done; await b.close()
    ev = chunks
    names = {(e["pid"], e["tid"]): e["args"]["name"] for e in ev if e.get("name") == "thread_name"}
    by = collections.defaultdict(collections.Counter)
    for e in ev:
        if e.get("ph") != "X": continue
        th = names.get((e["pid"], e["tid"]), "?")
        if th in ("CrRendererMain", "Compositor") or th.startswith("CompositorTileWorker"):
            if e["name"] in ("UpdateLayoutTree", "Layout", "Paint", "PrePaint", "Layerize", "RasterTask", "TileManager::RunRasterTask", "FunctionCall", "TimerFire", "ParseHTML", "Commit", "HitTest", "ImageDecodeTask", "PaintImage"):
                by[th.split(" ")[0].rstrip("0123456789/")][e["name"]] += e.get("dur", 0)
    for th, c in by.items():
        print(th, ", ".join(f"{k} {v/1000:.0f}ms" for k, v in c.most_common(8)))
    mains = {k for k, v in names.items() if v == "CrRendererMain"}
    t0 = min(e["ts"] for e in ev if e.get("ts"))
    tasks = sorted([e for e in ev if (e["pid"], e["tid"]) in mains and e.get("ph") == "X" and e.get("name") in ("RunTask", "ThreadControllerImpl::RunTask")], key=lambda e: -e.get("dur", 0))[:8]
    for e in tasks:
        st, en = e["ts"], e["ts"] + e["dur"]; inner = collections.Counter()
        for x in ev:
            if (x["pid"], x["tid"]) == (e["pid"], e["tid"]) and x.get("ph") == "X" and st <= x["ts"] < en and x is not e and x["name"] in ("UpdateLayoutTree", "Layout", "Paint", "PrePaint", "Layerize", "FunctionCall", "Commit", "HitTest"):
                inner[x["name"]] += x.get("dur", 0)
        print(f"  {(st - t0)/1000:6.0f} {e['dur']/1000:5.0f}  " + ", ".join(f"{k} {v/1000:.0f}" for k, v in inner.most_common(4)))
asyncio.run(main())
