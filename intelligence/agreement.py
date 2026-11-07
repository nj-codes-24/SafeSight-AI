"""Inter-annotator agreement for evaluation labels (docs/product_research/17 and 19). Two independent label sets of
the same clips are compared with a measure suited to each kind of decision; no single number is allowed to stand for all
of them.

1. Event detection (did both annotators find the same violation?): events of the same hazard and kind are paired
   one-to-one when their intervals overlap or start within tol_s, and their identity anchors, where both have them at
   nearby times, are close. Reported as raw counts (both, only A, only B) and positive specific agreement
   PSA = 2·both / (2·both + only A + only B). Cohen's kappa is NOT used here: the "neither found an event" cell is
   undefined on a continuous timeline, so kappa would be arbitrary.
2. Temporal boundaries (for paired events): absolute start and end differences (median, 90th percentile, maximum) and
   temporal IoU. Seconds, not a coefficient, because the protocol tolerates a known uncertainty.
3. Interval states (monitorable, uncertain, unobservable, unusable, not_applicable, plus "unlabelled"): both
   timelines sampled every step_s; observed agreement, Cohen's kappa and, per state, specific agreement 2·n_ii / (row_i +
   col_i) with its sample count. Kappa applies because both annotators classify the same time units. Limitations:
   neighbouring samples are not independent (kappa's standard error would be too small, so none is reported), kappa
   depends on prevalence (a rare state can disagree badly behind a high overall kappa), hence the per-state values.
4. Event attributes for paired events (observability, requirement basis): percent agreement and kappa when there are
   at least 10 pairs; below that the counts are reported as insufficient.

Added in milestone M3:
5. Hazard category: events of any hazard paired across hazards by time and anchors; the hazard confusion and the share
   of cross-hazard pairs whose hazard differs. Only meaningful once more than one hazard can occur in the same place.
6. Zone assignment: for paired events that name a zone, percent agreement on the zone (a nominal attribute with very
   few pairs per clip, so no kappa below 10 pairs).
7. Event kind (uncertainty): events of one hazard paired regardless of kind (violation, uncertain, not applicable); the
   kind confusion shows where one reviewer called "violation" what the other called "uncertain". This is the
   event-level view of uncertainty agreement; the interval-state view is measure 3.
8. Annotation confidence (high, medium, low; optional field) on paired violation events: percent agreement and
   linearly weighted kappa (an ordinal scale) with at least 10 pairs.
9. Per clip: positive specific agreement and interval kappa for every clip, and a clip-level bootstrap interval for the
   pooled values (clips resampled whole, because samples inside a clip are not independent). With 15 clips the interval
   is wide; it is reported so the pooled number is not mistaken for a precise one.

`flags` lists every measure below its target (kappa or specific agreement < 0.6 where at least 10 samples or events
exist; PSA < 0.8; median boundary difference > 1 s; zone agreement < 0.8 with at least 5 pairs; any cross-hazard or
cross-kind disagreement on a paired event; a clip whose interval kappa is below 0.4), so a weak category cannot hide
behind a good aggregate.
"""
import random
import statistics
from collections import Counter

CONFIDENCE = ("low", "medium", "high")

STATES_UNLABELLED = "unlabelled"


def _kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None, None
    cats = sorted({c for p in pairs for c in p})
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / (n * n)
    return round(po, 4), (round((po - pe) / (1 - pe), 4) if pe < 1 else (1.0 if po == 1 else None))


def _state_at(intervals, hazard, t):
    for iv in intervals:
        if iv["hazard"] == hazard and iv["start_s"] <= t < iv["end_s"]:
            return iv["state"]
    return STATES_UNLABELLED


def interval_agreement(a, b, hazard, step_s=0.5):
    dur = min(a["duration_s"], b["duration_s"])
    pairs = [(_state_at(a["intervals"], hazard, k * step_s), _state_at(b["intervals"], hazard, k * step_s))
             for k in range(int(dur / step_s))]
    po, kappa = _kappa(pairs)
    cats = sorted({c for p in pairs for c in p})
    conf = {f"{x}|{y}": n for (x, y), n in Counter(pairs).items()}
    specific = {}
    for c in cats:
        nii = sum(1 for x, y in pairs if x == c and y == c)
        row, col = sum(1 for x, _ in pairs if x == c), sum(1 for _, y in pairs if y == c)
        specific[c] = {"specific_agreement": round(2 * nii / (row + col), 4), "samples_a": row, "samples_b": col}
    return {"step_s": step_s, "samples": len(pairs), "observed_agreement": po, "kappa": kappa, "per_state": specific,
            "confusion": conf}


