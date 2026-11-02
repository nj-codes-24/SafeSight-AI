"""View A: the source gallery. Selecting a card opens the player; nothing is processed until Start is pressed there."""
from pathlib import Path

import streamlit as st

from app import runlock, sources, theme

TYPES = ["Demo footage", "Upload video", "Webcam"]


def open_source(key):
    st.query_params["source"] = key


def card(src, i, last=None, uri=None, info=None):
    info = info or {}
    if src.kind == "webcam":
        thumb = f'<div class="ss-webcam">{theme.CAM_SVG}</div>'
        tag, status = "Webcam", '<span class="dot off"></span>Opens device 0 when you press Start'
    else:
        thumb = f'<img src="{uri}" alt="">' if uri else ""
        tag = "Demo clip" if src.kind == "demo" else "Upload"
        status = (f'<span class="dot"></span>Ready · {info.get("width")}×{info.get("height")} · {info.get("fps", 0):.0f} fps'
                  if info.get("frames") else '<span class="dot off"></span>Could not read this file')
    dur = f'<span class="dur">{theme.clock(info["duration"])}</span>' if info.get("duration") else ""
    last_html = ""
    if last:
        s, n = last
        last_html = f'<div class="last">Last run {theme.when(s["started_at"], False)} · {n} incident{"" if n == 1 else "s"}</div>'
    elif src.kind != "webcam":
        last_html = '<div class="last">Not run yet</div>'
    with st.container(key=f"card_{i}"):
        st.markdown(f'<div class="ss-card"><div class="thumb">{thumb}<span class="tag">{tag}</span>{dur}'
                    f'<span class="play">{theme.PLAY_SVG}</span></div><div class="meta"><div class="t">{theme.esc(src.title)}</div>'
                    f'<div class="s">{status}</div>{last_html}</div></div>', unsafe_allow_html=True)
        st.button(f"Open {src.title}", key=f"open_{i}", on_click=open_source, args=(src.key,))


def grid(items, prefix, last):
    """One wrapping row: three cards across on a desktop, two on a tablet, one on a phone (see theme CSS)."""
    with st.container(horizontal=True, key=f"grid_{prefix}", gap=None):
        for i, src in enumerate(items):
            info = sources.info(src) if src.path else {}
            uri = sources.thumb_uri(src) if src.path else None
            card(src, f"{prefix}{i}", last.get(src.name) if src.path else None, uri, info)


def render(db):
    sessions, rows = db.sessions(), db.rows()
    demos = sources.demo_sources()
    st.markdown(f'<div class="ss-hero"><div><h1>Sources</h1><p>Choose a feed to open it in the monitor. '
                f'Nothing is processed until you press Start.</p></div><div class="facts">'
                f'<div><b>{len(demos)}</b>demo clips</div><div><b>{len(sessions)}</b>sessions recorded</div>'
                f'<div><b>{len(rows)}</b>incidents on file</div></div></div>', unsafe_allow_html=True)
    h = runlock.holder()
    if h and not h["mine"]:
        st.info(f"Monitoring is running in another browser tab ({h['source']}). Only one run can be active at a time.",
                icon=":material/info:")
    kind = st.segmented_control("Source type", TYPES, default=TYPES[0], required=True, key="srctype", label_visibility="collapsed")
    st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
    last = sources.last_sessions(sessions, rows)
    if kind == "Demo footage":
        if demos:
            grid(demos, "d", last)
        else:
            theme.empty("No demo clips in data/demo. Run training/fetch_mixkit.py or add clips listed in demo_clips.json.", "No demo footage")
    elif kind == "Upload video":
        up = st.file_uploader("Add a video file", type=["mp4", "avi", "mov", "mkv", "webm"], key="uploader")
        if up:
            sources.UPLOADS.mkdir(parents=True, exist_ok=True)
            dest = sources.UPLOADS / Path(up.name).name
            if not dest.exists() or dest.stat().st_size != up.size:
                dest.write_bytes(up.getbuffer())
            st.button(f"Open {dest.name} in the monitor", type="primary", icon=":material/play_arrow:", key="open_upload",
                      on_click=open_source, args=(f"upload:{dest.name}",))
        ups = sources.upload_sources()
        st.markdown('<div style="height:.8rem"></div>', unsafe_allow_html=True)
        if ups:
            theme.h3(f"Your uploads · {len(ups)}")
            grid(ups, "u", last)
        else:
            theme.empty("Uploaded videos are kept in data/demo/uploads and appear here.", "No uploads yet")
    else:
        with st.container(horizontal=True, key="grid_w", gap=None):
            card(sources.WEBCAM, "w0")
        st.markdown('<div class="ss-note" style="padding-top:.4rem">The webcam is not opened until you press Start in the monitor, '
                   'so no preview is captured here. If no camera is connected, the monitor says so.</div>', unsafe_allow_html=True)
