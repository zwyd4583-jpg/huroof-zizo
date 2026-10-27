"""Phone simulation: new Discover topics, add/take-away game, today's challenge and its streak."""
import asyncio, datetime, json, pathlib, sys
from playwright.async_api import async_playwright
from common import BRIDGE, ROOT, OUT, URL, out

PROJ = ROOT
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else out(pathlib.Path(__file__).stem); OUT.mkdir(parents=True, exist_ok=True)
SEED = """
try {
  if (!sessionStorage.getItem('seeded')) {
    localStorage.clear();
    localStorage.setItem('zizo-kid', JSON.stringify({ name: 'سارة', g: 'f' }));
    localStorage.setItem('zizo-stars', '10');
    sessionStorage.setItem('seeded', '1');
  }
} catch (e) {}
"""
AR = "٠١٢٣٤٥٦٧٨٩"
def num(s): return int("".join(str(AR.index(c)) if c in AR else c for c in s))
def key(d): return f"{d.year}-{d.month}-{d.day}"


async def main():
    problems, notes = [], []
    def expect(cond, msg): (notes if cond else problems).append(("ok  " if cond else "BAD ") + msg)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        await page.add_init_script(BRIDGE + SEED)
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" and "capacitor.js" not in m.text and "ERR_FILE_NOT_FOUND" not in m.text and "voice/index.json" not in m.text and "404" not in m.text else None)
        # these checks follow the phone's voice, so the recordings are left out
        await page.route("**/voice/index.json", lambda r: r.fulfill(status=404, body=""))
        await page.goto(URL)
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(500)

        async def spoken(): return await page.evaluate("window.__spoken.splice(0)")
        async def ls(k): return await page.evaluate(f"localStorage.getItem('{k}')")
        async def overflow(name):
            if await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"): problems.append(f"{name}: sideways overflow")
        async def shot(name, full=False): await page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)

        async def answer_rounds(n, label, shots=None, wrong_first=True):
            modes = []
            for rnd in range(n):
                await page.wait_for_timeout(250)
                st = await page.evaluate("window.__zizoTest.target()")
                modes.append(st["mode"])
                if st["mode"] == "math":
                    parts = await page.locator("#pEq span").all_text_contents()
                    a, op, bb = num(parts[0]), parts[1], num(parts[2])
                    ans = a + bb if op == "+" else a - bb
                    items = await page.locator(".mathpics .it").count(); gone = await page.locator(".mathpics .it.gone").count()
                    ok_pics = (items == a + bb and gone == 0) if op == "+" else (items == a and gone == bb)
                    expect(ok_pics and ans == st["target"] + 1, f"{label} {rnd+1}: {parts[0]}{op}{parts[2]}={ans}, pictures {items}/{gone}")
                    if shots is not None and op not in shots: await shot(f"math-{'add' if op == '+' else 'sub'}"); shots.add(op)
                if shots is not None and st["mode"] not in shots and st["mode"] != "math":
                    await shot(f"q-{st['mode']}"); shots.add(st["mode"])
                await overflow(f"{label} {st['mode']}")
                if wrong_first and rnd == 0:
                    wrong = page.locator(f"#choices .choice:not([data-o='{st['target']}'])").first
                    await wrong.click(); await page.wait_for_timeout(120)
                await page.click(f"#choices .choice[data-o='{st['target']}']")
                await page.wait_for_timeout(150)
                expect(await page.locator("#choices .choice.right").count() == 1, f"{label} round {rnd+1} ({st['mode']}) right")
                if st["mode"] == "math":
                    qm = await page.text_content("#pEq .qm")
                    expect(num(qm) == st["target"] + 1, f"answer shown in the equation ({qm})")
                await page.wait_for_timeout(1500)
            await page.wait_for_timeout(400)
            return modes

        # --- welcome: today's challenge button ---
        t = await page.text_content("#wlDaily")
        expect("٥ نجوم إضافية" in t, f"welcome daily button: {t}")
        await shot("01-welcome")
        await overflow("welcome")
        await page.click("#goLearn"); await spoken()

        # --- discover: the new topics ---
        await page.click(".tab[data-v=discover]")
        expect(await page.locator(".dchip").count() == 6, "6 discover topics")
        for topic, n in [("foods", 12), ("body", 8), ("jobs", 12)]:
            await page.click(f".dchip[data-topic={topic}]")
            await page.wait_for_timeout(200)
            c = await page.locator("#dgrid .dtile").count()
            expect(c == n, f"{topic}: {c} items")
            await shot(f"02-{topic}")
            await overflow(topic)
            await spoken()  # forget what the last game said
            await page.click("#dgrid .dtile >> nth=1")
            await page.wait_for_timeout(250)
            s = await spoken()
            expect(len(s) == 2, f"{topic} item 2 spoken: {s}")
            await shot(f"03-{topic}-item")
            # play this topic's game from the detail page
            await page.click("#toGameD")
            await answer_rounds(5, topic, shots=set())
            expect(await page.locator("#endArea").is_visible(), f"{topic} game ends")
            await page.click(".tab[data-v=discover]")

        # --- games menu ---
        await page.click(".tab[data-v=play]")
        await page.wait_for_timeout(300)
        heads = await page.locator(".games-head").all_text_contents()
        expect(len(heads) == 3, f"menu sections {heads}")
        expect(await page.locator(".gamecard").count() == 13, "13 game cards")
        await shot("04-menu"); await overflow("menu")
        await page.evaluate("window.scrollTo(0, 700)"); await page.wait_for_timeout(150); await shot("04b-menu-lower")

        # --- add and take away ---
        await page.evaluate("window.scrollTo(0, 0)")
        await page.click(".gamecard[data-mode=math]")
        await page.wait_for_timeout(250)
        s = await spoken(); expect(any("كَمْ يُساوي" in x for x in s), f"math question spoken {s}")
        seen = set()
        for _ in range(3):
            await answer_rounds(5, "math", shots=seen)
            await page.click("#again")
            if {"+", "−"} <= seen: break
        await page.click("#gamesBack")

        # --- today's challenge ---
        st0 = int(await ls("zizo-stars"))
        await page.click(".daily-card")
        modes = await answer_rounds(5, "daily", shots=set())
        expect(len(set(modes)) == 5, f"5 different kinds today: {modes}")
        st1 = int(await ls("zizo-stars"))
        expect(st1 == st0 + 10, f"5 + 5 extra stars ({st0} -> {st1})")
        dstate = json.loads(await ls("zizo-daily"))
        today = datetime.date.today()
        expect(dstate == {"last": key(today), "streak": 1}, f"daily saved {dstate}")
        expect(not await page.locator("#again").is_visible(), "no 'play again' after the challenge")
        sub = await page.text_content("#endSub"); nxt = await page.text_content("#endNext")
        notes.append(f"    end: {sub} / {nxt}")
        await shot("05-daily-end")
        await page.click("#gamesBack")
        await page.wait_for_timeout(200)
        expect("تمّ اليوم" in await page.text_content(".daily-card .jsub"), "card shows done today")
        await shot("06-menu-done")
        # same kinds on a replay, no extra stars
        await page.click(".daily-card")
        modes2 = await answer_rounds(5, "daily again", wrong_first=False)
        expect(modes2 == modes, "same questions kinds all day")
        st2 = int(await ls("zizo-stars"))
        expect(st2 == st1 + 5, f"replay gives no extra stars ({st1} -> {st2})")
        expect("أعدتِ" in await page.text_content("#endSub"), "replay message")
        # streak: last done yesterday with 3 days -> today makes 4
        y = today - datetime.timedelta(days=1)
        await page.evaluate(f"localStorage.setItem('zizo-daily', JSON.stringify({{last:'{key(y)}', streak:3}}))")
        await page.reload(); await page.wait_for_timeout(500)
        expect((await page.text_content("#wlStreak")).strip() == "🔥 ٣", f"welcome streak {await page.text_content('#wlStreak')}")
        await shot("07-welcome-streak")
        await page.click("#goDaily"); await page.wait_for_timeout(200)
        await answer_rounds(5, "daily streak", wrong_first=False)
        dstate = json.loads(await ls("zizo-daily"))
        expect(dstate["streak"] == 4, f"streak 3 -> {dstate['streak']}")
        nxt = await page.text_content("#endNext")
        expect("٤ أيام متتالية" in nxt, f"streak text: {nxt}")
        await shot("08-daily-streak")
        # missed a day: streak starts again
        old = today - datetime.timedelta(days=2)
        await page.evaluate(f"localStorage.setItem('zizo-daily', JSON.stringify({{last:'{key(old)}', streak:6}}))")
        await page.reload(); await page.wait_for_timeout(500)
        expect((await page.text_content("#wlStreak")).strip() == "", "no streak shown after a missed day")
        await page.click("#goDaily"); await page.wait_for_timeout(200)
        await answer_rounds(5, "daily after gap", wrong_first=False)
        expect(json.loads(await ls("zizo-daily"))["streak"] == 1, "streak restarts at 1")
        # back button from the challenge goes to the games menu
        await page.click("#gamesBack"); await page.wait_for_timeout(150)
        expect(await page.locator("#gameMenu").is_visible(), "back to games menu")

        print("\n".join(notes)); print("PROBLEMS:" if problems else "no problems"); print("\n".join(problems))
        await b.close()

asyncio.run(main())
