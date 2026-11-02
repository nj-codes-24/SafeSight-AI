"""End-to-end QA of the redesigned app in headless Edge, driving the real page with real mouse events.

Covers: gallery -> player -> settings menu -> monitoring run -> session figures -> incidents -> inspector ->
analytics -> history and CSV export -> back to the gallery -> upload -> webcam -> second-tab run lock.
Screenshots go to .qa/screenshots/final_<W>x<H>/ and the log to .qa/qa_log_<W>x<H>.txt (both git-ignored).
Needs the app running (python launch.py), the model at models/best.pt and the demo clips in data/demo.
Usage: .venv\\Scripts\\python.exe scripts\\qa\\qa_flow.py [width height]
"""
import asyncio
import json
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as d  # noqa: E402

W, H = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1440, 900)
OUT = ROOT / ".qa" / "screenshots" / f"final_{W}x{H}"
UPLOAD_SRC = ROOT / "data" / "demo" / "framing_bare_head.mp4"
UPLOAD_NAME = "qa_upload_framing.mp4"


async def page(port, url="about:blank"):
    t = json.loads(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")).read())
    cdp = d.CDP(await websockets.connect(t["webSocketDebuggerUrl"], max_size=256 * 2**20))
    asyncio.ensure_future(cdp.reader())
    await cdp.send("Page.enable")
    await cdp.send("DOM.enable")
    await cdp.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
    return cdp


async def goto(cdp, url, wait="!!document.querySelector('.st-key-topbar')"):
    await cdp.send("Page.navigate", url=url)
    await cdp.wait_for(wait, 60)
    await asyncio.sleep(2.5)


async def click_key(cdp, key):
    """Click the centre of the element container with class st-key-<key>."""
    xy = await cdp.js(f"""(() => {{ const e = document.querySelector('.st-key-{key}'); if (!e) return null;
        e.scrollIntoView({{block: 'center'}}); const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()""")
    if not xy:
        raise RuntimeError(f"no element .st-key-{key}")
    await asyncio.sleep(0.3)
    xy = await cdp.js(f"(() => {{ const r = document.querySelector('.st-key-{key}').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()")
    await cdp.click_at(*xy)


async def wiggle(cdp):
    """Move the mouse over the player so the overlay controls are shown."""
    for x in (W // 2, W // 2 + 20):
        await cdp.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=H // 2)


async def scroll_to(cdp, selector, offset=-90):
    await cdp.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (e) {{ e.scrollIntoView({{block: 'start'}}); "
                 f"const m = document.querySelector('[data-testid=stMain]') || window; m.scrollBy(0, {offset}); }} }})()")
    await asyncio.sleep(1.2)


def db_counts():
    c = sqlite3.connect(ROOT / "logs/incidents/incidents.db")
    return c.execute("select count(*) from sessions").fetchone()[0], c.execute("select count(*) from incidents").fetchone()[0]


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d.SHOTS = OUT
    edge = subprocess.Popen([d.EDGE, "--headless=new", f"--remote-debugging-port={d.PORT}", f"--user-data-dir={d.OUT / 'edge_profile'}",
                             f"--window-size={W},{H}", "--no-first-run", "--hide-scrollbars", "--mute-audio", "--remote-allow-origins=*",
                             "--use-fake-ui-for-media-stream", "about:blank"])
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{d.PORT}/json/version")
                break
            except Exception:
                time.sleep(0.2)
        a = await page(d.PORT)
        await a.send("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(d.OUT / "download"))
        d.log(f"viewport {W}x{H}; DB at start {db_counts()}")

        # 1 gallery
        await goto(a, d.APP)
        await a.shot("01_gallery")
        cards = await a.js("document.querySelectorAll('[class*=st-key-card_]').length")
        imgs = await a.js("[...document.querySelectorAll('.ss-card .thumb img')].filter(i => i.naturalWidth > 100).length")
        overflow = await a.js("document.documentElement.scrollWidth > window.innerWidth + 1")
        d.log(f"gallery: {cards} cards, {imgs} real thumbnails loaded, horizontal overflow={overflow}")
        await a.send("Input.dispatchMouseEvent", type="mouseMoved", x=int(W * .5), y=int(H * .45))
        await asyncio.sleep(0.6)
        await a.shot("01b_gallery_hover")

        # 2 open a source (night clip) from its card
        idx = await a.js("[...document.querySelectorAll('.ss-card .t')].findIndex(e => e.innerText.startsWith('Jackhammer'))")
        await click_key(a, f"open_d{idx}")
        await a.wait_for("location.search.includes('roadworks_night')", 20)
        await asyncio.sleep(2.5)
        await wiggle(a)
        await a.shot("02_player_ready")
        poster = await a.js("!!document.querySelector('.ss-poster img')")
        d.log(f"player opened: {await a.js('location.search')}; poster img={poster}")

        # 3 settings menu in the player
        await click_key(a, "gear")
        await asyncio.sleep(1.2)
        await a.shot("03_settings_detection")
        tabs = await a.js("[...document.querySelectorAll('[data-testid=stPopoverBody] [role=tab]')].map(t => t.innerText)")
        d.log(f"settings tabs: {tabs}")
        for name, shot in (("Restricted zones", "03b_settings_zones"), ("Model", "03c_settings_model")):
            await a.click("[data-testid=stPopoverBody] [role=tab]", name)
            await asyncio.sleep(1.2)
            await a.shot(shot)
        model_txt = await a.js("document.querySelector('[data-testid=stPopoverBody]').innerText")
        d.log("settings model tab: " + " | ".join(l for l in model_txt.splitlines() if l.strip())[-420:])
        await a.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        await asyncio.sleep(0.8)

        # 4 start monitoring with the big play button
        before = db_counts()
        await click_key(a, "bigplay")
        t0 = time.perf_counter()
        d.log("Start pressed (big play)")
        back_disabled = None
        for _ in range(40):
            await asyncio.sleep(0.5)
            if await a.js("!!document.querySelector('.st-key-player [data-testid=stImage] img')"):
                break
        back_disabled = await a.js("document.querySelector('.st-key-back button')?.disabled")
        d.log(f"first frame after {time.perf_counter() - t0:.1f}s; back button disabled during run: {back_disabled}")
        await asyncio.sleep(max(0, 9.0 - (time.perf_counter() - t0)))
        await wiggle(a)
        await asyncio.sleep(0.5)
        await a.shot("04_player_live")
        d.log("live: " + (await a.js("document.querySelector('.ss-prog')?.innerText || ''")).replace("\n", " "))
        await asyncio.sleep(1.5)
        await a.send("Input.dispatchMouseEvent", type="mouseMoved", x=5, y=5)
        await asyncio.sleep(3.2)
        idle = await a.js("document.body.getAttribute('data-ss-idle')")
        await a.shot("04b_player_live_controls_faded")
        d.log(f"controls faded while idle: {idle == '1'}")
        ok = await a.wait_for("!!document.querySelector('.ss-ptop[data-state=done]')", 120)
        d.log(f"run finished={ok} after {time.perf_counter() - t0:.1f}s; DB {before} -> {db_counts()}")
        await asyncio.sleep(2)
        await wiggle(a)
        await a.shot("05_player_finished")

        # 5 session figures, incidents, inspector, analytics
        await scroll_to(a, ".ss-info", -20)
        await a.shot("06_info_and_session")
        m = await a.js("[...document.querySelectorAll('.ss-metrics')[0].querySelectorAll('.ss-m')].map(e => e.innerText.replace(/\\n/g,' '))")
        d.log(f"session metrics: {m}")
        await scroll_to(a, "[class*=st-key-inc_s_]", -160)
        await a.shot("07_incidents")
        n_inc = await a.js("document.querySelectorAll('[class*=st-key-inc_s_]').length")
        d.log(f"incident cards for this session: {n_inc}")
        first = await a.js("(() => { const e = document.querySelector('[class*=st-key-pick_s_]'); return e ? [...e.classList].find(c => c.startsWith('st-key-')).slice(7) : null })()")
        if first:
            await click_key(a, first)
            await a.wait_for("!!document.querySelector('[role=dialog]')", 15)
            await asyncio.sleep(1.5)
            await a.shot("08_incident_inspector")
            dlg = await a.js("document.querySelector('[role=dialog]').innerText")
            d.log("inspector: " + " | ".join(l for l in dlg.splitlines() if l.strip())[:400])
            await a.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            await asyncio.sleep(1)
        await scroll_to(a, "[class*=st-key-inc_s_]", 360)
        await a.shot("09_session_analytics")
        await click_key(a, "nav_results")  # the top-bar link opens the gallery's Results tab
        await a.wait_for("!!document.querySelector('#results')", 15)
        await scroll_to(a, "#results", -40)
        await a.shot("10_history")
        hist = await a.js("[...document.querySelectorAll('.ss-metrics.five .ss-m')].map(e => e.innerText.replace(/\\n/g,' '))")
        d.log(f"history metrics: {hist}")
        await scroll_to(a, "[data-baseweb=tab-list]", -40)
        await a.shot("11_history_log")
        await a.click("[data-testid=stDownloadButton] button", "Export CSV")
        await asyncio.sleep(2.5)
        csvs = sorted((d.OUT / "download").glob("*.csv"), key=lambda p: p.stat().st_mtime)
        d.log(f"CSV export: {csvs[-1].name if csvs else None}, {len(csvs[-1].read_text(encoding='utf-8').splitlines()) - 1 if csvs else 0} rows")

        # 6 back to the gallery's source cards (Results is already in the gallery)
        await a.js("(document.querySelector('[data-testid=stMain]') || window).scrollTo(0, 0)")
        await a.click("[data-testid=stButtonGroup] button", "Demo footage")
        await a.wait_for("!location.search.includes('source')", 15)
        await asyncio.sleep(2)
        back = await a.js("!!document.querySelector('[class*=st-key-card_]')")
        d.log(f"back to gallery: {back}")

        # 7 upload: the real file uploader, then open and run the uploaded clip
        await a.click("[data-testid=stButtonGroup] button", "Upload video")
        await asyncio.sleep(1.5)
        tmp = d.OUT / UPLOAD_NAME
        shutil.copy2(UPLOAD_SRC, tmp)
        doc = await a.send("DOM.getDocument", depth=-1, pierce=True)
        node = await a.send("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")
        await a.send("DOM.setFileInputFiles", files=[str(tmp)], nodeId=node["nodeId"])
        ok = await a.wait_for("!!document.querySelector('.st-key-open_upload')", 30)
        await asyncio.sleep(1.5)
        await a.shot("12_upload")
        d.log(f"upload accepted and saved: {ok}; file on disk: {(ROOT / 'data/demo/uploads' / UPLOAD_NAME).exists()}")
        await click_key(a, "open_upload")
        await a.wait_for("location.search.includes('upload')", 20)
        await asyncio.sleep(2.5)
        await click_key(a, "bigplay")
        ok = await a.wait_for("!!document.querySelector('.ss-ptop[data-state=done]')", 120)
        await asyncio.sleep(1.5)
        await wiggle(a)
        await a.shot("13_upload_finished")
        sess = await a.js("[...document.querySelectorAll('.ss-h2 span')].map(e => e.innerText)[0]")
        d.log(f"uploaded clip run finished={ok}; session: {sess}")

        # 8 webcam
        await goto(a, d.APP + "/?source=webcam%3A0")
        await click_key(a, "bigplay")
        await asyncio.sleep(9)
        state = await a.js("document.querySelector('.ss-ptop')?.getAttribute('data-state')")
        msg = await a.js("document.querySelector('.ss-poster .msg')?.innerText || ''")
        frame = await a.js("!!document.querySelector('.st-key-player [data-testid=stImage] img')")
        d.log(f"webcam: state={state}, frame shown={frame}, message={msg!r}")
        if frame:  # a real camera is attached: stop it at once and keep no screenshot of the room
            await click_key(a, "ctl_stop")
            await asyncio.sleep(2)
            d.log("webcam produced frames; stopped immediately (no screenshot kept)")
        else:
            await a.shot("14_webcam")

        # 9 single-run lock: tab A runs, tab B must not be able to start
        await goto(a, d.APP + "/?source=demo%3Atrack_work_day.mp4")
        b = await page(d.PORT)
        await goto(b, d.APP + "/?source=demo%3Aballast_train.mp4")
        await click_key(a, "bigplay")
        await asyncio.sleep(6)
        await b.send("Page.reload")
        await b.wait_for("!!document.querySelector('.st-key-topbar')", 30)
        await asyncio.sleep(2.5)
        dis = await b.js("document.querySelector('.st-key-bigplay button')?.disabled")
        b_state = await b.js("document.querySelector('.ss-ptop')?.getAttribute('data-state')")
        b_top = await b.js("document.querySelector('.st-key-topbar').innerText.replace(/\\n/g,' ')")
        await b.shot("15_second_tab_locked")
        d.log(f"second tab while A runs: start disabled={dis}, player state={b_state}, top bar='{b_top}'")
        await a.wait_for("!!document.querySelector('.ss-ptop[data-state=done]')", 120)
        await asyncio.sleep(2)
        await b.send("Page.reload")
        await b.wait_for("!!document.querySelector('.st-key-topbar')", 30)
        await asyncio.sleep(2.5)
        dis2 = await b.js("document.querySelector('.st-key-bigplay button')?.disabled")
        d.log(f"after A finished: second tab start disabled={dis2}")
        exc = sum([await x.js("!!document.querySelector('[data-testid=stException]')") for x in (a, b)])
        d.log(f"Streamlit exceptions on pages: {exc}; DB at end {db_counts()}")
    finally:
        (ROOT / ".qa" / f"qa_log_{W}x{H}.txt").write_text("\n".join(d.LOG) + "\n", encoding="utf-8")
        edge.terminate()


if __name__ == "__main__":
    asyncio.run(main())
