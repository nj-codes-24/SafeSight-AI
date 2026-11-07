"""M2.1 before/after diagnostic: the frozen M2 logic and the new logic, replayed on the same recorded model traces, scored
with the M2 time-only matcher and the new identity-aware matcher.

    python scripts/validation/m2_1_diagnostics.py

DIAGNOSTIC ONLY. The labels are the provisional AI set (v1, and v1.2 = v1 plus identity anchors); nothing here is a
validated measurement or a claimed improvement. No threshold, model or lifecycle setting was tuned on these labels:
the lifecycle defaults were fixed before this script was run (inference/config.py). Writes
reports/validation/m2_1_diagnostics/ only; the M2 result files are never touched.

Variants:
  A  M2 logic, time-only matcher                        (reproduces the M2 baseline from traces)
  B  M2 logic, identity-aware matcher                   (effect of the matcher alone)
  C  new logic, camera-wide PROVISIONAL head requirement, identity-aware matcher
     (the M2 assumption made explicit, so the lifecycle and visibility effects are isolated)
  D  new logic, no PPE policy (the shipped default): every missing-helmet alert is a review item, none is a violation
"""
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.annotations import load_set, scoring_inputs, verify_lock  # noqa: E402
from intelligence.event_metrics import evaluate, poisson_interval, wilson  # noqa: E402
from scripts.validation.replay import load_trace, replay  # noqa: E402

VAL = ROOT / "reports" / "validation"
OUT = VAL / "m2_1_diagnostics"
TYPE_TO_HAZARD = {"NO_HELMET": "PPE.HEAD.MISSING", "ZONE_INTRUSION": "ZONE.ENTRY"}
ASSUMED_EVERYWHERE = {"schema": "safesight.ppe_policy/1.0", "version": "diagnostic-assumption", "status": "draft",
                      "entries": [{"id": "ALL", "camera": "*", "ppe": ["head"], "required": True, "status": "provisional",
                                   "basis": "the M2 assumption (helmet required everywhere), made explicit; not a site policy"}]}
# Since M3 a provisional entry gives review items, not confirmed violations (inference/tracker.py): re-running variant C
# raises the same incidents at the same times, but classified "requires_review". The stored M2.1 results predate this.
VARIANTS = {"A": ("legacy", None, False), "B": ("legacy", None, True), "C": ("current", ASSUMED_EVERYWHERE, True),
            "D": ("current", None, True)}


def predictions(incidents, trace, extras):
    w, h, fps = trace["width"], trace["height"], trace["fps"]
    boxes = extras["boxes"] if isinstance(extras, dict) else None
    if boxes is None:
        boxes = {}
        for fi, (persons, _) in enumerate(trace["frames"]):
            for p in persons:
                boxes.setdefault(p[0], {})[fi] = p[1:5]
    out = []
    for e in incidents:
        tracks = e.get("tracks") or [e["worker_id"]]
        b = {}
        for tid in tracks:
            for fi, (x1, y1, x2, y2) in boxes.get(tid, {}).items():
                b[round(fi / fps, 3)] = [x1 / w, y1 / h, x2 / w, y2 / h]
        out.append({"type": TYPE_TO_HAZARD[e["type"]], "t": e["t"], "t_end": e["t_end"], "zone": e["zone"],
                    "incident_id": e["incident_id"], "worker_id": e["worker_id"], "boxes": b,
                    "classification": e.get("classification"), "end_reason": e.get("end_reason")})
    return out


