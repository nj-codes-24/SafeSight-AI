"""SafeSight AI. Run with: python launch.py

Two views in one page: the source gallery (default) and the monitoring player for the selected source (?source=...).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import runlock, sources, theme  # noqa: E402
from app.components.shared import get_db  # noqa: E402
from app.views import gallery, player, settings  # noqa: E402
from inference.config import load_config  # noqa: E402  (plain JSON; no torch)

ASSETS = Path(__file__).resolve().parent / "assets"
st.set_page_config(page_title="SafeSight AI", page_icon=str(ASSETS / "mark.svg"), layout="wide", initial_sidebar_state="collapsed")
theme.inject()

db = get_db()
src = sources.find(st.query_params.get("source", ""))
if st.query_params.get("source") and src is None:
    st.query_params.clear()
running_here = player.starting()
cfg = load_config()

# ---------------------------------------------------------------- top bar
with st.container(key="topbar", horizontal=True, vertical_alignment="center", gap="medium", wrap=False):
    st.markdown(f'<div class="ss-logo">{theme.LOGO_SVG}<b>SafeSight <span>AI</span></b></div>', unsafe_allow_html=True, width="content")
    st.button("Sources", type="tertiary", key="nav_sources", on_click=player.go_gallery, disabled=running_here or src is None)
    if src is not None:
        st.markdown(f'<div class="ss-crumb">/ <b>{theme.esc(src.title)}</b></div>', unsafe_allow_html=True, width="content")
        st.markdown('<a class="ss-navlink" href="#history" target="_self">History</a>', unsafe_allow_html=True, width="content")
    st.markdown("", width="stretch")
    h = runlock.holder()
    if h or running_here:
        status = theme.pill("Monitoring", Path((h or {}).get("source") or (src.name if src else "")).stem, live=True)
    else:
        status = theme.pill("Idle", color=theme.GOOD)
    st.markdown(status, unsafe_allow_html=True, width="content")
    st.markdown(f'<span class="ss-chip">M5 · no-helmet {cfg["no_helmet_conf"]:.2f}</span>', unsafe_allow_html=True, width="content")
    with st.popover("", icon=":material/settings:", key="hdr_gear", help="Settings"):
        settings.render("hdr", src, disabled=running_here)

if src is None:
    with st.container(key="view_gallery"):
        gallery.render(db)
else:
    with st.container(key="view_player"):
        player.render(src, db)
