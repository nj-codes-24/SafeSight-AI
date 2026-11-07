"""Event-level validation: compare predicted incidents with labelled hazard episodes.

An episode is a labelled interval during which a hazard condition held (docs/product_research/09 and 17). A prediction
matches an episode of the same hazard, and of the same zone when the episode names one, if its time lies within
[start - max(tolerance, start uncertainty), end + max(tolerance, end uncertainty)]. Each episode is matched once;
further matches are duplicates. Unmatched predictions are false alarms in monitorable time, context false alarms in
not-applicable regions, and unscorable in uncertain, unobservable or unusable regions (ignore).

Episodes may be optional (a match counts as found, a miss does not count) or context (a match is a context false alarm).
Without these fields, ignore regions and context regions, the behaviour is the original one.

Intervals are 95 %: Wilson for proportions and Byar's approximation for Poisson counts assume independent events;
cluster_bootstrap resamples whole source groups (recordings from one site or session) for correlated data.

Identity-aware matching (evaluate(..., identity=True), match_identity): an episode may carry identity anchors, points
{t, x, y} (normalised) where the labelled worker's head or body was at time t; a prediction may carry `boxes`, the
normalised boxes of its worker's track(s) by time ({t: [x1, y1, x2, y2]}), and `camera` / `session`. A pair is
identity-CONSISTENT if an anchor falls inside the prediction's box at that time, INCONSISTENT if the prediction's worker
was visible then but elsewhere, and UNKNOWN when there is no anchor or no box near the anchor time. Inconsistent pairs
never match: another worker's alert cannot be credited to this episode, nor counted as its duplicate. Unknown pairs
fall back to time alone and are counted, so a report shows how much of a result rests on identity. Different cameras
or sessions never match. Pairs are assigned globally (one episode, one prediction): consistent before unknown, then
required before optional, then containment, then the nearest start, then prediction time and id, so the result is
deterministic and independent of input order. Identity is never invented: without anchors and boxes this is the
temporal matcher.

Scope (both matchers, milestone M3): an episode and a prediction that both name a camera, or both name a session, must
name the same one. Where one side does not name it, the pair is allowed: that is the documented fallback for labels
made per clip (one clip is one camera session), and pooled multi-camera inputs must carry `camera` on both sides:
inputs naming more than one camera (or session) in which any item omits it are refused with ValueError.

End outcomes (M3): a prediction may carry `end_reason` from the incident lifecycle. Only "resolved" is positive
evidence that the condition ended. Any other end (observation lost, camera interrupted, view changed, blocked, scene
switched, view unverified, session end, reclassified) has an unknown outcome: the incident stopped being observed, not
necessarily the violation. Matches carry `end_outcome` ("resolved", "unknown", or None for runs before M2.1). The
duration error stays defined over all matches, because the protocol also ends a labelled episode when the worker leaves
view or the camera cuts (`17` §5), so both sides measure observed duration; it is additionally broken down by end
outcome. A resolved incident whose labelled episode went on for longer than max(tolerance, end uncertainty) after the
incident ended is a `premature_resolution`: the system said the violation was over while it continued. An unknown end
is never counted as a resolution, premature or otherwise.

Alert groups (M3): predictions may carry `group_id` (incident_lifecycle). A duplicate in the same group as a matched
prediction is a continuation the operator was not notified about again; `duplicates_same_group` counts them, so the
duplicate rate can be read at incident level and at notification level.
"""
import math
import random
import statistics

from intelligence.taxonomy import HAZARDS, hazard_for

Z95 = 1.959964


def wilson(k: int, n: int, z: float = Z95):
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    c, h = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (c - h) / d), 4), round(min(1.0, (c + h) / d), 4)


def poisson_interval(k: int, z: float = Z95):
    """Byar's approximation to the exact (Garwood) interval for a Poisson count; exact when k is 0."""
    if k == 0:
        return 0.0, -math.log(0.5 * math.erfc(z / math.sqrt(2)))
    lo = k * (1 - 1 / (9 * k) - z / (3 * math.sqrt(k))) ** 3
    hi = (k + 1) * (1 - 1 / (9 * (k + 1)) + z / (3 * math.sqrt(k + 1))) ** 3
    return lo, hi


def severity_of(item: dict) -> int | None:
    if item.get("severity") is not None:
        return int(item["severity"])
    try:
        return hazard_for(item["hazard"], item.get("zone_kind")).severity
    except (KeyError, ValueError):
        return HAZARDS[item["hazard"]].severity if item["hazard"] in HAZARDS else None


