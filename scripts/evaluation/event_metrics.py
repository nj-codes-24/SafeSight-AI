"""Event-level evaluation of one monitored source against labelled hazard episodes.

Ground truth (JSON): {"source": "...", "duration_s": 3600, "episodes": [{"hazard": "ZONE_INTRUSION", "zone": "Aisle 4",
"start_s": 812.4, "end_s": 829.0}]}. Hazards use the pipeline's incident types or taxonomy codes.

Predictions come from an incidents database session, or from a JSON list of {"type", "t", "zone"}.

    python scripts/evaluation/event_metrics.py --truth gt.json --session S20261103-080000 [--db logs/incidents/incidents.db]
    python scripts/evaluation/event_metrics.py --truth gt.json --predictions preds.json --out report.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from database.database import DB_PATH, IncidentDB  # noqa: E402
from intelligence.event_metrics import evaluate  # noqa: E402


def predictions_from_db(db_path, session_id) -> list:
    db = IncidentDB(db_path)
    hazard = {a["incident_id"]: a["hazard_code"] for a in db.assessments(session_id)}
    rows = db.rows(session_id)
    if not rows:
        raise SystemExit(f"no incidents for session {session_id} in {db_path}")
    return [{"type": r["incident_type"], "t": r["video_time_s"], "zone": r["zone"], "hazard": hazard.get(r["incident_id"]),
             "incident_id": r["incident_id"]} for r in rows]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--truth", required=True, help="ground-truth episodes JSON")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="session id in the incidents database")
    src.add_argument("--predictions", help="JSON list of predictions instead of a database session")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--tolerance", type=float, default=2.0, help="seconds allowed before an episode starts or after it ends")
    ap.add_argument("--out", help="write the report here as JSON")
    a = ap.parse_args(argv)
    truth = json.loads(Path(a.truth).read_text(encoding="utf-8"))
    preds = (predictions_from_db(a.db, a.session) if a.session
             else json.loads(Path(a.predictions).read_text(encoding="utf-8")))
    report = {"source": truth.get("source"), **evaluate(truth["episodes"], preds, truth["duration_s"], a.tolerance)}
    text = json.dumps(report, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return report


if __name__ == "__main__":
    main()
