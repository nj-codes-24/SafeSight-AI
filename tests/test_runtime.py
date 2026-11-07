"""Headless runtime tests with deterministic synthetic cameras and a fake detector. No model, GPU or footage needed.

The fake detector finds the synthetic source's bright box in the actual frame pixels and, like ByteTrack in
Ultralytics 8.4, restarts its IDs at 1 after every reset, so the tests exercise camera-scoped and reset-safe IDs.
Scenario letters follow the milestone brief (docs/product_research/16 section 9); the real-model and real-footage
scenarios are in tests/test_runtime_integration.py.
"""
import ast
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from database.database import IncidentDB
from runtime import config as rconfig
from runtime import logs
from runtime.health import DEGRADED, ERROR, RECONNECTING, STOPPED, STREAMING
from runtime.service import Runtime
from runtime.sources import RtspSource, SourceError, SyntheticSource, make_source

ROOT = Path(__file__).resolve().parents[1]
LEFT_HALF = [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]


class BoxDetector:
    names = {0: "person", 1: "helmet", 2: "no_helmet"}

    def __init__(self, delay=0.0):
        self.delay, self.next_id, self.tid = delay, 0, None

    def reset(self):
        self.next_id, self.tid = 0, None  # IDs restart at 1 after a reset, as in ByteTrack

    def track(self, frame, *args):
        if self.delay:
            time.sleep(self.delay)
        ys, xs = np.nonzero(frame[:, :, 2] > 200)  # channel 2 is never used by the frame-number pixel
        if not len(xs):
            self.tid = None
            return [], []
        if self.tid is None:
            self.next_id += 1
            self.tid = self.next_id
        return [(self.tid, np.array([xs.min(), ys.min(), xs.max() + 1, ys.max() + 1], float), 0.9)], []


class FakeBackend:
    mode = "fake"

    def __init__(self, delay=0.0):
        self.delay, self.stopped = delay, False

    def detector_for(self, camera_id):
        return BoxDetector(self.delay)

    def stop(self):
        self.stopped = True

    def stats(self):
        return {"mode": self.mode}


def make_cfg(tmp_path, cameras, **runtime) -> rconfig.RuntimeConfig:
    data = {"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                        "status_file": str(tmp_path / "status.json"), "log_file": None, "status_interval_s": 0.2,
                        "pipeline_config": str(tmp_path / "no_app_config.json"), **runtime},
            "inference": {"backend": "null"}, "sites": [{"id": "site-a", "name": "Site A"}, {"id": "site-b", "name": "Site B"}],
            "cameras": cameras}
    return rconfig.parse(data)


def cam(cid, site="site-a", zones=(), processing=None, reconnect=None, overrides=None, health=None, **source):
    c = {"id": cid, "site": site, "source": {"type": "synthetic", **source}, "zones": [
        {"name": "Left", "polygon": LEFT_HALF, **z} for z in zones]}
    for k, v in (("processing", processing), ("reconnect", reconnect), ("overrides", overrides), ("health", health)):
        if v:
            c[k] = v
    return c


def run(cfg, backend=None, duration=30, watch=None):
    """Run until every camera finishes (or the duration passes); watch(runtime) is polled while it runs."""
    rt = Runtime(cfg, backend=backend or FakeBackend())
    rt.start()
    end = time.monotonic() + duration
    while not rt.done() and time.monotonic() < end:
        if watch:
            watch(rt)
        time.sleep(0.05)
    stuck = rt.stop()
    assert stuck == []
    return rt


def db_rows(cfg, q, *args):
    con = sqlite3.connect(cfg.database)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(q, args)]
    finally:
        con.close()


# ------------------------------------------------------------------ configuration and secrets

