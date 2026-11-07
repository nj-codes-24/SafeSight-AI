"""Local annotation and review app for SafeSight evaluation labels (docs/product_research/17_ANNOTATION_PROTOCOL.md).

    .venv\\Scripts\\python.exe -m streamlit run scripts/validation/annotator.py
    .venv\\Scripts\\python.exe -m streamlit run scripts/validation/annotator.py -- --package reports/validation/human_review/reviewer_A

Step through a clip frame by frame, mark start and end, record events and intervals with observability and
uncertainty, record where the worker is (an identity anchor), zoom to native pixels, and save versioned
safesight.labels/1.1 JSON. Runs on this machine only. Blind by design: it never reads incidents, databases or
evaluation results.

Reviewer mode (--package): only that package's clips and label folder are reachable, in the package's own order; the
development/held-out split is not shown; the reviewer cannot change a file's status (verification happens only after
adjudication, in scripts/validation/human_review.py); a clip is finished with "Clip complete".
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.annotations import EVENT_KINDS, INTERVAL_STATES, OBSERVABILITY, SCHEMA_1_1, validate  # noqa: E402
from intelligence.taxonomy import BUILT, HAZARDS  # noqa: E402

VAL = ROOT / "reports" / "validation"
SCORED = [c for c, h in HAZARDS.items() if h.status == BUILT and c in ("PPE.HEAD.MISSING", "ZONE.ENTRY")]

st.set_page_config(page_title="SafeSight annotator", layout="wide")
ap = argparse.ArgumentParser()
ap.add_argument("--package")
args = ap.parse_known_args(sys.argv[1:])[0]
PACKAGE = (ROOT / args.package) if args.package and not Path(args.package).is_absolute() else (Path(args.package) if args.package else None)


def shown(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:  # a package copied outside the repository
        return str(p)


@st.cache_data
def manifest():
    with open(VAL / "clip_manifest.csv", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["evaluated"] == "yes"]


def package_clips(pkg):
    meta = json.loads((pkg / "package.json").read_text(encoding="utf-8"))
    labs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (pkg / "labels").glob("*.json")}
    return meta, [{"clip_id": c, "file": labs[c]["file"], "sha256": labs[c]["sha256"], "fps": labs[c]["fps"],
                   "frames_decoded": labs[c]["frames"], "duration_s": labs[c]["duration_s"]} for c in meta["order"]]


@st.cache_data
def frame(path, idx):
    cap = cv2.VideoCapture(str(ROOT / path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def new_labels(r, label_set, who):
    return {"schema": SCHEMA_1_1, "label_set": label_set, "clip_id": r["clip_id"], "file": r["file"], "sha256": r["sha256"],
            "fps": float(r["fps"]), "frames": int(r["frames_decoded"]), "duration_s": float(r["duration_s"]), "split": r["split"],
            "source_group": r["source_group"], "status": "provisional",
            "annotators": [{"id": who, "kind": "human", "role": "first-pass", "date": date.today().isoformat(),
                            "blind_to_model_output": "yes", "notes": ""}],
            "scope": {h: "evaluated" for h in SCORED}, "zones": [], "intervals": [], "events": [], "people": {}, "attributes": {}}


with st.sidebar:
    if PACKAGE:
        meta, clips = package_clips(PACKAGE)
        st.header(f"Review package · {meta['package']}")
        who = st.text_input("Your reviewer id", meta.get("reviewer_id") or "",
                            help="Initials or a pseudonym; never a worker's name. Kept for the whole package.")
        if who and who != meta.get("reviewer_id"):
            meta["reviewer_id"] = who
            (PACKAGE / "package.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        label_set, folder = meta["label_set"], PACKAGE / "labels"
        clip = st.selectbox("Clip", clips, format_func=lambda r: f"{r['clip_id']} · {r['duration_s']} s")
    else:
        clips = manifest()
        st.header("Label set")
        label_set = st.text_input("Label set", "m2-human-v1", help="Folder under reports/validation/annotations/")
        who = st.text_input("Your annotator id", "annotator-1", help="Initials or a pseudonym; never a worker's name")
        clip = st.selectbox("Clip", clips, format_func=lambda r: f"{r['clip_id']} · {r['split']} · {r['duration_s']} s")
        folder = VAL / "annotations" / label_set
    path = folder / f"{clip['clip_id']}.json"
    key = f"lab_{label_set}_{clip['clip_id']}"
    if key not in st.session_state:
        st.session_state[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_labels(clip, label_set, who)
    lab = st.session_state[key]
    st.caption(f"{'Editing ' + shown(path) if path.exists() else 'New file'} · status {lab['status']}")
    st.warning("Do not look at model output, alerts or other people's labels while labelling (protocol §1).")

fps, n = float(clip["fps"]), int(clip["frames_decoded"])
zones = json.loads((ROOT / "models" / "runtime_config.json").read_text()).get("zones", {}).get(clip["clip_id"], [])
left, right = st.columns([3, 2])
with left:
    idx = st.slider("Frame", 0, n - 1, st.session_state.get("idx", 0), key="idx")
    b = st.columns(6)
    for col, (label, d) in zip(b, (("-1 s", -round(fps)), ("-1 f", -1), ("+1 f", 1), ("+1 s", round(fps)))):
        if col.button(label):
            st.session_state.idx = int(np.clip(idx + d, 0, n - 1))
            st.rerun()
    if b[4].button("Mark start"):
        st.session_state.mark_start = idx / fps
    if b[5].button("Mark end"):
        st.session_state.mark_end = idx / fps
    px, py = st.columns(2)
    ax = px.slider("Worker position x (fraction of width)", 0.0, 1.0, 0.5, 0.01, key="ax")
    ay = py.slider("Worker position y (fraction of height)", 0.0, 1.0, 0.5, 0.01, key="ay")
    f = frame(clip["file"], idx)
    if f is not None:
        f = f.copy()
        h, w = f.shape[:2]
        for z in zones:
            cv2.polylines(f, [(np.array(z["polygon"]) * [w, h]).astype(np.int32)], True, (0, 200, 255), 2, cv2.LINE_AA)
        c = (int(ax * w), int(ay * h))
        cv2.drawMarker(f, c, (255, 0, 255), cv2.MARKER_CROSS, max(20, w // 40), 2)
        st.image(f, channels="BGR", caption=f"{idx / fps:.2f} s · frame {idx}", width="stretch")
        if st.checkbox("Zoom to native pixels around the marker"):
            x0, y0 = max(0, min(w - 480, c[0] - 240)), max(0, min(h - 270, c[1] - 135))
            st.image(frame(clip["file"], idx)[y0:y0 + 270, x0:x0 + 480], channels="BGR",
                     caption="native resolution, no scaling", width=480)
    s0, s1 = st.session_state.get("mark_start"), st.session_state.get("mark_end")
    st.write(f"Marked: start {s0 if s0 is None else round(s0, 2)} s · end {s1 if s1 is None else round(s1, 2)} s")

with right:
    tabs = st.tabs(["Event", "Interval", "Save"] if PACKAGE else ["Event", "Interval", "Review", "Save"])
    tab_e, tab_i, tab_s = tabs[0], tabs[1], tabs[-1]
    with tab_e:
        hz = st.selectbox("Hazard", [h for h in SCORED if lab.get("scope", {}).get(h, "evaluated") == "evaluated"])
        kind = st.selectbox("Kind", sorted(EVENT_KINDS))
        zone = st.selectbox("Zone", [None] + [z["name"] for z in zones]) if hz == "ZONE.ENTRY" else None
        worker = st.text_input("Worker (appearance and position only)")
        obs = st.selectbox("Observability", sorted(OBSERVABILITY))
        req = st.selectbox("Requirement (PPE)", ["evident", "assumed", None]) if hz.startswith("PPE.") else None
        confidence = st.selectbox("Your confidence in this event", ["high", "medium", "low"],
                                  help="How sure you are of this event as labelled (protocol §12 A6). Low is a valid answer.")
        u0 = st.number_input("Start uncertainty (s)", 0.0, 30.0, 0.2, 0.1)
        u1 = st.number_input("End uncertainty (s)", 0.0, 30.0, 0.2, 0.1)
        anchor = st.checkbox("Record the marker as this worker's position now (identity anchor)", value=True)
        note = st.text_input("Note")
        if st.button("Add event", type="primary", disabled=s0 is None or s1 is None):
            nid = f"{clip['clip_id']}-E{len(lab['events']) + 1:02d}"
            lab["events"].append({"id": nid, "hazard": hz, "kind": kind, "start_s": round(min(s0, s1), 3),
                                  "end_s": round(max(s0, s1), 3), "start_unc_s": u0, "end_unc_s": u1, "zone": zone, "worker": worker,
                                  "observability": obs, "requirement": req, "confidence": confidence,
                                  "evidence_frames": [idx], "status": "provisional",
                                  "annotator": who, "reviews": [], "note": note,
                                  "anchors": [{"t": round(idx / fps, 3), "x": round(ax, 3), "y": round(ay, 3)}] if anchor else []})
            st.success(f"Added {nid}")
        if lab["events"] and st.button("Add the marker as another anchor to the last event"):
            lab["events"][-1].setdefault("anchors", []).append({"t": round(idx / fps, 3), "x": round(ax, 3), "y": round(ay, 3)})
            st.success(f"Anchor added to {lab['events'][-1]['id']}")
    with tab_i:
        ih = st.selectbox("Hazard ", [h for h in SCORED if lab.get("scope", {}).get(h, "evaluated") == "evaluated"])
        state = st.selectbox("State", sorted(INTERVAL_STATES))
        inote = st.text_input("Interval note")
        if st.button("Add interval", type="primary", disabled=s0 is None or s1 is None):
            lab["intervals"].append({"hazard": ih, "start_s": round(min(s0, s1), 3), "end_s": round(max(s0, s1), 3),
                                     "state": state, "note": inote})
    if not PACKAGE:
        with tabs[2]:
            if lab["events"]:
                ev = st.selectbox("Event", lab["events"], format_func=lambda e: f"{e['id']} {e['hazard']} {e['kind']} {e['start_s']}–{e['end_s']} s")
                decision = st.radio("Decision", ["agree", "correct", "reject", "uncertain"], horizontal=True)
                comment = st.text_input("Reason / correction")
                if st.button("Record review"):
                    ev["reviews"].append({"reviewer": who, "date": date.today().isoformat(), "decision": decision, "comment": comment})
                    st.success("Recorded")
            status = st.selectbox("File status", ["provisional", "reviewed", "adjudicated", "verified"],
                                  index=["provisional", "reviewed", "adjudicated", "verified"].index(lab["status"]))
            lab["status"] = status
    with tab_s:
        if PACKAGE:
            lab["review_complete"] = st.checkbox("Clip complete (every interval and event recorded)", lab.get("review_complete", False))
            lab["reviewer_notes"] = st.text_area("Notes for the adjudicator (judgement calls, protocol questions)",
                                                 lab.get("reviewer_notes", ""))
        st.subheader("Events")
        ev_df = st.data_editor(pd.DataFrame(lab["events"]).drop(columns=["reviews", "anchors"], errors="ignore"),
                               num_rows="dynamic", key=f"ev_{key}", width="stretch")
        st.subheader("Intervals")
        iv_df = st.data_editor(pd.DataFrame(lab["intervals"]), num_rows="dynamic", key=f"iv_{key}", width="stretch")
        if st.button("Validate and save", type="primary", disabled=PACKAGE is not None and not who):
            reviews = {e["id"]: e.get("reviews", []) for e in lab["events"]}
            anchors = {e["id"]: e.get("anchors", []) for e in lab["events"]}
            events = [{**{k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()},
                       "reviews": reviews.get(r.get("id"), []), "anchors": anchors.get(r.get("id"), [])}
                      for r in ev_df.to_dict("records")]
            out = {**lab, "schema": SCHEMA_1_1, "events": events, "intervals": iv_df.to_dict("records")}
            if PACKAGE and who not in {x["id"] for x in out["annotators"]}:
                out["annotators"] = out["annotators"] + [{"id": who, "kind": "human", "role": meta.get("role", "independent-reviewer"),
                                                          "date": date.today().isoformat(), "blind_to_model_output": "yes"}]
            try:
                validate(out)
            except (ValueError, KeyError, TypeError) as e:
                st.error(f"Not saved: {e}")
            else:
                folder.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(out, indent=1), encoding="utf-8")
                st.session_state[key] = out
                st.success(f"Saved {shown(path)}")