def score(labels, preds_by_clip, identity):
    rows, per_ep = [], []
    for cid, lab in labels.items():
        for hz in ("PPE.HEAD.MISSING", "ZONE.ENTRY"):
            if lab["scope"].get(hz) != "evaluated":
                continue
            si = scoring_inputs(lab, hz)
            p = [x for x in preds_by_clip.get(cid, []) if x["type"] == hz]
            r = evaluate(si["episodes"], p, lab["duration_s"], 2.0, si["ignore"], si["context"], si["monitorable_s"],
                         si["context_s"], 3.0, identity=identity)
            rows.append({"clip_id": cid, "split": lab["split"], "hazard": hz, "monitorable_s": si["monitorable_s"],
                         "alerts": len(p), **{k: r[k] for k in ("episodes", "true_positives", "missed", "false_alarms",
                                                               "duplicates", "context_false_alarms", "unscorable",
                                                               "optional_detected", "optional_episodes", "late_detections")},
                         "identity": r.get("identity")})
            for kind, ms in (("required", r["matches"]), ("optional", r["optional_matches"])):
                for m in ms:
                    ep = si["episodes"][m["episode"]]
                    per_ep.append({"clip_id": cid, "split": lab["split"], "hazard": hz, "event_id": ep["id"], "episode": kind,
                                   "true_start_s": ep["start_s"], "true_end_s": ep["end_s"], "incident_id": m["prediction"]["incident_id"],
                                   "worker_id": m["prediction"]["worker_id"], "alert_t": m["prediction"]["t"],
                                   "alert_end_t": m["prediction"]["t_end"], "latency_s": m["latency_s"],
                                   "true_duration_s": round(ep["end_s"] - ep["start_s"], 2),
                                   "alert_duration_s": None if m["prediction"]["t_end"] is None else round(m["prediction"]["t_end"] - m["prediction"]["t"], 2),
                                   "duration_error_s": m.get("duration_error_s"), "identity": m.get("identity", "n/a (time only)")})
            for ep in r["missed_episodes"]:
                per_ep.append({"clip_id": cid, "split": lab["split"], "hazard": hz, "event_id": ep["id"], "episode": "required",
                               "true_start_s": ep["start_s"], "true_end_s": ep["end_s"], "incident_id": None, "identity": "missed"})
            cats = [("true_positive", [m["prediction"] for m in r["matches"]]), ("optional", [m["prediction"] for m in r["optional_matches"]]),
                    ("false_alarm", r["false_alarm_predictions"]), ("duplicate", r["duplicate_predictions"]),
                    ("context", r["context_false_alarm_predictions"]), ("unscorable", r["unscorable_predictions"])]
            for cat, ps in cats:
                for x in ps:
                    per_ep.append({"clip_id": cid, "split": lab["split"], "hazard": hz, "episode": "alert", "identity": cat,
                                   "incident_id": x["incident_id"], "worker_id": x["worker_id"], "alert_t": x["t"],
                                   "alert_end_t": x["t_end"], "event_id": x.get("end_reason")})
    return rows, per_ep


def agg(rows, split=None, hazard=None):
    sel = [r for r in rows if (split is None or r["split"] == split) and (hazard is None or r["hazard"] == hazard)]
    s = {k: sum(r[k] for r in sel) for k in ("alerts", "episodes", "true_positives", "missed", "false_alarms", "duplicates",
                                            "context_false_alarms", "unscorable", "late_detections", "optional_detected",
                                            "optional_episodes")}
    hrs = sum(r["monitorable_s"] for r in sel) / 3600
    tp, fa, n, dup, ctx = s["true_positives"], s["false_alarms"], s["episodes"], s["duplicates"], s["context_false_alarms"]
    lo, hi = poisson_interval(fa)
    ident = Counter()
    for r in sel:
        ident.update({k: v for k, v in (r["identity"] or {}).items() if k.startswith("matched") or k.startswith("excluded")})
    return {**s, "monitorable_hours": round(hrs, 4), "precision": round(tp / (tp + fa), 3) if tp + fa else None,
            "precision_wilson95": wilson(tp, tp + fa), "recall": round(tp / n, 3) if n else None, "recall_wilson95": wilson(tp, n),
            "alert_precision": round(tp / (tp + fa + dup + ctx), 3) if tp + fa + dup + ctx else None,
            "duplicate_rate": round(dup / (tp + dup), 3) if tp + dup else None,
            "false_alarms_per_monitorable_hour": round(fa / hrs, 2) if hrs else None,
            "false_alarms_per_hour_poisson95": (round(lo / hrs, 2), round(hi / hrs, 2)) if hrs else None,
            "identity": dict(ident), "sufficient": n >= 10}