def _same_hazard(ep: dict, pred: dict) -> bool:
    return ep["hazard"] in (pred.get("type"), pred.get("hazard"))


def _window(ep, tol):
    return ep["start_s"] - max(tol, ep.get("start_unc_s", 0.0)), ep["end_s"] + max(tol, ep.get("end_unc_s", 0.0))


def _inside(t, regions):
    return any(a <= t <= b for a, b in regions)


def _scope_ok(ep, pred) -> bool:
    """Different cameras or sessions never match (module docstring: Scope)."""
    return all(ep.get(k) is None or pred.get(k) is None or ep[k] == pred[k] for k in ("camera", "session"))


def _check_pooled_scope(episodes, predictions):
    """The per-clip fallback (a missing camera or session matches any) is only safe when the inputs come from one camera
    session. Once they name more than one, an item without the field could match across cameras, so it is refused."""
    items = list(episodes) + list(predictions)
    for k in ("camera", "session"):
        named = {x[k] for x in items if x.get(k) is not None}
        if len(named) > 1 and any(x.get(k) is None for x in items):
            raise ValueError(f"inputs pool {len(named)} values of '{k}' but some items do not name one; "
                             f"every episode and prediction must carry '{k}' when inputs are pooled")


RESOLVED_END = "resolved"


def end_outcome(pred) -> str | None:
    """"resolved" (positive evidence the condition ended), "unknown" (any other end), or None (no lifecycle record)."""
    r = pred.get("end_reason")
    return None if r is None else "resolved" if r == RESOLVED_END else "unknown"


def _timing(ep, pred, t, tolerance_s):
    m = {"latency_s": round(t - ep["start_s"], 2)}
    if pred.get("t_end") is not None:
        m["duration_error_s"] = round((pred["t_end"] - t) - (ep["end_s"] - ep["start_s"]), 2)
        m["end_outcome"] = end_outcome(pred)
        m["premature_resolution"] = m["end_outcome"] == "resolved" and \
            ep["end_s"] - pred["t_end"] > max(tolerance_s, ep.get("end_unc_s", 0.0))
    return m


def match(episodes: list, predictions: list, tolerance_s: float = 2.0, ignore=(), context=()) -> dict:
    """Greedy in prediction time. Among free candidate episodes a required one beats an optional or context one, one
    containing the time beats one only reached by the tolerance, and then the nearest start wins."""
    _check_pooled_scope(episodes, predictions)
    matched, out = set(), {k: [] for k in ("matches", "optional_matches", "context_false_alarms", "duplicates",
                                           "false_alarms", "unscorable")}
    for pred in sorted(predictions, key=lambda x: x["t"]):
        t = pred["t"]
        cands = [(i, ep) for i, ep in enumerate(episodes) if _same_hazard(ep, pred) and _scope_ok(ep, pred)
                 and (ep.get("zone") is None or ep.get("zone") == pred.get("zone"))
                 and _window(ep, tolerance_s)[0] <= t <= _window(ep, tolerance_s)[1]]
        free = [c for c in cands if c[0] not in matched]
        if free:
            i, ep = min(free, key=lambda c: (bool(c[1].get("optional") or c[1].get("context")),
                                             not c[1]["start_s"] <= t <= c[1]["end_s"], abs(t - c[1]["start_s"])))
            matched.add(i)
            m = {"episode": i, "prediction": pred, **_timing(ep, pred, t, tolerance_s)}
            key = "context_false_alarms" if ep.get("context") else "optional_matches" if ep.get("optional") else "matches"
            out[key].append(m if key != "context_false_alarms" else pred)
        elif cands:
            out["duplicates"].append(pred)
        elif _inside(t, context):
            out["context_false_alarms"].append(pred)
        elif _inside(t, ignore):
            out["unscorable"].append(pred)
        else:
            out["false_alarms"].append(pred)
    out["missed"] = [ep for i, ep in enumerate(episodes) if i not in matched and not ep.get("optional") and not ep.get("context")]
    out["optional_missed"] = [ep for i, ep in enumerate(episodes) if i not in matched and ep.get("optional")]
    return out


CONSISTENT, UNKNOWN, INCONSISTENT = "consistent", "unknown", "inconsistent"