def _anchor_ok(ea, eb, max_dt=1.0, max_dist=0.12):
    """False only if both have anchors at nearby times and they are far apart (different workers)."""
    near = [(x, y) for x in ea.get("anchors") or [] for y in eb.get("anchors") or [] if abs(x["t"] - y["t"]) <= max_dt]
    if not near:
        return True
    return any(((x["x"] - y["x"]) ** 2 + (x["y"] - y["y"]) ** 2) ** 0.5 <= max_dist for x, y in near)


def _overlap(ea, eb, tol):
    return min(ea["end_s"], eb["end_s"]) - max(ea["start_s"], eb["start_s"]) > 0 or abs(ea["start_s"] - eb["start_s"]) <= tol


def _iou(ea, eb):
    inter = max(0.0, min(ea["end_s"], eb["end_s"]) - max(ea["start_s"], eb["start_s"]))
    union = max(ea["end_s"], eb["end_s"]) - min(ea["start_s"], eb["start_s"])
    return inter / union if union > 0 else 1.0


def pair_events(a, b, hazard, kind="violation", tol_s=2.0):
    """One-to-one pairs of events. hazard=None or kind=None pairs across hazards or kinds (measures 5 and 7)."""
    ea = [e for e in a["events"] if hazard in (None, e["hazard"]) and kind in (None, e["kind"])]
    eb = [e for e in b["events"] if hazard in (None, e["hazard"]) and kind in (None, e["kind"])]
    cands = sorted(((i, j) for i, x in enumerate(ea) for j, y in enumerate(eb) if _overlap(x, y, tol_s) and _anchor_ok(x, y)),
                   key=lambda ij: (-_iou(ea[ij[0]], eb[ij[1]]), ij))
    used_a, used_b, pairs = set(), set(), []
    for i, j in cands:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            pairs.append((ea[i], eb[j]))
    return pairs, [e for i, e in enumerate(ea) if i not in used_a], [e for j, e in enumerate(eb) if j not in used_b]


def event_agreement(a, b, hazard, kind="violation", tol_s=2.0):
    pairs, only_a, only_b = pair_events(a, b, hazard, kind, tol_s)
    n2 = 2 * len(pairs)
    ds = [abs(x["start_s"] - y["start_s"]) for x, y in pairs]
    de = [abs(x["end_s"] - y["end_s"]) for x, y in pairs]

    def q(v):
        if not v:
            return None
        s = sorted(v)
        return {"median": round(statistics.median(s), 3), "p90": round(s[min(len(s) - 1, int(0.9 * len(s)))], 3), "max": round(s[-1], 3)}

    attrs = {}
    for name in ("observability", "requirement"):
        ap = [(x.get(name), y.get(name)) for x, y in pairs]
        po, kappa = _kappa(ap)
        attrs[name] = {"pairs": len(ap), "agreement": po, "kappa": kappa if len(ap) >= 10 else "insufficient (< 10 pairs)",
                       "confusion": {f"{x}|{y}": n for (x, y), n in Counter(ap).items()}}
    return {"kind": kind, "both": len(pairs), "only_a": len(only_a), "only_b": len(only_b),
            "positive_specific_agreement": round(n2 / (n2 + len(only_a) + len(only_b)), 4) if n2 + len(only_a) + len(only_b) else None,
            "start_abs_diff_s": q(ds), "end_abs_diff_s": q(de),
            "temporal_iou_median": round(statistics.median(_iou(x, y) for x, y in pairs), 3) if pairs else None,
            "attributes": attrs, "_pairs": pairs, "_only_a": only_a, "_only_b": only_b}


def state_disagreements(a, b, hazard, step_s=0.5, min_s=1.0):
    """Contiguous spans where the two interval timelines disagree for at least min_s."""
    dur = min(a["duration_s"], b["duration_s"])
    out, cur = [], None
    for k in range(int(dur / step_s) + 1):
        t = k * step_s
        sa, sb = (_state_at(a["intervals"], hazard, t), _state_at(b["intervals"], hazard, t)) if t < dur else (None, None)
        if sa != sb and t < dur:
            if cur and cur["a"] == sa and cur["b"] == sb:
                cur["end_s"] = t + step_s
            else:
                if cur and cur["end_s"] - cur["start_s"] >= min_s:
                    out.append(cur)
                cur = {"start_s": t, "end_s": t + step_s, "a": sa, "b": sb}
        else:
            if cur and cur["end_s"] - cur["start_s"] >= min_s:
                out.append(cur)
            cur = None
    return out


