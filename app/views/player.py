"""View B: the monitoring player, with the session, its incidents, session analytics and history below it.

The monitoring loop is the same as before: Pipeline.process on each frame, the UI refreshed about 12 times a second.
Only one run may be active on the server at a time (app/runlock.py).
"""
import time
from datetime import datetime

import cv2
import streamlit as st

from app import runlock, sources, theme
from app.components.shared import get_db, get_detector, model_ready
from app.views import insights, settings
from inference.config import load_config

KIND_LABEL = {"demo": "DEMO CLIP", "upload": "UPLOAD", "webcam": "WEBCAM"}


class Slot:
    """An st.empty() that only reaches the browser when its HTML changes."""

    def __init__(self, **kw):
        self.ph, self.last, self.kw = st.empty(), None, kw

    def markdown(self, body):
        if body != self.last:
            self.ph.markdown(body, unsafe_allow_html=True, **self.kw)
            self.last = body


def go_gallery():
    st.query_params.clear()


def starting():
    """True in the script run triggered by a Start click (button values are known before the widgets are drawn)."""
    return bool(st.session_state.get("bigplay") or st.session_state.get("ctl_play"))


def ptop_html(state, src, cfg):
    tag = {"live": theme.pill("LIVE", live=True), "ready": theme.pill("Ready", color=theme.GOOD),
           "done": theme.pill("Finished"), "busy": theme.pill("Busy", color=theme.WARN)}[state]
    return (f'<div class="ss-ptop" data-state="{state}"><span class="src">{tag}{theme.esc(src.title)}</span>'
            f'<span class="ss-chip">M5 · no-helmet {cfg["no_helmet_conf"]:.2f}</span></div>')


def progress_html(frames, fps, total, rate=None, live=False):
    t = frames / fps if fps else 0
    if total:
        pct = min(100, 100 * frames / total)
        bar = f'<div class="bar{" live" if live else ""}"><i style="width:{pct:.1f}%"></i></div>'
        right = theme.clock(total / fps)
    else:  # webcam: no duration
        bar = f'<div class="bar{" live" if live else ""}"><i style="width:{100 if live else 0}%"></i></div>'
        right = "live" if live else "—"
    r = f'<span class="fps">{rate:.0f} FPS</span>' if isinstance(rate, (int, float)) else ""
    return f'<div class="ss-prog"><span>{theme.clock(t)}</span>{bar}<span>{right}</span>{r}</div>'


def info_html(src, info, cfg, status, last):
    poster = sources.thumb_uri(src, 480) if src.path else None
    poster_html = f'<img src="{poster}" alt="">' if poster else f'<div class="ss-webcam">{theme.CAM_SVG}</div>'
    desc = sources.DESCRIPTIONS.get(src.stem) or (
        "A video you uploaded. It is processed exactly like the demo footage." if src.kind == "upload"
        else "The default camera on this computer (device 0), opened only while monitoring runs.")
    zones = [z["name"] for z in cfg.get("zones", {}).get(src.stem, [])]
    tags = [f'<span class="ss-tag on">{ {"demo": "Demo footage", "upload": "Uploaded video", "webcam": "Webcam"}[src.kind] }</span>']
    if info.get("frames"):
        tags += [f'<span class="ss-tag">{info["width"]}×{info["height"]}</span>', f'<span class="ss-tag">{info["fps"]:.0f} fps</span>',
                 f'<span class="ss-tag">{theme.clock(info["duration"])}</span>']
    tags += [f'<span class="ss-tag zone">Zone · {theme.esc(z)}</span>' for z in zones] or ['<span class="ss-tag">No zones</span>']
    kv = [("Model", "M5 · YOLO26n · ByteTrack"),
          ("Thresholds", f"worker {cfg['person_conf']:.2f} · helmet {cfg['ppe_conf']:.2f} · no-helmet {cfg['no_helmet_conf']:.2f}"),
          ("Status", status)]
    if src.meta.get("artist"):
        kv.append(("Footage", f"{src.meta['artist']} · {src.meta.get('license', '').split('.')[0]}"))
    if last:
        kv.append(("Last run", f"{theme.when(last[0]['started_at'], False)} · {last[1]} incident{'' if last[1] == 1 else 's'}"))
    kvh = "".join(f"<div><b>{k}</b>{theme.esc(v)}</div>" for k, v in kv)
    year = f"<sup>{KIND_LABEL[src.kind]}</sup>"
    return (f'<div class="ss-info"><div class="poster">{poster_html}</div><div><h1>{theme.esc(src.title)}{year}</h1>'
            f'<p class="desc">{theme.esc(desc)}</p></div><div class="side"><div class="tags">{"".join(tags)}</div>'
            f'<div class="kv">{kvh}</div></div></div>')


