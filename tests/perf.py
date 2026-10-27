"""Smoothness on a slow phone: CPU slowed 6x, frames longer than 50 ms counted as stutter,
long main-thread tasks, and how long after a tap Zizo starts talking."""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
RATE = float(sys.argv[1]) if len(sys.argv) > 1 else 6
PROBE = """
window.__fr = []; window.__lt = []; window.__aud = [];
(function loop(t0){ requestAnimationFrame(function(t){ if (t0) window.__fr.push([t, t - t0]); loop(t); }); })();
try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push([e.startTime, e.duration]))).observe({ entryTypes: ['longtask'] }); } catch(e){}
(() => { const AC = window.AudioContext || window.webkitAudioContext; const orig = AC.prototype.createBufferSource;
  AC.prototype.createBufferSource = function(){ const s = orig.call(this); const st = s.start.bind(s);
    s.start = (...a) => { window.__aud.push(performance.now()); return st(...a); }; return s; }; })();
window.__mark = function(n){ window.__marks = window.__marks || []; window.__marks.push([n, performance.now()]); };
"""

async def scenario(page, name, fn):
    t0 = await page.evaluate("performance.now()")
    await fn()
    t1 = await page.evaluate("performance.now()")
    fr = await page.evaluate(f"window.__fr.filter(f => f[0] >= {t0} && f[0] <= {t1}).map(f => f[1])")
    lt = await page.evaluate(f"window.__lt.filter(l => l[0] >= {t0} && l[0] <= {t1}).map(l => l[1])")
    bad = [round(x) for x in fr if x > 50]
    return {"name": name, "frames": len(fr), "stutters>50ms": len(bad), "worst_ms": round(max(fr) if fr else 0),
            "long_tasks": len(lt), "longest_task_ms": round(max(lt) if lt else 0)}

async def tap_and_voice(page, sel, force=False):
    n0 = await page.evaluate("window.__aud.length")
    t = await page.evaluate("performance.now()")
    await page.click(sel, force=force)
    try:
        await page.wait_for_function(f"window.__aud.length > {n0}", timeout=6000)
        return round(await page.evaluate(f"window.__aud[{n0}] - {t}"))
    except Exception:
        return None

async def main():
    out, lat = [], {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": RATE})
        await page.add_init_script(BRIDGE + PROBE + """window.__zizoTest.intro = true; try { if (!sessionStorage.getItem('s')) { localStorage.clear();
          localStorage.setItem('zizo-kid', JSON.stringify({name:'علي', g:'m'})); sessionStorage.setItem('s','1'); } } catch(e){}""")
        await page.goto("http://127.0.0.1:8765/index.html")
        out.append(await scenario(page, "opening", lambda: page.wait_for_timeout(5500)))
        async def letters():
            await page.click("#goLearn"); await page.wait_for_timeout(900)
            lat['letter tap'] = await tap_and_voice(page, "#grid .tile >> nth=1"); await page.wait_for_timeout(1500)
            for _ in range(3):
                lat.setdefault('next letter', []).append(await tap_and_voice(page, "#nextL")); await page.wait_for_timeout(1200)
        out.append(await scenario(page, "letters", letters))
        async def tabs():
            for t in ["numbers", "discover", "play", "trace", "stories", "letters"]:
                await page.click(f".tab[data-v={t}]"); await page.wait_for_timeout(700)
        out.append(await scenario(page, "switching tabs", tabs))
        async def game():
            await page.click(".tab[data-v=play]"); await page.wait_for_timeout(500)
            await page.click(".gamecard[data-mode=listen]"); await page.wait_for_timeout(2500)
            for r in range(3):
                st = await page.evaluate("window.__zizoTest.target()")
                await page.evaluate("window.__oldc = document.querySelector('#choices .choice')")
                lat.setdefault('right answer', []).append(await tap_and_voice(page, f"#choices .choice[data-o='{st['target']}']"))
                await page.wait_for_function("() => !document.body.contains(window.__oldc) || !document.getElementById('endArea').hidden", timeout=20000)
                await page.wait_for_timeout(1800)
            await page.click("#gamesBack")
        out.append(await scenario(page, "game (answers, Zizo jumping in)", game))
        async def story():
            await page.click(".tab[data-v=stories]"); await page.wait_for_timeout(600)
            lat['open story'] = await tap_and_voice(page, "#sgrid .stile >> nth=2"); await page.wait_for_timeout(1500)
            for _ in range(2):
                lat.setdefault('next page', []).append(await tap_and_voice(page, "#nextS")); await page.wait_for_timeout(1500)
        out.append(await scenario(page, "story pages", story))
        await b.close()
    for o in out: print(json.dumps(o, ensure_ascii=False))
    print("voice starts after tap (ms):", json.dumps(lat, ensure_ascii=False))
asyncio.run(main())
