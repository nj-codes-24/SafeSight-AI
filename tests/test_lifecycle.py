"""Incident lifecycle, PPE requirement policy, visibility handling and alert grouping (milestone M2.1).

Deterministic: a scripted detector feeds the real Pipeline exact tracks and head boxes at 10 frames per second, with
short timings (confirm 0.5 s, resolve 1 s, grace 2 s, lost track 1 s). No model, GPU or footage is needed.
"""
import numpy as np
import pytest

from database.database import IncidentDB
from inference.incident_lifecycle import INTERRUPTED, LOST, RESOLVED, SESSION_END
from inference.ppe_association import Detection
from inference.tracker import CONFIRMED_VIOLATION, NOT_APPLICABLE, NOT_CONFIGURED, PPE_CATEGORIES, PPE_NOT_OBSERVABLE, Pipeline
from intelligence import ppe_policy as ppe

FPS = 10
W, H = 400, 300
CFG = {"confirm_seconds": 0.5, "resolve_seconds": 1.0, "grace_seconds": 2.0, "lost_track_seconds": 1.0,
       "cooldown_seconds": 30.0, "burst_seconds": 10.0}
REQUIRED = {"schema": ppe.SCHEMA, "version": "t-1", "status": "draft", "entries": [
    {"id": "R1", "camera": "cam", "ppe": ["head"], "required": True, "status": "confirmed", "established_by": "Safety lead"}]}


def person(x=100, y=60, tid=1):
    return (tid, np.array([x, y, x + 40, y + 160], float), 0.9)


def head(kind, x=100, y=60, conf=0.9):
    return Detection(np.array([x + 10, y, x + 30, y + 22], float), conf, kind)


class Script:
    """Detector stand-in: frame i returns frames[i] (persons, heads); nothing after the end."""

    def __init__(self):
        self.frames, self.i = [], 0

    def add(self, seconds, persons=(), heads=()):
        self.frames += [(list(persons), list(heads))] * round(seconds * FPS)
        return self

    def reset(self):
        pass

    def track(self, frame, *a):
        f = self.frames[self.i] if self.i < len(self.frames) else ([], [])
        self.i += 1
        return f


def run(tmp_path, script, policy=REQUIRED, zones=None, cfg=None, finish=True, until=None):
    db = IncidentDB(tmp_path / "t.db")
    p = Pipeline(script, FPS, {**CFG, **(cfg or {})}, "cam", zones=zones or [], db=db, evidence_dir=tmp_path / "ev",
                 annotate=False, ppe_policy=policy)
    frame = np.zeros((H, W, 3), np.uint8)
    for _ in range(until or len(script.frames)):
        p.process(frame)
    if finish:
        p.finish("scripted")
    return p, db


def life(db):
    return db.lifecycle()


def bare(seconds, tid=1, x=100):
    return dict(seconds=seconds, persons=[person(x, tid=tid)], heads=[head("no_helmet", x)])


# ------------------------------------------------------------------ the ten lifecycle scenarios

def test_1_continuous_violation_is_one_incident_open_for_its_whole_duration(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(20)))
    (r,) = life(db)
    assert r["end_reason"] == SESSION_END and r["classification"] == "violation"
    assert r["opened_t"] == pytest.approx(0.4, abs=0.11) and r["last_observed_t"] == pytest.approx(19.9, abs=0.01)
    assert r["exposure_s"] == pytest.approx(20.0, abs=0.15) and r["unobserved_s"] == 0
    assert len(db.rows()) == 1 and db.rows()[0]["status"] == "CLOSED"


def test_2_brief_detector_interruption_does_not_end_the_incident(tmp_path):
    s = Script().add(**bare(5)).add(1.5, [person()]).add(0.5).add(**bare(5))  # head unseen 1.5 s, then person unseen 0.5 s
    p, db = run(tmp_path, s)
    (r,) = life(db)
    assert len(db.rows()) == 1 and r["end_reason"] == SESSION_END
    assert 1.0 <= r["unobserved_s"] <= 2.0  # the gap is reported, not hidden (the vote carries the state ~0.5 s into it)
    assert r["exposure_s"] == pytest.approx(12.0, abs=0.2)  # bounded by observations on both sides of the gap


