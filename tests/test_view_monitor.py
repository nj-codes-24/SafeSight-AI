"""Camera view-change detection and its effect on incidents, tracking and zones.

Every camera movement here is SIMULATED: a virtual camera pans, tilts, rotates or zooms over a procedural textured
scene (tests/view_scenes.py), or the frame is replaced (cut), covered, defocused or dimmed. No physical camera was
moved. Scenario letters follow the milestone brief (docs/product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md); the
monitor runs with its documented defaults throughout, at 10 frames per second. The demo-footage checks are in
tests/test_view_monitor_footage.py.
"""
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from database.database import IncidentDB
from inference import view_monitor as vm
from inference.incident_lifecycle import SESSION_END, VIEW_INTERRUPTION
from inference.tracker import Pipeline
from runtime import config as rconfig
from runtime.service import Runtime
from runtime.sources import FrameSource
from runtime.view import ViewGuard
from tests import view_scenes as vs
from tests.test_runtime import LEFT_HALF, BoxDetector, FakeBackend

FPS = 10
W1, W2 = vs.world(1), vs.world(2)
T0 = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)  # wall clock of video time 0 in the guard tests


def lerp(t, t0, t1, a, b):
    return a + min(1.0, max(0.0, (t - t0) / (t1 - t0))) * (b - a)


def scene(t, world=W1, walkers=4, **cam):
    im = vs.camera(world, **cam)
    if walkers:
        vs.walkers(im, t, n=walkers)
    return im


def run(frame_at, seconds=30, settings=None, reference=None):
    """Feed the monitor every frame due for a check; returns the monitor and every transition."""
    m = vm.ViewMonitor(settings or vm.ViewSettings(), reference)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        if m.due(t):
            out += m.observe(vs.noise(frame_at(t), i), t)
    return m, out


def kinds(trs):
    return [tr.kind for tr in trs if tr.kind]


def states(trs):
    return [tr.state for tr in trs]


# ------------------------------------------------------------------ A-L: the monitor alone

def test_a_stable_scene_with_moving_workers_is_never_a_view_change():
    m, trs = run(lambda t: scene(t), 60)
    assert states(trs) == [vm.VIEW_STABLE] and m.state == vm.VIEW_STABLE and not m.warnings
    assert m.reference is not None and trs[0].t == pytest.approx(2.0)  # reference after init_s of steady view


@pytest.mark.parametrize("name, cam, movement", [
    ("b_pan", dict(cx=(900, 1044)), "pan"),  # 15 % of the view width
    ("c_tilt", dict(cy=(550, 615)), "tilt"),  # 12 % of the view height
    ("d_rotation", dict(angle=(0, 6)), "rotation"),
    ("e_zoom", dict(zoom=(1.0, 1.3)), "zoom"),
])
def test_bcde_persistent_camera_movement_is_detected_and_described(name, cam, movement):
    def frame(t):
        return scene(t, **{k: lerp(t, 10, 11, *v) for k, v in cam.items()})

    m, trs = run(frame, 30)
    (tr,) = [x for x in trs if x.kind]
    assert tr.kind == vm.CAMERA_VIEW_CHANGED and tr.state == vm.VIEW_CHANGED
    assert tr.evidence["transform"]["movement"][0] == movement
    expect = {"b_pan": ("dx", 0.15), "c_tilt": ("dy", 0.12), "d_rotation": ("angle_deg", -6.0), "e_zoom": ("scale", 1.3)}
    key, value = expect[name]  # camera turned right / tilted down / rotated / zoomed in
    assert tr.evidence["transform"][key] == pytest.approx(value, rel=0.08)
    assert tr.reliable_t == pytest.approx(10.0)  # the last check before the camera started to move
    assert tr.t - tr.suspected_t >= vm.ViewSettings().confirm_s  # persistence, not one frame
    assert tr.evidence["evidence_quality"] == "high"
    assert m.state == vm.VIEW_UNVERIFIED and m.candidate is not None  # the new view settled: an operator must decide


def test_f_abrupt_cut_to_another_scene_is_a_scene_switch():
    m, trs = run(lambda t: scene(t) if t < 10 else scene(t, world=W2), 25)
    assert kinds(trs) == [vm.CAMERA_SCENE_SWITCHED]
    tr = [x for x in trs if x.kind][0]
    assert tr.reliable_t == pytest.approx(9.5) and tr.suspected_t == pytest.approx(10.0)


@pytest.mark.parametrize("block", [lambda t: vs.covered(int(t * 10)), lambda t: vs.defocused(scene(t))],
                         ids=["lens_covered", "object_against_lens"])
