"""Headless runtime with the real model and the demo footage (skipped without weights or clips).

These compare the runtime with the existing single-camera path (inference.tracker.process_video): run offline over the
same frames, every camera must produce exactly the incidents the original pipeline produces for that clip, whether it
runs alone or next to other cameras sharing one model. Everything is written to temporary databases.
"""
import json
import sqlite3
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
pytest.importorskip("ultralytics", reason="needs the full runtime (requirements.txt)")
ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
CLIPS = {"track_work_day": "track-day", "roadworks_night": "roadworks-night", "helmet_put_on": "helmet-on"}
if not (ROOT / "models" / "best.pt").exists() or not all((DEMO / f"{c}.mp4").exists() for c in CLIPS):
    pytest.skip("needs models/best.pt and the demo clips in data/demo", allow_module_level=True)

from database.database import IncidentDB  # noqa: E402
from inference.tracker import load_config, process_video  # noqa: E402
from runtime import config as rconfig  # noqa: E402
from runtime.service import Runtime  # noqa: E402
from tests.test_runtime import _interrupt, _start_cli, _wait_status, db_rows  # noqa: E402


def incidents(rows):
    return sorted((r["incident_type"], r["worker_id"], r["zone"], round(r["video_time_s"], 2)) for r in rows)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    """Incidents of the original single-camera path for each clip."""
    import inference.incident_manager as im

    d = tmp_path_factory.mktemp("baseline")
    old, im.EVIDENCE_DIR = im.EVIDENCE_DIR, d / "ev"
    out = {}
    try:
        for clip in CLIPS:
            db = IncidentDB(d / f"{clip}.db")
            process_video(DEMO / f"{clip}.mp4", cfg=load_config(), camera_id=clip, db=db)
            out[clip] = incidents(db.rows())
            db.close()
    finally:
        im.EVIDENCE_DIR = old
    return out


def offline_config(tmp_path, clips, backend):
    cams = [{"id": CLIPS[c], "site": "demo", "source": {"type": "file", "path": str(DEMO / f"{c}.mp4"), "realtime": False},
             "zones_from_app": c, "processing": {"max_fps": None, "queue_size": 4}}
            for c in clips]
    app_zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    for c in cams:  # clips without dashboard zones run without zones, as in the dashboard
        if c["zones_from_app"] not in app_zones:
            del c["zones_from_app"]
    return rconfig.parse({"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                                      "status_file": str(tmp_path / "status.json"), "log_file": None},
                          "inference": {"backend": backend}, "sites": [{"id": "demo"}], "cameras": cams}, app_zones)


def run_offline(cfg):
    rt = Runtime(cfg)
    rt.start()
    rt.wait(exit_when_done=True, duration=300)
    assert rt.stop() == []
    return rt


def test_a_single_camera_matches_the_original_pipeline(tmp_path, baseline):
    cfg = offline_config(tmp_path, ["track_work_day"], "shared")
    rt = run_offline(cfg)
    rows = db_rows(cfg, "SELECT * FROM incidents")
    assert incidents(rows) == baseline["track_work_day"] and rows
    h = rt.workers["track-day"].health.snapshot()
    assert h["frames"]["processed"] == h["frames"]["read"] == 373 and h["state"] == "STOPPED"
    assert all(c["camera_id"] == "track-day" and c["site_id"] == "demo" for c in db_rows(cfg, "SELECT * FROM incident_context"))
    assert all(Path(r["evidence_path"]).exists() for r in rows)


@pytest.mark.parametrize("backend", ["batched", "shared"])
def test_b_concurrent_cameras_match_their_single_camera_results(tmp_path, baseline, backend):
    cfg = offline_config(tmp_path, list(CLIPS), backend)
    rt = run_offline(cfg)
    rows = db_rows(cfg, "SELECT * FROM incidents")
    for clip, cid in CLIPS.items():
        assert incidents([r for r in rows if r["camera_id"] == cid]) == baseline[clip], (backend, clip)
        assert rt.workers[cid].health.snapshot()["frames"]["dropped_backpressure"] == 0
    if backend == "batched":
        assert rt.backend.stats()["mean_batch"] > 1.5  # the cameras really shared batches


def test_h_cli_monitors_demo_cameras_without_a_browser(tmp_path):
    cfg = {"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                       "status_file": str(tmp_path / "status.json"), "log_file": str(tmp_path / "runtime.log"),
                       "status_interval_s": 1},
           "inference": {"backend": "batched"}, "sites": [{"id": "demo"}],
           "cameras": [{"id": cid, "site": "demo", "source": {"type": "file", "path": str(DEMO / f"{clip}.mp4"), "loop": True},
                        **({"zones_from_app": clip} if clip != "helmet_put_on" else {})} for clip, cid in CLIPS.items()]}
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(cfg))
    p = _start_cli(path)
    try:
        status = tmp_path / "status.json"
        s = _wait_status(status, lambda s: all(c["frames"]["processed"] > 50 for c in s["cameras"].values()), timeout=120)
        assert {c["state"] for c in s["cameras"].values()} <= {"STREAMING", "DEGRADED"} and s["process"]["ui_loaded"] is False
        time.sleep(3)
        _interrupt(p)
        out, _ = p.communicate(timeout=60)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0, out.decode(errors="replace")
    con = sqlite3.connect(tmp_path / "rt.db")
    cams = {r[0] for r in con.execute("SELECT camera_id FROM incidents")}
    ends = {r[0] for r in con.execute("SELECT end_reason FROM runtime_sessions")}
    con.close()
    assert cams and cams <= set(CLIPS.values()) and ends == {"shutdown"}
