"""Interleaved A/B of live-loop throughput: original UI (port 8502) vs redesigned UI (8501), same clip, same viewport.

Throughput = frames / (session save time - session start time), read from the incident database.
"""
import asyncio
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as d  # noqa: E402

W, H = int(sys.argv[1]), int(sys.argv[2])
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
APPS = {"original": "http://localhost:8502", "redesign": "http://localhost:8501"}


def last_throughput():
    c = sqlite3.connect(ROOT / "logs/incidents/incidents.db")
    sid, end, frames = c.execute("select session_id, started_at, frames from sessions order by rowid desc limit 1").fetchone()
    dur = (datetime.fromisoformat(end) - datetime.strptime(sid[1:], "%Y%m%d-%H%M%S")).total_seconds()
    return sid, frames, dur


async def main():
    d.SHOTS = ROOT / ".qa" / "ab_shots"
    d.SHOTS.mkdir(parents=True, exist_ok=True)
    edge = subprocess.Popen([d.EDGE, "--headless=new", f"--remote-debugging-port={d.PORT}", f"--user-data-dir={d.OUT / 'edge_profile'}",
                             f"--window-size={W},{H}", "--no-first-run", "--hide-scrollbars", "--remote-allow-origins=*", "about:blank"])
    res = {k: [] for k in APPS}
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
        await cdp.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        for r in range(ROUNDS):
            for name, url in APPS.items():
                await cdp.send("Page.navigate", url=url + "/live")
                await cdp.wait_for("!!document.querySelector('[data-testid=stSelectbox]')", 60)
                await asyncio.sleep(2)
                await cdp.choose_clip("Jackhammer crew, night")
                await cdp.click("[data-testid=stButton] button", "Start")
                await cdp.wait_for("document.body.innerText.includes('Finished')", 180)
                sid, frames, dur = last_throughput()
                res[name].append(round(frames / dur, 1))
                print(f"round {r + 1} {name:9s} {sid} {frames} frames in {dur:.0f} s = {frames / dur:.1f} FPS", flush=True)
                await asyncio.sleep(1)
    finally:
        edge.terminate()
    print({k: (v, round(sum(v) / len(v), 1)) for k, v in res.items()})
    (ROOT / ".qa" / f"ab_{W}x{H}.json").write_text(json.dumps(res, indent=1))


asyncio.run(main())
