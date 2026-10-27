"""Which of the app's own functions take the time when switching tabs and answering (CPU slowed 6x)."""
import asyncio, pathlib, collections
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out

def summarize(prof, top=14):
    nodes = {n["id"]: n for n in prof["nodes"]}
    self_t = collections.Counter()
    dt = dict(zip(prof["samples"], prof["timeDeltas"]))
    for sid, d in zip(prof["samples"], prof["timeDeltas"]):
        n = nodes[sid]; cf = n["callFrame"]
        self_t[(cf["functionName"] or "(anon)") + ":" + str(cf.get("lineNumber", 0) + 1)] += d
    # inclusive time per app function
    parent = {}
    for n in prof["nodes"]:
        for c in n.get("children", []): parent[c] = n["id"]
    incl = collections.Counter()
    for sid, d in zip(prof["samples"], prof["timeDeltas"]):
        seen = set(); x = sid
        while x is not None:
            cf = nodes[x]["callFrame"]
            if "index.html" in cf.get("url", ""):
                k = (cf["functionName"] or "(anon)") + ":" + str(cf.get("lineNumber", 0) + 1)
                if k not in seen: incl[k] += d; seen.add(k)
            x = parent.get(x)
    print("  inclusive (ms):", ", ".join(f"{k} {v/1000:.0f}" for k, v in incl.most_common(top)))
    print("  self (ms):", ", ".join(f"{k} {v/1000:.0f}" for k, v in self_t.most_common(8)))

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
        await cdp.send("Profiler.enable"); await cdp.send("Profiler.setSamplingInterval", {"interval": 200})
        await cdp.send("Profiler.start")
        for t in ["numbers", "discover", "play", "trace", "stories", "letters"]:
            await page.click(f".tab[data-v={t}]"); await page.wait_for_timeout(700)
        prof = (await cdp.send("Profiler.stop"))["profile"]
        print("TABS"); summarize(prof)
        await page.click(".tab[data-v=play]"); await page.wait_for_timeout(500)
        await page.click(".gamecard[data-mode=listen]"); await page.wait_for_timeout(2500)
        await cdp.send("Profiler.start")
        for r in range(2):
            st = await page.evaluate("window.__zizoTest.target()")
            await page.evaluate("window.__oldc = document.querySelector('#choices .choice')")
            await page.click(f"#choices .choice[data-o='{st['target']}']")
            await page.wait_for_function("() => !document.body.contains(window.__oldc)", timeout=20000)
            await page.wait_for_timeout(1500)
        prof = (await cdp.send("Profiler.stop"))["profile"]
        print("GAME"); summarize(prof)
        await b.close()
asyncio.run(main())
