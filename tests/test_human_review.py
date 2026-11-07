"""Inter-annotator agreement (intelligence/agreement.py) and the human review workflow (scripts/validation/human_review.py).

All label sets here are synthetic test fixtures; nothing in this file is, or stands in for, a human review.
"""
import copy
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from intelligence.agreement import compare, event_agreement, interval_agreement, state_disagreements
from intelligence.annotations import SCHEMA_1_1, verify_lock

ROOT = Path(__file__).resolve().parents[1]
PPE = "PPE.HEAD.MISSING"
spec = importlib.util.spec_from_file_location("human_review", ROOT / "scripts" / "validation" / "human_review.py")
hr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hr)


def lab(events=(), intervals=None, who="ann-a", kind="human", complete=True, cid="clip"):
    return {"schema": SCHEMA_1_1, "label_set": "x", "clip_id": cid, "file": "x.mp4", "sha256": "0", "fps": 25.0, "frames": 1500,
            "duration_s": 60.0, "status": "provisional", "annotators": [{"id": who, "kind": kind}], "scope": {PPE: "evaluated"},
            "intervals": [{"hazard": PPE, "start_s": 0, "end_s": 60, "state": "monitorable"}] if intervals is None else intervals,
            "events": list(events), "review_complete": complete}


def ev(eid, a, b, x=None, obs="clear", req="evident", kind="violation", conf="high"):
    e = {"id": eid, "hazard": PPE, "kind": kind, "start_s": a, "end_s": b, "observability": obs, "requirement": req, "confidence": conf}
    if x is not None:
        e["anchors"] = [{"t": a + 1, "x": x, "y": 0.5}]
    return e


def test_identical_labels_agree_perfectly():
    a = lab([ev("a1", 10, 20)])
    r = compare({"clip": a}, {"clip": copy.deepcopy(a)}, hazards=(PPE,))
    h = r["hazards"][PPE]
    assert h["intervals"]["kappa"] == 1.0 and h["violation_events"]["positive_specific_agreement"] == 1.0
    assert h["violation_events"]["start_abs_diff_median_s"] == 0 and r["flags"] == []


def test_missed_event_and_late_boundaries_are_flagged():
    a, b = lab([ev("a1", 10, 20), ev("a2", 40, 45)]), lab([ev("b1", 11.5, 20)])
    r = compare({"clip": a}, {"clip": b}, hazards=(PPE,))["hazards"][PPE]["violation_events"]
    assert (r["both"], r["only_a"], r["only_b"]) == (1, 1, 0) and r["positive_specific_agreement"] == round(2 / 3, 4)
    flags = compare({"clip": a}, {"clip": b}, hazards=(PPE,))["flags"]
    assert any("specific agreement" in f for f in flags) and any("boundary" in f for f in flags)


def test_events_use_specific_agreement_not_kappa():
    r = event_agreement(lab([ev("a1", 10, 20)]), lab([]), PPE)
    assert "kappa" not in {k for k in r if not k.startswith("_")} and r["positive_specific_agreement"] == 0.0


def test_anchors_keep_two_workers_apart():
    a, b = lab([ev("a1", 10, 20, x=0.2)]), lab([ev("b1", 10, 20, x=0.8)])
    r = event_agreement(a, b, PPE)
    assert (r["both"], r["only_a"], r["only_b"]) == (0, 1, 1)


def test_interval_states_report_kappa_and_per_state_agreement():
    a = lab(intervals=[{"hazard": PPE, "start_s": 0, "end_s": 30, "state": "monitorable"},
                       {"hazard": PPE, "start_s": 30, "end_s": 60, "state": "uncertain"}])
    b = lab(intervals=[{"hazard": PPE, "start_s": 0, "end_s": 50, "state": "monitorable"},
                       {"hazard": PPE, "start_s": 50, "end_s": 60, "state": "uncertain"}])
    r = interval_agreement(a, b, PPE, step_s=1.0)
    assert r["samples"] == 60 and r["observed_agreement"] == round(40 / 60, 4) and r["kappa"] < 0.6
    assert r["per_state"]["uncertain"]["specific_agreement"] == round(2 * 10 / (30 + 10), 4)
    assert state_disagreements(a, b, PPE) == [{"start_s": 30.0, "end_s": 50.0, "a": "uncertain", "b": "monitorable"}]
    flags = compare({"clip": a}, {"clip": b}, hazards=(PPE,))["flags"]
    assert any("kappa" in f for f in flags) and any("'uncertain'" in f for f in flags)