def test_g_blockage_is_blocked_not_relocation(block):
    m, trs = run(lambda t: scene(t) if t < 10 else block(t), 25)
    assert kinds(trs) == [vm.CAMERA_BLOCKED] and m.state == vm.BLOCKED and not m.trusted


def test_h_brief_occlusion_by_a_passing_object_does_not_confirm_anything():
    def frame(t):
        im = scene(t)
        if 10 <= t < 11.5:  # something big passes right in front of the camera for 1.5 s
            vs.paste(im, vs.sprite(7, 560, 330), 40, 15)
        return im

    m, trs = run(frame, 30)
    assert kinds(trs) == [] and m.state == vm.VIEW_STABLE and m.disturbances == 1
    assert vm.SUSPECTED in states(trs)  # suspected, then cleared: no incident would have been touched


def test_i_lighting_change_is_not_relocation_and_lights_off_recovers_by_itself():
    m, trs = run(lambda t: scene(t) if t < 10 else vs.lighting(scene(t), 0.35, 1.4), 30)
    assert kinds(trs) == [] and m.state == vm.VIEW_STABLE  # dimmed to 35 % with a gamma change: same view
    m, trs = run(lambda t: scene(t) if t < 10 or t > 20 else vs.lighting(scene(t), 0.02, 1.0), 35)
    assert kinds(trs) == [vm.CAMERA_BLOCKED]  # nothing visible: unobservable, never "the camera moved"
    assert states(trs)[-2:] == [vm.RECOVERING, vm.VIEW_STABLE] and m.state == vm.VIEW_STABLE


def test_j_many_workers_moving_is_not_camera_movement():
    def frame(t):
        im = scene(t, walkers=0)
        vs.walkers(im, t, n=8, seed=20)
        return im

    m, trs = run(frame, 60)
    assert kinds(trs) == [] and m.state == vm.VIEW_STABLE


def test_k_vehicles_crossing_the_view_are_not_camera_movement():
    def frame(t):
        im = scene(t)
        vs.forklift(im, t)  # over a third of the width, every 8 s
        return im

    m, trs = run(frame, 60)
    assert kinds(trs) == [] and m.state == vm.VIEW_STABLE


def test_l_original_view_returning_recovers_after_the_stable_window():
    m, trs = run(lambda t: scene(t, cx=900 if t < 10 or t >= 20 else 1044), 30)
    assert kinds(trs) == [vm.CAMERA_VIEW_CHANGED]
    rec = [x for x in trs if x.state == vm.RECOVERING][0]
    back = trs[-1]
    assert back.state == vm.VIEW_STABLE and back.t - rec.t >= vm.ViewSettings().recover_s
    assert rec.t == pytest.approx(20.0) and m.reference is not None and not m.warnings


# ------------------------------------------------------------------ instability, references, settings

def test_vibration_is_a_warning_not_a_relocation():
    jit = np.random.default_rng(5).normal(0, 12, (400, 2))  # about 1.3 % of the width, every frame
    m, trs = run(lambda t: scene(t, cx=900 + jit[int(t * 10)][0], cy=550 + jit[int(t * 10)][1]), 40)
    assert kinds(trs) == [] and m.trusted
    assert any(w.startswith("vibration") or w.startswith("unstable") for w in m.warnings)


def test_small_shift_within_tolerance_is_the_same_view():
    m, trs = run(lambda t: scene(t, cx=lerp(t, 10, 11, 900, 909.6)), 25)  # 1 % of the width
    assert kinds(trs) == [] and m.state == vm.VIEW_STABLE


def test_loop_restart_and_reconnect_to_the_same_view_are_not_changes():
    m, trs = vm.ViewMonitor(), []
    for i in range(200):
        t = i / FPS
        disc = i in (60, 120)  # a looping file restarted / the stream reconnected: checked at once, compared to the reference
        if m.due(t, disc):
            trs += m.observe(vs.noise(scene(t), i), t, disc)
    assert states(trs) == [vm.VIEW_STABLE] and m.disturbances == 0


def test_stored_reference_is_verified_before_trust_and_a_different_view_is_unverified():
    ref = vm.Fingerprint.from_png(vm.fingerprint(vm.small_gray(scene(0, walkers=0), 320)).to_png())  # PNG round trip
    m, trs = run(lambda t: scene(t), 10, reference=ref)
    assert states(trs) == [vm.VIEW_STABLE] and trs[0].cause.startswith("registered reference")
    m, trs = run(lambda t: scene(t, world=W2), 25, reference=ref)  # camera re-aimed while the system was off
    assert kinds(trs) == [vm.CAMERA_VIEW_UNVERIFIED] and not m.trusted


