"""Label set m2-provisional-v1.2: v1 plus identity anchors (schema safesight.labels/1.1), then locked.

    python scripts/validation/labels_m2_provisional_v1_2.py

Only anchors are added: where each labelled worker was at a given time, as normalised points (x, y) on the frame, read
by eye from plain frames with a coordinate grid (scripts/validation/anchor_sheet.py), never from model boxes. No event
time, kind, state or interval changes. Anchors are given only where several people could be confused; elsewhere
matching falls back to time and says so. Like v1 this is an AI-made provisional set, and it was made after the M2
error analysis (not blind), so it serves the identity-aware diagnostic comparison only.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.annotations import SCHEMA_1_1, load_set, lock  # noqa: E402

BASE = ROOT / "reports" / "validation" / "annotations"
SRC, DST = BASE / "m2-provisional-v1", BASE / "m2-provisional-v1.2"
ANCHORS = {  # event id -> [(t, x, y)]: body centre of the labelled worker
    "c01-E01": [(45.0, 0.88, 0.50), (55.0, 0.94, 0.40)],
    "c01-E02": [(55.0, 0.53, 0.45), (64.0, 0.56, 0.50)],
    "c01-E03": [(205.0, 0.19, 0.55), (215.0, 0.20, 0.60), (225.0, 0.13, 0.60)],
    "c01-E04": [(205.0, 0.78, 0.55), (215.0, 0.63, 0.62), (225.0, 0.61, 0.60)],
    "roadworks_night-E02": [(11.5, 0.21, 0.55)],
    "roadworks_night-E03": [(11.5, 0.89, 0.60)],
    "roadworks_night-E04": [(2.0, 0.51, 0.60), (8.0, 0.54, 0.62), (11.5, 0.49, 0.62)],
    "roadworks_night-E05": [(2.0, 0.65, 0.60), (8.0, 0.66, 0.60), (11.5, 0.62, 0.60)],
    "roadworks_night-E06": [(2.0, 0.75, 0.55), (3.5, 0.78, 0.50)],
    "c08-E01": [(3.0, 0.29, 0.66), (8.0, 0.27, 0.65)],
    "c08-E02": [(8.0, 0.31, 0.65)],
    "c08-E04": [(3.0, 0.17, 0.66)],
    "track_work_day-E01": [(2.0, 0.35, 0.55), (6.0, 0.39, 0.55)],
    "framing_bare_head-E01": [(3.0, 0.73, 0.55), (7.0, 0.73, 0.55)],
    "framing_bare_head-E02": [(3.0, 0.84, 0.55), (7.0, 0.84, 0.55)],
    "helmet_put_on-E01": [(0.5, 0.52, 0.45)],
}


def main():
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)
    labels = load_set(SRC)
    used = set()
    for cid, lab in labels.items():
        lab.update(schema=SCHEMA_1_1, label_set=DST.name, derived_from=SRC.name, changes=[])
        for e in lab["events"]:
            if e["id"] in ANCHORS:
                e["anchors"] = [{"t": t, "x": x, "y": y} for t, x, y in ANCHORS[e["id"]]]
                used.add(e["id"])
                lab["changes"].append({"event": e["id"], "added": "identity anchors", "found_by":
                                       "plain frames with a coordinate grid; post hoc (after M2 error analysis), not blind"})
        (DST / f"{cid}.json").write_text(json.dumps(lab, indent=1, ensure_ascii=False), encoding="utf-8")
    if set(ANCHORS) - used:
        raise SystemExit(f"unknown event ids: {sorted(set(ANCHORS) - used)}")
    m = lock(DST, note="v1 plus identity anchors only (schema 1.1); for identity-aware diagnostics; not primary")
    print(f"{DST.name}: {len(labels)} files, {len(used)} events anchored, combined {m['combined_sha256']}")


if __name__ == "__main__":
    main()
