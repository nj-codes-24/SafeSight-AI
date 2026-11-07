"""Independent human review of the evaluation labels: blinded packages, progress, completion checks, exports, agreement,
adjudication, verified lock (milestones M2.1 and M3).

    python scripts/validation/human_review.py prepare        two empty, blinded packages: reviewer_1, reviewer_2
    python scripts/validation/human_review.py status         progress.csv per package and review_progress.csv
    python scripts/validation/human_review.py check          completion_check.json per package (completeness, blinding)
    python scripts/validation/human_review.py export         exports/events.csv and exports/intervals.csv per package
    python scripts/validation/human_review.py agreement      agreement/agreement.json, disagreement_report.md, adjudication_worksheet.csv
    python scripts/validation/human_review.py adjudicate     a merged starting point for the third reviewer
    python scripts/validation/human_review.py lock-verified  checks everything, sets status verified, locks m2-verified-v1

Reviewers label in the annotator in reviewer mode, which shows only their own package:
    python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_1

Nothing here labels anything. `lock-verified` refuses unless two different human reviewers completed every clip and
passed the completion checks, a third person adjudicated every disagreement, and no pending item is left. Packages never
contain model output, AI labels, evaluation results or the development/held-out split; `check` verifies that.

The M2.1 packages reviewer_A and reviewer_B (never started) stay on disk unchanged as a record; M3 uses reviewer_1 and
reviewer_2, with per-package instructions, a clip manifest and an annotation-confidence field.
"""
import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.agreement import compare, pair_events, state_disagreements  # noqa: E402
from intelligence.annotations import SCHEMA_1_1, lock, validate  # noqa: E402

BASE = ROOT / "reports" / "validation" / "human_review"
VERIFIED = ROOT / "reports" / "validation" / "annotations" / "m2-verified-v1"
PROTOCOL = ROOT / "docs" / "product_research" / "17_ANNOTATION_PROTOCOL.md"
HAZARDS = ("PPE.HEAD.MISSING", "ZONE.ENTRY")
REVIEWERS = ("1", "2")
SEEDS = {"1": 311, "2": 322}
DECISIONS = {"1", "2", "both", "neither", "edited"}
PACKAGE_FILES = {"package.json", "INSTRUCTIONS.md", "clip_manifest.csv", "progress.csv", "completion_check.json"}
FORBIDDEN_KEYS = {"split", "source_group", "prediction", "predictions", "incident_id", "incidents", "alerts", "model",
                  "model_output", "score", "scores", "risk"}  # never in a blinded package
EFFORT_X_REALTIME = 8  # protocol experience: 6-10 times real time


