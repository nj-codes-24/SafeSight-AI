"""Identity-aware event matching (intelligence/event_metrics.py match_identity): adversarial cases (milestone M2.1)."""
import random

from intelligence.event_metrics import CONSISTENT, INCONSISTENT, UNKNOWN, evaluate, identity_relation, match, match_identity

PPE, ZONE = "PPE.HEAD.MISSING", "ZONE.ENTRY"
LEFT, RIGHT = [0.10, 0.20, 0.30, 0.90], [0.60, 0.20, 0.80, 0.90]


def ep(start, end, x, y=0.3, t=None, hazard=PPE, **kw):
    return {"hazard": hazard, "start_s": start, "end_s": end, "anchors": [{"t": start + 1 if t is None else t, "x": x, "y": y}], **kw}


def pred(t, box, t_end=None, iid=None, hazard=PPE, span=(0, 60), **kw):
    return {"type": hazard, "t": t, "t_end": t_end, "incident_id": iid or f"I{t}", "boxes": {s / 2: box for s in range(span[0] * 2, span[1] * 2)}, **kw}


def test_relation():
    assert identity_relation(ep(0, 10, 0.2), pred(1, LEFT)) == CONSISTENT
    assert identity_relation(ep(0, 10, 0.7), pred(1, LEFT)) == INCONSISTENT
    assert identity_relation(ep(0, 10, 0.2), pred(1, LEFT, span=(20, 30))) == UNKNOWN  # worker not visible at the anchor time
    assert identity_relation({"hazard": PPE, "start_s": 0, "end_s": 1}, pred(1, LEFT)) == UNKNOWN  # no anchor


def test_two_workers_violating_at_once_are_not_swapped():
    eps = [ep(0, 20, 0.2), ep(0, 20, 0.7)]  # left worker, right worker
    preds = [pred(1.0, RIGHT, 5.0, "right"), pred(9.0, LEFT, 19.0, "left")]  # the right worker is detected first
    swapped = match(eps, preds)
    assert {m["prediction"]["incident_id"]: m["episode"] for m in swapped["matches"]} == {"right": 0, "left": 1}  # time only
    m = match_identity(eps, preds)
    assert {x["prediction"]["incident_id"]: x["episode"] for x in m["matches"]} == {"left": 0, "right": 1}
    assert {x["latency_s"] for x in m["matches"]} == {9.0, 1.0} and m["identity"]["matched_consistent"] == 2


def test_two_workers_entering_the_same_zone():
    eps = [ep(0, 12, 0.2, hazard=ZONE, zone="Z"), ep(0, 4, 0.7, hazard=ZONE, zone="Z")]
    preds = [pred(0.4, RIGHT, 12.0, "r", ZONE, zone="Z"), pred(0.7, LEFT, 4.0, "l", ZONE, zone="Z")]
    m = match_identity(eps, preds)
    errs = {x["prediction"]["incident_id"]: x["duration_error_s"] for x in m["matches"]}
    assert errs == {"l": -8.7, "r": 7.6} and not m["false_alarms"]  # each duration compared with its own worker's episode


def test_reused_tracker_id_on_another_person_is_not_a_duplicate():
    e = {"hazard": PPE, "start_s": 0, "end_s": 10, "anchors": [{"t": 1, "x": 0.2, "y": 0.3}, {"t": 8, "x": 0.2, "y": 0.3}]}
    preds = [pred(1, LEFT, iid="first", worker_id=1), pred(8, RIGHT, iid="other", worker_id=1, span=(7, 12))]
    assert len(match([e], preds)["duplicates"]) == 1  # time only: looks like a repeat for the same episode
    m = match_identity([e], preds)
    assert [p["incident_id"] for p in m["false_alarms"]] == ["other"] and not m["duplicates"]
    # with only the early anchor, the other person's identity is unknown: the fallback keeps it a possible duplicate
    assert len(match_identity([ep(0, 10, 0.2)], preds)["duplicates"]) == 1


