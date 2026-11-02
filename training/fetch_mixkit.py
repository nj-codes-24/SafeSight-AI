"""Fetch the Mixkit clips used by the demo. These are downloaded, not shipped: standalone redistribution is unconfirmed.

Only clips whose own page states the Mixkit Stock Video Free License are listed. Many Mixkit clips are under a
Restricted, personal-use-only licence, so check the clip page before adding an ID here.
"""
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "demo" / "mixkit"
IDS = [1440, 1459]
OUT.mkdir(parents=True, exist_ok=True)
for i in IDS:
    dst = OUT / f"mixkit-{i}.mp4"
    if not dst.exists():
        req = urllib.request.Request(f"https://assets.mixkit.co/videos/{i}/{i}-720.mp4", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            dst.write_bytes(r.read())
    print(dst.name, dst.stat().st_size // 1024, "KB")