def compare(labels_a: dict, labels_b: dict, hazards=("PPE.HEAD.MISSING", "ZONE.ENTRY"), tol_s=2.0, step_s=0.5):
    """Agreement over every clip both sets cover. Returns per-hazard summaries, per-clip detail and flags."""
    clips = sorted(set(labels_a) & set(labels_b))
    out = {"clips": clips, "missing_in_a": sorted(set(labels_b) - set(labels_a)),
           "missing_in_b": sorted(set(labels_a) - set(labels_b)), "hazards": {}, "flags": []}
    for h in hazards:
        clips_h = [c for c in clips if labels_a[c].get("scope", {}).get(h) == "evaluated"
                   or labels_b[c].get("scope", {}).get(h) == "evaluated"]
        pairs_iv = []
        ev = {"both": 0, "only_a": 0, "only_b": 0}
        ds, de, ious, attr = [], [], [], {"observability": [], "requirement": []}
        kinds = Counter()
        zones, kind_pairs, conf = [], [], []
        per_clip = {}
        for c in clips_h:
            a, b = labels_a[c], labels_b[c]
            dur = min(a["duration_s"], b["duration_s"])
            clip_iv = [(_state_at(a["intervals"], h, k * step_s), _state_at(b["intervals"], h, k * step_s)) for k in range(int(dur / step_s))]
            pairs_iv += clip_iv
            e = event_agreement(a, b, h, "violation", tol_s)
            for k in ev:
                ev[k] += e[k]
            per_clip[c] = {"iv": clip_iv, "both": e["both"], "only_a": e["only_a"], "only_b": e["only_b"]}
            for x, y in e["_pairs"]:
                ds.append(abs(x["start_s"] - y["start_s"]))
                de.append(abs(x["end_s"] - y["end_s"]))
                ious.append(_iou(x, y))
                for name in attr:
                    attr[name].append((x.get(name), y.get(name)))
                if x.get("zone") or y.get("zone"):
                    zones.append((x.get("zone"), y.get("zone")))
                if x.get("confidence") in CONFIDENCE and y.get("confidence") in CONFIDENCE:
                    conf.append((x["confidence"], y["confidence"]))
            kind_pairs += [(x["kind"], y["kind"]) for x, y in pair_events(a, b, h, None, tol_s)[0]]
            for kind in ("uncertain", "not_applicable"):
                k2 = event_agreement(a, b, h, kind, tol_s)
                kinds[f"{kind}: both"] += k2["both"]
                kinds[f"{kind}: only_a"] += k2["only_a"]
                kinds[f"{kind}: only_b"] += k2["only_b"]
        po, kappa = _kappa(pairs_iv)
        per_state = {}
        for s in sorted({x for p in pairs_iv for x in p}):
            nii = sum(1 for x, y in pairs_iv if x == s and y == s)
            row, col = sum(1 for x, _ in pairs_iv if x == s), sum(1 for _, y in pairs_iv if y == s)
            per_state[s] = {"specific_agreement": round(2 * nii / (row + col), 4), "samples": row + col}
        n2 = 2 * ev["both"]
        psa = round(n2 / (n2 + ev["only_a"] + ev["only_b"]), 4) if n2 + ev["only_a"] + ev["only_b"] else None
        med = lambda v: round(statistics.median(v), 3) if v else None  # noqa: E731
        attrs = {}
        for name, ap in attr.items():
            pa, ka = _kappa(ap)
            attrs[name] = {"pairs": len(ap), "agreement": pa, "kappa": ka if len(ap) >= 10 else "insufficient (< 10 pairs)"}
        zone_ok = sum(x == y for x, y in zones)
        kind_diff = sum(x != y for x, y in kind_pairs)
        cpo, _ = _kappa(conf)
        clip_rows = {c: {"interval_kappa": _kappa(v["iv"])[1], "interval_samples": len(v["iv"]),
                         "violation_both": v["both"], "violation_only_a": v["only_a"], "violation_only_b": v["only_b"],
                         "positive_specific_agreement": round(2 * v["both"] / (2 * v["both"] + v["only_a"] + v["only_b"]), 4)
                         if v["both"] + v["only_a"] + v["only_b"] else None} for c, v in per_clip.items()}
        out["hazards"][h] = {"clips": len(clips_h), "intervals": {"samples": len(pairs_iv), "step_s": step_s, "observed_agreement": po,
                                                                  "kappa": kappa, "per_state": per_state,
                                                                  "kappa_clip_bootstrap95": _clip_bootstrap(
                                                                      list(per_clip.values()), lambda u: _kappa([p for x in u for p in x["iv"]])[1])},
                             "violation_events": {**ev, "positive_specific_agreement": psa, "start_abs_diff_median_s": med(ds),
                                                  "end_abs_diff_median_s": med(de), "temporal_iou_median": med(ious),
                                                  "psa_clip_bootstrap95": _clip_bootstrap(list(per_clip.values()), _psa)},
                             "other_events": dict(kinds), "attributes": attrs,
                             "zone_assignment": {"pairs": len(zones), "agreement": round(zone_ok / len(zones), 4) if zones else None,
                                                 "confusion": {f"{x}|{y}": n for (x, y), n in Counter(zones).items()}},
                             "event_kind": {"pairs": len(kind_pairs), "different_kind": kind_diff,
                                            "confusion": {f"{x}|{y}": n for (x, y), n in Counter(kind_pairs).items()}},
                             "confidence": {"pairs": len(conf), "agreement": cpo,
                                            "weighted_kappa": _weighted_kappa(conf) if len(conf) >= 10 else "insufficient (< 10 pairs)"},
                             "per_clip": clip_rows}
        if len(zones) >= 5 and zone_ok / len(zones) < 0.8:
            out["flags"].append(f"{h}: zone assignment agreement {round(zone_ok / len(zones), 4)} < 0.8")
        if kind_diff:
            out["flags"].append(f"{h}: {kind_diff} paired event(s) with a different kind (e.g. violation vs uncertain)")
        for c, r in clip_rows.items():
            if r["interval_kappa"] is not None and r["interval_samples"] >= 10 and r["interval_kappa"] < 0.4:
                out["flags"].append(f"{h}: clip {c} interval kappa {r['interval_kappa']} < 0.4")
        if kappa is not None and len(pairs_iv) >= 10 and kappa < 0.6:
            out["flags"].append(f"{h}: interval-state kappa {kappa} < 0.6")
        for s, v in per_state.items():
            if v["samples"] >= 10 and v["specific_agreement"] < 0.6:
                out["flags"].append(f"{h}: state '{s}' specific agreement {v['specific_agreement']} < 0.6")
        if psa is not None and psa < 0.8:
            out["flags"].append(f"{h}: violation-event positive specific agreement {psa} < 0.8")
        if ds and (med(ds) > 1 or med(de) > 1):
            out["flags"].append(f"{h}: median boundary difference above 1 s (start {med(ds)}, end {med(de)})")
        for name, v in attrs.items():
            if isinstance(v["kappa"], float) and v["kappa"] < 0.6:
                out["flags"].append(f"{h}: {name} kappa {v['kappa']} < 0.6")
    cross, hz = [], Counter()
    for c in clips:
        for x, y in pair_events(labels_a[c], labels_b[c], None, "violation", tol_s)[0]:
            cross.append((x["hazard"], y["hazard"]))
    hz.update(cross)
    diff = sum(x != y for x, y in cross)
    out["hazard_category"] = {"pairs": len(cross), "different_hazard": diff, "confusion": {f"{x}|{y}": n for (x, y), n in hz.items()}}
    if diff:
        out["flags"].append(f"{diff} paired violation event(s) labelled with different hazards")
    return out