def test_attribute_kappa_needs_ten_pairs():
    r = event_agreement(lab([ev("a1", 10, 20, obs="clear")]), lab([ev("b1", 10, 20, obs="partial")]), PPE)
    assert r["attributes"]["observability"]["agreement"] == 0.0 and r["attributes"]["observability"]["kappa"].startswith("insufficient")


# ------------------------------------------------------------------ workflow

@pytest.fixture
def base(tmp_path):
    clips = [{"clip_id": c, "file": "data/demo/x.mp4", "sha256": "0", "fps": 25.0, "frames": 1500, "duration_s": 60.0,
              "scope": {PPE: "evaluated", "ZONE.ENTRY": "not_applicable"}} for c in ("c1", "c2", "c3")]
    hr.prepare(tmp_path, clips)
    return tmp_path


def reviewer(base, who, rid, events, complete=True, kind="human"):
    for p in (base / f"reviewer_{who}" / "labels").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        d.update(annotators=[{"id": rid, "kind": kind}], review_complete=complete,
                 intervals=[{"hazard": PPE, "start_s": 0, "end_s": 60, "state": "monitorable"}],
                 events=[{**e, "id": f"{p.stem}-{e['id']}"} for e in events])
        p.write_text(json.dumps(d), encoding="utf-8")


def test_packages_are_blind_and_empty(base):
    for who in "12":
        meta = json.loads((base / f"reviewer_{who}" / "package.json").read_text(encoding="utf-8"))
        assert meta["reviewer_id"] is None and "split" not in meta and all(set(c) == {"clip_id", "file", "sha256", "duration_s"}
                                                                            for c in meta["clips"])
        for p in (base / f"reviewer_{who}" / "labels").glob("*.json"):
            d = json.loads(p.read_text(encoding="utf-8"))
            assert d["events"] == [] and d["intervals"] == [] and d["annotators"] == [] and "split" not in d
    a = json.loads((base / "reviewer_1" / "package.json").read_text())["order"]
    b = json.loads((base / "reviewer_2" / "package.json").read_text())["order"]
    assert sorted(a) == sorted(b)  # same clips, each reviewer in its own order


def test_prepare_never_overwrites_a_reviewers_work(base):
    reviewer(base, "1", "ann-a", [ev("e1", 1, 5)], complete=False)
    with pytest.raises(SystemExit, match="refusing"):
        hr.prepare(base, [{"clip_id": "c1", "file": "x", "sha256": "0", "fps": 25.0, "frames": 1, "duration_s": 60.0,
                           "scope": {PPE: "evaluated"}}])


def test_agreement_needs_finished_work(base):
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20)])
    reviewer(base, "2", "ann-b", [ev("e1", 10, 20)], complete=False)
    with pytest.raises(SystemExit, match="complete"):
        hr.agreement(base)


def adjudicate_all(base, adjudicator):
    ws = base / "agreement" / "adjudication_worksheet.csv"
    rows = list(csv.DictReader(open(ws, encoding="utf-8")))
    for r in rows:
        r.update(decision="1", adjudicator=adjudicator, reason="test")
    with open(ws, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]) if rows else ["clip_id", "hazard", "item", "a", "b", "decision", "adjudicator", "reason"])
        w.writeheader()
        w.writerows(rows)
    for p in (base / "adjudication" / "labels").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["events"] = [{**e, "adjudication": "decided"} for e in d["events"] if e.get("adjudication") != "pending" or "1:" in e["from"][0]]
        p.write_text(json.dumps(d), encoding="utf-8")


def test_lock_verified_refuses_until_everything_is_done(base, tmp_path):
    dest = tmp_path / "verified"
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20), ev("e2", 40, 45)])
    reviewer(base, "2", "ann-a", [ev("e1", 10.4, 20)])  # same person twice
    hr.agreement(base)
    hr.adjudicate(base)
    with pytest.raises(SystemExit, match="different"):
        hr.lock_verified(base, dest)
    reviewer(base, "2", "ann-b", [ev("e1", 10.4, 20)], kind="ai")
    with pytest.raises(SystemExit, match="human"):
        hr.lock_verified(base, dest)
    reviewer(base, "2", "ann-b", [ev("e1", 10.4, 20)])
    hr.agreement(base)
    hr.adjudicate(base)
    with pytest.raises(SystemExit, match="pending|decision"):
        hr.lock_verified(base, dest)
    adjudicate_all(base, "ann-a")
    with pytest.raises(SystemExit, match="third person"):
        hr.lock_verified(base, dest)
    adjudicate_all(base, "adj-c")
    m = hr.lock_verified(base, dest)
    assert m["statuses"] == ["verified"] and m["ground_truth"] is True and verify_lock(dest)
    with pytest.raises(SystemExit, match="never overwritten"):
        hr.lock_verified(base, dest)


