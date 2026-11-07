"""Label set m2-provisional-v1.1: v1 plus the corrections found during error analysis, then locked.

    python scripts/validation/labels_m2_provisional_v1_1.py

These corrections are post hoc and not blind: each was found by looking at a model alert at full resolution. That is
why v1 stays the primary, pre-registered result and v1.1 is reported beside it as a sensitivity check, never instead
of it. Only clear errors are corrected here; judgement calls go to the human review queue in
docs/product_research/18_VALIDATION_RESULTS.md.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.annotations import load_set, lock  # noqa: E402

BASE = ROOT / "reports" / "validation" / "annotations"
SRC, DST = BASE / "m2-provisional-v1", BASE / "m2-provisional-v1.1"
CHANGES = [
    {"clip_id": "c01", "hazard": "PPE.HEAD.MISSING", "interval": [230.5, 245.0], "from": "uncertain", "to": "monitorable",
     "note": "close shot; the worker wears a dark grey hard hat",
     "reason": "v1 said 'dark rigid headwear: hard hat or not unclear' from the contact sheet; at full resolution the "
               "shell and brim are unambiguous at 239-245 s",
     "found_by": "inspecting alert INC-20261105-26ABA020 (post hoc, not blind)"},
]


def main():
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)
    labels = load_set(SRC)
    for cid, lab in labels.items():
        lab["label_set"] = DST.name
        lab["derived_from"] = SRC.name
        lab["changes"] = []
        for ch in (c for c in CHANGES if c["clip_id"] == cid):
            iv = next(i for i in lab["intervals"] if i["hazard"] == ch["hazard"] and [i["start_s"], i["end_s"]] == ch["interval"])
            if iv["state"] != ch["from"]:
                raise SystemExit(f"{cid}: expected {ch['from']} at {ch['interval']}, found {iv['state']}")
            iv["state"], iv["note"] = ch["to"], ch["note"]
            lab["changes"].append({k: ch[k] for k in ("hazard", "interval", "from", "to", "reason", "found_by")})
        (DST / f"{cid}.json").write_text(json.dumps(lab, indent=1, ensure_ascii=False), encoding="utf-8")
    m = lock(DST, note="v1 plus post-hoc corrections found during M2 error analysis; sensitivity check, not primary")
    print(f"{DST.name}: {len(labels)} files, {len(CHANGES)} change(s), combined {m['combined_sha256']}, "
          f"ground truth {m['ground_truth']}")


if __name__ == "__main__":
    main()
