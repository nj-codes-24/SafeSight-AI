"""Reject images whose derived no_helmet label covers a real helmet, found by eye in the M2-disagreement sheet."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
order = json.loads((ROOT / "reports/diagnostics/sh17_audit/disagree_order.json").read_text())
BY_EYE = [17, 19, 22, 23, 36, 42, 66, 71, 104, 122, 123, 124]  # sheet positions: row * 12 + column
stems = sorted({order[i] for i in BY_EYE})
(ROOT / "reports/diagnostics/sh17_audit/rejected_by_eye.json").write_text(json.dumps(stems, indent=0))
D = ROOT / "data/processed/merged_h_sh17"
for s in stems:
    (D / "images/train" / f"{s}.jpg").unlink(missing_ok=True)
    (D / "labels/train" / f"{s}.txt").unlink(missing_ok=True)
print(len(stems), len(list((D / "images/train").glob("sh17_*"))))
c = {}
for f in (D / "labels/train").iterdir():
    for l in f.read_text().splitlines():
        c[l[0]] = c.get(l[0], 0) + 1
print(c)