def identity_relation(ep: dict, pred: dict, max_dt: float = 0.5, grow: float = 0.15) -> str:
    """Whether a prediction's worker is the episode's labelled worker (module docstring)."""
    anchors, boxes = ep.get("anchors") or [], pred.get("boxes") or {}
    if not anchors or not boxes:
        return UNKNOWN
    times = sorted(boxes)
    seen = False
    for a in anchors:
        near = [t for t in times if abs(t - a["t"]) <= max_dt]
        if not near:
            continue
        seen = True
        x1, y1, x2, y2 = boxes[min(near, key=lambda t: abs(t - a["t"]))]
        gx, gy = grow * (x2 - x1), grow * (y2 - y1)
        if x1 - gx <= a["x"] <= x2 + gx and y1 - gy <= a["y"] <= y2 + gy:
            return CONSISTENT
    return INCONSISTENT if seen else UNKNOWN


def match_identity(episodes: list, predictions: list, tolerance_s: float = 2.0, ignore=(), context=()) -> dict:
    """Identity-aware, globally assigned matching. Same output keys as match(), plus `identity` statistics."""
    _check_pooled_scope(episodes, predictions)
    rel = {}
    for i, ep in enumerate(episodes):
        for j, p in enumerate(predictions):
            lo, hi = _window(ep, tolerance_s)
            if _same_hazard(ep, p) and (ep.get("zone") is None or ep.get("zone") == p.get("zone")) and lo <= p["t"] <= hi \
                    and _scope_ok(ep, p):
                rel[i, j] = identity_relation(ep, p)
    pairs = sorted((k for k, r in rel.items() if r != INCONSISTENT), key=lambda k: (
        rel[k] != CONSISTENT, bool(episodes[k[0]].get("optional") or episodes[k[0]].get("context")),
        not episodes[k[0]]["start_s"] <= predictions[k[1]]["t"] <= episodes[k[0]]["end_s"],
        abs(predictions[k[1]]["t"] - episodes[k[0]]["start_s"]), predictions[k[1]]["t"], str(predictions[k[1]].get("incident_id")), k[0]))
    used_e, used_p, by_pred = set(), set(), {}
    for i, j in pairs:
        if i in used_e or j in used_p:
            continue
        used_e.add(i)
        used_p.add(j)
        by_pred[j] = i
    out = {k: [] for k in ("matches", "optional_matches", "context_false_alarms", "duplicates", "false_alarms", "unscorable")}
    stats = {"matched_consistent": 0, "matched_unknown": 0, "excluded_inconsistent_pairs": sum(r == INCONSISTENT for r in rel.values()),
             "predictions_with_boxes": sum(1 for p in predictions if p.get("boxes")),
             "episodes_with_anchors": sum(1 for e in episodes if e.get("anchors"))}
    for j, p in sorted(enumerate(predictions), key=lambda x: (x[1]["t"], str(x[1].get("incident_id")))):
        if j in by_pred:
            i = by_pred[j]
            ep = episodes[i]
            stats["matched_consistent" if rel[i, j] == CONSISTENT else "matched_unknown"] += 1
            m = {"episode": i, "prediction": p, **_timing(ep, p, p["t"], tolerance_s), "identity": rel[i, j]}
            key = "context_false_alarms" if ep.get("context") else "optional_matches" if ep.get("optional") else "matches"
            out[key].append(m if key != "context_false_alarms" else p)
        elif any(rel.get((i, j)) in (CONSISTENT, UNKNOWN) for i in used_e):
            out["duplicates"].append(p)  # the same (or a possibly same) worker's episode was already matched
        elif _inside(p["t"], context):
            out["context_false_alarms"].append(p)
        elif _inside(p["t"], ignore):
            out["unscorable"].append(p)
        else:
            out["false_alarms"].append(p)
    out["missed"] = [ep for i, ep in enumerate(episodes) if i not in used_e and not ep.get("optional") and not ep.get("context")]
    out["optional_missed"] = [ep for i, ep in enumerate(episodes) if i not in used_e and ep.get("optional")]
    out["identity"] = stats
    return out


