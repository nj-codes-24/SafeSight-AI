"""Player settings menu (gear icon). Same settings and persistence as before: models/runtime_config.json via
inference.config, applied from the next monitoring run."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from app import theme
from inference.config import load_config, save_config
from inference.zone_monitor import validate_polygon

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "data" / "demo"
WEIGHTS = ROOT / "models" / "best.pt"
VALIDATED_NO_HELMET = 0.60  # application threshold from the final evaluation (reports/final_report.md)


@st.cache_data(show_spinner=False)
def model_record(mtime):
    rec = {}
    path = ROOT / "models" / "model_config.yaml"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" in line and not line.startswith((" ", "#")):
                k, v = line.split(":", 1)
                rec[k.strip()] = v.strip()
    rec["actual_sha256"] = hashlib.sha256(WEIGHTS.read_bytes()).hexdigest().upper() if WEIGHTS.exists() else ""
    return rec


def camera_views():
    views = []
    if (DEMO / "demo_clips.json").exists():
        views = [c["file"] for c in json.loads((DEMO / "demo_clips.json").read_text(encoding="utf-8"))]
    if (DEMO / "uploads").exists():
        views += [f"uploads/{p.name}" for p in (DEMO / "uploads").iterdir() if p.is_file()]
    return views


def render(prefix, current=None, disabled=False):
    """prefix keeps widget keys unique between the header menu and the player menu; current is the open Source."""
    cfg = load_config()
    st.markdown('<div style="font-size:1rem;font-weight:600;color:var(--ink)">Settings</div>', unsafe_allow_html=True)
    if disabled:
        st.caption("Monitoring is running. Stop it to change settings. Saved changes apply from the next run.")
    else:
        st.caption("Saved changes apply from the next monitoring run.")
    det, alerts, zones, model = st.tabs(["Detection", "Safety alerts", "Restricted zones", "Model"])

    with det:
        person = st.slider("Worker confidence", 0.10, 0.90, float(cfg["person_conf"]), 0.05, key=f"{prefix}_person", disabled=disabled,
                           help="Person boxes below this are ignored by the tracker.")
        ppe = st.slider("Helmet confidence", 0.10, 0.90, float(cfg["ppe_conf"]), 0.05, key=f"{prefix}_ppe", disabled=disabled,
                        help="Helmet detections below this are not used as head evidence.")
        no_helmet = st.slider("No-helmet confidence", 0.10, 0.90, float(cfg["no_helmet_conf"]), 0.05, key=f"{prefix}_nh", disabled=disabled,
                              help=f"Application threshold {VALIDATED_NO_HELMET:.2f}, chosen on validation data.")
        if abs(no_helmet - VALIDATED_NO_HELMET) > 1e-9:
            st.warning(f"Differs from the validated application threshold of {VALIDATED_NO_HELMET:.2f}.")
    with alerts:
        confirm = st.number_input("Alert confirmation (s)", 0.1, 10.0, float(cfg["confirm_seconds"]), 0.1, key=f"{prefix}_confirm",
                                  disabled=disabled, help="A worker's state must hold this long before it is decided.")
        cool = st.number_input("Duplicate-alert cooldown (s)", 0.0, 3600.0, float(cfg["cooldown_seconds"]), 5.0, key=f"{prefix}_cool",
                               disabled=disabled, help="The same worker and incident type will not alert again within this time.")
        st.markdown(f'<div class="ss-note">A worker becomes COMPLIANT or VIOLATION only after head evidence agrees for the '
                    f'confirmation time. Without head evidence the worker stays UNCERTAIN and no alert is raised. A track lost for '
                    f'{cfg["lost_track_seconds"]:.1f} s is forgotten; a new ID alerting at the same place inside the cooldown is '
                    f'treated as the same worker.</div>', unsafe_allow_html=True)
    changed = (person, ppe, no_helmet, confirm, cool) != (cfg["person_conf"], cfg["ppe_conf"], cfg["no_helmet_conf"],
                                                          cfg["confirm_seconds"], cfg["cooldown_seconds"])
    for tab, k in ((det, "a"), (alerts, "b")):
        with tab:
            if st.button("Save rules", type="primary", icon=":material/save:", width="stretch", key=f"{prefix}_save_{k}",
                         disabled=disabled or not changed):
                cfg.update(person_conf=person, ppe_conf=ppe, no_helmet_conf=no_helmet, confirm_seconds=confirm, cooldown_seconds=cool)
                save_config(cfg)
                st.toast("Rules saved. They apply from the next run.", icon=":material/check:")
                st.rerun()

    with zones:
        views = camera_views()
        if not views:
            theme.empty("Zones are set per camera view. Add a clip first.")
        else:
            default = 0
            if current is not None and current.path is not None:
                rel = current.path.name if current.kind == "demo" else f"uploads/{current.path.name}"
                default = views.index(rel) if rel in views else 0
            clip = st.selectbox("Camera view", views, index=default, key=f"{prefix}_view", disabled=disabled)
            cam = Path(clip).stem
            zl = cfg.get("zones", {}).get(cam, [])
            pick = st.selectbox("Zone", [z["name"] for z in zl] + ["New zone"], key=f"{prefix}_zone_{cam}", disabled=disabled)
            zone = next((z for z in zl if z["name"] == pick), None)
            name = st.text_input("Zone name", value=zone["name"] if zone else "Hazard zone", key=f"{prefix}_zname_{cam}_{pick}", disabled=disabled)
            pts = zone["polygon"] if zone else [[0.3, 0.5], [0.7, 0.5], [0.7, 0.95], [0.3, 0.95]]
            table = st.data_editor(pd.DataFrame(pts, columns=["x", "y"]), num_rows="dynamic", hide_index=True, width="stretch",
                                   key=f"{prefix}_pts_{cam}_{pick}", disabled=disabled)
            st.caption("Corners as fractions of frame width (x) and height (y), in drawing order. A worker's foot point inside raises an alert.")
            try:
                polygon, valid = validate_polygon(table.dropna().values.tolist()), True
            except (ValueError, TypeError) as e:
                st.error(f"Invalid zone: {e}")
                valid = False
            cap = cv2.VideoCapture(str(DEMO / clip))
            cap.set(cv2.CAP_PROP_POS_FRAMES, 10)
            ok, frame = cap.read()
            cap.release()
            if ok:
                h, w = frame.shape[:2]
                if valid:
                    p = (np.array(polygon) * [w, h]).astype(np.int32)
                    layer = frame.copy()
                    cv2.fillPoly(layer, [p], (11, 158, 245))
                    cv2.addWeighted(layer, 0.25, frame, 0.75, 0, frame)
                    cv2.polylines(frame, [p], True, (11, 158, 245), 3, cv2.LINE_AA)
                st.image(cv2.resize(frame, (640, int(h * 640 / w))), channels="BGR", width="stretch")
            a, b = st.columns(2)
            if a.button("Save zone", type="primary", icon=":material/check:", width="stretch", key=f"{prefix}_zsave",
                        disabled=disabled or not valid):
                keep = [z for z in zl if z["name"] not in (name, pick)]
                cfg.setdefault("zones", {})[cam] = keep + [{"name": name.strip() or "Zone", "polygon": polygon}]
                save_config(cfg)
                st.toast(f"Zone saved for {cam}.", icon=":material/check:")
                st.rerun()
            if b.button("Delete zone", icon=":material/delete:", width="stretch", key=f"{prefix}_zdel", disabled=disabled or zone is None):
                cfg["zones"][cam] = [z for z in zl if z["name"] != pick]
                save_config(cfg)
                st.toast(f"Zone deleted from {cam}.", icon=":material/delete:")
                st.rerun()

    with model:
        rec = model_record(WEIGHTS.stat().st_mtime if WEIGHTS.exists() else 0)
        sha = rec.get("actual_sha256", "")
        match = bool(sha) and sha == rec.get("sha256", "").upper()
        theme.kv([("Active model", "M5", False),
                  ("Architecture", theme.esc(rec.get("architecture", "YOLO26n").split(",")[0]), False),
                  ("Experiment", theme.esc(rec.get("experiment", "—")), True),
                  ("Weights", "models/best.pt", True),
                  ("SHA-256", f"{sha[:10]}…{sha[-6:]}" if sha else "missing", True),
                  ("Frozen record", theme.badge("Verified", theme.GOOD) if match else theme.badge("Mismatch", theme.BAD), False),
                  ("Application threshold", f"no-helmet {cfg['no_helmet_conf']:.2f}", True),
                  ("Tracker", "ByteTrack · person boxes only", False),
                  ("Classes", "person · helmet · no_helmet", False),
                  ("Licence", "Non-commercial (SH17 data)", False)])
