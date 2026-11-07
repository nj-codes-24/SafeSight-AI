"""Evaluation matching audit (milestone M3): camera and session scope in both matchers, hazard and zone identity,
ignore regions, duplicates across tracker resets and alert groups, end outcomes (a camera-view interruption is never a
resolution), and cluster-aware pooling. Every input is a synthetic fixture."""
import pytest

from intelligence.event_metrics import evaluate, match, match_identity, summarise

PPE, ZONE = "PPE.HEAD.MISSING", "ZONE.ENTRY"
LEFT, RIGHT = [0.10, 0.20, 0.30, 0.90], [0.60, 0.20, 0.80, 0.90]


def boxes(box, a=0, b=60):
    return {s / 2: box for s in range(a * 2, b * 2)}


@pytest.mark.parametrize("matcher", [match, match_identity])
def test_a_worker_on_one_camera_never_matches_an_episode_on_another(matcher):
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10, "camera": "dock-1"}]
    preds = [{"type": PPE, "t": 1.0, "camera": "dock-2", "incident_id": "x", "worker_id": 1}]
    m = matcher(eps, preds)
    assert not m["matches"] and len(m["missed"]) == 1 and len(m["false_alarms"]) == 1


@pytest.mark.parametrize("matcher", [match, match_identity])
def test_pooled_cameras_match_each_to_its_own_camera(matcher):
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10, "camera": c} for c in ("a", "b")]
    preds = [{"type": PPE, "t": 1.0, "camera": "b", "incident_id": "pb"}, {"type": PPE, "t": 2.0, "camera": "a", "incident_id": "pa"}]
    pairs = {eps[x["episode"]]["camera"]: x["prediction"]["camera"] for x in matcher(eps, preds)["matches"]}
    assert pairs == {"a": "a", "b": "b"}


@pytest.mark.parametrize("matcher", [match, match_identity])
def test_sessions_are_scoped_like_cameras(matcher):
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10, "camera": "a", "session": "s1"}]
    assert not matcher(eps, [{"type": PPE, "t": 1.0, "camera": "a", "session": "s2", "incident_id": "x"}])["matches"]


def test_documented_fallback_when_labels_do_not_name_the_camera():
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10}]  # per-clip labels: one clip is one camera session
    assert len(match(eps, [{"type": PPE, "t": 1.0, "camera": "a", "incident_id": "x"}])["matches"]) == 1


@pytest.mark.parametrize("matcher", [match, match_identity])
@pytest.mark.parametrize("key", ["camera", "session"])
def test_pooled_inputs_with_an_unnamed_item_are_refused(matcher, key):
    # an unnamed prediction would otherwise match camera a's episode although it may come from camera b
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10, key: "a"}, {"hazard": PPE, "start_s": 20, "end_s": 30, key: "b"}]
    with pytest.raises(ValueError, match=key):
        matcher(eps, [{"type": PPE, "t": 1.0, "incident_id": "x"}])
    with pytest.raises(ValueError, match=key):
        evaluate(eps, [{"type": PPE, "t": 1.0, "incident_id": "x"}], 60.0)


@pytest.mark.parametrize("matcher", [match, match_identity])
def test_one_camera_with_unnamed_labels_still_uses_the_fallback(matcher):
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10}]
    preds = [{"type": PPE, "t": 1.0, "camera": "a", "incident_id": "x"}, {"type": PPE, "t": 30.0, "camera": "a", "incident_id": "y"}]
    m = matcher(eps, preds)
    assert len(m["matches"]) == 1 and len(m["false_alarms"]) == 1


def test_hazard_and_zone_identity():
    eps = [{"hazard": ZONE, "start_s": 0, "end_s": 10, "zone": "Dock edge"}]
    preds = [{"type": PPE, "t": 1.0, "incident_id": "ppe"}, {"type": ZONE, "t": 1.0, "zone": "Aisle 4", "incident_id": "other zone"}]
    r = evaluate(eps, preds, 60)
    assert r["true_positives"] == 0 and r["missed"] == 1 and r["false_alarms"] == 2


def test_uncertain_and_unobservable_time_is_unscorable_not_a_false_alarm():
    preds = [{"type": PPE, "t": t, "incident_id": str(t)} for t in (5.0, 25.0, 45.0)]
    r = evaluate([], preds, 60, ignore=[(20, 30)], monitorable_s=40, context=[(40, 50)])
    assert (r["false_alarms"], r["unscorable"], r["context_false_alarms"]) == (1, 1, 1)
    assert r["hours"] == round(40 / 3600, 4)  # only monitorable time is the denominator


def test_exact_duplicate_prediction_is_a_duplicate():
    eps = [{"hazard": PPE, "start_s": 0, "end_s": 10}]
    preds = [{"type": PPE, "t": 1.0, "incident_id": "a"}, {"type": PPE, "t": 1.0, "incident_id": "b"}]
    r = evaluate(eps, preds, 60, identity=True)
    assert (r["true_positives"], r["duplicates"], r["false_alarms"], r["duplicate_rate"]) == (1, 1, 0, 0.5)