def _clips():
    zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    with open(ROOT / "reports" / "validation" / "clip_manifest.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["evaluated"] == "yes"]
    return [{"clip_id": r["clip_id"], "file": r["file"], "sha256": r["sha256"], "fps": float(r["fps"]),
             "frames": int(r["frames_decoded"]), "duration_s": float(r["duration_s"]),
             "zones": [z["name"] for z in zones.get(r["clip_id"], [])],
             "scope": {"PPE.HEAD.MISSING": "evaluated", "ZONE.ENTRY": "evaluated" if r["clip_id"] in zones else "not_applicable"}}
            for r in rows]


def skeleton(c, label_set):
    return {"schema": SCHEMA_1_1, "label_set": label_set, "clip_id": c["clip_id"], "file": c["file"], "sha256": c["sha256"],
            "fps": c["fps"], "frames": c["frames"], "duration_s": c["duration_s"], "status": "provisional", "annotators": [],
            "scope": c["scope"], "zones": [], "intervals": [], "events": [], "people": {}, "attributes": {},
            "review_complete": False, "reviewer_notes": ""}


def _dir(base, who):
    return Path(base) / f"reviewer_{who}"


INSTRUCTIONS = """# Instructions for reviewer {who} (package {package_id})

You are one of two independent reviewers. The other reviewer labels the same clips in a different order, from an
empty label set, without seeing your work. A third person resolves disagreements afterwards. Your labels become ground
truth only after that adjudication; until then they are `provisional`.

Allow roughly {hours} hours: {n} clips, {minutes} minutes of video; labelling usually takes 6–10 times real time.
Work alone. Do not discuss clips with the other reviewer until both of you have finished.

## Before you start

1. Read `docs/product_research/17_ANNOTATION_PROTOCOL.md` in full, including §12 (amendments A1–A6). Its SHA-256 is
   `{protocol_sha}` (also in `package.json`). Tell the coordinator if the file you read differs.
2. Pick a reviewer id: initials or a pseudonym. Never use a worker's name. Use the same id for every clip.
3. Open only your own package:
   `python -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_{who}`
4. `clip_manifest.csv` lists your clips in your order, with duration, the hazards to label and the zones drawn.

## Stay blind

Do not open, or ask anyone about, any of these:
- `reports/validation/annotations/` (the AI first pass and its versions)
- every other folder in `reports/validation/` except your own package: `eval_runs/`, `representative_failures/`,
  `m2_1_diagnostics/`, `m2_1_runtime_check/`, `m3_baseline/`, `sensitivity_v1.1/`, `traces/`, `review/`, the other
  reviewer's package
- any `*_analysis.csv`, `baseline_metrics.json`, `error_causes.json`, `validation_summary.md`
- `docs/product_research/18_…`, `19_…` and `21_…`
- the SafeSight dashboard, and any SafeSight runtime output

The tool never shows model output. If you see a box, label or alert from SafeSight anywhere while labelling, stop and
tell the coordinator. The safest setup is a separate copy of the repository that holds only `data/demo/`,
`scripts/validation/annotator.py`, `intelligence/`, `models/runtime_config.json` (zone outlines) and your package.

## For each clip, in your package's order

1. Watch the whole clip once without labelling.
2. Cover the **whole** clip with intervals for head protection (`PPE.HEAD.MISSING`) and, where the manifest lists
   zones, for `ZONE.ENTRY`. States: monitorable, uncertain, unobservable, unusable, not_applicable (protocol §4).
   Unlabelled time counts as unobservable, so leave no gaps by accident. Camera cuts, fades and title cards are
   `unusable`.
3. Record every event (protocol §5–8), each with its **hazard** and, for zone events, the **zone**:
   - a violation, from the first to the last frame it is true and visible;
   - an uncertain stretch (you cannot tell);
   - a not-applicable person (for example a passer-by on a public street).
4. For each event give: the worker (appearance and position only), the observability (judge at native resolution:
   tick "Zoom to native pixels"), the requirement basis for PPE (evident or assumed), the start and end uncertainty in
   seconds, and **your confidence** (high, medium, low). Low confidence is a valid, useful answer.
5. Put the purple marker on the worker and keep "Record the marker as this worker's position" ticked. Where several
   people could be confused, add more anchors as the worker moves.
6. A rigid hard hat is compliant. A soft cap, beanie, hood, balaclava or bare head is not. A hat in the hand is not
   worn. If you cannot tell rigid from soft, label `uncertain`, not violation (§7). Zoom before deciding.
7. The zones in these clips were drawn for a demonstration (`real_restriction: false`). Label geometric entry of the
   feet into the drawn polygon; do not decide whether the entry was allowed.
8. Write judgement calls into the event note, and anything the adjudicator should know about the clip into "Notes for
   the adjudicator". Validate and save. When the clip is fully done, tick "Clip complete" and save again.

## When you finish

Tell the coordinator. They run `python scripts/validation/human_review.py check`; your package's
`completion_check.json` must show `ready: true`. Problems are listed per clip; fix them and save again.
"""


def prepare(base=BASE, clips=None):
    clips = clips or _clips()
    proto = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest().upper()
    for who in REVIEWERS:
        d = _dir(base, who)
        existing = [json.loads(p.read_text(encoding="utf-8")) for p in (d / "labels").glob("*.json")] if d.exists() else []
        if any(x["events"] or x["intervals"] or x.get("annotators") for x in existing):
            raise SystemExit(f"{d} already holds a reviewer's work; refusing to overwrite it")
    for who in REVIEWERS:
        d = _dir(base, who)
        (d / "labels").mkdir(parents=True, exist_ok=True)
        order = [c["clip_id"] for c in clips]
        random.Random(SEEDS[who]).shuffle(order)
        label_set = f"m2-human-r{who}"
        ident = hashlib.sha256(json.dumps([label_set, order, proto, [c["sha256"] for c in clips]]).encode()).hexdigest()[:8].upper()
        package_id = f"SSV-M3-R{who}-{ident}"
        (d / "package.json").write_text(json.dumps({
            "package": f"reviewer_{who}", "package_id": package_id, "label_set": label_set, "reviewer_id": None,
            "role": "independent-reviewer", "created": date.today().isoformat(),
            "protocol": "docs/product_research/17_ANNOTATION_PROTOCOL.md", "protocol_sha256": proto, "schema": SCHEMA_1_1,
            "order": order, "clips": [{k: c[k] for k in ("clip_id", "file", "sha256", "duration_s")} for c in clips],
            "blinding": "Contains no model output, no AI labels, no evaluation results and no development/held-out split. "
                        "Label from the footage only, at native resolution where needed, following the protocol."},
            indent=1), encoding="utf-8")
        by_id = {c["clip_id"]: c for c in clips}
        with open(d / "clip_manifest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["order", "clip_id", "file", "sha256", "duration_s", "fps", "frames", "hazards_to_label", "zones_drawn",
                        "estimated_minutes"])
            for i, cid in enumerate(order, 1):
                c = by_id[cid]
                w.writerow([i, cid, c["file"], c["sha256"], c["duration_s"], c["fps"], c["frames"],
                            ";".join(h for h, s in c["scope"].items() if s == "evaluated"), ";".join(c.get("zones", [])),
                            round(c["duration_s"] * EFFORT_X_REALTIME / 60)])
        total = sum(c["duration_s"] for c in clips)
        (d / "INSTRUCTIONS.md").write_text(INSTRUCTIONS.format(
            who=who, package_id=package_id, n=len(clips), minutes=round(total / 60), protocol_sha=proto,
            hours=f"{total * 6 / 3600:.1f}–{total * 10 / 3600:.1f}"), encoding="utf-8")
        for c in clips:
            (d / "labels" / f"{c['clip_id']}.json").write_text(json.dumps(skeleton(c, label_set), indent=1), encoding="utf-8")
    status(base)
    print(f"prepared {base}")