@pytest.mark.parametrize("bad, match", [
    ({"cameras": []}, "at least one camera"),
    ({"cameras": [cam("a"), cam("a")]}, "unique"),
    ({"cameras": [{**cam("a"), "colour": "red"}]}, "unknown key"),
    ({"cameras": [cam("a", site="nowhere")]}, "not in sites"),
    ({"cameras": [{"id": "a", "source": {"type": "rtsp", "url": "rtsp://admin:secret@10.0.0.5/s"}}]}, "credentials"),
    ({"cameras": [{"id": "a", "source": {"type": "rtsp", "url": "rtsp://10.0.0.5/s?password=x"}}]}, "credentials"),
    ({"cameras": [{"id": "a", "source": {"type": "rtsp", "url": "http://10.0.0.5/s"}}]}, "rtsp://"),
    ({"cameras": [{"id": "a", "source": {"type": "file"}}]}, "needs path"),
    ({"cameras": [{"id": "a", "source": {"type": "file", "path": "x.mp4", "fps": 5}}]}, "does not take"),
    ({"cameras": [cam("a", zones=[{"kind": "electical"}])]}, "unknown zone kind"),
    ({"cameras": [cam("a", overrides={"no_such": 1})]}, "unknown key"),
    ({"cameras": [cam("a", processing={"queue_size": 0})]}, "between"),
    ({"inference": {"backend": "gpu"}, "cameras": [cam("a")]}, "backend"),
])
def test_invalid_configurations_are_rejected(bad, match):
    data = {"sites": [{"id": "site-a"}], **bad}
    with pytest.raises(rconfig.ConfigError, match=match):
        rconfig.parse(data)


def test_valid_configuration_and_defaults(tmp_path):
    cfg = make_cfg(tmp_path, [cam("a", zones=[{"kind": "machine_exclusion"}], processing={"max_fps": 5}),
                              {"id": "b", "enabled": False, "source": {"type": "file", "path": "data/demo/x.mp4"}}])
    a, b = cfg.cameras
    assert a.processing.max_fps == 5 and a.processing.queue_size == 2 and a.zones[0]["kind"] == "machine_exclusion"
    assert not b.enabled and b.source["path"] == "data/demo/x.mp4"
    assert rconfig.parse({"cameras": [cam("x")]}, {}).database == ROOT / "logs" / "runtime" / "incidents.db"
    z = rconfig.parse({"cameras": [{"id": "x", "source": {"type": "synthetic"}, "zones_from_app": "v"}]},
                      {"v": [{"name": "Z", "polygon": LEFT_HALF}]})
    assert z.cameras[0].zones == [{"name": "Z", "polygon": [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]], "kind": "restricted"}]


def test_shipped_configurations_validate():
    for name in ("runtime.demo.yaml", "runtime.example.yaml"):
        cfg = rconfig.load(ROOT / "config" / name)
        assert cfg.cameras and all(c.source["type"] in ("file", "rtsp") for c in cfg.cameras)


def test_credentials_are_resolved_from_environment_and_never_logged(monkeypatch, capsys):
    monkeypatch.setenv("SS_TEST_USER", "viewer")
    monkeypatch.setenv("SS_TEST_PASS", "s3cr#t pass")
    src = make_source({"type": "rtsp", "url": "rtsp://10.1.2.3:554/live?ch=1", "username_env": "SS_TEST_USER",
                       "password_env": "SS_TEST_PASS"}, "c1")
    url = src._url()
    assert url == "rtsp://viewer:s3cr%23t%20pass@10.1.2.3:554/live?ch=1"
    assert src.describe() == "rtsp://10.1.2.3:554/live?…" and "viewer" not in src.describe()
    log = logs.setup(None, "INFO")
    try:
        raise RuntimeError(f"failed to open {url} with s3cr#t pass")
    except RuntimeError:
        log.exception("connect failed for rtsp://admin:hunter22@10.9.9.9/x")
    err = capsys.readouterr().err
    assert "s3cr" not in err and "hunter22" not in err and "viewer:" not in err and "rtsp://***@10.9.9.9/x" in err
    monkeypatch.delenv("SS_TEST_PASS")
    with pytest.raises(Exception) as e:
        src._url()
    assert e.value.fatal and "SS_TEST_PASS" in str(e.value)
    logging.getLogger(logs.LOGGER).handlers.clear()


def test_runtime_package_never_imports_the_ui():
    for p in (ROOT / "runtime").glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.split(".")[0] in ("streamlit", "app") for n in names), p.name


# ------------------------------------------------------------------ scenario A: single camera

