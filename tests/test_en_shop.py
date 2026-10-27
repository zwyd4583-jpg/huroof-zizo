"""Phone simulation of the English sections, English games, English tracing and Zizo's shop."""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright
from common import BRIDGE, ROOT, OUT, URL, out

PROJ = ROOT
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else out("en_shop")
OUT.mkdir(parents=True, exist_ok=True)

# An older install: 16 stars earned, Zizo wearing the party hat it won at 10 stars, no shop yet
OLD = """
try {
  if (!sessionStorage.getItem('seeded')) {
    localStorage.clear();
    localStorage.setItem('zizo-kid', JSON.stringify({ name: 'سارة', g: 'f' }));
    localStorage.setItem('zizo-stars', '16');
    localStorage.setItem('zizo-outfit', JSON.stringify({ hat: 'party', scarf: 'blue', extra: 'none' }));
    sessionStorage.setItem('seeded', '1');
  }
} catch (e) {}
"""

# Trace by filling the guide glyph with short horizontal strokes, the way a careful child colours over it
FILL_TRACE = """
(en) => {
  const cv = document.getElementById('cv'), r = cv.getBoundingClientRect(), S = r.width;
  const c = document.createElement('canvas'); c.width = c.height = Math.round(S);
  const g = c.getContext('2d');
  const ch = window.__traceChar;
  const pl = window.__zizoTest.placeGlyph(g, ch), x = pl.x, y = pl.y;
  g.fillText(ch, x, y);
  const d = g.getImageData(0, 0, c.width, c.height).data, W = c.width;
  // centre line of the glyph at full size (Zhang-Suen), then walk it into finger strokes
  const img = new Uint8Array(W*W);
  for (let i = 0; i < W*W; i++) img[i] = d[i*4 + 3] > 128 ? 1 : 0;
  const at = (x, y) => (x < 0 || y < 0 || x >= W || y >= W) ? 0 : img[y*W + x];
  let changed = true;
  while (changed){
    changed = false;
    for (let step = 0; step < 2; step++){
      const kill = [];
      for (let y = 0; y < W; y++) for (let x = 0; x < W; x++){
        if (!img[y*W + x]) continue;
        const P = [at(x, y-1), at(x+1, y-1), at(x+1, y), at(x+1, y+1), at(x, y+1), at(x-1, y+1), at(x-1, y), at(x-1, y-1)];
        let B = 0, A = 0;
        for (let k = 0; k < 8; k++){ B += P[k]; if (!P[k] && P[(k+1) % 8]) A++; }
        if (B < 2 || B > 6 || A !== 1) continue;
        if (step === 0 ? (P[0]*P[2]*P[4] === 0 && P[2]*P[4]*P[6] === 0) : (P[0]*P[2]*P[6] === 0 && P[0]*P[4]*P[6] === 0)) kill.push(y*W + x);
      }
      kill.forEach(i => img[i] = 0);
      if (kill.length) changed = true;
    }
  }
  const seen = new Uint8Array(W*W), strokes = [];
  const nbrs = (x, y) => { const o = []; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if ((dx || dy) && at(x+dx, y+dy) && !seen[(y+dy)*W + x+dx]) o.push([x+dx, y+dy]); return o; };
  // start walks at line ends first, so each stroke runs end to end like a finger would
  const order = [];
  for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) if (img[y*W + x]){
    let k = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if ((dx || dy) && at(x+dx, y+dy)) k++;
    order.push([k === 1 ? 0 : 1, x, y]);
  }
  order.sort((a, b) => a[0] - b[0]);
  for (const [, sx, sy] of order){
    if (seen[sy*W + sx]) continue;
    let px = sx, py = sy; const s = [[px, py]]; seen[py*W + px] = 1;
    for (;;){ const n = nbrs(px, py); if (!n.length) break; [px, py] = n[0]; seen[py*W + px] = 1; s.push([px, py]); }
    strokes.push(s);
  }
  const ev = (type, px, py) => cv.dispatchEvent(new PointerEvent(type, { clientX: r.left + px, clientY: r.top + py, pointerId: 1, bubbles: true, isPrimary: true }));
  strokes.forEach(s => {
    ev('pointerdown', s[0][0], s[0][1]);
    for (let k = 2; k < s.length; k += 2) ev('pointermove', s[k][0], s[k][1]);
    ev('pointerup', s[s.length-1][0], s[s.length-1][1]);
  });
  return strokes.length;
}
"""
SCRIBBLE = """
() => {
  const cv = document.getElementById('cv'), r = cv.getBoundingClientRect(), S = r.width;
  const ev = (type, px, py) => cv.dispatchEvent(new PointerEvent(type, { clientX: r.left + px, clientY: r.top + py, pointerId: 1, bubbles: true, isPrimary: true }));
  ev('pointerdown', S*0.85, S/2);
  for (let a = 0; a <= Math.PI*2; a += 0.08) ev('pointermove', S/2 + S*0.35*Math.cos(a), S/2 + S*0.35*Math.sin(a));
  ev('pointerup', S*0.85, S/2);
}
"""