def _load(folder):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.json"))}


def _labels(base, who):
    return _load(_dir(base, who) / "labels")


def _coverage(lab, hazard):
    """Share of the clip covered by intervals of this hazard (overlaps are a validation error, so a sum suffices)."""
    cov = sum(iv["end_s"] - iv["start_s"] for iv in lab.get("intervals", []) if iv["hazard"] == hazard)
    return round(cov / lab["duration_s"], 3) if lab.get("duration_s") else 0


def status(base=BASE):
    labs = {w: _labels(base, w) for w in REVIEWERS}
    rows = []
    for cid in sorted(set().union(*labs.values())):
        row = {"clip_id": cid}
        for w in REVIEWERS:
            lab = labs[w].get(cid, {})
            row.update({f"r{w}_status": "done" if lab.get("review_complete") else ("in progress" if lab.get("events") or
                                                                                   lab.get("intervals") else "not started"),
                        f"r{w}_reviewer": ",".join(x["id"] for x in lab.get("annotators", [])),
                        f"r{w}_events": len(lab.get("events", [])),
                        f"r{w}_ppe_coverage": _coverage(lab, "PPE.HEAD.MISSING") if lab else 0})
        rows.append(row)
    if not rows:
        return rows
    for w in REVIEWERS:
        keep = ["clip_id"] + [k for k in rows[0] if k.startswith(f"r{w}_")]
        _write(_dir(base, w) / "progress.csv", [{k: r[k] for k in keep} for r in rows])
    _write(Path(base) / "review_progress.csv", rows)
    done = {w: sum(r[f"r{w}_status"] == "done" for r in rows) for w in REVIEWERS}
    print(", ".join(f"reviewer {w} {done[w]}/{len(rows)} clips done" for w in REVIEWERS))
    return rows


def _write(path, rows, fields=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields or (list(rows[0]) if rows else ["empty"]))
        w.writeheader()
        w.writerows(rows)


def _forbidden(obj, path=""):
    if isinstance(obj, dict):
        return [f"{path}/{k}" for k in obj if k in FORBIDDEN_KEYS] + [x for k, v in obj.items() for x in _forbidden(v, f"{path}/{k}")]
    if isinstance(obj, list):
        return [x for i, v in enumerate(obj) for x in _forbidden(v, f"{path}[{i}]")]
    return []


