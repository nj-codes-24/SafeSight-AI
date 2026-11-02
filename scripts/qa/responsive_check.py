"""Layout check at several screen sizes: gallery, player and the information below it. Starts no monitoring run.
Usage: .venv\\Scripts\\python.exe scripts\\qa\\responsive_check.py"""
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as d  # noqa: E402

SIZES = [(1920, 1080), (1440, 900), (1366, 768), (1024, 768), (768, 1024)]
OUT = ROOT / ".qa" / "screenshots" / "responsive"


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d.SHOTS = OUT
    edge = subprocess.Popen([d.EDGE, "--headless=new", f"--remote-debugging-port={d.PORT}", f"--user-data-dir={d.OUT / 'edge_profile'}",
                             "--window-size=1920,1080", "--no-first-run", "--hide-scrollbars", "--remote-allow-origins=*", "about:blank"])
    try:
        for _ in range(50):
            try:
                page = next(t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{d.PORT}/json").read()) if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        cdp = d.CDP(await websockets.connect(page["webSocketDebuggerUrl"], max_size=256 * 2**20))
        asyncio.ensure_future(cdp.reader())
        await cdp.send("Page.enable")
        for w, h in SIZES:
            await cdp.send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=w < 900)
            for name, url in (("gallery", d.APP), ("player", d.APP + "/?source=demo%3Aroadworks_night.mp4")):
                await cdp.send("Page.navigate", url=url)
                await cdp.wait_for("!!document.querySelector('.st-key-topbar')", 60)
                await asyncio.sleep(3)
                await cdp.shot(f"{w}x{h}_{name}")
                over = await cdp.js("document.documentElement.scrollWidth > window.innerWidth + 1"
)
                ratio = await cdp.js("(() => { const p = document.querySelector('.st-key-player'); if (!p) return null; const r = p.getBoundingClientRect(); return +(r.width / r.height).toFixed(3); })()")
                cols = await cdp.js("(() => { const c = [...document.querySelectorAll('[class*=st-key-card_]')]; if (!c.length) return null; const t = c[0].getBoundingClientRect().top; return c.filter(e => Math.abs(e.getBoundingClientRect().top - t) < 5).length; })()")
                d.log(f"{w}x{h} {name}: overflow={over} player_ratio={ratio} cards_per_row={cols}")
                if name == "player":
                    await cdp.js("(() => { const e = document.querySelector('.ss-info'); e && e.scrollIntoView({block: 'start'}); })()")
                    await asyncio.sleep(1)
                    await cdp.shot(f"{w}x{h}_player_info")
    finally:
        (ROOT / ".qa" / "responsive_log.txt").write_text("\n".join(d.LOG) + "\n", encoding="utf-8")
        edge.terminate()


asyncio.run(main())