def test_3_longer_occlusion_ends_with_unknown_outcome_at_the_last_observation(tmp_path):
    s = Script().add(**bare(5)).add(4).add(**bare(3))  # 4 s unseen: longer than grace (2 s)
    p, db = run(tmp_path, s)
    first = life(db)[0]
    assert first["end_reason"] == LOST and first["last_observed_t"] == pytest.approx(4.9, abs=0.01)
    assert first["ended_t"] == first["last_observed_t"] and first["exposure_s"] < 5.1  # no invented exposure
    # back inside the cooldown: recorded against the same group, not a duplicate incident or notification
    assert len(db.rows()) == 1 and len(db.notifications()) == 1
    ev = [e["event"] for e in db.events()]
    assert "reobserved_after_unknown_end" in ev and "reobservation_ended" in ev
    g = db.groups()[0]
    assert g["reobserved_s"] == pytest.approx(2.5, abs=0.15)  # 3 s back in view, minus 0.5 s to re-confirm the vote
    assert g["exposure_s"] > first["exposure_s"]


def test_3b_reobservation_still_going_after_the_cooldown_opens_a_linked_incident(tmp_path):
    s = Script().add(**bare(3)).add(3).add(**bare(8))
    p, db = run(tmp_path, s, cfg={"cooldown_seconds": 5.0})
    a, b = life(db)
    assert a["end_reason"] == LOST and b["relation"] == "continued_after_unknown_end" and b["linked_to"] == a["incident_id"]
    assert a["group_id"] == b["group_id"] and len(db.notifications()) == 1  # same group: no second notification


def test_4_confirmed_resolution_needs_sustained_compliance(tmp_path):
    flicker = Script().add(**bare(4)).add(0.3, [person()], [head("helmet")]).add(**bare(4))
    p, db = run(tmp_path, flicker)
    assert len(life(db)) == 1 and life(db)[0]["end_reason"] == SESSION_END  # one compliant moment is not a resolution
    resolved = Script().add(**bare(4)).add(5, [person()], [head("helmet")])
    p, db = run(tmp_path / "b", resolved)
    (r,) = life(db)
    # ends at the last frame the vote still read VIOLATION (it lags the change by up to 0.3 s), not at the decision time
    assert r["end_reason"] == RESOLVED and r["ended_t"] == r["last_observed_t"] == pytest.approx(4.3, abs=0.11)
    assert r["closed_t"] >= r["ended_t"] + 1.0  # decided after compliance was held for resolve_seconds


def test_5_worker_leaving_view_is_not_treated_as_compliant(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(5)).add(6))
    (r,) = life(db)
    assert r["end_reason"] == LOST and r["ended_t"] == pytest.approx(4.9, abs=0.01)
    assert any(e["event"] == "track_lost" for e in db.events())


def test_6_worker_returning_under_a_new_track_id_continues_the_incident(tmp_path):
    s = Script().add(**bare(5)).add(1.2).add(**bare(5, tid=2, x=104))  # tracker lost them; new ID at the same place
    p, db = run(tmp_path, s)
    (r,) = life(db)
    assert r["tracks"] == [1, 2] and r["end_reason"] == SESSION_END and len(db.rows()) == 1
    ev = [e for e in db.events() if e["event"] == "reassociated"]
    assert ev and ev[0]["detail"]["basis"].startswith("position")


def test_7_new_violation_after_resolution_is_not_suppressed_by_the_cooldown(tmp_path):
    s = Script().add(**bare(3)).add(3, [person()], [head("helmet")]).add(**bare(3))
    p, db = run(tmp_path, s)
    a, b = life(db)
    assert a["end_reason"] == RESOLVED and b["opened_t"] < a["ended_t"] + 30  # well inside the old 30 s cooldown
    assert a["group_id"] != b["group_id"]
    assert [n["kind"] for n in db.notifications()] == ["alert", "recurrence"]


def test_8_tracker_reset_ends_incidents_at_the_last_observation(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(4)), finish=False)
    p.reset_tracks()
    (r,) = life(db)
    assert r["end_reason"] == INTERRUPTED and r["ended_t"] == pytest.approx(3.9, abs=0.01)


