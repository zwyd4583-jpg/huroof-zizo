"""Next letter on the slow phone: time from the tap until Zizo's voice starts, with optional extra CSS."""
import asyncio, pathlib, sys, statistics
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
PROBE = (HERE / "perf.py").read_text().split('PROBE = """')[1].split('"""')[0] if 'PROBE = """' in (HERE / "perf.py").read_text() else ""
CSS = sys.argv[1] if len(sys.argv) > 1 else ""
PORT = sys.argv[2] if len(sys.argv) > 2 else "8765"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await ctx.new_page(); cdp = await ctx.new_cdp_session(page)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 6})
        await page.add_init_script(BRIDGE + PROBE + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto(f"http://127.0.0.1:{PORT}/index.html"); await page.wait_for_timeout(1500)
        if CSS: await page.add_style_tag(content=CSS)
        await page.click("#goLearn"); await page.wait_for_timeout(800)
        await page.click("#grid .tile >> nth=2"); await page.wait_for_timeout(1500)
        lat = []
        for _ in range(8):
            n0 = await page.evaluate("window.__aud.length")
            t = await page.evaluate("(() => { const t = performance.now(); document.getElementById('nextL').click(); return t; })()")
            await page.wait_for_function(f"window.__aud.length > {n0}", timeout=6000)
            lat.append(round(await page.evaluate(f"window.__aud[{n0}] - {t}"))); await page.wait_for_timeout(1300)
        print(f"{CSS[:60]!r:64} median {statistics.median(lat):.0f} ms  {lat}")
        await b.close()
asyncio.run(main())
