"""Collect every sentence the app says and write the recording list for the voice workflow.

Usage: python3 voice_phrases.py <project_dir> <engine-settings.json> <out_list.json>
The settings file holds the engine part of the list ("engine", "voices"/"chatterbox", "styles", "qa").
Each sentence gets a stable file id from its text, so re-recording keeps the same names.
"""
import asyncio, json, pathlib, sys, zlib
from playwright.async_api import async_playwright


async def phrases(proj):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        await page.add_init_script("window.__zizoTest = {}; try { localStorage.clear(); } catch (e) {}")
        await page.goto((proj / "www/index.html").as_uri())
        await page.wait_for_timeout(300)
        out = await page.evaluate("window.__zizoTest.phrases()")
        await b.close()
    return out


def file_id(p):
    return f"{p['lang']}-{zlib.crc32(p['key'].encode('utf-8')):08x}"


def main(proj, settings, out_path):
    proj = pathlib.Path(proj).resolve()
    ph = asyncio.run(phrases(proj))
    spec = json.loads(pathlib.Path(settings).read_text(encoding="utf-8"))
    ids = {}
    for p in ph:
        i = file_id(p)
        if i in ids and ids[i] != p["key"]:
            raise SystemExit(f"id clash: {p['key']} / {ids[i]}")
        ids[i] = p["key"]
    def item(p):
        it = {"id": file_id(p), "lang": p["lang"], "text": p["speak"], "key": p["key"]}
        if p.get("accept"):
            it["accept"] = p["accept"]
        # short words are the hardest to get right: record them more times and keep the clearest
        it["candidates"] = 6 if len(p["speak"].split()) <= 2 else 2
        return it
    spec["items"] = [item(p) for p in ph]
    spec["reels"] = False
    pathlib.Path(out_path).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    ar = sum(1 for p in ph if p["lang"] == "ar")
    print(f"{len(ph)} sentences ({ar} Arabic, {len(ph) - ar} English) -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