def test_annotator_reviewer_mode_shows_only_the_package(base, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    real = [r for r in csv.DictReader(open(ROOT / "reports" / "validation" / "clip_manifest.csv", encoding="utf-8"))
            if r["evaluated"] == "yes"][:2]
    if not real:
        pytest.skip("no clip manifest")
    pkg = base / "real"
    hr.prepare(pkg, [{"clip_id": r["clip_id"], "file": r["file"], "sha256": r["sha256"], "fps": float(r["fps"]),
                      "frames": int(r["frames_decoded"]), "duration_s": float(r["duration_s"]),
                      "scope": {PPE: "evaluated", "ZONE.ENTRY": "not_applicable"}} for r in real])
    monkeypatch.setattr(sys, "argv", ["annotator.py", "--package", str(pkg / "reviewer_1")])
    at = AppTest.from_file(str(ROOT / "scripts" / "validation" / "annotator.py"), default_timeout=60).run()
    assert not at.exception
    assert {o.split(" ·")[0] for o in at.sidebar.selectbox[0].options} == {r["clip_id"] for r in real}
    assert [t.label for t in at.tabs] == ["Event", "Interval", "Save"]  # no status or review controls for a reviewer


# ------------------------------------------------------------------ milestone M3: packages, checks, exports, measures

def test_packages_are_separately_identifiable_and_carry_instructions_and_manifests(base):
    metas = [json.loads((base / f"reviewer_{w}" / "package.json").read_text(encoding="utf-8")) for w in "12"]
    assert metas[0]["package_id"] != metas[1]["package_id"] and metas[0]["label_set"] == "m2-human-r1"
    for w, meta in zip("12", metas):
        d = base / f"reviewer_{w}"
        man = list(csv.DictReader(open(d / "clip_manifest.csv", encoding="utf-8")))
        assert [r["clip_id"] for r in man] == meta["order"] and man[0]["hazards_to_label"] == PPE
        text = (d / "INSTRUCTIONS.md").read_text(encoding="utf-8")
        assert f"reviewer {w}" in text and meta["package_id"] in text and meta["protocol_sha256"] in text
    hr.prepare(base.parent / "again", [{"clip_id": c, "file": "data/demo/x.mp4", "sha256": "0", "fps": 25.0, "frames": 1500,
                                        "duration_s": 60.0, "scope": {PPE: "evaluated", "ZONE.ENTRY": "not_applicable"}}
                                       for c in ("c1", "c2", "c3")])
    again = json.loads((base.parent / "again" / "reviewer_1" / "package.json").read_text(encoding="utf-8"))
    assert again["package_id"] == metas[0]["package_id"] and again["order"] == metas[0]["order"]  # reproducible


def test_check_blocks_incomplete_work_and_reports_why(base):
    res = hr.check(base)
    assert not res["1"]["ready"] and any("not marked complete" in p for p in res["1"]["problems"])
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20, conf=None)])
    res = hr.check(base, "1")["1"]
    assert not res["ready"] and any("confidence" in p for p in res["problems"])
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20, x=0.3)])
    res = hr.check(base, "1")["1"]
    assert res["ready"] and res["reviewer_ids"] == ["ann-a"] and json.loads((base / "reviewer_1" / "completion_check.json").read_text())["ready"]


def test_check_finds_gaps_and_blinding_breaches(base):
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20, x=0.3)])
    p = base / "reviewer_1" / "labels" / "c1.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["intervals"] = [{"hazard": PPE, "start_s": 0, "end_s": 30, "state": "monitorable"}]  # half the clip
    d["split"] = "held-out"  # must never reach a reviewer
    p.write_text(json.dumps(d), encoding="utf-8")
    (base / "reviewer_1" / "eval_predictions.json").write_text("{}", encoding="utf-8")
    probs = " | ".join(hr.check(base, "1")["1"]["problems"])
    assert "cover 50%" in probs and "forbidden fields" in probs and "unexpected files" in probs


def test_export_writes_flat_tables(base):
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20, x=0.3)])
    hr.export(base)
    rows = list(csv.DictReader(open(base / "reviewer_1" / "exports" / "events.csv", encoding="utf-8")))
    assert len(rows) == 3 and rows[0]["confidence"] == "high" and json.loads(rows[0]["anchors"])[0]["x"] == 0.3
    assert hr.check(base, "1")["1"]["ready"]  # exports are allowed inside the package


def zev(eid, a, b, zone, kind="violation", conf="high"):
    return {"id": eid, "hazard": "ZONE.ENTRY", "kind": kind, "start_s": a, "end_s": b, "zone": zone, "observability": "clear",
            "confidence": conf}


