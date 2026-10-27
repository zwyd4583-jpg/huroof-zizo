"""Phone simulation: Zizo calls the child by name.
A recorded name is played between the recordings around it; a name that was never recorded
is said by the phone's voice in the same place; the sentence otherwise stays in Zizo's voice."""
import asyncio, json, pathlib
from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).parent
from common import BRIDGE, ROOT, OUT, out
INDEX = json.loads((ROOT / "www/voice/index.json").read_text(encoding="utf-8"))


def seed(kid):
    return """try { if (!sessionStorage.getItem('seeded')) { localStorage.clear();
      localStorage.setItem('zizo-kid', JSON.stringify(%s)); localStorage.setItem('zizo-stars', '5');
      sessionStorage.setItem('seeded', '1'); } } catch (e) {}""" % json.dumps(kid, ensure_ascii=False)


async def run(p, kid, extra):
    clips = dict(INDEX["clips"])
    clips.update(extra)
    for k in [k for k, v in clips.items() if v is None]:
        del clips[k]  # None: pretend this one has not been recorded
    b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await b.new_context(viewport={"width": 400, "height": 800}, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.route("**/voice/index.json", lambda r: r.fulfill(
        content_type="application/json", body=json.dumps({"style": INDEX["style"], "clips": clips}, ensure_ascii=False)))
    await page.add_init_script(BRIDGE + seed(kid))
    await page.goto("http://127.0.0.1:8765/index.html")
    await page.wait_for_timeout(1500)
    greet = await page.evaluate("(window.__zizoTest.played || [])[0] || ''")
    # finish a game round: "أَحْسَنْتِ يا <name>" or a praise with the name
    await page.click("#goLearn"); await page.click(".tab[data-v=play]")
    await page.click(".gamecard[data-mode=listen]")
    for _ in range(5):
        await page.wait_for_timeout(250)
        st = await page.evaluate("window.__zizoTest.target()")
        await page.click(f"#choices .choice[data-o='{st['target']}']")
        await page.wait_for_timeout(2500)
    played = await page.evaluate("window.__zizoTest.played || []")
    spoken = await page.evaluate("window.__spoken")
    await b.close()
    return greet, played, spoken, errors


async def main():
    problems = []
    # stand-ins for recordings not made yet: real files the listen game never plays
    c = INDEX["clips"]
    sara, ahlan, play = c["الدِّيكُ يَصِيح"], c["الكَلْبُ يَنْبَح"], c["القِطَّةُ تَمُوء"]
    async with async_playwright() as p:
        # 1) a recorded name, typed the way parents often type it (ه for ة)
        greet, played, spoken, errors = await run(p, {"name": "ساره", "g": "f"},
                                                  {"name:ساره": sara, "أَهْلاً": ahlan, "هَيّا نَلْعَب": play})
        problems += errors
        if greet != f"{ahlan}+{sara}+{play}":
            problems.append(f"greeting with a recorded name: {greet}")
        if not any(sara in x for x in played[1:]):
            problems.append("the recorded name was never said during the game")
        if spoken:
            problems.append(f"phone voice used with a recorded name: {spoken}")
        print("recorded name:", greet, "| game sentences with the name:", sum(sara in x for x in played[1:]))
        # 2) a name nobody recorded: the phone says just "يا <name>", Zizo says the rest
        greet, played, spoken, errors = await run(p, {"name": "زوزو", "g": "m"},
                                                  {"أَهْلاً": ahlan, "هَيّا نَلْعَب": play})
        problems += errors
        if greet != f"{ahlan}+[object Object]+{play}":
            problems.append(f"greeting with an unrecorded name: {greet}")
        if not spoken or any(s != "يا زوزو" for s in spoken):
            problems.append(f"phone voice should say only the name: {spoken}")
        print("unrecorded name:", greet, "| phone voice said:", sorted(set(spoken)), len(spoken), "times")
        # 3) before the words around the name are recorded: the sentence is said without the name, all by Zizo
        greet, played, spoken, errors = await run(p, {"name": "زوزو", "g": "m"}, {"أَهْلاً": None, "هَيّا نَلْعَب": None})
        problems += errors
        if greet != INDEX["clips"]["أَهْلاً! هَيّا نَلْعَب"]:
            problems.append(f"greeting fallback: {greet}")
        print("fallback greeting:", greet)
    print("PROBLEMS:" if problems else "no problems", "\n".join(problems))


asyncio.run(main())