async def main():
    problems, notes = [], []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        await page.add_init_script(BRIDGE + OLD)
        page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" and "capacitor.js" not in m.text and "ERR_FILE_NOT_FOUND" not in m.text and "voice/index.json" not in m.text and "404" not in m.text else None)
        # these checks follow the phone's voice, so the recordings are left out
        await page.route("**/voice/index.json", lambda r: r.fulfill(status=404, body=""))
        await page.goto(URL)
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(500)

        def expect(cond, msg):
            (notes if cond else problems).append(("ok  " if cond else "BAD ") + msg)

        async def spoken():
            return await page.evaluate("window.__spoken.splice(0)")

        async def overflow(name):
            if await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                problems.append(f"{name}: sideways overflow")

        async def ls(key):
            return await page.evaluate(f"localStorage.getItem('{key}')")

        # --- migration from the old prizes ---
        owned = json.loads(await ls("zizo-owned"))
        expect(sorted(owned) == sorted(["cap", "orange", "none", "crown", "blue", "party", "glasses"]), f"old prizes kept: {owned}")
        expect(await ls("zizo-stars") == "16", "stars kept at 16")
        expect(await page.evaluate("document.getElementById('starPill').classList.contains('can-buy')"), "dot on the star pill")
        await page.screenshot(path=str(OUT / "01-welcome.png"))
        await page.click("#goLearn")
        await spoken()

        # --- English letters ---
        await page.click(".lchip[data-lang=en]")
        n = await page.locator("#grid .tile").count()
        expect(n == 26, f"26 English letter tiles ({n})")
        await page.screenshot(path=str(OUT / "02-en-grid.png"))
        await overflow("en grid")
        await page.click("#grid .tile >> nth=0")
        await page.wait_for_timeout(300)
        s = await spoken(); expect(s == ["EN:A", "EN:Apple"], f"letter A spoken {s}")
        await page.screenshot(path=str(OUT / "03-en-letter.png"))
        await overflow("en letter")
        # X ends its word
        await page.click(".lchip[data-lang=en]")
        await page.click("#grid .tile >> nth=23")
        await page.wait_for_timeout(200)
        await page.screenshot(path=str(OUT / "04-en-x.png"))
        await spoken()
        await page.click(".lchip[data-lang=ar]")
        n = await page.locator("#grid .tile").count()
        expect(n == 28, f"back to 28 Arabic letters ({n})")

        # --- English numbers ---
        await page.click(".tab[data-v=numbers]")
        await page.click(".nchip[data-lang=en]")
        await page.click("#ngrid .tile >> nth=2")
        await spoken()
        await page.click("#nBox .obj >> nth=0"); await page.click("#nBox .obj >> nth=1")
        await page.wait_for_timeout(200)
        s = await spoken(); expect(s[:2] == ["EN:one", "EN:two"], f"counting in English {s}")
        await page.screenshot(path=str(OUT / "05-en-number.png"))
        await overflow("en number")

        # --- English games ---
        await page.click(".tab[data-v=play]")
        await page.wait_for_timeout(300)
        heads = await page.locator(".games-head").count()
        expect(heads == 3, "3 game sections")
        await page.screenshot(path=str(OUT / "06-games.png"), full_page=True)
        await overflow("games menu")
        await page.evaluate("document.querySelector('.games-head').scrollIntoView({block:'center'})")
        await page.wait_for_timeout(200)
        await page.screenshot(path=str(OUT / "06b-games-en.png"))
        stars0 = int(await ls("zizo-stars"))
        for mode in ["enListen", "enWord", "enCount"]:
            await page.click(f".gamecard[data-mode={mode}]")
            for rnd in range(5):
                await page.wait_for_timeout(250)
                s = await spoken()
                if rnd == 0:
                    await page.screenshot(path=str(OUT / f"07-{mode}.png"))
                    await overflow(mode)
                if mode == "enCount":
                    want = str(await page.locator("#pBox .obj").count())
                else:
                    want = [x[3:] for x in s if x.startswith("EN:")][-1]
                choices = await page.locator("#choices .choice").all()
                keys = [(await c.text_content()) if mode != "enWord" else (await c.get_attribute("aria-label")) for c in choices]
                right = choices[keys.index(want)]
                # one wrong answer first in round 0
                if rnd == 0:
                    await choices[(keys.index(want) + 1) % len(choices)].click()
                    await page.wait_for_timeout(150)
                    expect(await page.locator("#choices .choice.wrong").count() == 1, f"{mode}: a wrong answer is marked")
                await right.click()
                await page.wait_for_timeout(200)
                ok = await page.locator("#choices .choice.right").count()
                expect(ok == 1, f"{mode} round {rnd+1}: picked {want!r}")
                await page.wait_for_timeout(1500)
            await page.wait_for_timeout(400)
            expect(await page.locator("#endArea").is_visible(), f"{mode} ends after 5 rounds")
            if mode == "enCount":
                await page.screenshot(path=str(OUT / "08-end.png"))
            await page.click("#gamesBack")
        stars1 = int(await ls("zizo-stars"))
        expect(stars1 == stars0 + 15, f"15 stars from 3 English games ({stars0} -> {stars1})")

        # --- English tracing ---
        await page.click(".tab[data-v=trace]")
        await page.click(".tchip[data-kind=en]")
        await page.wait_for_timeout(300)
        label = await page.text_content("#tLabelText")
        expect(label == "حرف A", f"trace label {label!r}")
        await page.screenshot(path=str(OUT / "09-trace-A.png"))
        for kind, idx_clicks, ch in [("en", 0, "A"), ("en", 1, "B"), ("en", 6, "G"), ("enNum", 0, "1"), ("enNum", -1, "10"), ("letters", 1, "ب"), ("letters", 3, "ث")]:
            await page.click(f".tchip[data-kind={kind}]")
            steps = idx_clicks
            # step with next (or prev for "10") until the label shows the item
            for _ in range(30):
                t = await page.text_content("#tLabelText")
                if t.endswith(ch) or (kind == "letters" and t == {"ب": "حرف الباء", "ث": "حرف الثاء"}[ch]):
                    break
                await page.click("#nextT" if steps >= 0 else "#prevT")
            await page.evaluate(f"window.__traceChar = {json.dumps(ch)}")
            st = int(await ls("zizo-stars"))
            # scribble first: must not win
            await page.evaluate(SCRIBBLE)
            await page.click("#doneT")
            await page.wait_for_timeout(150)
            expect(int(await ls("zizo-stars")) == st, f"trace {ch}: a big circle does not win")
            await page.click("#clearT")
            await page.evaluate(FILL_TRACE, kind in ("en", "enNum"))
            if ch in ("A", "10"):
                await page.screenshot(path=str(OUT / f"10-trace-{ch}.png"))
            await page.click("#doneT")
            await page.wait_for_timeout(200)
            bubble = await page.text_content("#bubble")
            won = int(await ls("zizo-stars")) == st + 1
            expect(won, f"trace {ch}: careful tracing wins ({bubble})")
            await page.wait_for_timeout(1900)
        await overflow("trace")

        # --- the shop ---
        await page.click("#starPill")
        await page.wait_for_timeout(300)
        stars = int(await ls("zizo-stars"))
        wallet = await page.text_content("#wallet")
        expect(wallet.strip() != "", f"wallet shows {wallet.strip()} (stars {stars})")
        await page.screenshot(path=str(OUT / "11-shop.png"), full_page=True)
        await overflow("shop")
        can = await page.locator(".prize.can").count(); cant = await page.locator(".prize.cant").count()
        notes.append(f"    shop: {can} affordable, {cant} too dear, stars {stars}")
        # buy the wizard hat if affordable, else the first affordable item
        first_can = page.locator(".prize.can").first
        name = await first_can.locator(".pname").text_content()
        await first_can.click()
        await page.wait_for_timeout(300)
        expect(await page.locator("#prizeModal").is_visible(), f"buy dialog for {name}")
        await page.screenshot(path=str(OUT / "12-buy.png"))
        await page.click("#buyPrize")
        await page.wait_for_timeout(300)
        after = int(await ls("zizo-stars"))
        owned2 = json.loads(await ls("zizo-owned"))
        outfit = json.loads(await ls("zizo-outfit"))
        expect(after < stars, f"bought {name}: stars {stars} -> {after}")
        expect(len(owned2) == len(owned) + 1, f"owned now {len(owned2)} items")
        notes.append(f"    outfit now {outfit}")
        await page.screenshot(path=str(OUT / "13-after-buy.png"))
        # spend down until nothing is affordable
        while await page.locator(".prize.can").count():
            await page.locator(".prize.can").first.click()
            await page.click("#buyPrize")
            await page.wait_for_timeout(150)
        left = int(await ls("zizo-stars"))
        expect(left >= 0, f"stars never below zero ({left})")
        if await page.locator(".prize.cant").count():
            await page.locator(".prize.cant").first.click()
            await page.wait_for_timeout(250)
            note = await page.text_content("#prizeNote"); btn = await page.text_content("#buyPrize")
            expect("ينقصك" in note, f"too dear: {note} / {btn}")
            await page.screenshot(path=str(OUT / "14-too-dear.png"))
            await page.evaluate("window.__back && window.__back()")
            await page.wait_for_timeout(200)
            expect(not await page.locator("#prizeModal").is_visible(), "back button closes the dialog")
            await page.locator(".prize.cant").first.click()
            await page.click("#buyPrize")
            await page.wait_for_timeout(300)
            expect(await page.locator("#v-play").is_visible(), "'play and collect' goes to the games")
        pill = await page.evaluate("document.getElementById('starPill').classList.contains('can-buy')")
        expect(not pill, "no dot when nothing is affordable")

        # --- reload: what was bought stays, nothing is given for free ---
        owned3 = sorted(json.loads(await ls("zizo-owned")))
        await page.evaluate("localStorage.setItem('zizo-stars', '200')")
        await page.reload()
        await page.wait_for_timeout(400)
        owned4 = sorted(json.loads(await ls("zizo-owned")))
        expect(owned3 == owned4, "reload keeps the bought items and gives nothing extra")

        print("\n".join(notes))
        print("PROBLEMS:" if problems else "no problems")
        print("\n".join(problems))
        await b.close()

asyncio.run(main())