def check(base=BASE, who=None) -> dict:
    """Completion and blinding checks per package. Blocking problems make `ready` false; warnings do not."""
    out = {}
    for w in ([who] if who else REVIEWERS):
        d = _dir(base, w)
        meta = json.loads((d / "package.json").read_text(encoding="utf-8"))
        labs = _labels(base, w)
        problems, warnings, per_clip = [], [], {}
        stray = [str(p.relative_to(d)).replace("\\", "/") for p in d.rglob("*") if p.is_file()
                 and not (p.name in PACKAGE_FILES and p.parent == d) and not (p.parent == d / "labels" and p.suffix == ".json")
                 and not (p.parent == d / "exports" and p.suffix == ".csv")]
        if stray:
            problems.append(f"blinding: unexpected files in the package: {stray}")
        if set(labs) != {c["clip_id"] for c in meta["clips"]}:
            problems.append("the labels folder does not hold exactly the package's clips")
        ids = set()
        for cid, lab in labs.items():
            p, warn = [], []
            try:
                validate(lab)
            except (ValueError, KeyError, TypeError) as e:
                p.append(f"invalid: {e}")
            bad = _forbidden(lab)
            if bad:
                p.append(f"blinding: forbidden fields {bad}")
            if not lab.get("review_complete"):
                p.append("not marked complete")
            ann = lab.get("annotators") or []
            if not ann or any(a.get("kind") != "human" or not a.get("id") for a in ann):
                p.append("needs a named human annotator")
            ids |= {a.get("id") for a in ann}
            for h, s in lab.get("scope", {}).items():
                if s == "evaluated" and _coverage(lab, h) < 0.99:
                    p.append(f"{h} intervals cover {_coverage(lab, h):.0%} of the clip (needs the whole clip)")
            for e in lab.get("events", []):
                if e.get("kind") == "violation" and not e.get("confidence"):
                    p.append(f"{e['id']}: violation without the reviewer's confidence")
                if e.get("hazard") == "ZONE.ENTRY" and e.get("kind") == "violation" and not e.get("zone"):
                    p.append(f"{e['id']}: zone event without a zone")
                if not e.get("anchors"):
                    warn.append(f"{e['id']}: no identity anchor")
            per_clip[cid] = {"ok": not p, "problems": p, "warnings": warn}
            problems += [f"{cid}: {x}" for x in p]
            warnings += [f"{cid}: {x}" for x in warn]
        if len(ids - {None}) > 1:
            problems.append(f"more than one reviewer id in one package: {sorted(ids - {None})}")
        res = {"package": meta["package"], "package_id": meta.get("package_id"), "checked": date.today().isoformat(),
               "ready": not problems, "clips_ready": sum(v["ok"] for v in per_clip.values()), "clips": len(per_clip),
               "reviewer_ids": sorted(ids - {None}), "problems": problems, "warnings": warnings, "per_clip": per_clip}
        (d / "completion_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        out[w] = res
        print(f"reviewer_{w}: {'READY' if res['ready'] else 'NOT READY'} ({res['clips_ready']}/{res['clips']} clips), "
              f"{len(problems)} problem(s), {len(warnings)} warning(s)")
    return out


def export(base=BASE):
    """Flat CSV copies of each reviewer's events and intervals (exports/), for reading and archiving."""
    for w in REVIEWERS:
        labs = _labels(base, w)
        ev = [{"clip_id": cid, **{k: e.get(k) for k in ("id", "hazard", "kind", "start_s", "end_s", "start_unc_s", "end_unc_s",
                                                         "zone", "worker", "observability", "requirement", "confidence",
                                                         "note")}, "anchors": json.dumps(e.get("anchors") or [])}
              for cid, lab in labs.items() for e in lab.get("events", [])]
        iv = [{"clip_id": cid, **{k: x.get(k) for k in ("hazard", "start_s", "end_s", "state", "note")}}
              for cid, lab in labs.items() for x in lab.get("intervals", [])]
        out = _dir(base, w) / "exports"
        out.mkdir(exist_ok=True)
        _write(out / "events.csv", ev, ["clip_id", "id", "hazard", "kind", "start_s", "end_s", "start_unc_s", "end_unc_s", "zone",
                                        "worker", "observability", "requirement", "confidence", "note", "anchors"])
        _write(out / "intervals.csv", iv, ["clip_id", "hazard", "start_s", "end_s", "state", "note"])
        print(f"reviewer_{w}: {len(ev)} events, {len(iv)} intervals exported")


def _complete(labs):
    return labs and all(x.get("review_complete") for x in labs.values())


def agreement(base=BASE, require_complete=True):
    a, b = (_labels(base, w) for w in REVIEWERS)
    if require_complete and not (_complete(a) and _complete(b)):
        raise SystemExit("agreement is computed on finished work: both reviewers must mark every clip complete first")
    res = compare(a, b, HAZARDS)
    out = Path(base) / "agreement"
    out.mkdir(parents=True, exist_ok=True)
    (out / "agreement.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    one, two = REVIEWERS
    rows = []
    for cid in res["clips"]:
        for h in HAZARDS:
            if a[cid]["scope"].get(h) != "evaluated":
                continue
            for kind in ("violation", "uncertain", "not_applicable"):
                pairs, oa, ob = pair_events(a[cid], b[cid], h, kind)
                for x in oa:
                    rows.append({"clip_id": cid, "hazard": h, "item": f"{kind} event only in {one}", "a": f"{x['id']} {x['start_s']}-{x['end_s']}", "b": ""})
                for y in ob:
                    rows.append({"clip_id": cid, "hazard": h, "item": f"{kind} event only in {two}", "a": "", "b": f"{y['id']} {y['start_s']}-{y['end_s']}"})
                for x, y in pairs:
                    diffs = []
                    if max(abs(x["start_s"] - y["start_s"]), abs(x["end_s"] - y["end_s"])) > 1.0:
                        diffs.append("boundaries differ by more than 1 s")
                    diffs += [f"{k} differs" for k in ("observability", "requirement", "zone") if x.get(k) != y.get(k)]
                    if diffs:
                        rows.append({"clip_id": cid, "hazard": h, "item": f"{kind} event: " + "; ".join(diffs),
                                     "a": f"{x['id']} {x['start_s']}-{x['end_s']} {x.get('observability')}/{x.get('requirement')}/{x.get('zone')}",
                                     "b": f"{y['id']} {y['start_s']}-{y['end_s']} {y.get('observability')}/{y.get('requirement')}/{y.get('zone')}"})
            for x, y in pair_events(a[cid], b[cid], h, None)[0]:
                if x["kind"] != y["kind"]:
                    rows.append({"clip_id": cid, "hazard": h, "item": f"same stretch, different kind: {x['kind']} vs {y['kind']}",
                                 "a": f"{x['id']} {x['start_s']}-{x['end_s']}", "b": f"{y['id']} {y['start_s']}-{y['end_s']}"})
            for s in state_disagreements(a[cid], b[cid], h):
                rows.append({"clip_id": cid, "hazard": h, "item": f"interval state {s['start_s']}-{s['end_s']} s",
                             "a": s["a"], "b": s["b"]})
        for x, y in pair_events(a[cid], b[cid], None, "violation")[0]:
            if x["hazard"] != y["hazard"]:
                rows.append({"clip_id": cid, "hazard": f"{x['hazard']} vs {y['hazard']}", "item": "same violation, different hazard",
                             "a": f"{x['id']} {x['start_s']}-{x['end_s']}", "b": f"{y['id']} {y['start_s']}-{y['end_s']}"})
        for w, labs in ((one, a), (two, b)):
            if labs[cid].get("reviewer_notes"):
                rows.append({"clip_id": cid, "hazard": "", "item": f"reviewer {w} note (read before deciding)",
                             "a": labs[cid]["reviewer_notes"] if w == one else "", "b": labs[cid]["reviewer_notes"] if w == two else ""})
    for r in rows:
        r.update({"decision": "", "adjudicator": "", "reason": ""})
    _write(out / "adjudication_worksheet.csv", rows, ["clip_id", "hazard", "item", "a", "b", "decision", "adjudicator", "reason"])
    lines = ["# Disagreement report", "", f"Reviewers {one} and {two}. Clips compared: {len(res['clips'])}. "
             f"Items to adjudicate: {len(rows)}.", "", "Flags (measures below target):", ""] + \
        [f"- {f}" for f in res["flags"] or ["none"]] + [""]
    hc = res["hazard_category"]
    lines += [f"Hazard category: {hc['pairs']} cross-hazard violation pairs, {hc['different_hazard']} with different hazards.", ""]
    for h, v in res["hazards"].items():
        ev, iv = v["violation_events"], v["intervals"]
        lines += [f"## {h}", "", f"- Violation events: both {ev['both']}, only {one} {ev['only_a']}, only {two} {ev['only_b']}, "
                  f"positive specific agreement {ev['positive_specific_agreement']} (clip bootstrap 95 % {ev['psa_clip_bootstrap95']})",
                  f"- Boundaries (paired): median |start| {ev['start_abs_diff_median_s']} s, |end| {ev['end_abs_diff_median_s']} s, "
                  f"temporal IoU median {ev['temporal_iou_median']}",
                  f"- Interval states: {iv['samples']} samples every {iv['step_s']} s, agreement {iv['observed_agreement']}, "
                  f"kappa {iv['kappa']} (clip bootstrap 95 % {iv['kappa_clip_bootstrap95']})",
                  f"- Event kind (uncertainty): {v['event_kind']['pairs']} pairs, {v['event_kind']['different_kind']} with a different kind",
                  f"- Zone assignment: {v['zone_assignment']['pairs']} pairs, agreement {v['zone_assignment']['agreement']}",
                  f"- Confidence: {v['confidence']['pairs']} pairs, agreement {v['confidence']['agreement']}, "
                  f"weighted kappa {v['confidence']['weighted_kappa']}", ""] + \
                 [f"  - {s}: specific agreement {x['specific_agreement']} ({x['samples']} samples)" for s, x in iv["per_state"].items()] + \
                 ["", "| Clip | Interval kappa | Violations both / only one / only two | PSA |", "|---|---|---|---|"] + \
                 [f"| {c} | {r['interval_kappa']} | {r['violation_both']} / {r['violation_only_a']} / {r['violation_only_b']} | "
                  f"{r['positive_specific_agreement']} |" for c, r in v["per_clip"].items()] + [""]
    lines += ["Limitations: 0.5 s samples inside a clip are not independent (no kappa standard error is given; the clip "
              "bootstrap is the honest interval and is wide with 15 clips). Kappa depends on prevalence, hence the per-state "
              "values. Event agreement uses positive specific agreement, not kappa, because 'neither reviewer found an event' "
              "is not a countable cell on a timeline."]
    (out / "disagreement_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} items to adjudicate; flags: {res['flags'] or 'none'}")
    return res, rows


def adjudicate(base=BASE):
    """Merged starting point for the adjudicator: agreed events (mean boundaries), single-reviewer events marked
    pending, reviewer 1's intervals; every disagreement is listed in the worksheet."""
    one, two = REVIEWERS
    a, b = (_labels(base, w) for w in REVIEWERS)
    if not (_complete(a) and _complete(b)):
        raise SystemExit("both reviewers must finish before adjudication")
    out = Path(base) / "adjudication" / "labels"
    out.mkdir(parents=True, exist_ok=True)
    for cid in sorted(set(a) & set(b)):
        lab = json.loads(json.dumps(a[cid]))
        lab.update(label_set="m2-adjudicated", status="reviewed", annotators=a[cid]["annotators"] + b[cid]["annotators"], events=[],
                   reviewer_notes={one: a[cid].get("reviewer_notes", ""), two: b[cid].get("reviewer_notes", "")})
        n = 0
        for h in HAZARDS:
            for kind in ("violation", "uncertain", "not_applicable"):
                pairs, oa, ob = pair_events(a[cid], b[cid], h, kind)
                for x, y in pairs:
                    n += 1
                    agreed = all(x.get(k) == y.get(k) for k in ("observability", "requirement", "zone"))
                    lab["events"].append({**x, "id": f"{cid}-E{n:02d}", "start_s": round(statistics.mean([x["start_s"], y["start_s"]]), 3),
                                          "end_s": round(statistics.mean([x["end_s"], y["end_s"]]), 3), "from": [f"{one}:{x['id']}", f"{two}:{y['id']}"],
                                          "confidence": None, "reviewer_confidence": [x.get("confidence"), y.get("confidence")],
                                          "adjudication": "agreed" if agreed else "pending"})
                for who, es in ((one, oa), (two, ob)):
                    for e in es:
                        n += 1
                        lab["events"].append({**e, "id": f"{cid}-E{n:02d}", "from": [f"{who}:{e['id']}"], "confidence": None,
                                              "adjudication": "pending"})
        (out / f"{cid}.json").write_text(json.dumps(lab, indent=1), encoding="utf-8")
    (out.parent / "package.json").write_text(json.dumps({
        "package": "adjudication", "label_set": "m2-adjudicated", "reviewer_id": None, "role": "adjudicator",
        "order": sorted(set(a) & set(b)), "created": date.today().isoformat(),
        "blinding": "Resolve each pending event and each worksheet row from the footage; do not consult model output."},
        indent=1), encoding="utf-8")
    print(f"adjudication workspace: {out}")


def lock_verified(base=BASE, dest=VERIFIED):
    one, two = REVIEWERS
    a, b = (_labels(base, w) for w in REVIEWERS)
    adj = _load(Path(base) / "adjudication" / "labels")
    problems = []
    if not (_complete(a) and _complete(b)):
        problems.append("both reviewers must mark every clip complete")
    checks = check(base)
    for w, c in checks.items():
        blocking = [p for p in c["problems"] if "not marked complete" not in p and "named human" not in p]
        if blocking:
            problems.append(f"reviewer {w} package fails its completion check ({len(blocking)} problem(s); see completion_check.json)")
    ids = {w: {x["id"] for lab in labs.values() for x in lab.get("annotators", [])} for w, labs in ((one, a), (two, b))}
    if not ids[one] or not ids[two] or ids[one] & ids[two]:
        problems.append(f"reviewers {one} and {two} must be different, named humans")
    kinds = {x.get("kind") for labs in (a, b) for lab in labs.values() for x in lab.get("annotators", [])}
    if kinds != {"human"}:
        problems.append(f"every reviewer must be human (found {sorted(map(str, kinds))})")
    ws = Path(base) / "agreement" / "adjudication_worksheet.csv"
    rows = list(csv.DictReader(open(ws, encoding="utf-8"))) if ws.exists() else None
    if rows is None:
        problems.append("run `agreement` first")
    else:
        undecided = [r for r in rows if r["decision"] not in DECISIONS or not r["adjudicator"]]
        if undecided:
            problems.append(f"{len(undecided)} worksheet item(s) without a decision and adjudicator")
        if {r["adjudicator"] for r in rows} & (ids[one] | ids[two]):
            problems.append(f"the adjudicator must be a third person, not reviewer {one} or {two}")
    if not adj or set(adj) != set(a):
        problems.append("the adjudication workspace must hold every clip (run `adjudicate`, then edit it)")
    pending = [e["id"] for lab in adj.values() for e in lab["events"] if e.get("adjudication") == "pending"]
    if pending:
        problems.append(f"{len(pending)} event(s) still pending adjudication")
    if problems:
        raise SystemExit("not verified:\n- " + "\n- ".join(problems))
    adjudicator = sorted({r["adjudicator"] for r in rows})
    if dest.exists():
        raise SystemExit(f"{dest} exists; a verified set is never overwritten (make a new version)")
    dest.mkdir(parents=True)
    for cid, lab in adj.items():
        lab.update(label_set=dest.name, status="verified", annotators=[x for x in lab["annotators"] if x.get("role") != "adjudicator"] + [
            {"id": x, "kind": "human", "role": "adjudicator", "date": date.today().isoformat()} for x in adjudicator])
        validate(lab)
        (dest / f"{cid}.json").write_text(json.dumps(lab, indent=1), encoding="utf-8")
    m = lock(dest, note="two independent human reviewers, adjudicated by a third; see reports/validation/human_review/")
    print(f"verified and locked: {dest} {m['combined_sha256']}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "status", "check", "export", "agreement", "adjudicate", "lock-verified"])
    a = ap.parse_args()
    {"prepare": prepare, "status": status, "check": check, "export": export, "agreement": agreement, "adjudicate": adjudicate,
     "lock-verified": lock_verified}[a.command]()


if __name__ == "__main__":
    main()