def zlab(events, **kw):
    lab_ = lab(events, **kw)
    lab_["scope"]["ZONE.ENTRY"] = "evaluated"
    lab_["intervals"].append({"hazard": "ZONE.ENTRY", "start_s": 0, "end_s": 60, "state": "monitorable"})
    return lab_


def test_zone_assignment_and_event_kind_disagreements_are_measured_and_flagged():
    a = zlab([zev(f"a{i}", 10 * i, 10 * i + 5, "Dock") for i in range(5)] + [ev("p1", 51, 58)])
    b = zlab([zev(f"b{i}", 10 * i, 10 * i + 5, "Dock" if i < 2 else "Aisle") for i in range(5)] + [ev("q1", 51, 58, kind="uncertain")])
    r = compare({"clip": a}, {"clip": b})
    z = r["hazards"]["ZONE.ENTRY"]["zone_assignment"]
    assert z["pairs"] == 5 and z["agreement"] == 0.4 and any("zone assignment" in f for f in r["flags"])
    k = r["hazards"][PPE]["event_kind"]
    assert k["different_kind"] == 1 and k["confusion"] == {"violation|uncertain": 1} and any("different kind" in f for f in r["flags"])


def test_hazard_category_confusion_is_reported():
    a, b = zlab([ev("a1", 10, 20)]), zlab([zev("b1", 10, 20, "Dock")])
    hc = compare({"clip": a}, {"clip": b})["hazard_category"]
    assert hc == {"pairs": 1, "different_hazard": 1, "confusion": {f"{PPE}|ZONE.ENTRY": 1}}


def test_confidence_uses_weighted_kappa_only_with_enough_pairs():
    few = compare({"c": lab([ev("a", 1, 5, conf="high")])}, {"c": lab([ev("b", 1, 5, conf="low")])}, hazards=(PPE,))
    assert few["hazards"][PPE]["confidence"]["weighted_kappa"].startswith("insufficient")
    confs = ["high", "medium", "low"] * 4
    a = {f"c{i}": lab([ev("a", 1, 5, conf=c)], cid=f"c{i}") for i, c in enumerate(confs)}
    b = {f"c{i}": lab([ev("b", 1, 5, conf=c)], cid=f"c{i}") for i, c in enumerate(confs)}
    assert compare(a, b, hazards=(PPE,))["hazards"][PPE]["confidence"]["weighted_kappa"] == 1.0


def test_per_clip_values_and_clip_bootstrap_keep_a_bad_clip_visible():
    good = lab(intervals=[{"hazard": PPE, "start_s": 0, "end_s": 60, "state": "monitorable"}])
    half = lab(intervals=[{"hazard": PPE, "start_s": 0, "end_s": 30, "state": "monitorable"},
                          {"hazard": PPE, "start_s": 30, "end_s": 60, "state": "uncertain"}])
    other = lab(intervals=[{"hazard": PPE, "start_s": 0, "end_s": 30, "state": "uncertain"},
                           {"hazard": PPE, "start_s": 30, "end_s": 60, "state": "monitorable"}])
    a = {"g1": half, "g2": half, "bad": half}
    b = {"g1": copy.deepcopy(half), "g2": copy.deepcopy(half), "bad": other}
    r = compare(a, b, hazards=(PPE,))
    pc = r["hazards"][PPE]["per_clip"]
    assert pc["g1"]["interval_kappa"] == 1.0 and pc["bad"]["interval_kappa"] < 0.4
    assert any("clip bad interval kappa" in f for f in r["flags"])
    lo, hi = r["hazards"][PPE]["intervals"]["kappa_clip_bootstrap95"]
    assert lo < r["hazards"][PPE]["intervals"]["kappa"] < hi or lo == hi
    assert good  # fixture used to build the others


def test_worksheet_lists_kind_and_zone_differences_and_reviewer_notes(base):
    reviewer(base, "1", "ann-a", [ev("e1", 10, 20, x=0.3)])
    reviewer(base, "2", "ann-b", [ev("e1", 10, 20, x=0.3, kind="uncertain")])
    p = base / "reviewer_2" / "labels" / "c1.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["reviewer_notes"] = "rigid vs soft unclear"
    p.write_text(json.dumps(d), encoding="utf-8")
    _, rows = hr.agreement(base)
    items = [r["item"] for r in rows]
    assert "same stretch, different kind: violation vs uncertain" in items and "reviewer 2 note (read before deciding)" in items
    assert (base / "agreement" / "disagreement_report.md").read_text(encoding="utf-8").count("| c1 |") == 1