def main():
    v1 = VAL / "annotations" / "m2-provisional-v1"
    v12 = VAL / "annotations" / "m2-provisional-v1.2"
    locks = {s.name: verify_lock(s)["combined_sha256"] for s in (v1, v12)}
    labels = load_set(v12)  # v1 plus anchors: identical episodes, so the time-only matcher gives v1's result
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"WARNING": "DIAGNOSTIC ONLY: provisional AI labels; not a validated measurement; no improvement is claimed",
              "labels": locks, "variants": {k: {"logic": v[0], "ppe_policy": "camera-wide provisional (M2 assumption)" if v[1]
                                                else ("none (default)" if v[0] == "current" else "n/a (M2 logic)"),
                                                "matcher": "identity-aware" if v[2] else "time only"} for k, v in VARIANTS.items()},
              "metrics": {}, "incidents": {}, "lifecycle": {}}
    all_eps, inc_rows = [], []
    cache = {}
    for name, (logic, pol, identity) in VARIANTS.items():
        preds, lifecycle = {}, Counter()
        for cid in labels:
            key = (logic, json.dumps(pol))
            if (key, cid) not in cache:
                inc, extras = replay(cid, logic, ppe_policy=pol)
                cache[key, cid] = (inc, extras, predictions(inc, load_trace(cid), extras))
            inc, extras, preds[cid] = cache[key, cid]
            for e in inc:
                lifecycle[(e["type"], e.get("classification"), e.get("end_reason"))] += 1
                if name in ("A", "C"):
                    inc_rows.append({"variant": name, "clip_id": cid, "incident_id": e["incident_id"], "type": e["type"],
                                     "worker_id": e["worker_id"], "t": e["t"], "t_end": e["t_end"],
                                     "duration_s": round(e["t_end"] - e["t"], 2), "classification": e.get("classification"),
                                     "end_reason": e.get("end_reason"), "observed_s": e.get("observed_s"),
                                     "unobserved_s": e.get("unobserved_s"), "exposure_s": e.get("exposure_s"),
                                     "tracks": e.get("tracks")})
            if logic == "current":
                lifecycle[("notifications",)] += len(extras["notifications"])
                lifecycle[("groups",)] += len(extras["groups"])
                for cat, s in extras["ppe"].items():
                    lifecycle[("ppe_worker_seconds", cat)] += s
        rows, per_ep = score(labels, preds, identity)
        for r in per_ep:
            all_eps.append({"variant": name, **r})
        result["metrics"][name] = {f"{hz} / {sp}": agg(rows, None if sp == "all" else sp, hz)
                                   for hz in ("PPE.HEAD.MISSING", "ZONE.ENTRY") for sp in ("all", "held-out", "development")
                                   if any(r["hazard"] == hz and (sp == "all" or r["split"] == sp) for r in rows)}
        durs = [abs(r["duration_error_s"]) for r in per_ep if r.get("duration_error_s") is not None and r["episode"] == "required"]
        lats = [r["latency_s"] for r in per_ep if r.get("latency_s") is not None and r["episode"] == "required"]
        result["metrics"][name]["timing"] = {"matched_required": len(lats), "latency_median_s": statistics.median(lats) if lats else None,
                                             "duration_abs_error_median_s": statistics.median(durs) if durs else None,
                                             "duration_abs_error_max_s": max(durs) if durs else None}
        result["lifecycle"][name] = {" / ".join(str(x) for x in k): round(v, 1) for k, v in sorted(lifecycle.items(), key=str)}
    (OUT / "comparison.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    for path, rows in ((OUT / "per_episode.csv", all_eps), (OUT / "incidents.csv", inc_rows)):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, keys)
            w.writeheader()
            w.writerows(rows)
    for name in VARIANTS:
        m = result["metrics"][name]
        p = m["PPE.HEAD.MISSING / held-out"]
        print(f"{name}: PPE held-out TP {p['true_positives']}/{p['episodes']} FP {p['false_alarms']} dup {p['duplicates']} "
              f"ctx {p['context_false_alarms']} uns {p['unscorable']} alerts {p['alerts']} alert-precision {p['alert_precision']} "
              f"identity {p['identity']} | timing {m['timing']}")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