def test_a_single_camera_end_to_end(tmp_path):
    cfg = make_cfg(tmp_path, [cam("dock", zones=[{}], pattern="walk", frames=400, period=100, processing={"max_fps": None})])
    rt = run(cfg)
    w = rt.workers["dock"]
    h = w.health.snapshot()
    assert h["state"] == STOPPED and w.end_reason == "end of stream"
    assert h["frames"]["read"] == h["frames"]["processed"] == 400 and h["frames"]["dropped_backpressure"] == 0
    rows = db_rows(cfg, "SELECT * FROM incidents")
    assert rows and all(r["camera_id"] == "dock" and r["session_id"] == w.session_id and r["status"] == "CLOSED" for r in rows)
    ctx = db_rows(cfg, "SELECT * FROM incident_context")
    assert {c["incident_id"] for c in ctx} == {r["incident_id"] for r in rows}
    assert all(c["site_id"] == "site-a" and c["closed_utc"] and c["opened_utc"].endswith("+00:00") for c in ctx)
    assert all(c["worker_ref"].startswith(f"dock/{w.session_id}/W") for c in ctx)
    assert len(db_rows(cfg, "SELECT * FROM risk_assessments")) == len(rows)
    s = db_rows(cfg, "SELECT * FROM runtime_sessions")[0]
    assert (s["camera_id"], s["site_id"], s["end_reason"], s["frames_processed"]) == ("dock", "site-a", "end of stream", 400)
    assert db_rows(cfg, "SELECT * FROM sessions")[0]["source"] == "camera:dock"
    status = json.loads(cfg.status_file.read_text())
    assert status["runtime"]["state"] == "stopped" and status["cameras"]["dock"]["state"] == STOPPED


# ------------------------------------------------------------------ scenario B: several cameras, correct attribution

def test_b_cameras_are_independent_and_attributed(tmp_path):
    cfg = make_cfg(tmp_path, [
        cam("a1", "site-a", zones=[{}], pattern="static", frames=300),      # always in the zone: one incident
        cam("b1", "site-b", zones=[{}], pattern="cycle", period=25, frames=300,  # in and out, no cooldown: several
            overrides={"cooldown_seconds": 0}),
        cam("b2", "site-b", zones=[], pattern="walk", frames=300),          # no zones: none
        cam("off", "site-a", zones=[{}], pattern="static", frames=300) | {"enabled": False},
    ], status_interval_s=0.1)
    rt = run(cfg)
    assert set(rt.workers) == {"a1", "b1", "b2"}
    by = {}
    for r in db_rows(cfg, "SELECT i.*, c.site_id, c.worker_ref FROM incidents i JOIN incident_context c USING (incident_id)"):
        by.setdefault(r["camera_id"], []).append(r)
    assert len(by["a1"]) == 1 and len(by["b1"]) >= 4 and "b2" not in by and "off" not in by
    assert {r["site_id"] for r in by["b1"]} == {"site-b"} and by["a1"][0]["site_id"] == "site-a"
    assert by["a1"][0]["worker_id"] == 1 and by["b1"][0]["worker_id"] == 1  # raw IDs collide across cameras by design...
    refs = {r["worker_ref"] for v in by.values() for r in v}
    assert len({ref for ref in refs if ref.endswith("/W1")}) == 2  # ...but worker references never do
    sessions = {r["camera_id"]: r["session_id"] for r in db_rows(cfg, "SELECT * FROM runtime_sessions")}
    assert len(set(sessions.values())) == 3 and all(r["session_id"] == sessions[c] for c, v in by.items() for r in v)
    st = json.loads(cfg.status_file.read_text())
    assert st["cameras"]["off"]["state"] == "DISABLED" and st["cameras"]["off"]["monitoring"] == "no"


# ------------------------------------------------------------------ scenario C: a failing camera does not stop others

