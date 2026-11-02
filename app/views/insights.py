"""Everything under the player: session figures, the session's incidents, session analytics and history.
All figures come from the incident database or from the run in this browser tab; nothing is estimated."""
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import sources, theme
from app.components.shared import get_db

STATUSES = ["OPEN", "CLOSED", "REVIEWED", "FALSE_ALARM"]


def plot(fig, height=280):
    st.plotly_chart(theme.style_fig(fig, height), width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------- session figures
def live_metrics(s):
    rate = s["compliance_rate"]
    return [("Active tracks", s["tracked_now"], "in view now"),
            ("Confirmed tracks", s["confirmed_tracks"], f"of {s['track_ids']} IDs · ≥ 1 s"),
            ("Compliant", s["compliant"], "in view", theme.GOOD, "", not s["compliant"]),
            ("Violation", s["violation"], "in view", theme.BAD, "", not s["violation"]),
            ("Uncertain", s["uncertain"], "head not clear", theme.WARN, "", not s["uncertain"]),
            ("Compliance", rate if rate is not None else "—", "decided workers", None, "%" if rate is not None else ""),
            ("Incidents", s["incidents"], "this run"),
            ("Processing", f"{s['fps']:.0f}" if isinstance(s["fps"], (int, float)) else s["fps"], "frames per second", None, " FPS")]


def final_metrics(row, end=None, n_inc=0):
    """row: the session's database record (final state of each confirmed track); end: the live snapshot at the end."""
    c, v, u = row["compliant"], row["violation"], row["uncertain"]
    rate = f"{100 * c / (c + v):.1f}" if c + v else "—"
    return [("Active tracks", end["tracked_now"] if end else "—", "in view at the end" if end else "not recorded"),
            ("Confirmed tracks", row["unique_workers"], f"of {end['track_ids']} IDs · ≥ 1 s" if end else "seen ≥ 1 s"),
            ("Compliant", c, "final state", theme.GOOD, "", not c),
            ("Violation", v, "final state", theme.BAD, "", not v),
            ("Uncertain", u, "final state", theme.WARN, "", not u),
            ("Compliance", rate, "decided workers", None, "%" if c + v else ""),
            ("Incidents", n_inc, "this session"),
            ("Processing", f"{row['avg_fps']:.0f}", "frames per second", None, " FPS")]


# ---------------------------------------------------------------- incident inspector
@st.dialog("Incident", width="large")
def inspect(iid):
    db = get_db()
    r = next((x for x in db.rows() if x["incident_id"] == iid), None)
    if r is None:
        theme.empty("This incident is no longer in the database.")
        return
    left, right = st.columns([1.75, 1], gap="large")
    ev = Path(r["evidence_path"]) if not theme.missing(r["evidence_path"]) else None
    with left:
        if ev and ev.exists():
            st.image(str(ev), width="stretch")
            st.caption(f"Evidence frame saved when the incident was confirmed · {ev.name}")
        else:
            theme.empty("The evidence file is not on disk.", "Evidence missing")
    with right:
        title = "No helmet" if r["incident_type"] == "NO_HELMET" else f"Zone intrusion · {r['zone']}"
        st.markdown(f'<div style="display:flex;gap:.45rem;margin-bottom:.5rem">{theme.type_badge(r["incident_type"])}{theme.status_badge(r["status"])}</div>'
                    f'<div style="font-family:var(--display);font-size:1.35rem;font-weight:600;margin-bottom:.6rem">{theme.esc(title)}</div>',
                    unsafe_allow_html=True)
        dur = "—"
        if not theme.missing(r["ended_at"]):
            dur = f"{(datetime.fromisoformat(r['ended_at']) - datetime.fromisoformat(r['started_at'])).total_seconds():.0f} s"
        theme.kv([("Worker", f"W{r['worker_id']} <span style='color:var(--ink-3)'>temporary ID</span>", False),
                  ("Confidence", f"{r['confidence']:.3f}", True),
                  ("Video time", f"{r['video_time_s']:.2f} s", True),
                  ("Started", theme.when(r["started_at"]), True),
                  ("Ended", theme.when(r["ended_at"]) if not theme.missing(r["ended_at"]) else "still open", True),
                  ("Duration", dur, True),
                  ("Zone", theme.esc(theme.show(r["zone"])), False),
                  ("Camera", theme.esc(r["camera_id"]), True),
                  ("Session", theme.esc(r["session_id"]), True),
                  ("Incident ID", theme.esc(r["incident_id"]), True)])
        status = st.selectbox("Review status", STATUSES, index=STATUSES.index(r["status"]) if r["status"] in STATUSES else 0,
                              format_func=lambda s: s.replace("_", " ").title(), key=f"status_{iid}")
        if st.button("Update status", type="primary", width="stretch", disabled=status == r["status"], key=f"upd_{iid}"):
            db.set_status(iid, status)
            st.rerun()


def incident_cards(rows, prefix, per_row=3):
    """Clickable cards with the evidence thumbnail. rows: list of incident dicts."""
    with st.container(horizontal=True, key=f"incgrid_{prefix}", gap=None):
        for r in rows:
            with st.container(key=f"inc_{prefix}_{r['incident_id']}"):
                thumb = sources.evidence_thumb(r["evidence_path"])
                img = f'<img src="{thumb}" alt="">' if thumb else ""
                what = "No helmet" if r["incident_type"] == "NO_HELMET" else f"Zone · {r['zone']}"
                st.markdown(f'<div class="ss-inc"><div class="ev">{img}</div><div><div class="top">{theme.type_badge(r["incident_type"])}'
                            f'{theme.status_badge(r["status"])}</div><div class="w" style="margin-top:.4rem">W{r["worker_id"]} · '
                            f'<span style="font-weight:500;color:var(--ink-2)">{theme.esc(what)}</span></div>'
                            f'<div class="sub">{r["video_time_s"]:.2f} s · {r["confidence"]:.2f} · {theme.when(r["started_at"])}</div></div></div>',
                            unsafe_allow_html=True)
                if st.button(f"Inspect {r['incident_id']}", key=f"pick_{prefix}_{r['incident_id']}"):
                    inspect(r["incident_id"])


# ---------------------------------------------------------------- session analytics
def session_analytics(row, rows, timeline):
    a, b = st.columns(2, gap="large")
    with a:
        theme.h3("Worker states · final state of confirmed tracks")
        vals = [("Compliant", row["compliant"], theme.GOOD), ("Violation", row["violation"], theme.BAD), ("Uncertain", row["uncertain"], theme.WARN)]
        fig = go.Figure(go.Bar(x=[v[1] for v in vals], y=[v[0] for v in vals], orientation="h", marker=dict(color=[v[2] for v in vals], cornerradius=3),
                               text=[v[1] for v in vals], textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x}<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="Tracks", rangemode="tozero", dtick=1)
        plot(fig, 230)
    with b:
        theme.h3("PPE compliance during the run · workers in view")
        if timeline:
            t = pd.DataFrame(timeline, columns=["t", "rate", "active", "violation"])
            fig = go.Figure()
            fig.add_scatter(x=t.t, y=t.rate, mode="lines", name="Compliance", line=dict(color=theme.INK, width=2), connectgaps=False,
                            hovertemplate="%{x:.1f} s · %{y:.0f}% compliant<extra></extra>")
            fig.add_bar(x=t.t, y=t.violation, name="Violations in view", marker=dict(color=theme.BAD), yaxis="y2", opacity=.55,
                        hovertemplate="%{x:.1f} s · %{y} in violation<extra></extra>")
            fig.update_layout(yaxis=dict(title="Compliant, %", range=[0, 105]), yaxis2=dict(overlaying="y", side="right", visible=False,
                                                                                         range=[0, max(4, t.violation.max() * 3)]),
                              bargap=0)
            fig.update_xaxes(title="Video time, s")
            plot(fig, 230)
        else:
            theme.empty("The compliance timeline is recorded only for runs made in this browser tab. Press Start to record one.",
                        "No timeline for this session")
    a, b = st.columns(2, gap="large")
    df = pd.DataFrame(rows)
    with a:
        theme.h3("Incident timeline · by category")
        if df.empty:
            theme.empty("No incidents were raised in this session.")
        else:
            df["label"] = df.incident_type.map(theme.TYPE_LABEL)
            fig = go.Figure()
            for k, g in df.groupby("label"):
                fig.add_scatter(x=g.video_time_s, y=g.label, mode="markers", name=f"{k} ({len(g)})",
                                marker=dict(size=12, color=theme.TYPE_COLOR[k], line=dict(color=theme.BG, width=2)),
                                customdata=g[["worker_id", "incident_id"]], hovertemplate="W%{customdata[0]} at %{x:.2f} s<br>%{customdata[1]}<extra></extra>")
            fig.update_xaxes(title="Video time, s", rangemode="tozero")
            plot(fig, 210)
    with b:
        theme.h3("Zone intrusions · by zone")
        z = df[df.incident_type == "ZONE_INTRUSION"] if not df.empty else df
        if z.empty:
            theme.empty("No restricted-zone entries in this session.")
        else:
            c = z.groupby("zone").size().sort_values()
            fig = go.Figure(go.Bar(x=c.values, y=c.index, orientation="h", marker=dict(color=theme.ZONE, cornerradius=3), text=c.values,
                                   textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x} entries<extra></extra>"))
            fig.update_xaxes(title="Entries", dtick=1, rangemode="tozero")
            plot(fig, 210)


# ---------------------------------------------------------------- history
def history(db):
    rows = pd.DataFrame(db.rows())
    sessions = pd.DataFrame(db.sessions())
    theme.h2("History", "all recorded sessions · every source", anchor="history")
    if sessions.empty:
        theme.empty("Recorded sessions appear here after the first run.", "No history yet")
        return
    comp, vio = int(sessions.compliant.sum()), int(sessions.violation.sum())
    hel = int((rows.incident_type == "NO_HELMET").sum()) if len(rows) else 0
    zone = int((rows.incident_type == "ZONE_INTRUSION").sum()) if len(rows) else 0
    theme.metrics([("Sessions", len(sessions), f"{int(sessions.frames.sum()):,} frames processed"),
                   ("Confirmed tracks", int(sessions.unique_workers.sum()), "seen ≥ 1 s · not a headcount"),
                   ("PPE incidents", hel, "no helmet", theme.BAD),
                   ("Zone incidents", zone, "restricted area", theme.ZONE),
                   ("Compliance", f"{100 * comp / (comp + vio):.1f}" if comp + vio else "—", "decided workers", None, "%" if comp + vio else "")], five=True)

    s = sessions.copy()
    s["n"] = range(1, len(s) + 1)
    s["rate"] = (100 * s.compliant / (s.compliant + s.violation)).where((s.compliant + s.violation) > 0)
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        theme.h3("Compliance trend · per session")
        fig = go.Figure(go.Scatter(x=s.n, y=s.rate, mode="lines+markers", line=dict(color=theme.INK, width=1.6),
                                   marker=dict(size=6, color=theme.INK), customdata=s[["session_id", "source", "compliant", "violation"]],
                                   hovertemplate="%{y:.0f}% · %{customdata[1]}<br>%{customdata[2]} compliant · %{customdata[3]} violation<br>%{customdata[0]}<extra></extra>"))
        fig.update_yaxes(title="Compliant, %", range=[0, 105])
        fig.update_xaxes(title="Session (oldest → newest)")
        plot(fig, 260)
    with b:
        theme.h3("Incident categories · by source")
        if len(rows):
            rows["label"] = rows.incident_type.map(theme.TYPE_LABEL)
            by = rows.groupby(["camera_id", "label"]).size().unstack(fill_value=0)
            by = by.loc[by.sum(axis=1).sort_values().index]
            fig = go.Figure()
            for k in ("No helmet", "Zone intrusion"):
                if k in by:
                    fig.add_bar(name=k, y=by.index, x=by[k], orientation="h", marker=dict(color=theme.TYPE_COLOR[k]),
                                hovertemplate=f"{k}: %{{x}}<extra>%{{y}}</extra>")
            fig.update_layout(barmode="stack")
            fig.update_xaxes(title="Incidents")
            plot(fig, 260)
        else:
            theme.empty("No incidents recorded yet.")
    if len(rows):
        theme.h3("Incidents per session")
        freq = rows.groupby(["session_id", "label"]).size().unstack(fill_value=0).reindex(s.session_id, fill_value=0)
        fig = go.Figure()
        for k in ("No helmet", "Zone intrusion"):
            if k in freq:
                fig.add_bar(name=k, x=s.n, y=freq[k].values, marker=dict(color=theme.TYPE_COLOR[k]), customdata=s[["session_id", "source"]],
                            hovertemplate=f"{k}: %{{y}}<br>%{{customdata[1]}}<br>%{{customdata[0]}}<extra></extra>")
        fig.update_layout(barmode="stack")
        fig.update_xaxes(title="Session (oldest → newest)")
        fig.update_yaxes(title="Incidents", dtick=1)
        plot(fig, 220)

    tabs = st.tabs(["Incident log", "Session records"])
    with tabs[0]:
        incident_log(db, rows)
    with tabs[1]:
        hist = pd.DataFrame({"Session": sessions.session_id, "Recorded": pd.to_datetime(sessions.started_at), "Source": sessions.source,
                             "Frames": sessions.frames, "Confirmed tracks": sessions.unique_workers, "Compliant": sessions.compliant,
                             "Violation": sessions.violation, "Uncertain": sessions.uncertain, "FPS": sessions.avg_fps})[::-1]
        st.dataframe(hist, hide_index=True, width="stretch", height=min(40 + 35 * len(hist), 380),
                     column_config={"Recorded": st.column_config.DatetimeColumn(format="D MMM HH:mm:ss"),
                                    "FPS": st.column_config.NumberColumn(format="%.1f")})


def incident_log(db, rows):
    if rows.empty:
        theme.empty("No incidents recorded yet.")
        return
    f1, f2, f3, f4 = st.columns([1.5, 1.5, 1.2, 1], vertical_alignment="bottom")
    types = f1.multiselect("Type", sorted(rows.incident_type.unique()), default=sorted(rows.incident_type.unique()),
                           format_func=lambda t: theme.TYPE_LABEL.get(t, t), key="log_types")
    sess = f2.multiselect("Session", list(rows.session_id.unique()), placeholder="All sessions", key="log_sessions")
    stat = f3.multiselect("Status", STATUSES, placeholder="Any status", format_func=lambda s: s.replace("_", " ").title(), key="log_status")
    f4.download_button("Export CSV", db.to_csv(), "safesight_incidents.csv", "text/csv", icon=":material/download:", width="stretch")
    view = rows[rows.incident_type.isin(types)]
    if sess:
        view = view[view.session_id.isin(sess)]
    if stat:
        view = view[view.status.isin(stat)]
    if view.empty:
        theme.empty("No incidents match these filters.")
        return
    table = pd.DataFrame({"Time": pd.to_datetime(view.started_at), "Type": view.incident_type.map(theme.TYPE_LABEL),
                          "Worker": "W" + view.worker_id.astype(str), "Zone": view.zone.map(theme.show), "Confidence": view.confidence,
                          "Video time": view.video_time_s, "Source": view.camera_id, "Session": view.session_id,
                          "Status": view.status.str.replace("_", " ").str.title(), "ID": view.incident_id})
    ev = st.dataframe(table, hide_index=True, width="stretch", height=min(40 + 35 * len(table), 360), on_select="rerun",
                      selection_mode="single-row", key="log_table",
                      column_config={"Time": st.column_config.DatetimeColumn(format="D MMM HH:mm:ss"),
                                     "Confidence": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                                     "Video time": st.column_config.NumberColumn(format="%.2f s")})
    picked = ev.selection.rows if ev and ev.selection else []
    a, b = st.columns([1, 3], vertical_alignment="center")
    if a.button("Inspect selected", icon=":material/open_in_full:", disabled=not picked, width="stretch", key="log_inspect"):
        inspect(view.iloc[picked[0]].incident_id)
    b.caption(f"{len(view)} incidents shown. Select a row, then inspect it to see the evidence and review its status.")
