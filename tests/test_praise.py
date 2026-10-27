"""Phone simulation: Zizo's praise is never cut off by the next question (games and tracing)."""
import asyncio, pathlib
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
SPY = """
(() => { const AC = window.AudioContext || window.webkitAudioContext; const orig = AC.prototype.createBufferSource;
  AC.prototype.createBufferSource = function(){ const s = orig.call(this); const st = s.start.bind(s), sp = s.stop.bind(s);
    s.start = (...a) => { s.__t0 = performance.now(); s.__on = true; window.__playing = (window.__playing || 0) + 1;
      s.addEventListener('ended', () => { if (s.__on){ s.__on = false; window.__playing--; } }); return st(...a); };
    s.stop = (...a) => { if (s.__on && performance.now() - s.__t0 < s.buffer.duration * 1000 - 120) (window.__cut = window.__cut || []).push(Math.round(performance.now() - s.__t0) + '/' + Math.round(s.buffer.duration * 1000) + ' after ' + JSON.stringify(((window.__zizoTest && window.__zizoTest.played) || []).slice(-2)) + ' screen ' + (document.querySelector('#gameArea') && !document.querySelector('#gameArea').hidden ? 'game' : 'menu'));
      if (s.__on){ s.__on = false; window.__playing--; } return sp(...a); };
    return s; }; })();
"""

async def main():
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)).new_page()
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        await page.add_init_script(BRIDGE + SPY + """try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html"); await page.wait_for_timeout(1500)
        # let Zizo finish his hello: silence that lasts (the hello is three recordings, with a gap between them)
        for _ in range(40):
            await page.wait_for_function("() => !window.__playing", timeout=12000); await page.wait_for_timeout(600)
            if not await page.evaluate("window.__playing"): break
        await page.click("#goLearn"); await page.click(".tab[data-v=play]")
        gaps = []
        for mode in ["listen", "math", "animal"]:
            await page.wait_for_timeout(300); await page.wait_for_function("() => !window.__playing", timeout=12000)
            await page.click(f".gamecard[data-mode={mode}]"); await page.wait_for_timeout(600)
            for r in range(5):
                # a patient child: answer once Zizo has finished asking
                await page.wait_for_timeout(400)
                await page.wait_for_function("() => !window.__playing", timeout=12000)
                await page.wait_for_timeout(200)
                st = await page.evaluate("window.__zizoTest.target()")
                await page.evaluate("window.__old = document.querySelector('#choices .choice'); window.__t = performance.now()")
                await page.click(f"#choices .choice[data-o='{st['target']}']")
                await page.wait_for_function("() => !document.body.contains(window.__old) || !document.getElementById('endArea').hidden", timeout=15000)
                gaps.append(round(await page.evaluate("performance.now() - window.__t")))
            await page.wait_for_timeout(500)
            await page.wait_for_function("() => !window.__playing", timeout=15000)  # the end-of-game praise
            await page.click("#gamesBack")
        cut = await page.evaluate("window.__cut || []")
        if cut: problems.append(f"speech cut off (played ms / length ms): {cut}")
        print("time to the next question (ms):", gaps)
        await b.close()
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))
asyncio.run(main())
