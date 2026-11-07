"""Physical camera acceptance harness (scripts/validation/camera_acceptance.py), milestone M3.

These tests exercise the harness only: a generated video file stands in for a camera and the session logs are
synthetic. Nothing here is, or may be reported as, a physical camera result; the harness itself labels file runs as
self-tests."""
import csv
import importlib.util
import json
import types
from pathlib import Path

import cv2
import pytest

from tests import view_scenes as vs

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("camera_acceptance", ROOT / "scripts" / "validation" / "camera_acceptance.py")
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)


def results(d):
    return {r["case"]: r for r in csv.DictReader(open(d / "results.csv", encoding="utf-8"))}


def test_plan_starts_with_every_case_not_run_and_is_never_overwritten(tmp_path):
    ca.plan("cam", tmp_path)
    s = ca.evaluate("cam", tmp_path)
    assert s["counts"]["NOT_RUN"] == len(ca.CASES) and s["verdict"].startswith("NOT STARTED")
    assert set(s["mandatory_not_run"]) == {c[0] for c in ca.CASES if c[6]}
    with pytest.raises(SystemExit, match="never overwritten"):
        ca.plan("cam", tmp_path)


def session(d, *transitions, kind="physical camera (rtsp)"):
    lines = [{"type": "probe_start", "kind": kind, "wall": 0.0}] + [{"type": "view_transition", **t} for t in transitions]
    (d / "session.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def test_evaluate_scores_only_cases_that_were_physically_performed(tmp_path):
    ca.plan("cam", tmp_path)
    for case, ev, t in (("B01", "start", 100.0), ("B01", "end", 115.0), ("V02", "start", 200.0), ("B05", "start", 300.0),
                        ("B05", "end", 303.0), ("S03", "start", 400.0)):
        ca.mark("cam", case, ev, out=tmp_path, now=t)
    session(tmp_path,
            {"wall": 105.5, "from": "VIEW_CHANGE_SUSPECTED", "to": "BLOCKED", "kind": "camera_blocked"},
            {"wall": 119.0, "from": "RECOVERING", "to": "VIEW_STABLE", "kind": None},
            {"wall": 301.0, "from": "VIEW_STABLE", "to": "VIEW_CHANGE_SUSPECTED", "kind": None})  # a transient suspicion is fine
    s = ca.evaluate("cam", tmp_path)
    r = results(tmp_path)
    assert r["B01"]["status"] == "PASS" and r["B01"]["latency_s"] == "5.5" and "recovered" in r["B01"]["detail"]
    assert r["V02"]["status"] == "FAIL"  # re-aimed but no view change recorded: a failure, not a guess
    assert r["B05"]["status"] == "PASS"  # someone close to the lens must not be reported
    assert r["S03"]["status"] == "REVIEW" and r["V01"]["status"] == "NOT_RUN"  # stream cases need a human verdict
    assert s["verdict"] == "INCOMPLETE" and not s["self_test"]


def test_a_late_detection_fails(tmp_path):
    ca.plan("cam", tmp_path)
    ca.mark("cam", "V01", "start", out=tmp_path, now=10.0)
    session(tmp_path, {"wall": 30.0, "from": "VIEW_CHANGE_SUSPECTED", "to": "VIEW_CHANGED", "kind": "camera_view_changed"})
    ca.evaluate("cam", tmp_path)
    assert results(tmp_path)["V01"]["status"] == "FAIL"


def test_unknown_case_and_event_are_rejected(tmp_path):
    with pytest.raises(SystemExit):
        ca.mark("cam", "Z99", "start", out=tmp_path)
    with pytest.raises(SystemExit):
        ca.mark("cam", "B01", "middle", out=tmp_path)


def test_probe_on_a_file_records_stream_statistics_and_view_states_as_a_self_test(tmp_path):
    path = tmp_path / "bench.avi"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, vs.OUT)
    world = vs.world()
    for i in range(100):  # 10 s of the registered view, then 10 s with the lens covered
        w.write(vs.noise(vs.camera(world), i))
    for i in range(100):
        w.write(vs.covered(i))
    w.release()
    args = types.SimpleNamespace(camera="bench", out=str(tmp_path / "out"), file=str(path), rtsp=None, transport="tcp",
                                 username_env=None, password_env=None, seconds=120, pace=False)
    s = ca.probe(args)
    assert s["frames"] == 200 and s["resolutions"] == ["640x360"] and s["kind"].startswith("harness self-test")
    assert s["final_view_state"] == "BLOCKED" and "HARNESS SELF-TEST" in s["note"]
    log = [json.loads(x) for x in (tmp_path / "out" / "session.jsonl").read_text().splitlines()]
    assert [x["to"] for x in log if x["type"] == "view_transition"][:1] == ["VIEW_STABLE"]
    assert any(x.get("kind") == "camera_blocked" for x in log)
    ca.plan("bench", tmp_path / "out")
    assert ca.evaluate("bench", tmp_path / "out")["verdict"].startswith("HARNESS SELF-TEST ONLY")