def test_9_camera_disconnect_then_same_worker_same_place_is_not_a_duplicate(tmp_path):
    s = Script().add(**bare(4)).add(**bare(4, tid=2, x=104))
    p, db = run(tmp_path, s, finish=False, until=40)
    p.reset_tracks()  # what the runtime does after a stream gap longer than lost_track_seconds
    frame = np.zeros((H, W, 3), np.uint8)
    for i in range(40):
        p.process(frame, t=60 + i / FPS)  # the stream comes back 56 s later (live time)
    p.finish("scripted")
    assert len(db.rows()) == 2  # beyond the cooldown: a new incident, linked to the interrupted one
    a, b = life(db)
    assert a["end_reason"] == INTERRUPTED and b["relation"] is None  # 56 s > cooldown: a new group
    p2, db2 = run(tmp_path / "b", Script().add(**bare(4)).add(**bare(4, tid=2, x=104)), finish=False, until=40)
    p2.reset_tracks()
    for i in range(40):
        p2.process(frame, t=5 + i / FPS)  # back after one second
    p2.finish("scripted")
    assert len(db2.rows()) == 1 and p2.incidents.suppressed == 1  # within the cooldown: a recorded re-observation
    assert any(e["event"] == "reobserved_after_unknown_end" for e in db2.events())


def test_10_shutdown_with_active_incidents_ends_and_persists_them(tmp_path):
    s = Script().add(5, [person(), person(220, tid=2)], [head("no_helmet"), head("no_helmet", 220)])
    p, db = run(tmp_path, s, zones=[{"name": "Z", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}])
    assert {(r["incident_type"], r["end_reason"]) for r in life(db)} == {("NO_HELMET", SESSION_END), ("ZONE_INTRUSION", SESSION_END)}
    assert len(life(db)) == 4 and all(r["status"] == "CLOSED" and r["ended_at"] for r in db.rows())
    assert all(g["state"] == "closed" for g in db.groups())
    assert sum(r["worker_seconds"] for r in db.ppe_observations()) == pytest.approx(10.0, abs=0.2)


# ------------------------------------------------------------------ grouping, duplicates and audit

def test_two_workers_same_rule_same_time_are_two_incidents_in_one_burst_notification(tmp_path):
    s = Script().add(5, [person(), person(250, tid=2)], [head("no_helmet"), head("no_helmet", 250)])
    p, db = run(tmp_path, s)
    assert len(db.rows()) == 2 and len({r["group_id"] for r in life(db)}) == 2
    (n,) = db.notifications()
    assert n["count"] == 2 and len(n["incident_ids"]) == 2  # one notification, both incidents kept


def test_a_visible_worker_never_takes_over_another_workers_incident(tmp_path):
    # worker 1 occluded next to worker 2 who becomes bare-headed: worker 2 must get its own incident
    s = Script().add(**bare(3)).add(1.5, [person(), person(130, tid=2)], [head("no_helmet", 130)])
    p, db = run(tmp_path, s)
    assert sorted(len(r["tracks"]) for r in life(db)) == [1, 1] and len(db.rows()) == 2


def test_operator_review_survives_detector_closure(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(3)), finish=False)
    iid = db.rows()[0]["incident_id"]
    db.set_status(iid, "FALSE_ALARM")
    p.finish("scripted")
    r = db.rows()[0]
    assert r["status"] == "FALSE_ALARM" and r["ended_at"]  # closing a detection does not overwrite a human decision


# ------------------------------------------------------------------ visibility

def test_head_cut_off_by_the_frame_is_not_a_missing_helmet(tmp_path):
    top = Script().add(6, [(1, np.array([100.0, 0, 140, 160]), 0.9)], [Detection(np.array([110.0, 0, 130, 20]), 0.9, "no_helmet")])
    p, db = run(tmp_path, top)
    assert db.rows() == [] and p.ppe_seconds[PPE_NOT_OBSERVABLE] > 5.5


def test_helmet_on_a_cut_off_head_still_counts(tmp_path):
    s = Script().add(**bare(3)).add(3, [(1, np.array([100.0, 0, 140, 160]), 0.9)],
                                       [Detection(np.array([110.0, 0, 130, 20]), 0.9, "helmet")])
    p, db = run(tmp_path, s)
    assert life(db)[0]["end_reason"] == RESOLVED


# ------------------------------------------------------------------ PPE requirement policy

def test_unconfigured_requirement_is_a_review_never_a_confirmed_violation(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(4)), policy=None)
    (r,) = life(db)
    assert r["classification"] == "requires_review" and db.assessments()[0]["requires_review"] is True
    assert p.ppe_seconds[NOT_CONFIGURED] > 3.9 and p.ppe_seconds[CONFIRMED_VIOLATION] == 0
    assert db.notifications()[0]["kind"] == "review"