def test_c_failed_cameras_do_not_affect_healthy_ones(tmp_path, monkeypatch):
    monkeypatch.delenv("SS_NO_SUCH_PASS", raising=False)
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(os.urandom(4096))
    fast = {"max_attempts": 2, "initial_delay_s": 0.05, "max_delay_s": 0.1}
    cfg = make_cfg(tmp_path, [
        cam("good", zones=[{}], pattern="static", frames=200, processing={"max_fps": None}),
        cam("dead", faults={"never_opens": True}, reconnect=fast),
        {"id": "missing", "source": {"type": "file", "path": str(tmp_path / "nope.mp4")}, "reconnect": fast},
        {"id": "corrupt", "source": {"type": "file", "path": str(corrupt)}, "reconnect": fast},
        {"id": "refused", "source": {"type": "rtsp", "url": "rtsp://127.0.0.1:9/none", "open_timeout_s": 2}, "reconnect": fast},
        {"id": "nocreds", "source": {"type": "rtsp", "url": "rtsp://127.0.0.1:9/none", "password_env": "SS_NO_SUCH_PASS"},
         "reconnect": fast},
    ])
    rt = run(cfg, duration=60)
    snap = {cid: w.health.snapshot() for cid, w in rt.workers.items()}
    assert snap["good"]["state"] == STOPPED and snap["good"]["frames"]["processed"] == 200
    for cid in ("dead", "missing", "corrupt", "refused", "nocreds"):
        assert snap[cid]["state"] == ERROR and snap[cid]["monitoring"] == "no", cid
    assert snap["nocreds"]["connect_attempts"] == 1 and "SS_NO_SUCH_PASS" in snap["nocreds"]["reason"]  # fatal: no retries
    assert snap["dead"]["connect_attempts"] == 2
    assert [r["camera_id"] for r in db_rows(cfg, "SELECT * FROM incidents")] == ["good"]
    outages = {r["camera_id"] for r in db_rows(cfg, "SELECT * FROM camera_outages")}
    assert outages == {"dead", "missing", "corrupt", "refused", "nocreds"}
    ends = {r["camera_id"]: r["end_reason"] for r in db_rows(cfg, "SELECT * FROM runtime_sessions")}
    assert ends["good"] == "end of stream" and all(ends[c].startswith("error:") for c in outages)


# ------------------------------------------------------------------ scenario D: reconnection

def test_d_reconnection_resets_tracks_without_duplicate_incidents(tmp_path):
    cfg = make_cfg(tmp_path, [cam("door", zones=[{}], pattern="static", frames=150, realtime=True,
                                  faults={"read_fail_at": [50], "open_failures": 2},
                                  processing={"max_fps": None}, overrides={"lost_track_seconds": 0.5},
                                  reconnect={"max_attempts": 5, "initial_delay_s": 0.3, "max_delay_s": 1})])
    seen = []
    rt = run(cfg, watch=lambda r: seen.append(r.workers["door"].health.snapshot()["state"]))
    w = rt.workers["door"]
    h = w.health.snapshot()
    assert RECONNECTING in seen and STREAMING in seen[seen.index(RECONNECTING):]
    assert h["reconnects"] == 1 and h["connect_attempts"] == 4 and w.source.opens == 4
    rows = db_rows(cfg, "SELECT * FROM incidents ORDER BY started_at")
    assert len(rows) == 1  # same person, same place after the outage: not a new incident
    assert w.pipeline.incidents.suppressed == 1
    assert sorted(w.pipeline.stats.seen_ids) == [1, 2]  # the detector restarted at ID 1; the session ID did not repeat
    o = db_rows(cfg, "SELECT * FROM camera_outages")
    assert len(o) == 1 and o[0]["ended_utc"] > o[0]["started_utc"]
    ctx = db_rows(cfg, "SELECT * FROM incident_context")[0]
    assert ctx["closed_utc"] <= o[0]["ended_utc"]  # the track ended where it was last seen, before the stream returned


# ------------------------------------------------------------------ scenario E: backpressure

def test_e_backpressure_is_bounded_and_counted(tmp_path):
    cfg = make_cfg(tmp_path, [cam("fast", pattern="walk", fps=200, frames=1000, realtime=True,
                                  processing={"max_fps": None, "queue_size": 3},
                                  health={"warmup_s": 0.5, "window_s": 2})])
    states, depths = [], []

    def watch(r):
        s = r.workers["fast"].health.snapshot()
        states.append(s["state"])
        depths.append(s["frames"]["queued"])

    rt = run(cfg, backend=FakeBackend(delay=0.02), watch=watch)
    f = rt.workers["fast"].health.snapshot()["frames"]
    assert f["read"] == 1000 and f["dropped_backpressure"] > 300
    assert f["read"] == f["processed"] + f["skipped_by_rate"] + f["dropped_backpressure"] + f["queued"]
    assert f["queue_max"] <= 3 and max(depths) <= 3
    assert DEGRADED in states  # a camera that cannot keep up must never look healthy