def test_same_worker_id_on_another_camera_never_matches():
    eps = [ep(0, 10, 0.2, camera="c1")]
    m = match_identity(eps, [pred(1, LEFT, worker_id=1, camera="c2")])
    assert m["missed"] and m["false_alarms"] and not m["matches"]


def test_track_fragmented_by_occlusion_or_reset_still_matches_through_its_chain():
    boxes = {**{s / 2: LEFT for s in range(0, 8)}, **{s / 2: [0.15, 0.2, 0.35, 0.9] for s in range(14, 40)}}  # two tracks
    p = {"type": PPE, "t": 1.0, "t_end": 18.0, "incident_id": "chain", "boxes": boxes}
    e = ep(0, 20, 0.25, t=15.0)  # anchor while the second track carries the worker
    assert match_identity([e], [p])["identity"]["matched_consistent"] == 1


def test_anchor_while_the_worker_is_occluded_falls_back_to_time_and_says_so():
    m = match_identity([ep(0, 20, 0.2, t=10)], [pred(1, LEFT, span=(0, 5))])
    assert len(m["matches"]) == 1 and m["identity"] == {**m["identity"], "matched_unknown": 1, "matched_consistent": 0}


def test_two_workers_crossing():
    a = {"hazard": PPE, "start_s": 0, "end_s": 20, "anchors": [{"t": 2, "x": 0.2, "y": 0.3}, {"t": 18, "x": 0.7, "y": 0.3}]}
    b = {"hazard": PPE, "start_s": 0, "end_s": 20, "anchors": [{"t": 2, "x": 0.7, "y": 0.3}, {"t": 18, "x": 0.2, "y": 0.3}]}
    path_a = {s / 2: (LEFT if s < 20 else RIGHT) for s in range(0, 40)}
    path_b = {s / 2: (RIGHT if s < 20 else LEFT) for s in range(0, 40)}
    preds = [{"type": PPE, "t": 15.0, "incident_id": "pa", "boxes": path_a}, {"type": PPE, "t": 1.0, "incident_id": "pb", "boxes": path_b}]
    m = match_identity([a, b], preds)
    assert {x["prediction"]["incident_id"]: x["episode"] for x in m["matches"]} == {"pa": 0, "pb": 1}


def test_several_incidents_of_one_hazard_in_one_clip():
    eps = [ep(0, 5, 0.2), ep(40, 45, 0.2), ep(41, 50, 0.7)]
    preds = [pred(1, LEFT, iid="a"), pred(41.5, RIGHT, iid="c"), pred(40.5, LEFT, iid="b")]
    m = match_identity(eps, preds)
    assert sorted((x["prediction"]["incident_id"], x["episode"]) for x in m["matches"]) == [("a", 0), ("b", 1), ("c", 2)]


def test_result_does_not_depend_on_input_order():
    eps = [ep(0, 20, 0.2), ep(0, 20, 0.7), ep(30, 35, 0.2)]
    preds = [pred(1, RIGHT, iid="x"), pred(3, LEFT, iid="y"), pred(4, LEFT, iid="z"), pred(31, LEFT, iid="w")]
    ref = None
    for seed in range(5):
        p = preds[:]
        random.Random(seed).shuffle(p)
        r = evaluate(eps, p, 60, identity=True)
        key = (r["true_positives"], r["duplicates"], r["false_alarms"], sorted((m["prediction"]["incident_id"], m["episode"])
                                                                              for m in r["matches"]))
        ref = ref or key
        assert key == ref


def test_without_identity_data_the_counts_equal_the_temporal_matcher():
    eps = [{"hazard": PPE, "start_s": s, "end_s": s + 5} for s in (0, 20, 40)]
    preds = [{"type": PPE, "t": t} for t in (1, 2, 21, 60)]
    a, b = evaluate(eps, preds, 100), evaluate(eps, preds, 100, identity=True)
    assert [a[k] for k in ("true_positives", "duplicates", "false_alarms", "missed")] == \
        [b[k] for k in ("true_positives", "duplicates", "false_alarms", "missed")]
    assert b["identity"]["matched_unknown"] == 2 and b["duplicate_rate"] == round(1 / 3, 4)
