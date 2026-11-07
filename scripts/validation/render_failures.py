"""Error-analysis material: evidence frames for false alarms and frames from missed episodes, plus review montages.

    python scripts/validation/render_failures.py

Runs after scoring (model output may be shown here; this is not label creation). Writes JPEGs (git-ignored, local
only) to reports/validation/representative_failures/<category>/ and montages to .../_montage_<category>.jpg.
"""
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VAL = ROOT / "reports" / "validation"
OUT = VAL / "representative_failures"


def header(im, text, width=640):
    im = cv2.resize(im, (width, int(im.shape[0] * width / im.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.rectangle(im, (0, 0), (width, 22), (0, 0, 0), -1)
    cv2.putText(im, text[:90], (4, 16), 0, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return im


def frame_at(path, t):
    cap = cv2.VideoCapture(str(ROOT / path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * fps))
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def montage(paths, out, cols=3):
    ims = [cv2.imread(str(p)) for p in paths[:12]]
    ims = [im for im in ims if im is not None]
    if not ims:
        return
    h = max(im.shape[0] for im in ims)
    ims = [cv2.copyMakeBorder(im, 0, h - im.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for im in ims]
    rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
    rows = [np.hstack(r + [np.full_like(ims[0], 255)] * (cols - len(r))) for r in rows]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    labels = {p.stem: json.loads(p.read_text(encoding="utf-8"))
              for p in (VAL / "annotations" / "m2-provisional-v1").glob("*.json")}
    made = {}
    with open(VAL / "false_alarm_analysis.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):  # unscorable alerts too: they are where a label may be too cautious
            im = cv2.imread(r["evidence"]) if r["evidence"] else None
            if im is None:
                im = frame_at(labels[r["clip_id"]]["file"], float(r["t_s"]))
            if im is None:
                continue
            d = OUT / r["category"]
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{r['clip_id']}_{float(r['t_s']):07.2f}_{r['incident_id']}.jpg"
            cv2.imwrite(str(p), header(im, f"{r['category']} {r['clip_id']} t={r['t_s']}s W{r['worker_id']} "
                                           f"{r['hazard']} label={r['label_state_at_t']}"), [cv2.IMWRITE_JPEG_QUALITY, 85])
            made.setdefault(r["category"], []).append(p)
    with open(VAL / "missed_event_analysis.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lab = labels[r["clip_id"]]
            a, b = float(r["start_s"]), float(r["end_s"])
            d = OUT / "missed"
            d.mkdir(parents=True, exist_ok=True)
            for k, t in (("early", min(b, a + 1.0)), ("mid", (a + b) / 2)):
                im = frame_at(lab["file"], t)
                if im is None:
                    continue
                p = d / f"{r['event_id']}_{k}_{t:07.2f}.jpg"
                cv2.imwrite(str(p), header(im, f"MISSED {r['event_id']} t={t:.1f}s {r['worker']} ({r['observability']})"),
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                made.setdefault("missed", []).append(p)
    for cat, paths in made.items():
        montage(paths, OUT / f"_montage_{cat}.jpg")
        print(cat, len(paths))


if __name__ == "__main__":
    main()