def test_operator_acceptance_is_the_only_way_to_a_new_reference():
    m, trs = run(lambda t: scene(t, cx=1044 if t >= 10 else 900), 30)
    old = m.reference
    assert m.state == vm.VIEW_UNVERIFIED and m.reference is old  # never replaced automatically
    tr = m.accept(m.current(), 30.0)
    assert tr.state == vm.VIEW_STABLE and m.reference is not old
    m.observe(vs.noise(scene(30.5, cx=1044), 1), 30.5)
    assert m.state == vm.VIEW_STABLE and m.prev_check.outcome == vm.MATCH


def test_blockage_only_mode_ignores_movement_but_not_blockage():
    s = vm.ViewSettings(geometry=False)
    m, trs = run(lambda t: scene(t, cx=lerp(t, 10, 11, 900, 1044)), 25, settings=s)
    assert kinds(trs) == []
    m, trs = run(lambda t: scene(t) if t < 10 else vs.covered(int(t * 10)), 25, settings=s)
    assert kinds(trs) == [vm.CAMERA_BLOCKED]


def test_uncovered_on_a_different_view_needs_its_own_persistence():
    """Covered for 10 s, then uncovered pointing elsewhere: a new change, confirmed confirm_s after it is visible."""
    m, trs = run(lambda t: scene(t) if t < 8 else vs.covered(int(t * 10)) if t < 18 else scene(t, cx=1044), 30)
    assert kinds(trs) == [vm.CAMERA_BLOCKED, vm.CAMERA_VIEW_CHANGED]
    changed = [x for x in trs if x.kind == vm.CAMERA_VIEW_CHANGED][0]
    assert changed.previous == vm.BLOCKED and changed.t - 18.0 >= vm.ViewSettings().confirm_s


def test_every_transition_is_allowed_by_the_state_table():
    for frame in (lambda t: scene(t, cx=900 if t < 10 or t >= 20 else 1044),
                  lambda t: scene(t) if t < 8 else vs.covered(1) if t < 16 else scene(t, world=W2)):
        m, trs = run(frame, 40)
        assert all(tr.state in vm.ALLOWED[tr.previous] for tr in trs)


def test_a_check_is_cheap():
    m = vm.ViewMonitor()
    frames = [vs.noise(scene(i / 10), i) for i in range(20)]
    for i in range(10):
        m.observe(frames[i], i / 2)
    t0 = time.perf_counter()
    for i in range(10, 20):
        m.observe(frames[i], i / 2)
    assert (time.perf_counter() - t0) / 10 < 0.05  # documented ~5 ms; generous bound for slow CI machines


# ------------------------------------------------------------------ M, N: incidents and zones through the view guard

class ScriptBox(BoxDetector):
    """BoxDetector with no helmet output: a person in a zone gives a zone incident only."""


def camera_cfg(tmp_path, zones=True, **view):
    data = {"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                        "status_file": str(tmp_path / "status.json"), "log_file": None,
                        "pipeline_config": str(tmp_path / "none.json")},
            "inference": {"backend": "null"}, "sites": [{"id": "site-a"}],
            "cameras": [{"id": "cam", "site": "site-a", "source": {"type": "synthetic"},
                         "zones": [{"name": "Left", "polygon": LEFT_HALF}] if zones else [],
                         "view_monitor": {"enabled": True, **view}}]}
    return rconfig.parse(data)


class Harness:
    """What runtime/worker.py does per frame, without threads: guard first, then the pipeline if the view is trusted."""

    def __init__(self, tmp_path, zones=True, db=None):
        self.cfg = camera_cfg(tmp_path, zones)
        self.cam = self.cfg.cameras[0]
        self.db = db or IncidentDB(self.cfg.database)
        self.session = f"S-{len(self.db.view_revisions())}-{time.perf_counter_ns() % 10**6}"
        self.p = Pipeline(ScriptBox(), FPS, {"confirm_seconds": 0.5, "lost_track_seconds": 1.0, "grace_seconds": 2.0},
                          "cam", zones=self.cam.zones, db=self.db, session_id=self.session, evidence_dir=tmp_path / "ev",
                          annotate=False, ppe_policy=None)
        self.g = ViewGuard(self.cam, self.db, self.session, tmp_path / "ev", logging.getLogger("test.view"))
        self.analysed = 0

    def feed(self, frame_at, t0, t1, now=None):
        for i in range(round(t0 * FPS), round(t1 * FPS)):
            t = i / FPS
            im = vs.noise(frame_at(t), i)
            im[:, :, 2] = np.minimum(im[:, :, 2], 185)
            vs.person_box(im)  # one worker standing in the left-half zone throughout
            self.g.poll_commands(now if now is not None else t, self.p)
            self.g.observe(im, t, T0 + timedelta(seconds=t), i == round(t0 * FPS), self.p)
            if self.g.analysing:
                self.p.process(im, t)
                self.analysed += 1
        return self