def render(src, db):
    cfg = load_config()
    info = sources.info(src)
    runs = st.session_state.setdefault("runs", {})
    run = runs.get(src.key)
    holder = runlock.holder()
    no_model = not model_ready()
    busy = bool(holder and not holder["mine"]) or no_model
    go_req = starting()
    open_error = st.session_state.pop("open_error", {}).get(src.key)  # set by a Start whose source would not open
    total = info.get("frames", 0)
    fps_src = info.get("fps") or 25.0

    with st.container(horizontal=True, vertical_alignment="center", key="backrow"):
        st.button("All sources", icon=":material/arrow_back:", type="tertiary", key="back", on_click=go_gallery, disabled=go_req,
                  help="Stop monitoring first" if go_req else None)

    # ------------------------------------------------------------ player
    with st.container(key="player"):
        with st.container(key="ptop"):
            ptop = Slot()
        with st.container(key="screen"):
            view = st.empty()
        bp = st.empty()
        with st.container(key="controls", horizontal=True, vertical_alignment="center", gap="small"):
            ctl = st.empty()
            prog = Slot(width="stretch")
            with st.popover("", icon=":material/settings:", key="gear", help="Settings"):
                settings.render("pl", src, disabled=go_req)
            st.html('<button class="ss-fs" data-ss-fs title="Fullscreen" aria-label="Fullscreen"></button>', width="content")

    big = bp.button("Start monitoring", icon=":material/play_arrow:", key="bigplay", disabled=busy, help="Start monitoring")
    play = ctl.button("", icon=":material/play_arrow:", key="ctl_play", disabled=busy, help="Start monitoring")
    go = big or play

    # ------------------------------------------------------------ information and sections (placeholders first)
    last = sources.last_sessions(db.sessions(), db.rows()).get(src.name) if src.path else None
    status = "Monitoring" if go else ("Model weights missing" if no_model else "Another tab is monitoring" if busy
                                      else ("Finished in this tab" if run else "Ready"))
    st.markdown(info_html(src, info, cfg, status, last), unsafe_allow_html=True)

    session_head = Slot()
    session_metrics = Slot()
    theme.h2("Incidents", "raised in this session · select one to inspect the evidence")
    feed = st.empty()
    theme.h2("Session analytics", "this session only")
    analytics = st.empty()

    # The session shown below the player: the run made in this tab, else the last recorded session of this source.
    row, srows, end, timeline, label = None, [], None, [], ""
    if run:
        row = next((s for s in db.sessions() if s["session_id"] == run["session_id"]), None)
        end, timeline = run["summary"], run["timeline"]
        label = f"Run in this tab · {run['session_id']} · {theme.when(run['ended'], False)}"
    elif last:
        row = last[0]
        label = f"Last recorded session · {row['session_id']} · from history"
    if row:
        srows = db.rows(row["session_id"])

    if not go:
        if busy:
            ptop.markdown(ptop_html("busy", src, cfg))
        else:
            ptop.markdown(ptop_html("done" if run else "ready", src, cfg))
        if run and run.get("frame") is not None:
            view.image(run["frame"], channels="BGR", width="stretch")
            prog.markdown(progress_html(run["frames"], run["fps_src"], run["total"], run["summary"]["fps"]))
        else:
            uri = sources.thumb_uri(src) if src.path else None
            img = f'<img src="{uri}" alt="">' if uri else ""
            msg = ("No model weights at models/best.pt. See models/README.md, then reload this page." if no_model
                   else "Monitoring is running in another browser tab. Stop it there first." if busy
                   else open_error or "Press play to start monitoring. The model processes the video on this computer.")
            view.markdown(f'<div class="ss-poster{"" if uri else " blank"}">{img}<div class="msg">{msg}</div></div>', unsafe_allow_html=True)
            prog.markdown(progress_html(0, fps_src, total))
        if row:
            session_head.markdown(f'<div class="ss-h2"><h2>Session</h2><span>{theme.esc(label)}</span></div>')
            session_metrics.markdown(f'<div class="ss-metrics">{"".join(theme.metric(*m) for m in insights.final_metrics(row, end, len(srows)))}</div>')
            with feed.container():
                if srows:
                    insights.incident_cards(srows, "s")
                else:
                    theme.empty("No incidents were raised in this session.")
            with analytics.container():
                insights.session_analytics(row, srows, timeline)
        else:
            session_head.markdown('<div class="ss-h2"><h2>Session</h2><span>no session yet for this source</span></div>')
            theme.empty("Press play to run the model on this source. Live figures appear here.", "Not run yet", target=session_metrics.ph)
            theme.empty("Incidents raised during the run appear here.", target=feed)
            theme.empty("Charts for the session appear when a run finishes.", target=analytics)
        insights.history(db)
        return

    # ------------------------------------------------------------ monitoring run
    bp.empty()
    ctl.button("", icon=":material/stop:", key="ctl_stop", help="Stop monitoring")
    ptop.markdown(ptop_html("live", src, cfg))
    view.markdown('<div class="ss-poster blank"><div class="msg" style="bottom:46%">Starting · loading the detection model and opening the source</div></div>',
                  unsafe_allow_html=True)
    prog.markdown(progress_html(0, fps_src, total, live=True))
    session_head.markdown('<div class="ss-h2"><h2>Session</h2><span>live · figures for workers in view now</span></div>')
    zero = {"tracked_now": 0, "confirmed_tracks": 0, "track_ids": 0, "compliant": 0, "violation": 0, "uncertain": 0,
            "compliance_rate": None, "incidents": 0, "fps": "—"}
    session_metrics.markdown(f'<div class="ss-metrics">{"".join(theme.metric(*m) for m in insights.live_metrics(zero))}</div>')
    theme.empty("Violations and zone entries appear here as they are confirmed.", target=feed)
    theme.empty("Charts for the session appear when the run finishes.", target=analytics)
    insights.history(db)

    if not runlock.acquire(src.name):
        h = runlock.holder()
        st.toast(f"Monitoring is already running in another tab ({h['source'] if h else 'unknown'}). Stop it there first.", icon=":material/block:")
        time.sleep(1.2)
        st.rerun()

    from inference.tracker import Pipeline  # noqa: E402  (imports torch, so only on Start)

    cap = cv2.VideoCapture(src.capture)
    if not cap.isOpened():
        runlock.release()
        msg = "No webcam is available on this computer." if src.kind == "webcam" else "This file could not be opened."
        # Rerun so the header, navigation and controls leave the Monitoring state; the message is shown on the poster.
        st.session_state["open_error"] = {src.key: msg}
        st.rerun()
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if src.path else 0
    det = get_detector()
    runlock.beat()
    pipe = Pipeline(det, fps, cfg, src.stem, db=get_db())
    alerts, timeline, small = [], [], None
    last_ui = last_bar = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            out = pipe.process(frame)
            new = pipe.incidents.drain_alerts()
            alerts.extend(new)
            now = time.perf_counter()
            if new or now - last_ui > 0.08:  # the browser cannot show more; this keeps inference FPS up
                small = cv2.resize(out, (1280, int(out.shape[0] * 1280 / out.shape[1])))
                view.image(small, channels="BGR", width="stretch")
                runlock.beat()
                s = pipe.summary()
                if now - last_bar > 0.5:
                    prog.markdown(progress_html(pipe.stats.frames, fps, total, s["fps"], live=True))
                    timeline.append((round(pipe.stats.frames / fps, 2), s["compliance_rate"], s["tracked_now"], s["violation"]))
                    last_bar = now
                session_metrics.markdown(f'<div class="ss-metrics">{"".join(theme.metric(*m) for m in insights.live_metrics(s))}</div>')
                if new:
                    feed.markdown('<div class="ss-feed">' + "".join(theme.alert_html(a) for a in alerts[::-1]) + "</div>",
                                  unsafe_allow_html=True)
                last_ui = now
    finally:  # also runs when Stop or a navigation interrupts the run
        cap.release()
        summary = pipe.finish(src.name)
        runlock.release()
        runs[src.key] = {"session_id": pipe.session_id, "summary": summary, "timeline": timeline, "frames": pipe.stats.frames,
                         "fps_src": fps, "total": total, "frame": small, "ended": datetime.now().isoformat(timespec="seconds")}
    st.rerun()
