"""Phone simulation: the fun sounds play at the right moments and the switch turns them off."""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright
from common import BRIDGE, ROOT, OUT, URL, out

PROJ = ROOT
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else out(pathlib.Path(__file__).stem); OUT.mkdir(parents=True, exist_ok=True)
SPY = """
window.__osc = 0; window.__noise = 0;
(function(){
  var P = (window.AudioContext || window.webkitAudioContext).prototype;
  var o = P.createOscillator, n = P.createBufferSource;
  P.createOscillator = function(){ window.__osc++; return o.apply(this, arguments); };
  P.createBufferSource = function(){ window.__noise++; return n.apply(this, arguments); };
})();
try {
  if (!sessionStorage.getItem('seeded')) {
    localStorage.clear();
    localStorage.setItem('zizo-kid', JSON.stringify({ name: 'سارة', g: 'f' }));
    localStorage.setItem('zizo-stars', '20');
    sessionStorage.setItem('seeded', '1');
  }
} catch (e) {}
"""


async def main():
    problems, notes = [], []
    def expect(c, m): (notes if c else problems).append(("ok  " if c else "BAD ") + m)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        await page.add_init_script(BRIDGE + SPY)
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" and "capacitor.js" not in m.text and "ERR_FILE_NOT_FOUND" not in m.text and "voice/index.json" not in m.text and "404" not in m.text else None)
        # these checks follow the phone's voice, so the recordings are left out
        await page.route("**/voice/index.json", lambda r: r.fulfill(status=404, body=""))
        await page.goto(URL)
        await page.wait_for_timeout(500)

        async def counts(): return await page.evaluate("[window.__osc, window.__noise]")
        async def delta(action):
            a = await counts(); await action(); await page.wait_for_timeout(250); z = await counts()
            return z[0] - a[0], z[1] - a[1]

        t = await page.text_content("#sfxToggle")
        expect("تعمل" in t, f"switch on the welcome screen: {t.strip()}")
        await page.screenshot(path=str(OUT / "welcome.png"))
        await page.click("#goLearn")

        # counting pops
        await page.click(".tab[data-v=numbers]")
        await page.click("#ngrid .tile >> nth=2")
        d = await delta(lambda: page.click("#nBox .obj >> nth=0"))
        expect(d == (1, 0), f"tap to count: pop {d}")

        # a game: wrong boing, right chime, win fanfare + claps
        await page.click(".tab[data-v=play]")
        await page.click(".gamecard[data-mode=count]")
        await page.wait_for_timeout(300)
        for rnd in range(5):
            st = await page.evaluate("window.__zizoTest.target()")
            if rnd == 0:
                d = await delta(lambda: page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first.click())
                expect(d == (2, 0), f"wrong answer: boing {d}")
            right = page.locator(f"#choices .choice[data-o='{st['target']}']")
            if rnd < 4:
                d = await delta(lambda: right.click())
                expect(d == (3, 0), f"right answer {rnd+1}: chime {d}")
                await page.wait_for_timeout(1500)
            else:
                a = await counts(); await right.click(); await page.wait_for_timeout(2300); z = await counts()
                d = (z[0] - a[0], z[1] - a[1])
                expect(d[0] >= 3 + 5 and d[1] >= 20, f"last answer + end of game: chime, fanfare and claps {d}")
        expect(await page.locator("#endArea").is_visible(), "game ended")

        # shop: coins
        await page.click("#starPill")
        await page.wait_for_timeout(200)
        await page.locator(".prize.can").first.click()
        d = await delta(lambda: page.click("#buyPrize"))
        expect(d[0] >= 3, f"buying: coins {d}")

        # switch off on the welcome screen: no more sounds, but the voice still reads
        await page.evaluate("window.__back && window.__back()")
        await page.evaluate("window.__back && window.__back()")
        await page.wait_for_timeout(200)
        if not await page.locator("#welcome").is_visible():
            await page.reload(); await page.wait_for_timeout(400)
        await page.click("#sfxToggle")
        expect(await page.get_attribute("#sfxToggle", "aria-pressed") == "false", "switch turned off")
        expect(await page.evaluate("localStorage.getItem('zizo-sfx')") == "off", "remembered off")
        await page.screenshot(path=str(OUT / "welcome-off.png"))
        await page.click("#goLearn")
        await page.click(".tab[data-v=play]")
        await page.click(".gamecard[data-mode=listen]")
        await page.wait_for_timeout(300)
        await page.evaluate("window.__spoken.splice(0)")
        st = await page.evaluate("window.__zizoTest.target()")
        d = await delta(lambda: page.locator(f"#choices .choice[data-o='{st['target']}']").click())
        spoken = await page.evaluate("window.__spoken.splice(0)")
        expect(d == (0, 0) and len(spoken) >= 1, f"sounds off: {d}, voice still speaks {spoken}")
        # after a reload it stays off
        await page.reload(); await page.wait_for_timeout(400)
        expect("متوقفة" in await page.text_content("#sfxToggle"), "stays off after reopening")
        await page.click("#sfxToggle")
        expect(await page.evaluate("localStorage.getItem('zizo-sfx')") == "on", "back on")

        print("\n".join(notes)); print("PROBLEMS:" if problems else "no problems"); print("\n".join(problems))
        await b.close()

asyncio.run(main())