def test_m_active_incident_is_interrupted_by_a_camera_move_not_resolved(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0, cx=lerp(t, 10, 11, 900, 1044)), 0, 30)
    h.p.finish("test", 30.0)
    (inc,) = h.db.lifecycle()
    assert inc["incident_type"] == "ZONE_INTRUSION" and inc["end_reason"] == vm.CAMERA_VIEW_CHANGED
    assert inc["end_reason"] in VIEW_INTERRUPTION and inc["end_reason"] != "resolved"
    assert inc["opened_t"] < 1.0  # original start preserved
    assert inc["ended_t"] == inc["last_observed_t"] == pytest.approx(10.0)  # last reliable check, not the decision time
    assert inc["closed_t"] == pytest.approx(15.5)  # decided after confirm_s of persistent evidence
    assert inc["exposure_s"] == pytest.approx(0.5 + 10.0 - inc["opened_t"], abs=0.01)  # no exposure invented after 10 s
    (ev,) = h.db.view_events()
    assert ev["event_type"] == vm.CAMERA_VIEW_CHANGED and ev["affected_incidents"] == [inc["incident_id"]]
    assert ev["last_reliable_t"] == pytest.approx(10.0) and ev["first_suspected_t"] == pytest.approx(10.5)
    ended = [e for e in h.db.events() if e["event"] == "ended"][0]["detail"]
    assert ended["view_event_id"] == ev["event_id"] and ended["observed_until_t"] > 10.0 and "risk_before" in ended
    assert h.db.rows()[0]["status"] == "CLOSED" and h.db.rows()[0]["evidence_path"]  # history kept, not resolved
    assert set(ev["snapshots"]) >= {"reference", "last_reliable", "confirmed", "candidate"}
    assert all(Path(p).exists() for p in ev["snapshots"].values())
    assert ev["state"] == vm.VIEW_UNVERIFIED and ev["candidate_revision"] == 2 and ev["recovered_utc"] is None
    assert h.analysed == 155  # 0-15.4 s analysed; nothing after the change was confirmed


def test_m_recovery_starts_fresh_incidents_with_new_track_ids_and_no_reopening(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0, cx=900 if t < 10 or t >= 18 else 1044), 0, 30)
    h.p.finish("test", 30.0)
    a, b = h.db.lifecycle()
    assert a["end_reason"] == vm.CAMERA_VIEW_CHANGED and b["end_reason"] == SESSION_END
    assert b["opened_t"] > 21.0 and b["group_id"] != a["group_id"] and b["relation"] is None  # new evidence, new incident
    assert min(b["tracks"]) > max(a["tracks"])  # old track IDs are never reused
    (ev,) = h.db.view_events()
    assert ev["outcome"] == "original_view_restored" and ev["recovered_t"] == pytest.approx(21.0)


def test_n_zone_geometry_is_unverified_after_a_view_change_until_an_operator_revalidates(tmp_path):
    h = Harness(tmp_path)
    moved = lambda t: scene(t, walkers=0, cx=lerp(t, 10, 11, 900, 1044))  # noqa: E731
    h.feed(moved, 0, 30)
    assert h.g.status()["zones"] == "suspended: view not trusted" and not h.p.zones_active
    cand = h.db.view_events()[0]["candidate_revision"]
    h.db.add_view_command("cam", "accept", "Site supervisor", revision=cand)  # zones NOT reviewed
    h.feed(moved, 30, 35)
    st = h.g.status()
    assert st["state"] == vm.VIEW_STABLE and st["reference_revision"] == cand and st["zones_status"] == "requires_review"
    assert st["zones"].startswith("requires_review") and not h.p.zones_active
    assert len(h.db.lifecycle()) == 1  # person still in the old zone's pixels: no alert from unverified geometry
    revs = {r["revision"]: r for r in h.db.view_revisions("cam")}
    assert revs[1]["status"] == "superseded" and revs[cand]["status"] == "active"  # history kept
    h.db.add_view_command("cam", "verify-zones", "Safety lead")
    h.feed(moved, 35, 40, now=100)
    assert h.p.zones_active and h.g.status()["zones"] == "monitoring"
    h.p.finish("test", 40.0)
    assert [r["end_reason"] for r in h.db.lifecycle()] == [vm.CAMERA_VIEW_CHANGED, SESSION_END]
    (ev,) = h.db.view_events()
    assert ev["outcome"].startswith("new_view_accepted") and ev["accepted_revision"] == cand
    assert [c["result"].split(":")[0].split(" ")[0] for c in h.db.view_commands("cam")] == ["accepted", "zones"]


