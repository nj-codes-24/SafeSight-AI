"""Tests for evaluation labels (intelligence/annotations.py) and the scoring rules added to intelligence/event_metrics.py.

The rules under test are the pre-registered ones in docs/product_research/17_ANNOTATION_PROTOCOL.md section 10.
"""
import copy
import json
from pathlib import Path

import pytest

from intelligence.annotations import SCHEMA, load_set, lock, scoring_inputs, validate, verify_lock
from intelligence.event_metrics import cluster_bootstrap, evaluate, match

ROOT = Path(__file__).resolve().parents[1]
PPE = "PPE.HEAD.MISSING"


def label(**changes):
    lab = {"schema": SCHEMA, "label_set": "t", "clip_id": "clip", "file": "x.mp4", "sha256": "0", "fps": 25.0, "frames": 2500,
           "duration_s": 100.0, "status": "provisional", "annotators": [{"id": "a", "kind": "human"}],
           "scope": {PPE: "evaluated"},
           "intervals": [{"hazard": PPE, "start_s": 0, "end_s": 40, "state": "monitorable"},
                         {"hazard": PPE, "start_s": 40, "end_s": 50, "state": "uncertain"},
                         {"hazard": PPE, "start_s": 50, "end_s": 70, "state": "not_applicable"},
                         {"hazard": PPE, "start_s": 70, "end_s": 90, "state": "monitorable"}],
           "events": [{"id": "e1", "hazard": PPE, "kind": "violation", "start_s": 10, "end_s": 20, "worker": "A",
                       "observability": "clear", "requirement": "evident"},
                      {"id": "e2", "hazard": PPE, "kind": "violation", "start_s": 30, "end_s": 30.5, "worker": "B",
                       "observability": "clear", "requirement": "evident"},
                      {"id": "e3", "hazard": PPE, "kind": "violation", "start_s": 72, "end_s": 80, "worker": "C",
                       "observability": "low", "requirement": "assumed"},
                      {"id": "e4", "hazard": PPE, "kind": "violation", "start_s": 82, "end_s": 88, "worker": "D",
                       "observability": "partial", "requirement": "assumed"}]}
    lab.update(changes)
    return lab


@pytest.mark.parametrize("change, msg", [
    ({"schema": "other/1"}, "schema"),
    ({"status": "final"}, "status"),
    ({"intervals": [{"hazard": PPE, "start_s": 0, "end_s": 20, "state": "monitorable"},
                    {"hazard": PPE, "start_s": 10, "end_s": 30, "state": "uncertain"}]}, "overlap"),
    ({"intervals": [{"hazard": PPE, "start_s": 0, "end_s": 200, "state": "monitorable"}]}, "outside"),
    ({"intervals": [{"hazard": PPE, "start_s": 0, "end_s": 10, "state": "safe"}]}, "state"),
    ({"events": [{"id": "x", "hazard": PPE, "kind": "violation", "start_s": 1, "end_s": 2}]}, "requirement"),
    ({"events": [{"id": "x", "hazard": "NOT.A.HAZARD", "kind": "violation", "start_s": 1, "end_s": 2}]}, "hazard"),
])
def test_invalid_labels_are_rejected(change, msg):
    with pytest.raises(ValueError, match=msg):
        validate(label(**change))


def test_scoring_inputs_apply_the_preregistered_rules():
    si = scoring_inputs(validate(label()), PPE)
    eps = {e["id"]: e for e in si["episodes"]}
    assert not eps["e1"]["optional"]  # clear, 10 s, evident: a primary positive
    assert eps["e2"]["optional"]  # shorter than 1 s: optional
    assert eps["e3"]["optional"]  # low observability: optional
    assert not eps["e4"]["optional"]  # partial and assumed: primary in the main variant...
    assert scoring_inputs(label(), PPE, include_assumed=False)["episodes"][-1]["optional"]  # ...optional in evident-only
    assert si["monitorable_s"] == 60 and si["context_s"] == 20 and si["context"] == [(50, 70)]
    assert (40, 50) in si["ignore"] and (90, 100.0) in si["ignore"]  # uncertain, and unlabelled time at the end


def test_same_worker_episodes_closer_than_the_cooldown_are_merged():
    lab = label(events=[{"id": "a1", "hazard": PPE, "kind": "violation", "start_s": 0, "end_s": 5, "worker": "W",
                         "observability": "clear", "requirement": "evident"},
                        {"id": "a2", "hazard": PPE, "kind": "violation", "start_s": 20, "end_s": 25, "worker": "W",
                         "observability": "clear", "requirement": "evident"},
                        {"id": "a3", "hazard": PPE, "kind": "violation", "start_s": 70, "end_s": 75, "worker": "W",
                         "observability": "clear", "requirement": "evident"}])
    eps = scoring_inputs(lab, PPE)["episodes"]
    assert [(e["start_s"], e["end_s"]) for e in eps] == [(0, 25), (70, 75)]


