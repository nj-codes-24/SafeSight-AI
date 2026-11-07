"""Unit tests for the hazard taxonomy, the risk policy engine, event-level metrics and their pipeline wiring.

Everything here runs without a model, GPU or PyTorch.
"""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from database.database import COLUMNS, IncidentDB
from inference.incident_manager import NO_HELMET, ZONE, IncidentManager
from inference.zone_monitor import Zone
from intelligence.event_metrics import evaluate, match, poisson_interval, wilson
from intelligence.risk import DEFAULT_POLICY, LEVELS, RiskEngine, load_policy, validate_policy
from intelligence.taxonomy import ENERGIES, HAZARDS, SENSING, STATUSES, ZONE_KINDS, hazard_for, validate_kind

ROOT = Path(__file__).resolve().parents[1]
FRAME = np.zeros((20, 20, 3), np.uint8)


def approved(**changes):
    p = copy.deepcopy(DEFAULT_POLICY)
    p.update(status="approved", approved_by="Site safety lead", approved_on="2026-11-05", **changes)
    return p


# ------------------------------------------------------------------ taxonomy

def test_taxonomy_entries_are_consistent():
    for code, h in HAZARDS.items():
        assert code == h.code and h.energy in ENERGIES and h.status in STATUSES
        assert h.severity in range(1, 6) and h.sensing and set(h.sensing) <= SENSING and h.evidence
    for k in ZONE_KINDS.values():
        assert k.person_entry is None or k.person_entry in HAZARDS


def test_pipeline_types_map_to_hazards():
    assert hazard_for(NO_HELMET).code == "PPE.HEAD.MISSING"
    assert hazard_for(ZONE).code == "ZONE.ENTRY"  # no kind: the original restricted-zone meaning
    assert hazard_for(ZONE, "machine_exclusion").code == "MACH.ZONE.ENTRY"
    assert hazard_for("VEH.PED.CONFLICT").severity == 5
    with pytest.raises(ValueError):
        hazard_for(ZONE, "pedestrian_only")  # a person in a walkway is not the hazard


def test_unknown_zone_kind_is_rejected_not_downgraded():
    assert validate_kind(None) == "restricted"
    with pytest.raises(ValueError):
        validate_kind("electical")
    assert Zone("Z", [[0, 0], [1, 0], [1, 1]]).kind == "restricted"
    with pytest.raises(ValueError):
        Zone("Z", [[0, 0], [1, 0], [1, 1]], "electical")


# ------------------------------------------------------------------ policy validation

def test_default_policy_is_a_valid_draft():
    p = validate_policy(DEFAULT_POLICY)
    assert p["status"] == "draft" and load_policy(ROOT / "no_such_policy.json")["version"] == DEFAULT_POLICY["version"]


@pytest.mark.parametrize("change", [
    {"status": "approved"},  # approved without an approver
    {"status": "final"},
    {"exposure_bands_s": [60, 10]},
    {"severity": {"NOT.A.HAZARD": 3}},
    {"severity": {"ZONE.ENTRY": 7}},
    {"evidence": {"strong": 0.4, "moderate": 0.6}},
    {"context": [{"when": {"machine_state": "running"}, "severity_delta": 9}]},
    {"actions": {"URGENT": ["page"]}},
])
def test_invalid_policies_are_rejected(change):
    with pytest.raises(ValueError):
        validate_policy({**DEFAULT_POLICY, **change})


def test_matrix_that_lowers_risk_with_longer_exposure_is_rejected():
    p = copy.deepcopy(DEFAULT_POLICY)
    p["matrix"]["4"] = ["HIGH", "MEDIUM", "HIGH", "CRITICAL"]
    with pytest.raises(ValueError):
        validate_policy(p)


# ------------------------------------------------------------------ risk engine

def test_level_follows_severity_and_exposure():
    r = RiskEngine()
    assert r.band(0) == 1 and r.band(10) == 2 and r.band(299.9) == 3 and r.band(300) == 4
    assert r.assess("ZONE.ENTRY", 2).level == "LOW"
    assert r.assess("ZONE.ENTRY", 400).level == "HIGH"
    assert r.assess("MACH.ZONE.ENTRY", 2).level == "HIGH"
    assert r.assess("MACH.ZONE.ENTRY", 15).level == "CRITICAL"


def test_confidence_changes_evidence_never_risk():
    r = RiskEngine()
    weak, strong = r.assess("MACH.ZONE.ENTRY", 2, score=0.3), r.assess("MACH.ZONE.ENTRY", 2, score=0.95)
    assert weak.level == strong.level and weak.severity == strong.severity
    assert (weak.evidence, weak.requires_review) == ("weak", True)
    assert (strong.evidence, strong.requires_review) == ("strong", False)