def test_accepting_a_view_the_camera_is_not_showing_is_rejected(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0, cx=900 if t < 10 or t >= 30 else 1044), 0, 30)
    cand = h.db.view_events()[0]["candidate_revision"]
    h.feed(lambda t: scene(t, walkers=0), 30, 32)  # camera put back before the operator acted
    h.db.add_view_command("cam", "accept", "Operator", revision=cand)
    h.feed(lambda t: scene(t, walkers=0), 32, 33, now=999)
    assert h.db.view_commands("cam")[0]["result"].startswith("rejected")


def test_blocked_at_start_then_visible_closes_its_event_and_establishes_a_reference(tmp_path):
    """Covered from the first frame (the harness's red "person" box leaks through, so the image is not uniform)."""
    h = Harness(tmp_path, zones=False)
    covered_then_scene = lambda t: vs.covered(int(t * 10)) if t < 8 else scene(t, walkers=0)  # noqa: E731
    h.feed(covered_then_scene, 0, 7)
    (ev,) = h.db.view_events()  # recorded although no reference exists
    assert ev["event_type"] == vm.CAMERA_BLOCKED and ev["previous_revision"] is None and ev["state"] == vm.BLOCKED
    assert ev["confirmed_t"] == pytest.approx(5.0) and ev["last_reliable_t"] is None and ev["recovered_t"] is None
    assert h.db.view_revisions("cam") == [] and h.g.mon.reference is None  # the obstructed image is never a reference
    assert not h.g.analysing and h.g.status()["state"] == vm.BLOCKED
    h.feed(covered_then_scene, 7, 14)
    (ev,) = h.db.view_events()
    assert ev["outcome"] == "observable again; reference established" and h.g.revision == 1 and h.g.analysing
    assert ev["recovered_t"] == pytest.approx(10.0)  # 2 s (init_s) of steady view after it became visible at 8 s
    (rev,) = h.db.view_revisions("cam")
    assert rev["status"] == "active" and rev["basis"].startswith("auto") and rev["created_utc"]
    ref = vm.Fingerprint.from_png(h.db.view_fingerprint("cam", 1))
    assert ref.n >= vm.ViewSettings().min_features and ref.std > 20  # built from the scene, not the cover
    # 0-4.9 s bootstrap (50 frames), nothing while blocked or re-establishing, then 10.0-13.9 s (40 frames)
    assert h.g.status()["state"] == vm.VIEW_STABLE and h.analysed == 50 + 40


def test_incident_raised_on_an_obstructed_start_gets_no_exposure_after_its_opening(tmp_path):
    h = Harness(tmp_path)  # zone on the left half; the red box is in it from the first frame
    h.feed(lambda t: vs.covered(int(t * 10)) if t < 8 else scene(t, walkers=0), 0, 14)
    h.p.finish("test", 14.0)
    first, second = h.db.lifecycle()
    assert first["end_reason"] == vm.CAMERA_BLOCKED and first["ended_t"] == first["opened_t"]  # no reliable view at all
    assert first["exposure_s"] == pytest.approx(0.5)  # the confirmation time only
    ended = [e for e in h.db.events() if e["event"] == "ended"][0]["detail"]
    assert ended["opened_after_last_reliable_view"] is True
    assert second["opened_t"] > 10.0 and second["group_id"] != first["group_id"] and min(second["tracks"]) > max(first["tracks"])


def test_reconnect_after_a_blockage_at_start_verifies_the_new_reference(tmp_path):
    h = Harness(tmp_path, zones=False)
    h.feed(lambda t: vs.covered(int(t * 10)) if t < 8 else scene(t, walkers=0), 0, 14)
    h2 = Harness(tmp_path, zones=False, db=h.db)  # restart: the reference made after the blockage is the stored one
    h2.feed(lambda t: scene(t, walkers=0), 0, 3)
    assert h2.g.mon.state == vm.VIEW_STABLE and h2.g.revision == 1 and len(h.db.view_revisions("cam")) == 1