def test_an_uncertain_stretch_is_not_merged_into_the_violation():
    lab = label(events=[{"id": "v", "hazard": PPE, "kind": "violation", "start_s": 0, "end_s": 1.4, "worker": "W",
                         "observability": "clear", "requirement": "evident"},
                        {"id": "u", "hazard": PPE, "kind": "uncertain", "start_s": 1.4, "end_s": 3.8, "worker": "W"}])
    eps = {e["id"]: e for e in scoring_inputs(lab, PPE)["episodes"]}
    assert (eps["v"]["end_s"], eps["v"]["optional"]) == (1.4, False) and eps["u"]["optional"]


def test_scoring_categories():
    si = scoring_inputs(label(), PPE)
    preds = [{"type": PPE, "t": 11.0, "incident_id": "tp", "t_end": 19.0},
             {"type": PPE, "t": 14.0, "incident_id": "dup"},
             {"type": PPE, "t": 30.2, "incident_id": "optional-short"},
             {"type": PPE, "t": 45.0, "incident_id": "in-uncertain"},
             {"type": PPE, "t": 60.0, "incident_id": "in-context"},
             {"type": PPE, "t": 74.0, "incident_id": "optional-low"},
             {"type": PPE, "t": 36.0, "incident_id": "fa"}]
    r = evaluate(si["episodes"], preds, 100, 2.0, si["ignore"], si["context"], si["monitorable_s"], si["context_s"])
    assert (r["true_positives"], r["false_alarms"], r["duplicates"], r["missed"]) == (1, 1, 1, 1)  # e4 (82-88 s) is missed
    assert (r["context_false_alarms"], r["unscorable"], r["optional_detected"], r["optional_episodes"]) == (1, 1, 2, 2)
    assert r["precision"] == 0.5 and r["recall"] == 0.5 and r["f1"] == 0.5
    assert r["false_alarms_per_hour"] == 60.0  # 1 false alarm in 60 monitorable seconds
    assert r["duration_abs_error_s_median"] == 2.0 and r["latency_s"]["median"] == 1.0


def test_annotation_uncertainty_widens_the_match_window():
    ep = [{"hazard": PPE, "start_s": 10, "end_s": 12, "start_unc_s": 4.0}]
    assert len(match(ep, [{"type": PPE, "t": 7.0}], 2.0)["matches"]) == 1  # inside 10 - 4
    assert len(match(ep, [{"type": PPE, "t": 5.0}], 2.0)["false_alarms"]) == 1


def test_late_detections_are_counted():
    r = evaluate([{"hazard": PPE, "start_s": 0, "end_s": 60}], [{"type": PPE, "t": 10.0}], 60)
    assert r["true_positives"] == 1 and r["late_detections"] == 1


def test_cluster_bootstrap():
    units = [{"tp": 1, "n": 1}, {"tp": 0, "n": 1}, {"tp": 1, "n": 2}]
    rec = lambda u: sum(x["tp"] for x in u) / sum(x["n"] for x in u)
    a, b = cluster_bootstrap(units, rec, 500, seed=1), cluster_bootstrap(units, rec, 500, seed=1)
    assert a == b and 0 <= a[0] <= 0.5 <= a[1] <= 1
    assert cluster_bootstrap([{"tp": 0, "n": 0}], lambda u: None, 100) is None  # undefined statistic: no interval


def test_lock_detects_changes(tmp_path):
    folder = tmp_path / "set1"
    folder.mkdir()
    (folder / "clip.json").write_text(json.dumps(label()))
    m = lock(folder)
    assert m["ground_truth"] is False and m["statuses"] == ["provisional"]
    assert verify_lock(folder)["combined_sha256"] == m["combined_sha256"]
    changed = copy.deepcopy(label())
    changed["events"][0]["end_s"] = 21
    (folder / "clip.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="changed since they were locked"):
        verify_lock(folder)


def test_a_dotted_version_has_its_own_lock(tmp_path):
    for name in ("set-v1", "set-v1.1"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "clip.json").write_text(json.dumps(label(label_set=name)))
    a = lock(tmp_path / "set-v1")
    lock(tmp_path / "set-v1.1")  # used to overwrite set-v1.lock.json
    assert verify_lock(tmp_path / "set-v1")["combined_sha256"] == a["combined_sha256"]
    assert sorted(p.name for p in tmp_path.glob("*.lock.json")) == ["set-v1.1.lock.json", "set-v1.lock.json"]


def test_repository_label_set_is_valid_and_locked():
    folder = ROOT / "reports" / "validation" / "annotations" / "m2-provisional-v1"
    if not folder.exists():
        pytest.skip("no label set in this checkout")
    labels = load_set(folder)
    m = verify_lock(folder)
    assert len(labels) == 15 and m["ground_truth"] is False
    assert all(lab["status"] == "provisional" and lab["annotators"][0]["kind"] == "ai" for lab in labels.values())


def test_annotator_app_starts_without_model_output():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    if not (ROOT / "reports" / "validation" / "clip_manifest.csv").exists():
        pytest.skip("no clip manifest")
    at = AppTest.from_file(str(ROOT / "scripts" / "validation" / "annotator.py"), default_timeout=60).run()
    assert not at.exception
    source = (ROOT / "scripts" / "validation" / "annotator.py").read_text(encoding="utf-8")
    assert "incidents.db" not in source and "eval_runs" not in source and "IncidentDB" not in source  # blind by design
