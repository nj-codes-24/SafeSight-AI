"""Minimal Chrome DevTools Protocol driver used by the browser QA scripts in this folder.

It drives a headless Microsoft Edge (or Chrome) against the running app with real mouse and keyboard events, so the
QA scripts exercise the actual Streamlit page. Outputs (screenshots, downloads, logs, browser profile) go to .qa/,
which is git-ignored.

Environment overrides:
  SAFESIGHT_URL   app address (default http://localhost:8501)
  SAFESIGHT_EDGE  browser executable (default: Microsoft Edge in Program Files (x86))
"""
import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".qa"
SHOTS = OUT / "screenshots"
EDGE = os.environ.get("SAFESIGHT_EDGE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
APP = os.environ.get("SAFESIGHT_URL", "http://localhost:8501")
PORT = 9333
W, H = 1600, 1000
LOG: list[str] = []


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
    LOG.append(line)
    print(line, flush=True)


class CDP:
    """One browser page over a DevTools websocket: send commands, evaluate JavaScript, click, screenshot."""

    def __init__(self, ws):
        self.ws, self.n, self.pending = ws, 0, {}

    async def reader(self):
        async for msg in self.ws:
            m = json.loads(msg)
            if "id" in m and m["id"] in self.pending:
                self.pending.pop(m["id"]).set_result(m)

    async def send(self, method, **params):
        self.n += 1
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        r = await fut
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r.get("result", {})

    async def js(self, expr):
        r = await self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def wait_for(self, expr, timeout=60, every=0.25):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            if await self.js(expr):
                return True
            await asyncio.sleep(every)
        return False

    async def click_at(self, x, y):
        for kind in ("mousePressed", "mouseReleased"):
            await self.send("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)

    async def click(self, selector, contains=None):
        """Click the centre of the first visible element matching selector (and containing text)."""
        expr = f"""(() => {{
          const els = [...document.querySelectorAll({json.dumps(selector)})].filter(e => e.offsetParent !== null &&
            ({json.dumps(contains)} === null || e.innerText.trim().includes({json.dumps(contains)})));
          if (!els.length) return null;
          els[0].scrollIntoView({{block: 'center'}});
          const r = els[0].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];
        }})()"""
        xy = await self.js(expr)
        if not xy:
            raise RuntimeError(f"not found: {selector} {contains!r}")
        await self.click_at(*xy)

    async def shot(self, name):
        r = await self.send("Page.captureScreenshot", format="png")
        SHOTS.mkdir(parents=True, exist_ok=True)
        path = SHOTS / f"{name}.png"
        path.write_bytes(base64.b64decode(r["data"]))
        log(f"screenshot {path.relative_to(ROOT)}")

    async def choose_clip(self, title):
        """Pick an option in the first select box on the page (used by the A/B timing script)."""
        await self.click("[data-testid=stSelectbox] [role=combobox]")
        await asyncio.sleep(0.6)
        await self.click("[role=option]", title)
        await asyncio.sleep(1.5)
