"""Safety-policy correctness (milestone M3): a rule nobody authorised never produces a confirmed violation; unseen is
never compliant; a camera that cannot observe never resolves anything; every operator decision is audited.

Same scripted detector as tests/test_lifecycle.py: no model, GPU or footage."""
import json

import numpy as np

from database.database import IncidentDB
from inference.incident_lifecycle import RESOLVED, VIEW_CHANGED
from inference.tracker import CONFIRMED_COMPLIANCE, CONFIRMED_VIOLATION, NOT_CONFIRMED, PPE_NOT_OBSERVABLE, Pipeline
from intelligence import ppe_policy as ppe
from runtime.__main__ import main
from tests.test_lifecycle import CFG, FPS, REQUIRED, H, Script, W, bare, head, life, person, run

PROVISIONAL = {**REQUIRED, "entries": [{"id": "P1", "camera": "cam", "ppe": ["head"], "required": True, "status": "provisional"}]}


def test_a_provisional_rule_gives_a_review_never_a_confirmed_violation(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(4)), policy=PROVISIONAL)
    (r,) = life(db)
    assert r["classification"] == "requires_review" and r["requirement"]["status"] == "provisional"
    assert p.ppe_seconds[NOT_CONFIRMED] > 3.9 and p.ppe_seconds[CONFIRMED_VIOLATION] == 0
    assert db.notifications()[0]["kind"] == "review" and db.assessments()[0]["requires_review"] is True


def test_a_confirmed_rule_in_a_draft_document_is_a_violation_and_says_the_document_is_draft(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(4)), policy=REQUIRED)
    (r,) = life(db)
    req = r["requirement"]
    assert r["classification"] == "violation" and req["status"] == "confirmed" and req["policy_status"] == "draft"


def test_a_provisional_rule_never_produces_confirmed_compliance_either(tmp_path):
    helmet = Script().add(3, [person()], [head("helmet")])
    p, _ = run(tmp_path, helmet, policy=PROVISIONAL)
    assert p.ppe_seconds[CONFIRMED_COMPLIANCE] == 0 and p.ppe_seconds[NOT_CONFIRMED] > 2.9


def test_a_worker_whose_head_is_never_seen_is_not_compliant(tmp_path):
    p, db = run(tmp_path, Script().add(5, [person()], []), policy=REQUIRED)  # person tracked, no head evidence at all
    assert db.rows() == [] and p.ppe_seconds[CONFIRMED_COMPLIANCE] == 0 and p.ppe_seconds[PPE_NOT_OBSERVABLE] > 4.9


def test_a_view_interruption_ends_an_incident_with_unknown_outcome_never_resolved(tmp_path):
    db = IncidentDB(tmp_path / "t.db")
    s = Script().add(**bare(3))
    p = Pipeline(s, FPS, CFG, "cam", zones=[], db=db, evidence_dir=tmp_path / "ev", annotate=False, ppe_policy=REQUIRED)
    frame = np.zeros((H, W, 3), np.uint8)
    for _ in range(len(s.frames)):
        p.process(frame)
    ended = p.interrupt_view(3.0, 2.5, VIEW_CHANGED, "VE-1", "camera moved")
    p.finish("scripted")
    (r,) = life(db)
    assert ended == [r["incident_id"]] and r["end_reason"] == VIEW_CHANGED and r["end_reason"] != RESOLVED
    assert r["ended_t"] <= 2.5  # ends at the last reliable observation, not when the change was confirmed


def test_operator_decisions_are_audited_and_survive_detector_closure(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(3)), finish=False)
    iid = db.rows()[0]["incident_id"]
    db.set_status(iid, "REVIEWED", reviewer="SL", note="bare head confirmed on evidence")
    db.set_status(iid, "FALSE_ALARM")  # an interface without user identity is recorded as unnamed
    p.finish("scripted")
    assert db.rows()[0]["status"] == "FALSE_ALARM"
    h = db.reviews(iid)
    assert [(x["previous_status"], x["status"], x["reviewer"]) for x in h] == [("OPEN", "REVIEWED", "SL"), ("REVIEWED", "FALSE_ALARM", None)]
    assert h[0]["note"] == "bare head confirmed on evidence" and h[0]["reviewed_utc"].endswith("+00:00")


def test_runtime_cli_records_a_named_review(tmp_path, capsys):
    db = IncidentDB(tmp_path / "rt.db")
    iid = db.add("NO_HELMET", 1, 0.9, "cam", "S1")
    db.close()
    cfg = tmp_path / "cli.json"
    cfg.write_text(json.dumps({"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                                           "status_file": str(tmp_path / "s.json"), "log_file": str(tmp_path / "r.log"),
                                           "pipeline_config": str(tmp_path / "none.json")},
                               "inference": {"backend": "null"}, "cameras": [{"id": "cam", "source": {"type": "synthetic"}}]}))
    assert main(["incident", "review", "--config", str(cfg), "--incident", iid, "--status", "REVIEWED"]) == 2  # --by required
    assert main(["incident", "review", "--config", str(cfg), "--incident", "INC-NOPE", "--status", "REVIEWED", "--by", "SL"]) == 2
    assert main(["incident", "review", "--config", str(cfg), "--incident", iid, "--status", "FALSE_ALARM", "--by", "SL",
                 "--note", "shadow"]) == 0
    assert main(["incident", "list", "--config", str(cfg)]) == 0
    assert "status=FALSE_ALARM" in capsys.readouterr().out
    db = IncidentDB(tmp_path / "rt.db")
    assert [(r["reviewer"], r["source"]) for r in db.reviews(iid)] == [("SL", "runtime-cli")]


def _inspector(db_path, iid):
    import app.views.insights as ins
    from database.database import IncidentDB

    db = IncidentDB(db_path)
    ins.get_db = lambda: db  # a temporary database: never the dashboard's own
    ins.inspect(iid)


def test_dashboard_review_records_reviewer_reason_and_history(tmp_path):
    import pytest

    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    db = IncidentDB(tmp_path / "t.db")
    iid = db.add("NO_HELMET", 3, 0.81, "cam", "S1", video_time_s=12.5)
    db.close()
    at = AppTest.from_function(_inspector, args=(str(tmp_path / "t.db"), iid), default_timeout=60).run()
    at.selectbox[0].set_value("FALSE_ALARM")
    at.text_input[0].input("SL")
    at.text_input[1].input("dark hard hat on evidence")
    at = at.run()
    at.button[0].click()
    at = at.run()
    assert not at.exception
    db = IncidentDB(tmp_path / "t.db")
    assert db.rows()[0]["status"] == "FALSE_ALARM"
    assert [(r["reviewer"], r["note"], r["source"]) for r in db.reviews(iid)] == [("SL", "dark hard hat on evidence", "dashboard")]
    assert any("OPEN→FALSE_ALARM by SL" in c.value for c in at.caption)


def test_policy_document_status_is_reported_on_every_decision():
    r = ppe.PPEPolicy(PROVISIONAL).requirement("head", "cam")
    assert (r.state, r.status, r.policy_status, r.policy_version) == (ppe.REQUIRED, "provisional", "draft", "t-1")
