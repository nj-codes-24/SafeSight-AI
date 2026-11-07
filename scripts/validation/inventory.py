"""Inventory the evaluation footage: hashes, decode check, cross-clip overlap, provenance, and review contact sheets.

    python scripts/validation/inventory.py            manifest + overlap check + overview contact sheets
    python scripts/validation/inventory.py --sheets   contact sheets only

Writes reports/validation/clip_manifest.csv and reports/validation/review/ (contact sheets are JPEG, which git ignores:
they show identifiable people from third-party footage and stay on this machine). Visual descriptions come from
reports/validation/clip_review.json, written by a reviewer after looking at the sheets, never from model output.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DEMO = ROOT / "data" / "demo"
OUT = ROOT / "reports" / "validation"
REVIEW = OUT / "review"

# Provenance, from training/prepare_demo.py and the two manifests: the demo clips are 1280-wide re-encodes.
DERIVED = {"track_work_day.mp4": "candidates/c04.webm", "roadworks_night.mp4": "candidates/c06.ogv",
           "ballast_train.mp4": "candidates/c05.webm", "helmet_put_on.mp4": "mixkit/mixkit-1440.mp4",
           "framing_bare_head.mp4": "mixkit/mixkit-1459.mp4"}
# Recordings from the same site or session are one statistical cluster.
GROUPS = {"c00": "G01-moira-close", "c01": "G01-moira-close", "c02": "G01-moira-close", "c03": "G02-scaffold",
          "c04": "G03-geneve-track", "c05": "G04-lodz-track", "c06": "G05-japan-roadworks", "c07": "G06-niosh-mast-climber",
          "c08": "G07-ljubljana-street", "c09": "G08-concrete-pour", "c10": "G08-concrete-pour", "c11": "G09-forklift-film",
          "c12": "G10-concrete-saw", "mixkit-1440": "G11-mixkit-1440", "mixkit-1459": "G12-mixkit-1459"}
# Development: used to choose the application threshold and tune the tracker (docs/evaluation.md). Held out: never tuned on.
DEV_RECORDINGS = {"c04", "c05", "c06", "mixkit-1440", "mixkit-1459"}


def files():
    out = [p for p in sorted(DEMO.glob("*.mp4"))]
    out += sorted((DEMO / "candidates").glob("c*.*")) + sorted((DEMO / "mixkit").glob("*.mp4"))
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


def dhash(frame):
    g = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (17, 16), interpolation=cv2.INTER_AREA)
    return np.packbits((g[:, 1:] > g[:, :-1]).flatten())


def scan(p):
    """Decode every frame; return metadata, decode failures and a dHash per second (for overlap detection)."""
    cap = cv2.VideoCapture(str(p))
    meta = {"fps": cap.get(cv2.CAP_PROP_FPS), "frames_reported": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "codec": int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("latin-1", "replace").strip("\x00")}
    n, hashes, dark = 0, [], 0
    step = max(1, round(meta["fps"] or 25))
    while True:
        ok = cap.grab()
        if not ok:
            break
        if n % step == 0:
            ok, f = cap.retrieve()
            if ok:
                hashes.append(dhash(f))
                dark += f.mean() < 20
        n += 1
    cap.release()
    meta.update(frames_decoded=n, duration_s=round(n / meta["fps"], 2) if meta["fps"] else None,
                dark_seconds=int(dark), readable=n > 0)
    return meta, hashes


def overlap(ha, hb, max_bits=6):
    """Share of sampled seconds of a that have a near-identical second in b (Hamming distance of 256-bit dHash)."""
    if not ha or not hb:
        return 0.0
    a, b = np.unpackbits(np.array(ha), axis=1), np.unpackbits(np.array(hb), axis=1)
    d = (a[:, None, :] != b[None, :, :]).sum(-1)
    return float((d.min(1) <= max_bits).mean())


def contact_sheet(p, out, every_s=None, cols=5, width=360, zones=None, start_s=0.0, end_s=None):
    """Timestamped frames in a grid (no model output). Returns the sheet paths."""
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = n / fps
    end_s = min(end_s or dur, dur)
    every_s = every_s or max(0.5, round((end_s - start_s) / 30, 1))
    times = list(np.arange(start_s, end_s, every_s))
    thumbs = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = cap.read()
        if not ok:
            continue
        h, w = f.shape[:2]
        if zones:
            for z in zones:
                pts = (np.array(z["polygon"]) * [w, h]).astype(np.int32)
                cv2.polylines(f, [pts], True, (0, 200, 255), max(2, w // 400), cv2.LINE_AA)
        f = cv2.resize(f, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
        cv2.rectangle(f, (0, 0), (width, 22), (0, 0, 0), -1)
        cv2.putText(f, f"{t:7.2f}s  f{int(t * fps)}", (4, 16), 0, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(f)
    cap.release()
    paths = []
    per = cols * 6
    for k in range(0, len(thumbs), per):
        chunk = thumbs[k:k + per]
        rows = [chunk[i:i + cols] for i in range(0, len(chunk), cols)]
        th, tw = chunk[0].shape[:2]
        sheet = np.full((th * len(rows), tw * cols, 3), 255, np.uint8)
        for r, row in enumerate(rows):
            for c, im in enumerate(row):
                sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = im[:th, :tw]
        path = out.parent / f"{out.stem}_{k // per + 1:02d}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", action="store_true", help="contact sheets only")
    a = ap.parse_args()
    app_zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    meta = {m["file"]: m for m in json.loads((DEMO / "candidates.json").read_text(encoding="utf-8"))}
    demo = {m["file"]: m for m in json.loads((DEMO / "demo_clips.json").read_text(encoding="utf-8"))}
    review = json.loads((OUT / "clip_review.json").read_text(encoding="utf-8")) if (OUT / "clip_review.json").exists() else {}
    if not a.sheets:
        rows, hashes = [], {}
        for p in files():
            rel = p.relative_to(DEMO).as_posix()
            m, hashes[rel] = scan(p)
            src_rel = DERIVED.get(rel)
            rec = Path(src_rel or rel).stem
            info = meta.get(Path(src_rel or rel).name, {}) if not rec.startswith("mixkit") else {}
            d = demo.get(rel, {})
            evaluated = rel in DERIVED or (rel.startswith("candidates/") and rec not in DEV_RECORDINGS)
            rows.append({
                "clip_id": p.stem, "file": f"data/demo/{rel}", "recording": rec, "source_group": GROUPS[rec],
                "derived_from": f"data/demo/{src_rel}" if src_rel else "", "sha256": sha256(p), "bytes": p.stat().st_size,
                **{k: m[k] for k in ("codec", "fps", "frames_reported", "frames_decoded", "duration_s", "width", "height",
                                     "dark_seconds", "readable")},
                "split": "development" if rec in DEV_RECORDINGS else "held-out",
                "evaluated": "yes" if evaluated else f"no: duplicate of {next((k for k, v in DERIVED.items() if v == rel), '?')}",
                "title": info.get("title") or d.get("title", ""), "source_page": info.get("page") or d.get("source_page", ""),
                "license": info.get("license") or d.get("license", ""),
                "internal_evaluation_use": "yes (licence permits use; frames not redistributed)"
                if "Mixkit" not in (info.get("license") or d.get("license", "")) else "yes (local only; Mixkit redistribution unconfirmed)",
                "app_zones": "; ".join(z["name"] for z in app_zones.get(p.stem, [])),
                **{k: review.get(p.stem, review.get(rec, {})).get(k, "") for k in
                   ("perspective", "environment", "activities", "observable_hazards", "lighting", "distance", "camera_motion",
                    "usability", "existing_annotations")},
            })
        keys = list(hashes)
        pairs = []
        for i, x in enumerate(keys):
            for y in keys[i + 1:]:
                o = max(overlap(hashes[x], hashes[y]), overlap(hashes[y], hashes[x]))
                if o > 0.2:
                    pairs.append({"a": x, "b": y, "shared_seconds_ratio": round(o, 3)})
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "clip_manifest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        (OUT / "overlap_check.json").write_text(json.dumps({"method": "dHash (256 bit) of one frame per second; pairs where "
                                                            "more than 20 % of seconds have a match within 6 bits",
                                                            "pairs": pairs}, indent=1))
        for r in rows:
            print(f"{r['clip_id']:<18} {r['recording']:<12} {r['split']:<11} {r['duration_s']:>7}s {r['width']}x{r['height']} "
                  f"{r['fps']:.2f}fps decoded {r['frames_decoded']}/{r['frames_reported']} dark_s {r['dark_seconds']} {r['evaluated']}")
        print("overlaps:", pairs)
    for p in files():
        rel = p.relative_to(DEMO).as_posix()
        if rel in DERIVED.values():
            continue  # duplicates are not reviewed separately
        contact_sheet(p, REVIEW / "overview" / p.stem, zones=app_zones.get(p.stem))


if __name__ == "__main__":
    main()