def test_inactive_requirement_raises_nothing(tmp_path):
    pol = {**REQUIRED, "entries": [{**REQUIRED["entries"][0], "effective_to": "2020-01-01T00:00:00+00:00"}]}
    p, db = run(tmp_path, Script().add(**bare(4)), policy=pol)
    assert db.rows() == [] and p.ppe_seconds[NOT_APPLICABLE] > 3.9


ZONED = {**REQUIRED, "entries": [{**REQUIRED["entries"][0], "zone": "Work area"}]}
WORK = [{"name": "Work area", "polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]], "kind": "work_area"}]


def test_outside_the_required_zone_no_violation_and_entering_it_raises_one(tmp_path):
    s = Script().add(**bare(4, x=40)).add(**bare(4, x=280))  # left half: not required; right half: required
    p, db = run(tmp_path, s, policy=ZONED, zones=WORK)
    (r,) = life(db)
    assert r["opened_t"] > 4.0 and r["classification"] == "violation"  # raised only after entering (debounced)
    assert p.ppe_seconds[NOT_APPLICABLE] > 3.5 and not db.groups()[0]["incident_type"] == "ZONE_INTRUSION"


def test_leaving_the_required_zone_resolves_the_violation(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(4, x=280)).add(**bare(4, x=40)), policy=ZONED, zones=WORK)
    (r,) = life(db)
    assert r["end_reason"] == RESOLVED


def test_foot_point_cut_off_makes_zone_membership_ambiguous(tmp_path):
    cut = Script().add(5, [(1, np.array([280.0, 150, 320, H]), 0.9)], [Detection(np.array([290.0, 150, 310, 172]), 0.9, "no_helmet")])
    p, db = run(tmp_path, cut, policy=ZONED, zones=WORK)
    assert life(db)[0]["classification"] == "requires_review"  # ambiguous requirement: review, not a violation


def test_policy_decisions():
    pol = ppe.PPEPolicy({**REQUIRED, "entries": REQUIRED["entries"] + [
        {"id": "X1", "camera": "cam", "zone": "Office", "ppe": ["head"], "required": False, "status": "confirmed",
         "established_by": "Safety lead"},
        {"id": "C1", "camera": "cam", "zone": "Dock", "ppe": ["head"], "required": True, "status": "provisional"},
        {"id": "C2", "camera": "cam", "zone": "Dock", "ppe": ["head"], "required": False, "status": "provisional"}]})
    assert pol.requirement("head", "cam").state == ppe.REQUIRED
    assert pol.requirement("head", "cam", zones_inside=["Office"]).state == ppe.NOT_REQUIRED  # zone beats camera-wide
    assert pol.requirement("head", "cam", zones_inside=["Dock"]).state == ppe.AMBIGUOUS  # conflict at the same scope
    assert pol.requirement("head", "cam", zones_uncertain=["Office"]).state == ppe.AMBIGUOUS
    assert pol.requirement("head", "other").state == ppe.UNCONFIGURED
    assert ppe.PPEPolicy(None).requirement("head", "cam").state == ppe.UNCONFIGURED
    assert pol.requirement("head", "cam").status == "confirmed"


@pytest.mark.parametrize("change, msg", [
    ({"status": "approved"}, "approved_by"),
    ({"entries": [{"id": "a", "camera": "c", "ppe": ["head"], "required": True, "status": "confirmed"}]}, "established_by"),
    ({"entries": [{"id": "a", "camera": "c", "ppe": ["helmetz"], "required": True, "status": "provisional"}]}, "ppe must"),
    ({"entries": [{"id": "a", "camera": "c", "ppe": ["head"], "required": True, "status": "provisional",
                   "effective_from": "2026-01-01"}]}, "UTC offset"),
    ({"entries": [{"id": "a", "camera": "c", "ppe": ["head"], "required": "yes", "status": "provisional"}]}, "true or false"),
    ({"entries": [{"id": "a", "camera": "c", "ppe": ["head"], "required": True, "status": "provisional", "colour": 1}]}, "unknown"),
])
def test_invalid_ppe_policies_are_rejected(change, msg):
    with pytest.raises(ValueError, match=msg):
        ppe.validate({**REQUIRED, **change})


def test_every_category_is_reported(tmp_path):
    p, db = run(tmp_path, Script().add(**bare(2)), policy=None)
    assert {r["category"] for r in db.ppe_observations()} == set(PPE_CATEGORIES)