def test_tracker_reset_fragment_is_a_duplicate_and_same_group_is_counted_apart():
    ep = {"hazard": PPE, "start_s": 0, "end_s": 30, "anchors": [{"t": 2, "x": 0.2, "y": 0.5}, {"t": 20, "x": 0.2, "y": 0.5}]}
    first = {"type": PPE, "t": 1.0, "t_end": 10.0, "incident_id": "i1", "group_id": "g1", "boxes": boxes(LEFT, 0, 10)}
    after_reset = {"type": PPE, "t": 15.0, "t_end": 29.0, "incident_id": "i2", "group_id": "g1", "boxes": boxes(LEFT, 15, 30)}
    other_worker = {"type": PPE, "t": 16.0, "incident_id": "i3", "group_id": "g9", "boxes": boxes(RIGHT, 15, 30)}
    r = evaluate([ep], [first, after_reset, other_worker], 60, identity=True)
    assert r["true_positives"] == 1 and r["duplicates"] == 1 and r["duplicates_same_group"] == 1
    assert [p["incident_id"] for p in r["false_alarm_predictions"]] == ["i3"]  # another worker is never a duplicate
    r2 = evaluate([ep], [first, {**after_reset, "group_id": "g2"}], 60, identity=True)
    assert r2["duplicates"] == 1 and r2["duplicates_same_group"] == 0  # a new group: the operator was notified again


@pytest.mark.parametrize("reason", ["camera_view_changed", "camera_blocked", "camera_scene_switched", "camera_view_unverified",
                                    "camera_interrupted", "observation_lost", "session_end"])
def test_an_interruption_is_never_counted_as_a_resolution(reason):
    ep = {"hazard": PPE, "start_s": 0, "end_s": 40}
    p = {"type": PPE, "t": 1.0, "t_end": 12.0, "end_reason": reason, "incident_id": "x"}
    r = evaluate([ep], [p], 60)
    assert r["ended_unknown_outcome"] == 1 and r["ended_resolved"] == 0 and r["premature_resolutions"] == 0
    assert r["matches"][0]["end_outcome"] == "unknown" and r["duration_by_end_outcome"]["unknown"]["matches"] == 1


def test_premature_resolution_needs_the_violation_to_continue_past_the_tolerance():
    ep = {"hazard": PPE, "start_s": 0, "end_s": 40, "end_unc_s": 3.0}
    early = {"type": PPE, "t": 1.0, "t_end": 12.0, "end_reason": "resolved", "incident_id": "early"}
    on_time = {"type": PPE, "t": 1.0, "t_end": 38.0, "end_reason": "resolved", "incident_id": "ok"}
    assert evaluate([ep], [early], 60)["premature_resolutions"] == 1
    assert evaluate([ep], [on_time], 60)["premature_resolutions"] == 0  # within max(2 s, 3 s uncertainty)
    legacy = evaluate([ep], [{"type": PPE, "t": 1.0, "t_end": 12.0, "incident_id": "old"}], 60)
    assert legacy["matches"][0]["end_outcome"] is None and legacy["premature_resolutions"] == 0
    assert legacy["duration_abs_error_s_median"] == 29.0  # duration error itself is unchanged


def row(cluster, tp, fa, n, s=3600.0, **kw):
    base = {"source_group": cluster, "episodes": n, "true_positives": tp, "missed": n - tp, "false_alarms": fa, "duplicates": 0,
            "context_false_alarms": 0, "unscorable": 0, "optional_episodes": 0, "optional_detected": 0, "late_detections": 0,
            "monitorable_s": s, "context_s": 0.0}
    return {**base, **kw}


def test_summarise_pools_counts_and_resamples_whole_clusters():
    one_site = [row("G1", 3, 1, 4) for _ in range(5)]  # 20 episodes, all from one site
    many = [row(f"G{i}", 3, 1, 4) for i in range(5)]
    a, b = summarise(one_site, boot_n=500), summarise(many, boot_n=500)
    assert (a["episodes"], a["true_positives"], a["false_alarms"], a["monitorable_hours"]) == (20, 15, 5, 5.0)
    assert a["recall"] == b["recall"] == 0.75 and a["recall_wilson95"] == b["recall_wilson95"]
    assert a["sufficient_for_recall_estimate"] is False and b["sufficient_for_recall_estimate"] is True
    assert a["recall_cluster_bootstrap95"] == (0.75, 0.75)  # one cluster: the bootstrap cannot pretend to be informative
    assert summarise(many, boot_n=500) == b  # deterministic


def test_summarise_does_not_let_one_large_site_set_the_interval_alone():
    rows = [row("big", 40, 0, 40)] + [row(f"s{i}", 0, 0, 2) for i in range(4)]
    s = summarise(rows, boot_n=2000)
    assert s["recall"] == round(40 / 48, 4)
    lo, hi = s["recall_cluster_bootstrap95"]
    assert lo == 0.0 and hi > 0.9  # resampling sites shows the result rests on one site
    w_lo, _ = s["recall_wilson95"]
    assert w_lo > 0.6  # the independence interval would have hidden it


def test_summarise_sums_m3_counts_only_when_every_row_has_them():
    rows = [row("a", 1, 0, 1, premature_resolutions=1, duplicates_same_group=0, ended_resolved=1, ended_unknown_outcome=0),
            row("b", 1, 0, 1, premature_resolutions=0, duplicates_same_group=2, ended_resolved=0, ended_unknown_outcome=1)]
    s = summarise(rows, boot_n=100)
    assert (s["premature_resolutions"], s["duplicates_same_group"], s["ended_unknown_outcome"]) == (1, 2, 1)
    assert "premature_resolutions" not in summarise([row("a", 1, 0, 1)], boot_n=100)
