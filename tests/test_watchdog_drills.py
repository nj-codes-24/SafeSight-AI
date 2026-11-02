"""Controlled failure drills: a real watchdog process against a dummy trainer in a throwaway directory.

Nothing here touches runs/ or any production checkpoint.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WD = ROOT / "watchdog_svc" / "watchdog.py"


def run_drill(tmp, mode, timeout=60):
    control, logs = tmp / "control", tmp / "logs" / "watchdog"
    control.mkdir(parents=True)
    job = {"exp": f"drill_{mode}", "project": str(tmp), "batch": 16,
           "cmd": [str(ROOT / "tests" / "dummy_trainer.py"), "--dir", str(tmp / f"drill_{mode}"), "--mode", mode]}
    (control / "queue.json").write_text(json.dumps([job]))
    p = subprocess.Popen([sys.executable, str(WD), "--control", str(control), "--logdir", str(logs), "--poll", "0.5",
                          "--audit-interval", "4", "--stall", "4", "--start-grace", "4", "--nan-limit", "5",
                          "--restart-delay", "0.2"])
    try:
        end = time.time() + timeout
        hist = control / "history.json"
        while time.time() < end and not hist.exists():
            time.sleep(0.5)
        assert hist.exists(), "job never finished"
    finally:
        (control / "stop").write_text("")
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
    events = [json.loads(l) for l in (logs / "events.log").read_text().splitlines()]
    launches = [json.loads(l) for l in (tmp / f"drill_{mode}" / "launches.jsonl").read_text().splitlines()]
    return json.loads(hist.read_text())[-1], events, launches, logs


@pytest.mark.parametrize("mode,expect", [("crash", "dead"), ("stall", "stalled"), ("nan", "non-finite"), ("silent", "no heartbeat")])
def test_failure_detected(tmp_path, mode, expect):
    hist, events, launches, logs = run_drill(tmp_path, mode)
    fails = [e for e in events if e["kind"] == "failure"]
    assert fails and expect in fails[0]["msg"]
    assert (logs / "latest_health_report.txt").exists()
    assert list(logs.glob("health_report_*.json"))
    if mode == "crash":  # always crashes: must stop after the ladder, lowering load on the way
        assert hist["status"] == "failed"
        assert len(launches) == 5
        assert [l["batch"] for l in launches] == [16, 16, 8, 8, 4]
        assert launches[-1]["workers"] == 0
        assert any(e["kind"] == "giveup" for e in events)
    else:
        assert hist["status"] == "completed"
        assert launches[1]["resume"] is True


def test_clean_run_needs_no_recovery(tmp_path):
    hist, events, launches, _ = run_drill(tmp_path, "ok")
    assert hist["status"] == "completed" and len(launches) == 1
    assert not [e for e in events if e["kind"] == "failure"]
