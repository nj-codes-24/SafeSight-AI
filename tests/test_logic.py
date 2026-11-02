"""Unit tests for association, zones, incidents and persistence. No model or GPU needed."""
import numpy as np
import pytest

from database.database import COLUMNS, IncidentDB
from inference.incident_manager import NO_HELMET, ZONE, IncidentManager
from inference.ppe_association import COMPLIANT, UNCERTAIN, VIOLATION, Detection, HelmetStateTracker, assign_heads
from inference.zone_monitor import Zone, ZoneMonitor, validate_polygon

BOX = np.array([100.0, 100, 200, 400])


def det(cls, conf=0.8, box=(130, 100, 170, 140)):
    return Detection(np.array(box, float), conf, cls)


def test_head_must_be_in_upper_body():
    assert assign_heads([BOX], [det("helmet")])[0] is not None
    assert assign_heads([BOX], [det("helmet", box=(130, 340, 170, 380))])[0] is None  # helmet carried at the hip
    assert assign_heads([BOX], [det("helmet", box=(400, 100, 440, 140))])[0] is None


def test_one_helmet_cannot_serve_two_workers():
    other = np.array([120.0, 95, 220, 395])
    assert sum(x is not None for x in assign_heads([BOX, other], [det("helmet")])) == 1


def test_no_evidence_stays_uncertain():
    t = HelmetStateTracker(window=20, min_votes=5)
    for _ in range(50):
        state, _ = t.update(1, None)
    assert state == UNCERTAIN


def test_violation_needs_multiple_frames():
    t = HelmetStateTracker(window=20, min_votes=5)
    assert t.update(1, det("no_helmet"))[0] == UNCERTAIN
    for _ in range(4):
        state, conf = t.update(1, det("no_helmet"))
    assert state == VIOLATION and conf > 0.5


def test_mixed_evidence_is_uncertain_then_compliant():
    t = HelmetStateTracker(window=10, min_votes=4, ratio=0.7)
    for i in range(8):
        state, _ = t.update(1, det("helmet" if i % 2 else "no_helmet"))
    assert state == UNCERTAIN
    for _ in range(10):
        state, _ = t.update(1, det("helmet"))
    assert state == COMPLIANT


SQUARE = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]


def monitor():
    return ZoneMonitor([Zone("Z", SQUARE)], entry_frames=3, exit_frames=3)


def test_zone_entry_exit_debounced():
    m = monitor()
    assert [m.update(1, (10, 10), 100, 100) for _ in range(3)] == [[], [], []]
    assert m.update(1, (50, 50), 100, 100) == [] and m.update(1, (50, 50), 100, 100) == []
    assert m.update(1, (50, 50), 100, 100) == [("enter", "Z")]
    assert m.inside(1) == ["Z"]
    assert all(m.update(1, (50, 50), 100, 100) == [] for _ in range(20))  # staying inside does not re-fire
    m.update(1, (10, 10), 100, 100), m.update(1, (10, 10), 100, 100)
    assert m.update(1, (50, 50), 100, 100) == []  # edge jitter is not an exit
    for _ in range(2):
        m.update(1, (10, 10), 100, 100)
    assert m.update(1, (10, 10), 100, 100) == [("exit", "Z")]


def test_zone_uses_given_foot_point_only():
    m = ZoneMonitor([Zone("Z", SQUARE)], entry_frames=1, exit_frames=1)
    assert m.update(1, (50, 90), 100, 100) == []  # a body may overlap the zone while the feet are outside


@pytest.mark.parametrize("bad", [[[0, 0], [1, 1]], [[0, 0], [2, 0], [0, 1]], [[0, 0], [0.5, 0.5], [1, 1]]])
def test_invalid_polygons_rejected(bad):
    with pytest.raises(ValueError):
        validate_polygon(bad)


@pytest.fixture
def mgr(tmp_path, monkeypatch):
    monkeypatch.setattr("inference.incident_manager.EVIDENCE_DIR", tmp_path / "ev")
    return IncidentManager(IncidentDB(tmp_path / "t.db"), "S1", cooldown_s=30)


FRAME = np.zeros((20, 20, 3), np.uint8)


def test_one_incident_per_episode(mgr):
    for t in range(100):
        mgr.raise_incident(NO_HELMET, 7, 0.9, t / 10, FRAME)
    rows = mgr.db.rows()
    assert len(rows) == 1 and rows[0]["status"] == "OPEN"
    assert rows[0]["evidence_path"].endswith(".jpg")
    assert __import__("pathlib").Path(rows[0]["evidence_path"]).exists()


def test_cooldown_then_repeat(mgr):
    mgr.raise_incident(NO_HELMET, 7, 0.9, 0, FRAME)
    mgr.close(NO_HELMET, 7, 5)
    assert mgr.raise_incident(NO_HELMET, 7, 0.9, 20, FRAME) is None
    alert = mgr.raise_incident(NO_HELMET, 7, 0.9, 40, FRAME)
    assert alert["repeat"] is True
    assert len(mgr.db.rows()) == 2


def test_types_and_workers_are_separate(mgr):
    mgr.raise_incident(NO_HELMET, 1, 0.9, 0, FRAME)
    mgr.raise_incident(ZONE, 1, 0.9, 0, FRAME, "Z")
    mgr.raise_incident(ZONE, 2, 0.9, 0, FRAME, "Z")
    assert len(mgr.db.rows()) == 3


def test_persistence_and_csv(mgr, tmp_path):
    mgr.raise_incident(ZONE, 3, 0.8, 1.5, FRAME, "Press")
    mgr.close_all(9)
    db2 = IncidentDB(tmp_path / "t.db")
    r = db2.rows()[0]
    assert r["status"] == "CLOSED" and r["zone"] == "Press" and r["ended_at"]
    lines = db2.to_csv().strip().splitlines()
    assert lines[0].split(",") == COLUMNS and len(lines) == 2


def test_new_id_near_a_lost_tracks_incident_is_suppressed(tmp_path):
    db = IncidentDB(tmp_path / "t.db")
    mgr = IncidentManager(db, "S", cooldown_s=30)
    box = np.array([100.0, 100.0, 150.0, 300.0])
    assert mgr.raise_incident(NO_HELMET, 1, 0.9, 0, FRAME, None, box, {1})
    assert mgr.raise_incident(NO_HELMET, 2, 0.9, 5, FRAME, None, box + 20, {2}) is None
    assert mgr.suppressed == 1


def test_two_visible_workers_side_by_side_both_alert(tmp_path):
    db = IncidentDB(tmp_path / "t.db")
    mgr = IncidentManager(db, "S", cooldown_s=30)
    box = np.array([100.0, 100.0, 150.0, 300.0])
    assert mgr.raise_incident(NO_HELMET, 1, 0.9, 0, FRAME, None, box, {1, 2})
    assert mgr.raise_incident(NO_HELMET, 2, 0.9, 1, FRAME, None, box + 60, {1, 2})