def _summary(episodes, predictions, duration_s, tolerance_s, ignore=(), context=(), monitorable_s=None, context_s=None,
             late_s=3.0, identity=False):
    m = (match_identity if identity else match)(episodes, predictions, tolerance_s, ignore, context)
    required = [ep for ep in episodes if not ep.get("optional") and not ep.get("context")]
    tp, fa, n, ctx, dup = len(m["matches"]), len(m["false_alarms"]), len(required), len(m["context_false_alarms"]), len(m["duplicates"])
    seconds = duration_s if monitorable_s is None else monitorable_s
    hours = seconds / 3600
    lat = sorted(x["latency_s"] for x in m["matches"])
    derr = [abs(x["duration_error_s"]) for x in m["matches"] if "duration_error_s" in x]
    by_end = {o: [abs(x["duration_error_s"]) for x in m["matches"] if x.get("end_outcome") == o] for o in ("resolved", "unknown")}
    groups = {x["prediction"].get("group_id") for x in m["matches"] + m["optional_matches"]} - {None}
    fa_lo, fa_hi = poisson_interval(fa)
    precision = tp / (tp + fa) if tp + fa else None
    recall = tp / n if n else None
    return {
        "episodes": n, "predictions": len(predictions), "true_positives": tp, "false_alarms": fa,
        "duplicates": dup, "missed": len(m["missed"]),
        "precision": round(precision, 4) if precision is not None else None, "precision_95ci": wilson(tp, tp + fa),
        "recall": round(recall, 4) if recall is not None else None, "recall_95ci": wilson(tp, n),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision and recall else (0.0 if tp == 0 and n else None),
        "alert_precision": round(tp / (tp + fa + dup + ctx), 4) if tp + fa + dup + ctx else None,
        "hours": round(hours, 4),
        "false_alarms_per_hour": round(fa / hours, 3) if hours else None,
        "false_alarms_per_hour_95ci": (round(fa_lo / hours, 3), round(fa_hi / hours, 3)) if hours else None,
        "latency_s": {"median": statistics.median(lat), "p90": lat[min(len(lat) - 1, math.ceil(0.9 * len(lat)) - 1)],
                      "max": lat[-1]} if lat else None,
        "late_detections": sum(1 for x in lat if x > late_s),
        "duration_abs_error_s_median": round(statistics.median(derr), 2) if derr else None,
        "duration_by_end_outcome": {o: {"matches": len(v), "abs_error_s_median": round(statistics.median(v), 2) if v else None}
                                    for o, v in by_end.items()},
        "ended_resolved": len(by_end["resolved"]), "ended_unknown_outcome": len(by_end["unknown"]),
        "premature_resolutions": sum(1 for x in m["matches"] + m["optional_matches"] if x.get("premature_resolution")),
        "duplicates_same_group": sum(1 for p in m["duplicates"] if p.get("group_id") in groups),
        "missed_critical": sum(1 for ep in m["missed"] if (severity_of(ep) or 0) >= 4),
        "context_false_alarms": ctx, "context_hours": round(context_s / 3600, 4) if context_s else 0.0,
        "unscorable": len(m["unscorable"]),
        "optional_episodes": len(m["optional_matches"]) + len(m["optional_missed"]),
        "optional_detected": len(m["optional_matches"]),
        "duplicate_rate": round(dup / (tp + dup), 4) if tp + dup else None,
        **({"identity": m["identity"]} if identity else {}),
    }, m


def evaluate(episodes: list, predictions: list, duration_s: float, tolerance_s: float = 2.0, ignore=(), context=(),
             monitorable_s=None, context_s=None, late_s: float = 3.0, identity: bool = False) -> dict:
    """Episodes: {hazard, start_s, end_s, zone?, zone_kind?, severity?, optional?, context?, start_unc_s?, end_unc_s?,
    anchors?, camera?, session?}. Predictions: {type, t, zone?, hazard?, t_end?, boxes?, camera?, session?}. ignore and
    context are lists of (start_s, end_s). identity=True uses match_identity (module docstring)."""
    kw = dict(ignore=ignore, context=context, monitorable_s=monitorable_s, context_s=context_s, late_s=late_s, identity=identity)
    report, m = _summary(episodes, predictions, duration_s, tolerance_s, **kw)
    by_type = {}
    for h in sorted({ep["hazard"] for ep in episodes} | {p["type"] for p in predictions}):
        eps = [ep for ep in episodes if ep["hazard"] == h]
        preds = [p for p in predictions if h in (p["type"], p.get("hazard"))]
        by_type[h] = _summary(eps, preds, duration_s, tolerance_s, **kw)[0]
    report.update(tolerance_s=tolerance_s, by_hazard=by_type, missed_episodes=m["missed"],
                  false_alarm_predictions=m["false_alarms"], duplicate_predictions=m["duplicates"],
                  context_false_alarm_predictions=m["context_false_alarms"], unscorable_predictions=m["unscorable"],
                  matches=m["matches"], optional_matches=m["optional_matches"], optional_missed=m["optional_missed"])
    return report