def test_unknown_context_never_lowers_risk():
    r = RiskEngine(approved())
    base = r.assess("MACH.ZONE.ENTRY", 2)
    assert r.assess("MACH.ZONE.ENTRY", 2, context={}).severity == base.severity
    assert r.assess("MACH.ZONE.ENTRY", 2, context={"machine_state": "unknown"}).severity == base.severity
    locked = r.assess("MACH.ZONE.ENTRY", 2, context={"machine_state": "locked_out"})
    assert locked.severity == 2 and LEVELS.index(locked.level) < LEVELS.index(base.level)


def test_draft_policy_reports_but_does_not_apply_reductions():
    a = RiskEngine().assess("MACH.ZONE.ENTRY", 2, context={"machine_state": "locked_out"})
    assert a.severity == 5 and a.policy_status == "draft"
    assert any("not applied because the policy is a draft" in f for f in a.factors)


def test_site_and_zone_overrides():
    r = RiskEngine(approved(severity={"ZONE.ENTRY": 4}, zone_severity={"Press 3": 5}))
    assert r.assess("ZONE.ENTRY", 2).severity == 4
    a = r.assess("ZONE.ENTRY", 2, zone="Press 3")
    assert a.severity == 5 and a.level == "HIGH" and a.policy_status == "approved"
    assert a.actions == DEFAULT_POLICY["actions"]["HIGH"]


# ------------------------------------------------------------------ event metrics

def test_wilson_and_poisson_intervals():
    lo, hi = wilson(4, 4)
    assert abs(lo - 0.51) < 0.01 and hi == 1.0
    assert wilson(0, 0) is None
    assert poisson_interval(0)[0] == 0 and abs(poisson_interval(0)[1] - 3.689) < 0.01
    lo, hi = poisson_interval(10)
    assert abs(lo - 4.795) < 0.05 and abs(hi - 18.39) < 0.1


def test_match_counts_hits_duplicates_false_alarms_and_misses():
    eps = [{"hazard": ZONE, "zone": "A", "start_s": 10, "end_s": 20},
           {"hazard": ZONE, "zone": "A", "start_s": 50, "end_s": 55},
           {"hazard": NO_HELMET, "start_s": 100, "end_s": 130}]
    preds = [{"type": ZONE, "zone": "A", "t": 11.0},
             {"type": ZONE, "zone": "A", "t": 15.0},  # same episode again: duplicate
             {"type": ZONE, "zone": "B", "t": 51.0},  # wrong zone: false alarm, and episode 2 is missed
             {"type": NO_HELMET, "t": 99.0},  # within the 2 s tolerance before the start
             {"type": NO_HELMET, "t": 300.0}]
    m = match(eps, preds, tolerance_s=2.0)
    assert len(m["matches"]) == 2 and len(m["duplicates"]) == 1 and len(m["false_alarms"]) == 2 and len(m["missed"]) == 1
    r = evaluate(eps, preds, duration_s=1800)
    assert (r["true_positives"], r["false_alarms"], r["duplicates"], r["missed"]) == (2, 2, 1, 1)
    assert r["precision"] == 0.5 and r["recall"] == round(2 / 3, 4) and r["false_alarms_per_hour"] == 4.0
    assert r["latency_s"]["median"] == 0.0 and r["latency_s"]["max"] == 1.0
    assert r["missed_critical"] == 0  # a restricted-zone entry has severity 3
    assert r["by_hazard"][NO_HELMET]["true_positives"] == 1


def test_missed_severe_hazards_are_counted():
    eps = [{"hazard": ZONE, "zone": "Cell", "zone_kind": "machine_exclusion", "start_s": 5, "end_s": 9}]
    assert evaluate(eps, [], duration_s=60)["missed_critical"] == 1


def test_cli_reads_a_session(tmp_path, monkeypatch):
    monkeypatch.setattr("inference.incident_manager.EVIDENCE_DIR", tmp_path / "ev")
    db = IncidentDB(tmp_path / "t.db")
    mgr = IncidentManager(db, "S9", cooldown_s=30, assessor=lambda k, z, c, e: RiskEngine().assess(hazard_for(k).code, e, c, z))
    mgr.raise_incident(ZONE, 1, 0.9, 12.0, FRAME, "A")
    (tmp_path / "gt.json").write_text(json.dumps({"source": "x.mp4", "duration_s": 600,
                                                  "episodes": [{"hazard": "ZONE.ENTRY", "zone": "A", "start_s": 11, "end_s": 30}]}))
    spec = importlib.util.spec_from_file_location("event_metrics_cli", ROOT / "scripts" / "evaluation" / "event_metrics.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    r = cli.main(["--truth", str(tmp_path / "gt.json"), "--session", "S9", "--db", str(tmp_path / "t.db"),
                  "--out", str(tmp_path / "r.json")])
    assert r["true_positives"] == 1 and r["recall"] == 1.0 and (tmp_path / "r.json").exists()