def test_a_camera_that_never_settles_does_not_use_its_zones(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0, cx=900 + 40 * t), 0, 14)  # panning slowly all the time
    assert h.g.mon.bootstrapping and h.g.mon.unsettled and not h.p.zones_active
    assert h.g.status()["zones"] == "suspended: no steady view"


def test_operator_commands_from_the_command_line(tmp_path, capsys):
    from runtime.__main__ import main

    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0, cx=lerp(t, 10, 11, 900, 1044)), 0, 30)
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"runtime": {"database": str(h.cfg.database), "log_file": None},
                                "inference": {"backend": "null"},
                                "cameras": [{"id": "cam", "source": {"type": "synthetic"}}]}))
    assert main(["view", "list", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "cam#2" in out and "candidate" in out and "NOT acknowledged" in out
    assert main(["view", "accept", "--config", str(path), "--camera", "cam", "--by", "Supervisor"]) == 2  # no revision
    assert main(["view", "accept", "--config", str(path), "--camera", "nope", "--revision", "2", "--by", "S"]) == 2
    eid = h.db.view_events()[0]["event_id"]
    assert main(["view", "acknowledge", "--config", str(path), "--camera", "cam", "--event", eid, "--by", "Supervisor"]) == 0
    assert main(["view", "accept", "--config", str(path), "--camera", "cam", "--revision", "2", "--by", "Supervisor",
                 "--zones-reviewed"]) == 0
    h.feed(lambda t: scene(t, walkers=0, cx=1044), 30, 31, now=500)
    assert [c["result"].split(" ")[0] for c in h.db.view_commands("cam")] == ["acknowledged", "accepted"]
    e = h.db.view_events()[0]
    assert e["acknowledged"] == 1 and e["acknowledged_by"] == "Supervisor" and e["accepted_revision"] == 2
    assert h.g.zones_status == "verified" and h.p.zones_active


def test_view_checks_that_keep_failing_fail_safe(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0), 0, 5)
    assert len(h.db.lifecycle()) == 1 and h.g.analysing

    def broken(*a):
        raise RuntimeError("simulated failure")

    h.g.mon.observe = broken
    for k in range(5):  # what the worker does when the guard raises
        h.g.on_failure(RuntimeError("simulated failure"), 5.0 + k / 2, h.p)
    assert not h.g.analysing and h.g.status()["state"] == "CHECK_FAILED"
    (inc,) = h.db.lifecycle()
    assert inc["end_reason"] == vm.CAMERA_VIEW_UNVERIFIED and inc["ended_t"] <= 5.0
    (ev,) = h.db.view_events()  # the failure is an auditable view event, with the incident it ended
    assert ev["event_type"] == vm.CAMERA_VIEW_UNVERIFIED and ev["affected_incidents"] == [inc["incident_id"]]
    assert "simulated failure" in ev["cause"] and ev["recovered_t"] is None
    del h.g.mon.observe  # the check works again
    h.feed(lambda t: scene(t, walkers=0), 8, 10)
    (ev,) = h.db.view_events()
    assert ev["outcome"] == "view checks working again" and h.g.analysing and h.g.status()["state"] == vm.VIEW_STABLE


def test_reconnecting_to_a_different_view_is_not_analysed_while_in_doubt(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0), 0, 5)
    n = h.analysed
    h.feed(lambda t: scene(t, walkers=0, world=W2), 20, 30)  # the stream came back (discontinuity) on another scene
    assert h.analysed == n  # not one frame analysed: no zone alert can come from the unverified view
    (inc,) = h.db.lifecycle()
    # no continuity is measured across a stream gap, so this is a view change ("not recognised"), not a cut
    assert inc["end_reason"] == vm.CAMERA_VIEW_CHANGED and inc["ended_t"] <= 5.0
    h2 = Harness(tmp_path / "b")
    h2.feed(lambda t: scene(t, walkers=0), 0, 5)
    n = h2.analysed
    h2.feed(lambda t: scene(t, walkers=0), 20, 22)  # came back on the same view: trusted at once
    assert h2.analysed == n + 20 and not h2.db.view_events()