def test_e_offline_sources_block_instead_of_dropping(tmp_path):
    cfg = make_cfg(tmp_path, [cam("file", pattern="walk", frames=300, processing={"max_fps": None, "queue_size": 2})])
    f = run(cfg, backend=FakeBackend(delay=0.002)).workers["file"].health.snapshot()["frames"]
    assert f["processed"] == f["read"] == 300 and f["dropped_backpressure"] == 0


def test_rate_selection_keeps_the_configured_average(tmp_path):
    cfg = make_cfg(tmp_path, [cam("r", pattern="walk", fps=50, frames=500, processing={"max_fps": 15})])
    w = run(cfg).workers["r"]
    f = w.health.snapshot()["frames"]
    assert f["processed"] == 150 and f["skipped_by_rate"] == 350  # 10 s of 50 FPS at 15 FPS
    assert w.source.drawn == 150  # skipped frames are only grabbed, never decoded into images


def test_loop_restart_on_a_skipped_frame_still_resets_tracks(tmp_path):
    class Restarting(SyntheticSource):
        def _next(self, draw):
            if self.n == 7:  # content jumps on frame 7, which rate selection skips (frames 0, 5, 10 are analysed)
                self.discontinuity = True
            return super()._next(draw)

    cfg = make_cfg(tmp_path, [cam("loop", zones=[{}], pattern="static", fps=50, frames=40, processing={"max_fps": 10})])
    src = Restarting({"pattern": "static", "fps": 50, "frames": 40}, "loop")
    rt = Runtime(cfg, backend=FakeBackend(), sources={"loop": src})
    rt.start()
    while not rt.done():
        time.sleep(0.05)
    rt.stop()
    assert sorted(rt.workers["loop"].pipeline.stats.seen_ids) == [1, 2]  # reset on frame 10: a new, non-reused ID


# ------------------------------------------------------------------ scenario F: database concurrency

def test_f_concurrent_cameras_store_every_event_once(tmp_path):
    cams = [cam(f"c{i}", "site-a" if i % 2 else "site-b", zones=[{}], pattern="cycle", period=10, frames=400,
                overrides={"cooldown_seconds": 0, "confirm_seconds": 0.08}) for i in range(6)]
    rt = run(make_cfg(tmp_path, cams), duration=60)
    cfg = rt.cfg
    rows = db_rows(cfg, "SELECT * FROM incidents")
    assert len(rows) == len({r["incident_id"] for r in rows})
    for cid, w in rt.workers.items():
        mine = [r for r in rows if r["camera_id"] == cid]
        assert len(mine) == w.health.incidents_opened >= 15, cid
        assert all(r["session_id"] == w.session_id and r["status"] == "CLOSED" for r in mine)
    ctx = db_rows(cfg, "SELECT c.*, i.camera_id AS inc_camera FROM incident_context c JOIN incidents i USING (incident_id)")
    assert len(ctx) == len(rows) and all(c["camera_id"] == c["inc_camera"] and c["closed_utc"] for c in ctx)
    assert len(db_rows(cfg, "SELECT * FROM risk_assessments")) == len(rows)
    assert db_rows(cfg, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_f_parallel_writers_with_separate_connections(tmp_path):
    path, errors = tmp_path / "stress.db", []
    IncidentDB(path).close()

    def writer(k):
        db = IncidentDB(path)
        try:
            for i in range(150):
                db.add("ZONE_INTRUSION", i, 0.9, f"cam{k}", f"S{k}", "Z", i / 10)
        except Exception as e:
            errors.append(e)
        finally:
            db.close()

    threads = [threading.Thread(target=writer, args=(k,)) for k in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    db = IncidentDB(path)
    rows = db.rows()
    assert errors == [] and len(rows) == 1200 and len({r["incident_id"] for r in rows}) == 1200
    assert all(sum(r["camera_id"] == f"cam{k}" for r in rows) == 150 for k in range(8))
    db.close()


def test_incident_id_collisions_are_retried(tmp_path, monkeypatch):
    import uuid as uuid_mod

    db = IncidentDB(tmp_path / "c.db")
    fixed = uuid_mod.UUID("12345678123456781234567812345678")
    calls = iter([fixed, fixed, uuid_mod.UUID("87654321876543218765432187654321")])
    monkeypatch.setattr("database.database.uuid.uuid4", lambda: next(calls))
    a = db.add("NO_HELMET", 1, 0.9, "c", "S")
    b = db.add("NO_HELMET", 2, 0.9, "c", "S")  # first try collides with a; the retry succeeds
    assert a != b and len(db.rows()) == 2
    db.close()


# ------------------------------------------------------------------ scenario G: shutdown

def test_g_shutdown_during_monitoring_is_clean(tmp_path):
    cfg = make_cfg(tmp_path, [cam(f"loop{i}", zones=[{}], pattern="static", realtime=True, fps=25) for i in range(3)])
    backend = FakeBackend()
    rt = Runtime(cfg, backend=backend)
    rt.start()
    time.sleep(2.0)
    assert all(w.health.snapshot()["state"] == STREAMING for w in rt.workers.values())
    assert rt.stop(timeout=10) == []
    assert backend.stopped and all(not w.alive and w.source.closed >= 1 for w in rt.workers.values())
    assert not [t.name for t in threading.enumerate() if t.name.startswith(("capture-", "process-", "status"))]
    assert all(r["status"] == "CLOSED" and r["ended_at"] for r in db_rows(cfg, "SELECT * FROM incidents"))
    assert {r["end_reason"] for r in db_rows(cfg, "SELECT * FROM runtime_sessions")} == {"shutdown"}
    assert len(db_rows(cfg, "SELECT * FROM sessions")) == 3
    st = json.loads(cfg.status_file.read_text())
    assert st["runtime"]["state"] == "stopped" and {c["state"] for c in st["cameras"].values()} == {STOPPED}


def _cli_config(tmp_path, cameras):
    data = {"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                        "status_file": str(tmp_path / "status.json"), "log_file": str(tmp_path / "runtime.log"),
                        "status_interval_s": 0.5, "pipeline_config": str(tmp_path / "none.json")},
            "inference": {"backend": "null"}, "cameras": cameras}
    p = tmp_path / "cli.json"
    p.write_text(json.dumps(data))
    return p


def _start_cli(config, *extra):
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen([sys.executable, "-m", "runtime", "run", "--config", str(config), *extra], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)


def _interrupt(p):
    p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)