# ------------------------------------------------------------------ incident manager wiring

@pytest.fixture
def mgr(tmp_path, monkeypatch):
    monkeypatch.setattr("inference.incident_manager.EVIDENCE_DIR", tmp_path / "ev")
    engine = RiskEngine()
    kinds = {"Cell": "machine_exclusion"}
    return IncidentManager(IncidentDB(tmp_path / "t.db"), "S1", cooldown_s=30, min_exposure_s=0.5,
                           assessor=lambda k, z, c, e: engine.assess(hazard_for(k, kinds.get(z)).code, e, c, z))


def test_assessment_is_stored_and_escalates_with_exposure(mgr):
    alert = mgr.raise_incident(ZONE, 4, 0.9, 1.0, FRAME, "Cell")
    assert alert["risk"] == "HIGH" and alert["hazard"] == "MACH.ZONE.ENTRY" and alert["severity"] == 5
    for t in np.arange(1.0, 9.0, 0.1):
        mgr.tick(t)
    assert mgr.db.assessments()[0]["escalated_at_s"] is None  # at most 8.4 s of exposure: still band 1
    for t in np.arange(9.0, 12.0, 0.1):
        mgr.tick(t)
    a = mgr.db.assessments()[0]  # exposure reaches 10 s (band 2) at t = 10.5
    assert a["risk_level"] == "CRITICAL" and 10.4 <= a["escalated_at_s"] <= 10.7
    assert [e["to"] for e in mgr.drain_escalations()] == ["CRITICAL"]
    mgr.close(ZONE, 4, 31.0, "Cell")
    a = mgr.db.assessments("S1")[0]
    assert a["exposure_s"] == 30.5 and a["risk_level"] == "CRITICAL" and 10.4 <= a["escalated_at_s"] <= 10.7
    assert a["policy_status"] == "draft" and isinstance(a["factors"], list) and a["requires_review"] is False


def test_no_assessor_keeps_the_original_behaviour(tmp_path, monkeypatch):
    monkeypatch.setattr("inference.incident_manager.EVIDENCE_DIR", tmp_path / "ev")
    m = IncidentManager(IncidentDB(tmp_path / "t.db"), "S1", cooldown_s=30)
    alert = m.raise_incident(NO_HELMET, 1, 0.9, 0, FRAME)
    m.tick(100)
    m.close(NO_HELMET, 1, 100)
    assert set(alert) == {"incident_id", "type", "worker_id", "zone", "video_t", "evidence", "repeat"}
    assert m.db.assessments() == [] and m.db.to_csv().splitlines()[0].split(",") == COLUMNS


# ------------------------------------------------------------------ pipeline (needs the runtime, not the weights)

class ScriptedDetector:
    """Stands in for Detector: one worker standing still at (50, 60) for the given frames, then gone."""

    def __init__(self, frames):
        self.frames, self.i = frames, 0

    def reset(self):
        self.i = 0

    def track(self, frame, *args):
        self.i += 1
        return ([(1, np.array([40.0, 20.0, 60.0, 60.0]), 0.9)] if self.i <= self.frames else []), []


def test_pipeline_zone_kinds(tmp_path, monkeypatch):
    from inference.tracker import Pipeline  # importable without torch: the detector module is loaded lazily
    monkeypatch.setattr("inference.incident_manager.EVIDENCE_DIR", tmp_path / "ev")
    square = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]
    zones = [{"name": "Cell", "polygon": square, "kind": "machine_exclusion"},
             {"name": "Walkway", "polygon": square, "kind": "pedestrian_only"},
             {"name": "Store", "polygon": square}]
    db = IncidentDB(tmp_path / "t.db")
    p = Pipeline(ScriptedDetector(150), 10, {"confirm_seconds": 0.5}, "cam", zones=zones, db=db, policy=DEFAULT_POLICY)
    for _ in range(200):
        p.process(np.zeros((100, 100, 3), np.uint8))
    p.finish("scripted")
    rows = {r["zone"]: r for r in db.rows()}
    assert set(rows) == {"Cell", "Store"}  # no incident for a person in a walkway
    a = {x["zone"]: x for x in db.assessments()}
    assert a["Cell"]["hazard_code"] == "MACH.ZONE.ENTRY" and a["Cell"]["risk_level"] == "CRITICAL"
    assert a["Cell"]["escalated_at_s"] is not None and a["Cell"]["exposure_s"] > 10
    assert a["Store"]["hazard_code"] == "ZONE.ENTRY" and a["Store"]["risk_level"] == "MEDIUM"
    assert all(r["status"] == "CLOSED" for r in rows.values())
