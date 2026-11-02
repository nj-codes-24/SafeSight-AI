"""Transcode reviewed clips to 1280-wide mp4 for the demo, with attribution and a default zone per camera view."""
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
CLIPS = [  # candidate file, output name, title, restricted zone polygon (fractions of the frame)
    ("c04.webm", "track_work_day", "Track maintenance, day (3 workers)",
     [[0.0, 0.62], [0.42, 0.62], [0.42, 1.0], [0.0, 1.0]], "Live rail"),
    ("c06.ogv", "roadworks_night", "Jackhammer crew, night",
     [[0.42, 0.72], [0.82, 0.72], [0.82, 0.98], [0.42, 0.98]], "Breaking area"),
    ("c05.webm", "ballast_train", "Ballast train, moving camera", None, None),
    ("mixkit-1440.mp4", "helmet_put_on", "Worker puts helmet on (violation then compliant)", None, None),
    ("mixkit-1459.mp4", "framing_bare_head", "Bare-headed worker behind framing", None, None),
]
MIXKIT = {"license": "Mixkit Stock Video Free License (per clip page). Standalone redistribution unconfirmed: fetch, do not ship",
          "license_url": "https://mixkit.co/license/", "artist": "Mixkit"}


def main():
    meta = {m["file"]: m for m in json.loads((DEMO / "candidates.json").read_text(encoding="utf-8"))}
    out, cfg_path = [], ROOT / "models" / "runtime_config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    zones = cfg.setdefault("zones", {})
    for src, name, title, poly, zname in CLIPS:
        mix = src.startswith("mixkit")
        cap = cv2.VideoCapture(str(DEMO / ("mixkit" if mix else "candidates") / src))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        w, h = int(cap.get(3)), int(cap.get(4))
        size = (1280, int(h * 1280 / w))
        vw = cv2.VideoWriter(str(DEMO / f"{name}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        n = 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            vw.write(cv2.resize(f, size, interpolation=cv2.INTER_AREA))
            n += 1
        vw.release()
        cap.release()
        m = {**MIXKIT, "page": f"https://mixkit.co/ (clip {src})"} if mix else meta[src]
        out.append({"file": f"{name}.mp4", "title": title, "frames": n, "fps": fps, "source_page": m["page"],
                    "license": m["license"], "license_url": m["license_url"], "artist": m["artist"]})
        if poly:
            zones[name] = [{"name": zname, "polygon": poly}]
        print(name, n, fps)
    (DEMO / "demo_clips.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    cfg_path.write_text(json.dumps(cfg, indent=1))


if __name__ == "__main__":
    main()