def _wait_status(path, pred, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
            if pred(s):
                return s
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    raise AssertionError(f"status condition not reached; last status: {path.read_text() if path.exists() else 'none'}")


# ------------------------------------------------------------------ scenarios G and H through the command line

def test_g_h_cli_runs_headless_and_stops_on_signal(tmp_path):
    cfg = _cli_config(tmp_path, [{"id": "s1", "source": {"type": "synthetic", "pattern": "walk", "realtime": True}},
                                 {"id": "s2", "source": {"type": "synthetic", "pattern": "static", "realtime": True}}])
    p = _start_cli(cfg)
    try:
        status = tmp_path / "status.json"
        first = _wait_status(status, lambda s: all(c["frames"]["processed"] > 20 for c in s["cameras"].values()))
        second = _wait_status(status, lambda s: s["cameras"]["s1"]["frames"]["processed"] > first["cameras"]["s1"]["frames"]["processed"] + 20)
        assert second["process"]["ui_loaded"] is False  # no browser and no Streamlit in the runtime process
        # Monitoring (DEGRADED is correct, not a failure, if a loaded test machine falls below 80 % of the target rate)
        assert {c["state"] for c in second["cameras"].values()} <= {STREAMING, DEGRADED}
        _interrupt(p)
        out, _ = p.communicate(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0, out.decode(errors="replace")
    final = json.loads(status.read_text())
    assert final["runtime"]["state"] == "stopped" and {c["state"] for c in final["cameras"].values()} == {STOPPED}
    assert "shutdown complete" in (tmp_path / "runtime.log").read_text(encoding="utf-8")
    rs = db_rows(rconfig.parse(json.loads(cfg.read_text())), "SELECT * FROM runtime_sessions")
    assert {r["end_reason"] for r in rs} == {"shutdown"}


def test_cli_exit_codes(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cameras: []\n")
    r = subprocess.run([sys.executable, "-m", "runtime", "run", "--config", str(bad)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "at least one camera" in r.stderr
    cfg = _cli_config(tmp_path, [{"id": "s1", "source": {"type": "synthetic", "frames": 10}}])
    data = json.loads(cfg.read_text())
    data["inference"] = {"backend": "shared", "weights": str(tmp_path / "missing.pt")}
    cfg.write_text(json.dumps(data))
    r = subprocess.run([sys.executable, "-m", "runtime", "run", "--config", str(cfg)], cwd=ROOT, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 3 and "weights not found" in r.stderr + r.stdout


def test_status_command_reports_a_dead_runtime_as_not_monitoring(tmp_path):
    cfg = _cli_config(tmp_path, [{"id": "s1", "source": {"type": "synthetic", "frames": 10}}])
    status = tmp_path / "status.json"
    status.write_text(json.dumps({"runtime": {"state": "running", "pid": 999999, "updated_utc": "2026-01-01T00:00:00+00:00",
                                              "status_interval_s": 2, "inference": {"mode": "null"},
                                              "risk_policy": {"version": "v", "status": "draft"}, "note": "n"},
                                  "cameras": {"s1": {"state": "STREAMING", "monitoring": "yes", "frames": {}}}}))
    r = subprocess.run([sys.executable, "-m", "runtime", "status", "--config", str(cfg)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "NOT RUNNING" in r.stdout and "NO (runtime not running)" in r.stdout


class FakeModel:
    """Stands in for the shared Detector: returns each frame's marker so results can be matched to requests."""

    def __init__(self, fail=False):
        self.batches, self.fail = [], fail

    def predict_batch(self, frames):
        if self.fail:
            raise RuntimeError("CUDA error (simulated)")
        self.batches.append(len(frames))
        time.sleep(0.01)
        return [int(f[0, 0, 0]) for f in frames]


def _batched(model, cameras, wait_ms=20):
    from runtime.inference import BatchedBackend

    cfg = rconfig.Inference(backend="batched", max_batch=8, batch_wait_ms=wait_ms, timeout_s=5)
    b = BatchedBackend(cfg, base=model)
    b.cameras = cameras
    return b


def test_batched_backend_returns_each_camera_its_own_result():
    model = FakeModel()
    b = _batched(model, cameras=4)
    results, errors = {}, []

    def camera(k):
        try:
            results[k] = [b.submit(np.full((4, 4, 3), 10 * k + i, np.uint8)) for i in range(10)]
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=camera, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    b.stop()
    assert errors == [] and all(results[k] == [10 * k + i for i in range(10)] for k in range(4))
    assert max(model.batches) > 1 and sum(model.batches) == 40 and b.stats()["mean_batch"] > 1


def test_batched_backend_does_not_wait_for_a_single_camera_and_reports_failures():
    b = _batched(FakeModel(), cameras=1, wait_ms=500)
    t0 = time.perf_counter()
    assert b.submit(np.full((4, 4, 3), 7, np.uint8)) == 7
    assert time.perf_counter() - t0 < 0.3  # did not wait 500 ms for frames no other camera will send
    b.stop()
    with pytest.raises(RuntimeError, match="stopped"):
        b.submit(np.zeros((4, 4, 3), np.uint8))
    bad = _batched(FakeModel(fail=True), cameras=2, wait_ms=1)
    with pytest.raises(RuntimeError, match="CUDA error"):
        bad.submit(np.zeros((4, 4, 3), np.uint8))  # the failure reaches the waiting camera; the thread keeps serving
    assert bad.thread.is_alive()
    bad.stop()


def test_file_source_over_reported_length_ends_instead_of_reconnecting_forever(tmp_path):
    class Cap:
        def __init__(self, n):
            self.n = n

        def read(self):
            if self.n:
                self.n -= 1
                return True, np.zeros((2, 2, 3), np.uint8)
            return False, None

        def release(self):
            pass

    src = make_source({"type": "file", "path": str(tmp_path / "x.mp4"), "loop": False}, "f")
    src.cap, src.frames = Cap(5), 100  # the container claims 100 frames but holds 5
    assert all(src.read() is not None for _ in range(5))
    with pytest.raises(SourceError):
        src.read()  # looks like a mid-file failure: the worker reopens and resumes
    src.cap, src.reads_since_open = Cap(0), 0  # reopened at frame 5 and failing again at once
    assert src.read() is None  # the end of the file, not an endless reconnect loop


def test_synthetic_source_is_deterministic():
    a, b = SyntheticSource({"pattern": "walk"}, "x"), SyntheticSource({"pattern": "walk"}, "y")
    a.open(), b.open()
    assert all(np.array_equal(a.read(), b.read()) for _ in range(50))
    assert RtspSource.type == "rtsp"