def _psa(units):
    both, oa, ob = (sum(u[k] for u in units) for k in ("both", "only_a", "only_b"))
    return 2 * both / (2 * both + oa + ob) if both + oa + ob else None


def _clip_bootstrap(units, statistic, n=2000, seed=0):
    """Percentile 95 % interval over clips resampled whole (measure 9); None when undefined in most resamples."""
    if len(units) < 2:
        return None
    rng = random.Random(seed)
    vals = sorted(v for v in (statistic([units[rng.randrange(len(units))] for _ in units]) for _ in range(n)) if v is not None)
    if len(vals) < n / 2:
        return None
    return round(vals[int(0.025 * (len(vals) - 1))], 4), round(vals[int(0.975 * (len(vals) - 1))], 4)


def _weighted_kappa(pairs, cats=CONFIDENCE):
    """Linearly weighted kappa for an ordinal scale."""
    n, k = len(pairs), len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    w = [[1 - abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    obs = Counter((idx[a], idx[b]) for a, b in pairs)
    ra, cb = Counter(idx[a] for a, _ in pairs), Counter(idx[b] for _, b in pairs)
    po = sum(w[i][j] * obs[i, j] for i in range(k) for j in range(k)) / n
    pe = sum(w[i][j] * ra[i] * cb[j] for i in range(k) for j in range(k)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else (1.0 if po == 1 else None)