def cluster_bootstrap(units: list, statistic, n: int = 4000, seed: int = 0, level: float = 0.95):
    """Percentile interval of statistic(sample) over resampled clusters. units: one dict of summed counts per cluster
    (source group). statistic(list_of_units) -> float or None. Returns (low, high) or None."""
    if not units:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        v = statistic([units[rng.randrange(len(units))] for _ in units])
        if v is not None:
            vals.append(v)
    if len(vals) < n * 0.5:  # most resamples undefined (for example no positives): no meaningful interval
        return None
    vals.sort()
    a = (1 - level) / 2
    return round(vals[int(a * (len(vals) - 1))], 4), round(vals[int((1 - a) * (len(vals) - 1))], 4)


COUNT_KEYS = ("episodes", "true_positives", "missed", "false_alarms", "duplicates", "context_false_alarms", "unscorable",
              "optional_episodes", "optional_detected", "late_detections", "monitorable_s", "context_s")
EXTRA_COUNT_KEYS = ("duplicates_same_group", "ended_resolved", "ended_unknown_outcome", "premature_resolutions")  # M3


def summarise(rows: list, cluster_key: str = "source_group", boot_n: int = 4000) -> dict:
    """Pool per-clip result rows (counts as in COUNT_KEYS) into one summary with cluster-aware intervals.

    Each row is one clip's evaluate() counts for one hazard plus `monitorable_s`, `context_s` and the cluster key. The
    cluster is the unit of independence (a site or a source group): precision, recall and false alarms per monitorable
    hour get a percentile interval from resampling whole clusters, beside the Wilson and Poisson intervals that assume
    independent events. sufficient_for_recall_estimate needs at least 10 episodes from at least 3 clusters."""
    s = {k: sum(r[k] for r in rows) for k in COUNT_KEYS}
    s.update({k: sum(r[k] for r in rows) for k in EXTRA_COUNT_KEYS if all(k in r for r in rows)})
    tp, fa, n, hrs = s["true_positives"], s["false_alarms"], s["episodes"], s["monitorable_s"] / 3600
    prec, rec = (tp / (tp + fa) if tp + fa else None), (tp / n if n else None)
    groups = {}
    for r in rows:
        g = groups.setdefault(r[cluster_key], {"tp": 0, "fa": 0, "n": 0, "s": 0.0})
        g["tp"] += r["true_positives"]
        g["fa"] += r["false_alarms"]
        g["n"] += r["episodes"]
        g["s"] += r["monitorable_s"]
    units = list(groups.values())

    def rec_f(u):
        n_ = sum(x["n"] for x in u)
        return sum(x["tp"] for x in u) / n_ if n_ else None

    def prec_f(u):
        d = sum(x["tp"] + x["fa"] for x in u)
        return sum(x["tp"] for x in u) / d if d else None

    def fah_f(u):
        s_ = sum(x["s"] for x in u)
        return sum(x["fa"] for x in u) / (s_ / 3600) if s_ else None

    lo, hi = poisson_interval(fa)
    return {**{k: (round(v, 1) if isinstance(v, float) else v) for k, v in s.items()},
            "monitorable_hours": round(hrs, 4), "source_groups": len(groups),
            "groups_with_positives": sum(1 for g in units if g["n"]),
            "precision": round(prec, 4) if prec is not None else None, "precision_wilson95": wilson(tp, tp + fa),
            "precision_cluster_bootstrap95": cluster_bootstrap(units, prec_f, boot_n),
            "recall": round(rec, 4) if rec is not None else None, "recall_wilson95": wilson(tp, n),
            "recall_cluster_bootstrap95": cluster_bootstrap(units, rec_f, boot_n),
            "f1": round(2 * prec * rec / (prec + rec), 4) if prec and rec else (0.0 if n and not tp else None),
            "alert_precision": round(tp / (tp + fa + s["duplicates"] + s["context_false_alarms"]), 4)
            if tp + fa + s["duplicates"] + s["context_false_alarms"] else None,
            "false_alarms_per_monitorable_hour": round(fa / hrs, 2) if hrs else None,
            "false_alarms_per_hour_poisson95": (round(lo / hrs, 2), round(hi / hrs, 2)) if hrs else None,
            "false_alarms_per_hour_cluster_bootstrap95": cluster_bootstrap(units, fah_f, boot_n),
            "context_false_alarms_per_context_hour": round(s["context_false_alarms"] / (s["context_s"] / 3600), 2) if s["context_s"] else None,
            "sufficient_for_recall_estimate": n >= 10 and len([g for g in units if g["n"]]) >= 3,
            }