def test_restart_verifies_the_stored_reference_and_zone_edits_need_review(tmp_path):
    h = Harness(tmp_path)
    h.feed(lambda t: scene(t, walkers=0), 0, 5)
    h2 = Harness(tmp_path, db=h.db)  # same camera, same database: a restart
    assert h2.g.mon.reference is not None and not h2.g.analysing  # nothing analysed before verification
    h2.feed(lambda t: scene(t, walkers=0), 0, 3)
    assert h2.g.mon.state == vm.VIEW_STABLE and h2.g.revision == 1 and len(h.db.view_revisions()) == 1
    assert h2.analysed == 10  # 2 s to verify, then analysis
    h3 = Harness(tmp_path, db=h.db)
    h3.cam.zones[0]["polygon"] = [[0, 0], [0.6, 0], [0.6, 1], [0, 1]]
    h4 = ViewGuard(h3.cam, h.db, "S-x", tmp_path / "ev", logging.getLogger("t"))
    assert h4.zones_status == "requires_review"  # zones edited after they were checked against this view


# ------------------------------------------------------------------ O and status: the runtime with several cameras

class SceneSource(FrameSource):
    type = "synthetic"
    live = paced = False

    def __init__(self, frame_at, seconds, camera_id, person_until=None):
        super().__init__({}, camera_id)
        self.frame_at, self.n, self.fps, self.i = frame_at, int(seconds * FPS), float(FPS), 0
        self.person_until = person_until  # a covered lens shows no person either

    def open(self):
        pass

    def read(self):
        if self.i >= self.n:
            return None
        t = self.i / FPS
        im = vs.noise(self.frame_at(t), self.i)
        im[:, :, 2] = np.minimum(im[:, :, 2], 185)
        if self.person_until is None or t < self.person_until:
            vs.person_box(im)
        self.i += 1
        return im

    def describe(self):
        return "scene"


def test_o_one_camera_blocked_or_moved_does_not_affect_the_others(tmp_path):
    cams = [{"id": cid, "site": "site-a", "source": {"type": "synthetic"}, "zones": [{"name": "Left", "polygon": LEFT_HALF}],
             "view_monitor": {"enabled": True}, "processing": {"max_fps": None, "queue_size": 4}}
            for cid in ("steady", "moved", "blocked")]
    cfg = rconfig.parse({"runtime": {"database": str(tmp_path / "rt.db"), "evidence_dir": str(tmp_path / "ev"),
                                     "status_file": str(tmp_path / "status.json"), "log_file": None,
                                     "pipeline_config": str(tmp_path / "none.json")},
                         "inference": {"backend": "null"}, "sites": [{"id": "site-a"}], "cameras": cams})
    sources = {"steady": SceneSource(lambda t: scene(t, walkers=2), 25, "steady"),
               "moved": SceneSource(lambda t: scene(t, walkers=2, cx=lerp(t, 10, 11, 900, 1044)), 25, "moved"),
               "blocked": SceneSource(lambda t: scene(t, walkers=2) if t < 10 else vs.covered(int(t * 10)), 25, "blocked",
                                      person_until=10)}
    rt = Runtime(cfg, backend=FakeBackend(), sources=sources)
    rt.start()
    end = time.monotonic() + 60
    while not rt.done() and time.monotonic() < end:
        time.sleep(0.05)
    status = rt.status()["cameras"]
    assert rt.stop() == []
    con = sqlite3.connect(cfg.database)
    con.row_factory = sqlite3.Row
    life = {r["camera_id"]: dict(r) for r in con.execute("SELECT * FROM incident_lifecycle")}
    events = {r["camera_id"]: dict(r) for r in con.execute("SELECT * FROM camera_view_events")}
    con.close()
    assert life["steady"]["end_reason"] == SESSION_END and "steady" not in events  # untouched by its neighbours
    assert life["moved"]["end_reason"] == vm.CAMERA_VIEW_CHANGED and events["moved"]["event_type"] == vm.CAMERA_VIEW_CHANGED
    assert life["blocked"]["end_reason"] == vm.CAMERA_BLOCKED and events["blocked"]["event_type"] == vm.CAMERA_BLOCKED
    assert json.loads(events["blocked"]["affected_incidents"]) == [life["blocked"]["incident_id"]]
    assert status["steady"]["view"]["state"] == vm.VIEW_STABLE
    assert status["blocked"]["view"]["state"] == vm.BLOCKED and status["blocked"]["view"]["trusted"] is False
    # blocked confirmed at 15.0 s: its last 100 frames were checked, not analysed; the others analysed every frame
    assert rt.workers["blocked"].health.view_suspended == 100 and rt.workers["steady"].health.view_suspended == 0
    assert rt.workers["steady"].health.processed == 250 and status["steady"]["view"]["trusted"] is True


def test_a_connected_camera_with_an_untrusted_view_is_not_monitoring():
    from runtime.config import Health
    from runtime.health import STREAMING, CameraHealth

    h = CameraHealth("c", Health())
    h.set_state(STREAMING)
    h.set_view({"enabled": True, "state": vm.BLOCKED, "trusted": False, "zones": None,
                "last_event": {"cause": "uniform image (covered, dark or blank)"}})
    s = h.snapshot()
    assert s["state"] == STREAMING and s["monitoring"] == "no" and "BLOCKED" in s["reason"]  # connection != view
    h.set_view({"enabled": True, "state": vm.VIEW_STABLE, "trusted": True, "zones": "requires_review: not verified",
                "last_event": None})
    assert h.snapshot()["monitoring"] == "partial"
    h.set_view({"enabled": True, "geometry": False, "state": vm.VIEW_STABLE, "trusted": True, "zones": None,
                "last_event": None})
    s = h.snapshot()
    assert s["monitoring"] == "partial" and "position not validated" in s["reason"]  # blockage-only is never full
    h.set_view({"enabled": True, "geometry": True, "state": vm.VIEW_STABLE, "trusted": True, "zones": "monitoring",
                "last_event": None})
    assert h.snapshot()["monitoring"] == "yes"


def test_demo_configurations_keep_the_fixed_camera_guards():
    root = Path(__file__).resolve().parents[1] / "config"
    fixed = rconfig.load(root / "runtime.demo.yaml")
    defaults = vm.ViewSettings()
    for c in fixed.cameras:  # fixed-camera demo: full view monitoring, nothing relaxed
        assert c.view.enabled and c.view.geometry and c.view.max_shift == defaults.max_shift
        assert c.view.confirm_s == defaults.confirm_s and "fixed camera" in c.name
    hand = rconfig.load(root / "runtime.demo_handheld.yaml")
    assert len(hand.cameras) == 4 and hand.database != fixed.database
    for c in hand.cameras:  # hand-held footage: blockage only and therefore no zones, never presented as validated
        assert c.view.enabled and not c.view.geometry and c.zones == []


def _runtime_cameras_page(path):
    from pathlib import Path

    from app.views.insights import runtime_cameras

    runtime_cameras(Path(path))


def test_dashboard_shows_view_health_beside_connection(tmp_path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    now = datetime.now(timezone.utc).isoformat()
    cam = {"state": "STREAMING", "monitoring": "no", "reason": "camera view BLOCKED: uniform image",
           "view": {"enabled": True, "state": vm.BLOCKED, "trusted": False, "zones": "suspended: view not trusted",
                    "reference_revision": 1, "interrupted_incidents": 1, "warnings": [],
                    "last_event": {"event_type": vm.CAMERA_BLOCKED, "cause": "uniform image"}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"runtime": {"state": "running", "updated_utc": now, "status_interval_s": 2},
                             "cameras": {"dock": cam}}))
    at = AppTest.from_function(_runtime_cameras_page, args=(str(p),), default_timeout=30).run()
    assert not at.exception
    row = at.dataframe[0].value.iloc[0]
    assert row["Connection"] == "STREAMING" and row["View"] == vm.BLOCKED and row["Monitoring"] == "no"
    assert row["Interrupted incidents"] == 1 and row["Last view event"].startswith(vm.CAMERA_BLOCKED)
    at = AppTest.from_function(_runtime_cameras_page, args=(str(tmp_path / "none.json"),), default_timeout=30).run()
    assert not at.exception and not at.dataframe  # no runtime yet: a message, not an error


# ------------------------------------------------------------------ configuration

def test_view_monitor_configuration():
    cfg = camera_cfg(Path("."), zones=False, confirm_s=8, max_shift=0.03)
    v = cfg.cameras[0].view
    assert v.enabled and v.confirm_s == 8 and v.max_shift == 0.03 and v.recover_s == vm.ViewSettings().recover_s
    with pytest.raises(rconfig.ConfigError, match="geometry"):
        camera_cfg(Path("."), zones=True, geometry=False)
    with pytest.raises(rconfig.ConfigError, match="unknown key"):
        camera_cfg(Path("."), sensitivity=3)
    with pytest.raises(rconfig.ConfigError, match="max_shift"):
        camera_cfg(Path("."), max_shift=2)
    base = {"runtime": {"log_file": None}, "inference": {"backend": "null"}}
    syn = rconfig.parse({**base, "cameras": [{"id": "a", "source": {"type": "synthetic"}}]})
    f = rconfig.parse({**base, "cameras": [{"id": "a", "source": {"type": "file", "path": "x.mp4"}}]})
    assert not syn.cameras[0].view.enabled and f.cameras[0].view.enabled  # on for real sources by default
