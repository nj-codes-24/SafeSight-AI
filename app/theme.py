"""SafeSight design system: tokens, global CSS and small HTML builders shared by the views.

Colour roles (design/DESIGN_SYSTEM.md):
  ink (off-white)  the one accent: primary actions, progress, selection
  ok/bad/warn      worker state only, matching the colours drawn into the video
  zone             the restricted-zone incident category
"""
import html
import math
from datetime import datetime

import streamlit as st

BG, SURFACE, RAISED = "#0E0D0C", "#161514", "#1E1D1B"
LINE, LINE_STRONG = "#262422", "#34312E"
INK, INK_2, INK_3 = "#EDEAE5", "#A9A39B", "#77716A"
GOOD, BAD, WARN, ZONE = "#22C55E", "#EF4444", "#F59E0B", "#A78BFA"
FONT = "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
TYPE_LABEL = {"NO_HELMET": "No helmet", "ZONE_INTRUSION": "Zone intrusion"}
TYPE_COLOR = {"No helmet": BAD, "Zone intrusion": ZONE}
STATUS_COLOR = {"OPEN": BAD, "CLOSED": INK_3, "REVIEWED": INK, "FALSE_ALARM": INK_3}

CSS = """
<style>
:root {
  --bg: #0E0D0C; --surface: #161514; --raised: #1E1D1B; --line: #262422; --line-strong: #34312E;
  --ink: #EDEAE5; --ink-2: #A9A39B; --ink-3: #77716A;
  --ok: #22C55E; --bad: #EF4444; --warn: #F59E0B; --zone: #A78BFA;
  --mono: 'Cascadia Mono', Consolas, monospace; --display: 'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif;
  --r-sm: 6px; --r: 10px; --r-lg: 14px; --ease: cubic-bezier(.2,.7,.2,1);
}
/* ---------- frame: no sidebar, no Streamlit header ---------- */
.stApp { background: radial-gradient(1200px 520px at 50% -180px, #221f1b 0%, rgba(14,13,12,0) 70%), var(--bg); }
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="stDecoration"], [data-testid="stToolbar"] { display: none !important; }
[data-testid="stMainBlockContainer"], .block-container { max-width: 1320px; padding: 0 2.5rem 5rem !important; }
p, li, td { font-feature-settings: "tnum" 1; }
[data-testid="stWidgetLabel"] p { color: var(--ink-2); font-size: .82rem; font-weight: 500; }
[data-testid="stCaptionContainer"] p { color: var(--ink-3); font-size: .8rem; }
.st-key-view_gallery, .st-key-view_player { animation: ss-in .4s var(--ease); }
@keyframes ss-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---------- buttons ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stPopover"] > div > button {
  border-radius: var(--r-sm); font-weight: 600; transition: background .15s, border-color .15s, color .15s, transform .15s; }
.stButton > button[kind="primary"]:not(:disabled) { background: var(--ink); border-color: var(--ink); color: #12110F; }
.stButton > button[kind="primary"]:not(:disabled):hover { background: #fff; border-color: #fff; }
.stButton > button[kind="secondary"], .stDownloadButton > button { background: var(--raised); border-color: var(--line-strong); }
.stButton > button[kind="tertiary"] { color: var(--ink-2); padding: .25rem .5rem; }
.stButton > button[kind="tertiary"]:hover { color: var(--ink); }
.stButton > button:disabled { opacity: .45; }

/* ---------- top bar ---------- */
.st-key-topbar { position: sticky; top: 0; z-index: 50; margin: 0 -2.5rem 1.6rem; padding: .7rem 2.5rem;
  background: rgba(14,13,12,.78); backdrop-filter: blur(16px) saturate(140%); border-bottom: 1px solid var(--line); }
.ss-logo { display: flex; align-items: center; gap: .6rem; white-space: nowrap; }
.ss-logo b { font-family: var(--display); font-size: 1.08rem; font-weight: 600; color: var(--ink); letter-spacing: .01em; }
.ss-logo span { color: var(--ink-3); font-weight: 500; }
.ss-crumb { color: var(--ink-3); font-size: .92rem; white-space: nowrap; max-width: 30vw; overflow: hidden; text-overflow: ellipsis; }
.st-key-topbar > [data-testid="stElementContainer"] { min-width: 0; }
.ss-crumb b { color: var(--ink); font-weight: 500; }
.ss-navlink { color: var(--ink-2) !important; text-decoration: none !important; font-size: .9rem; font-weight: 600; padding: .3rem .5rem; border-radius: var(--r-sm); }
.ss-navlink:hover { color: var(--ink) !important; background: var(--raised); }
.ss-pill { display: inline-flex; align-items: center; gap: .5rem; padding: .3rem .75rem; border-radius: 999px; white-space: nowrap;
  font-size: .8rem; font-weight: 500; color: var(--ink-2); background: rgba(255,255,255,.04); border: 1px solid var(--line-strong); }
.ss-pill b { color: var(--ink); font-weight: 600; }
.ss-pill .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c, var(--ink-3)); }
.ss-pill.live { color: #FCA5A5; border-color: rgba(239,68,68,.4); background: rgba(239,68,68,.08); }
.ss-pill.live .dot { background: var(--bad); animation: ss-pulse 1.6s ease-in-out infinite; }
@keyframes ss-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
[data-testid="stPopover"] > div > button { background: transparent; border: 1px solid transparent; color: var(--ink-2); }
[data-testid="stPopover"] > div > button:hover { color: var(--ink); background: rgba(255,255,255,.06); }
[data-testid="stPopoverBody"] { background: rgba(24,23,21,.96); backdrop-filter: blur(20px); border: 1px solid var(--line-strong);
  border-radius: var(--r); box-shadow: 0 24px 60px -12px rgba(0,0,0,.7); width: 460px; max-width: 92vw; }

/* ---------- headings ---------- */
.ss-hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; margin: .4rem 0 1.2rem; flex-wrap: wrap; }
.ss-hero h1 { font-family: var(--display); font-size: 2rem; font-weight: 600; letter-spacing: -.015em; margin: 0; padding: 0; color: var(--ink); line-height: 1.15; }
.ss-hero p { color: var(--ink-2); font-size: 1rem; margin: .4rem 0 0; }
.ss-hero .facts { display: flex; gap: 1.6rem; color: var(--ink-3); font-size: .85rem; }
.ss-hero .facts b { display: block; color: var(--ink); font-size: 1.25rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.ss-h2 { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: 2.6rem 0 .9rem;
  padding-bottom: .6rem; border-bottom: 1px solid var(--line); }
.ss-h2 h2 { font-family: var(--display); font-size: 1.45rem !important; font-weight: 600 !important; margin: 0 !important; padding: 0 !important;
  color: var(--ink); letter-spacing: -.01em; line-height: 1.25 !important; }
.ss-info h1, .ss-hero h1 { padding: 0 !important; }
.ss-h2 span { color: var(--ink-3); font-size: .85rem; }
.ss-h3 { color: var(--ink-2); font-size: .82rem; font-weight: 600; margin: 1.2rem 0 .4rem; }

/* ---------- source gallery ---------- */
[class*="st-key-grid_"] { flex-wrap: wrap !important; gap: 2.2rem 1.75rem !important; }
[class*="st-key-incgrid_"] { flex-wrap: wrap !important; gap: .9rem !important; }
[class*="st-key-incgrid_"] > [data-testid="stLayoutWrapper"] { flex: 0 0 calc((100% - 1.8rem) / 3) !important; width: calc((100% - 1.8rem) / 3) !important; min-width: 0 !important; }
[class*="st-key-inc_"] { width: 100% !important; }
@media (max-width: 1100px) { [class*="st-key-incgrid_"] > [data-testid="stLayoutWrapper"] { flex-basis: calc((100% - .9rem) / 2) !important; width: calc((100% - .9rem) / 2) !important; } }
@media (max-width: 700px) { [class*="st-key-incgrid_"] > [data-testid="stLayoutWrapper"] { flex-basis: 100% !important; width: 100% !important; } }
[class*="st-key-grid_"] > [data-testid="stLayoutWrapper"] { flex: 0 0 calc((100% - 3.5rem) / 3) !important; width: calc((100% - 3.5rem) / 3) !important; min-width: 0 !important; }
[class*="st-key-card_"] { position: relative; width: 100% !important; flex: 1 1 auto !important; }
@media (max-width: 1100px) { [class*="st-key-grid_"] > [data-testid="stLayoutWrapper"] { flex-basis: calc((100% - 1.75rem) / 2) !important; width: calc((100% - 1.75rem) / 2) !important; } }
@media (max-width: 640px) { [class*="st-key-grid_"] > [data-testid="stLayoutWrapper"] { flex-basis: 100% !important; width: 100% !important; } }
.ss-card { border-radius: var(--r); transition: transform .3s var(--ease); }
.ss-card .thumb { position: relative; aspect-ratio: 16/9; border-radius: var(--r); overflow: hidden; background: #000;
  box-shadow: 0 1px 0 rgba(255,255,255,.05) inset, 0 12px 30px -18px rgba(0,0,0,.9); outline: 1px solid rgba(255,255,255,.06); outline-offset: -1px; }
.ss-card .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; filter: brightness(.88) saturate(.95);
  transition: transform .5s var(--ease), filter .3s; }
.ss-card .thumb::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,.55)); }
.ss-card .tag { position: absolute; left: .65rem; top: .65rem; z-index: 2; font-size: .68rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: var(--ink); background: rgba(14,13,12,.62); backdrop-filter: blur(8px); padding: .2rem .5rem; border-radius: 4px; }
.ss-card .dur { position: absolute; right: .65rem; bottom: .6rem; z-index: 2; font-family: var(--mono); font-size: .72rem; color: var(--ink);
  background: rgba(14,13,12,.62); padding: .12rem .4rem; border-radius: 4px; }
.ss-card .play { position: absolute; left: 50%; top: 50%; z-index: 2; width: 52px; height: 52px; margin: -26px 0 0 -26px; border-radius: 50%;
  background: rgba(237,234,229,.92); display: grid; place-items: center; opacity: 0; transform: scale(.85); transition: opacity .25s, transform .3s var(--ease); }
.ss-card .play svg { width: 20px; height: 20px; margin-left: 3px; fill: #12110F; }
.ss-card .meta { padding: .75rem .15rem 0; }
.ss-card .t { font-size: 1.02rem; font-weight: 600; color: var(--ink); line-height: 1.3; }
.ss-card .s { display: flex; align-items: center; gap: .45rem; color: var(--ink-3); font-size: .82rem; margin-top: .25rem; }
.ss-card .s .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); }
.ss-card .s .dot.off { background: var(--ink-3); }
.ss-card .last { color: var(--ink-3); font-size: .8rem; margin-top: .15rem; }
[class*="st-key-card_"]:hover .ss-card { transform: translateY(-3px); }
[class*="st-key-card_"]:hover .ss-card .thumb img { transform: scale(1.035); filter: brightness(1) saturate(1); }
[class*="st-key-card_"]:hover .ss-card .play { opacity: 1; transform: scale(1); }
[class*="st-key-card_"] [class*="st-key-open_"] { position: absolute !important; inset: 0; z-index: 5; }
[class*="st-key-card_"] [class*="st-key-open_"] .stButton, [class*="st-key-card_"] [class*="st-key-open_"] button { width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.ss-webcam { width: 100%; height: 100%; display: grid; place-items: center; background: radial-gradient(circle at 50% 40%, #24211e, #0b0a09); }
.ss-webcam svg { width: 46px; height: 46px; stroke: var(--ink-3); fill: none; stroke-width: 1.4; }

/* ---------- player ---------- */
.st-key-player { position: relative; border-radius: var(--r-lg); overflow: hidden; background: #000; gap: 0 !important;
  max-width: max(560px, calc((100vh - 190px) * 16 / 9)); margin: 0 auto; width: 100%;
  box-shadow: 0 40px 90px -40px rgba(0,0,0,.95), 0 0 0 1px rgba(255,255,255,.06); }
.st-key-player [data-testid="stImage"] img, .ss-poster img { width: 100%; display: block; border-radius: 0 !important; }
.st-key-player [data-testid="stElementToolbar"] { display: none; }
.ss-poster { position: relative; aspect-ratio: 16/9; }
.ss-poster img { height: 100%; object-fit: cover; filter: brightness(.55) saturate(.9); }
.ss-poster .msg { position: absolute; left: 0; right: 0; bottom: 5.4rem; text-align: center; color: var(--ink-2); font-size: .9rem; }
.ss-poster.blank { background: radial-gradient(circle at 50% 40%, #24211e, #0b0a09); }
.st-key-ptop { position: absolute !important; left: 1rem; right: 1rem; top: .9rem; z-index: 6; pointer-events: none; width: auto !important; }
.st-key-ptop [data-testid="stElementContainer"], .st-key-ptop .stMarkdown, .st-key-ptop [data-testid="stMarkdownContainer"] { width: 100% !important; }
.ss-ptop { display: flex; justify-content: space-between; align-items: center; gap: .8rem; transition: opacity .4s; }
.ss-ptop .src { color: var(--ink); font-size: .9rem; font-weight: 600; text-shadow: 0 1px 8px rgba(0,0,0,.8); display: flex; gap: .6rem; align-items: center; }
.ss-chip { font-family: var(--mono); font-size: .72rem; color: var(--ink-2); background: rgba(14,13,12,.55); backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,.08); padding: .22rem .55rem; border-radius: 6px; }
.st-key-bigplay { position: absolute !important; left: 50%; top: 50%; transform: translate(-50%, -62%); z-index: 6; width: auto !important; }
.st-key-bigplay button { width: 76px; height: 76px; border-radius: 50% !important; background: rgba(237,234,229,.94) !important;
  border: none !important; color: #12110F !important; box-shadow: 0 10px 40px rgba(0,0,0,.5); }
.st-key-bigplay button:hover:not(:disabled) { transform: scale(1.06); background: #fff !important; }
.st-key-bigplay button:disabled { opacity: .3 !important; cursor: not-allowed; }
[data-testid="stMultiSelectTagsContainer"] [data-tag] { background: var(--raised) !important; color: var(--ink) !important;
  border: 1px solid var(--line-strong) !important; }
[data-testid="stMultiSelectTagsContainer"] [data-tag] * { color: var(--ink) !important; }
.st-key-bigplay button [data-testid="stIconMaterial"] { font-size: 2.3rem; }
.st-key-bigplay button p { display: none; }
.st-key-controls > [data-testid="stElementContainer"]:nth-child(2) { flex: 1 1 auto !important; min-width: 0; width: auto !important; }
.st-key-controls { position: absolute !important; left: 1rem; right: 1rem; bottom: .9rem; z-index: 7; padding: .35rem .55rem; width: auto !important;
  background: rgba(20,19,17,.58); backdrop-filter: blur(18px) saturate(150%); border: 1px solid rgba(255,255,255,.08);
  border-radius: 12px; transition: opacity .45s var(--ease), transform .45s var(--ease); }
.st-key-controls .stButton > button { background: transparent !important; border: none !important; color: var(--ink) !important;
  min-height: 2.2rem; padding: 0 .55rem; }
.st-key-controls .stButton > button:hover { background: rgba(255,255,255,.08) !important; }
.st-key-controls .stButton > button:disabled { color: var(--ink-3) !important; }
.st-key-controls [data-testid="stPopover"] > div > button { min-height: 2.2rem; color: var(--ink); }
.ss-prog { display: flex; align-items: center; gap: .8rem; width: 100%; font-family: var(--mono); font-size: .76rem; color: var(--ink-2); }
.ss-prog .bar { flex: 1; height: 4px; border-radius: 4px; background: rgba(255,255,255,.16); position: relative; overflow: hidden; }
.ss-prog .bar i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--ink); border-radius: 4px; transition: width .45s linear; }
.ss-prog .bar.live i { background: linear-gradient(90deg, var(--ink), #fff); }
.ss-prog .fps { color: var(--ink); }
.ss-fs { border: none; width: 2.2rem; height: 2.2rem; border-radius: 6px; cursor: pointer; display: block;
  background: transparent url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23EDEAE5' stroke-width='1.8'%3E%3Cpath d='M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5'/%3E%3C/svg%3E") center / 18px no-repeat; }
.ss-fs:hover { background-color: rgba(255,255,255,.08); }
.ss-fs svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 1.8; }
body[data-ss-idle="1"] .st-key-controls, body[data-ss-idle="1"] .ss-ptop { opacity: 0; transform: translateY(4px); }
body[data-ss-idle="1"] .st-key-player { cursor: none; }
.st-key-backrow, .ss-info { max-width: max(560px, calc((100vh - 190px) * 16 / 9)); margin-left: auto !important; margin-right: auto !important; width: 100%; }
.st-key-player:fullscreen { max-width: none; border-radius: 0; display: flex; flex-direction: column; justify-content: center; background: #000; }
.st-key-player:fullscreen [data-testid="stImage"] img, .st-key-player:fullscreen .ss-poster img { max-height: 100vh; object-fit: contain; }
.st-key-back button { padding-left: 0 !important; }

/* ---------- information strip under the player ---------- */
.ss-info { display: grid; grid-template-columns: 168px 1fr 340px; gap: 1.6rem; align-items: start; margin-top: 1.4rem; box-sizing: border-box;
  padding: 1.3rem 1.4rem; background: linear-gradient(180deg, rgba(30,29,27,.72), rgba(22,21,20,.72)); border: 1px solid var(--line);
  border-radius: var(--r-lg); }
.ss-info .poster { aspect-ratio: 16/10; border-radius: 8px; overflow: hidden; outline: 1px solid rgba(255,255,255,.07); background: #000; }
.ss-info .poster img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ss-info h1 { font-family: var(--display); font-size: 1.7rem; font-weight: 700; margin: 0; padding: 0; color: var(--ink); letter-spacing: -.01em; line-height: 1.2; }
.ss-info h1 sup { font-family: var(--mono); font-size: .7rem; color: var(--ink-3); font-weight: 500; margin-left: .45rem; letter-spacing: .04em; vertical-align: super; }
.ss-info .desc { color: var(--ink-2); font-size: .94rem; line-height: 1.6; margin: .55rem 0 0; max-width: 62ch; }
.ss-info .tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .9rem; }
.ss-tag { font-size: .74rem; font-weight: 600; color: var(--ink-2); padding: .26rem .65rem; border-radius: 999px; background: rgba(255,255,255,.05);
  border: 1px solid var(--line-strong); white-space: nowrap; }
.ss-tag.on { background: var(--ink); color: #12110F; border-color: var(--ink); }
.ss-tag.zone { color: #C4B5FD; border-color: rgba(167,139,250,.35); background: rgba(167,139,250,.08); }
.ss-info .kv { font-size: .86rem; color: var(--ink-2); line-height: 1.75; }
.ss-info .kv b { color: var(--ink-3); font-weight: 600; font-size: .72rem; letter-spacing: .07em; text-transform: uppercase; margin-right: .35rem; }

/* ---------- metrics ---------- */
.ss-metrics { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.ss-metrics.five { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.ss-m { padding: 1rem 1rem 1.05rem; border-left: 1px solid var(--line); min-width: 0; }
.ss-m:first-child { border-left: none; padding-left: .2rem; }
.ss-m .l { display: flex; align-items: center; gap: .45rem; color: var(--ink-3); font-size: .78rem; font-weight: 500; white-space: nowrap; }
.ss-m .l i { width: 7px; height: 7px; border-radius: 50%; background: var(--c); flex: none; }
.ss-m .v { font-family: var(--display); font-size: 1.75rem; font-weight: 600; color: var(--ink); margin-top: .35rem; line-height: 1.1;
  font-variant-numeric: tabular-nums; letter-spacing: -.01em; white-space: nowrap; }
.ss-m .v small { font-size: .85rem; color: var(--ink-3); font-weight: 500; margin-left: .2rem; }
.ss-m .n { color: var(--ink-3); font-size: .74rem; margin-top: .2rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ss-m.dim .v { color: var(--ink-3); }

/* ---------- incidents ---------- */
[class*="st-key-inc_"] { position: relative; }
.ss-inc { display: grid; grid-template-columns: 132px 1fr; gap: .9rem; align-items: center; padding: .6rem; border-radius: var(--r); margin-bottom: .55rem;
  background: var(--surface); border: 1px solid var(--line); transition: border-color .2s, background .2s, transform .25s var(--ease); }
.ss-inc .ev { aspect-ratio: 16/9; border-radius: 6px; overflow: hidden; background: #000; }
.ss-inc .ev img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ss-inc .top { display: flex; align-items: center; gap: .5rem; }
.ss-inc .w { color: var(--ink); font-weight: 600; font-size: .95rem; }
.ss-inc .sub { color: var(--ink-3); font-size: .78rem; margin-top: .3rem; font-family: var(--mono); }
[class*="st-key-inc_"]:hover .ss-inc { border-color: var(--line-strong); background: var(--raised); transform: translateY(-2px); }
[class*="st-key-pick_"] { position: absolute !important; inset: 0; z-index: 4; }
[class*="st-key-pick_"] .stButton, [class*="st-key-pick_"] button { width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.ss-badge { display: inline-flex; align-items: center; padding: .12rem .5rem; border-radius: 4px; font-size: .7rem; font-weight: 700;
  letter-spacing: .03em; white-space: nowrap; color: var(--c, var(--ink-2));
  background: color-mix(in srgb, var(--c, #77716A) 14%, transparent); border: 1px solid color-mix(in srgb, var(--c, #77716A) 30%, transparent); }
.ss-feed { display: flex; flex-direction: column; gap: .5rem; }
.ss-alert { display: flex; align-items: center; gap: .8rem; padding: .7rem .9rem; border-radius: var(--r); background: var(--surface);
  border: 1px solid var(--line); border-left: 3px solid var(--c); animation: ss-in .35s var(--ease); }
.ss-alert .w { color: var(--ink); font-weight: 600; }
.ss-alert .t { margin-left: auto; color: var(--ink-3); font-family: var(--mono); font-size: .76rem; }
.ss-empty { color: var(--ink-3); font-size: .9rem; padding: 1.3rem 1.4rem; border: 1px dashed var(--line-strong); border-radius: var(--r); }
.ss-empty b { display: block; color: var(--ink-2); font-weight: 600; margin-bottom: .2rem; }

/* ---------- key-value panels (dialog, settings) ---------- */
.ss-kv .row { display: flex; justify-content: space-between; gap: 1rem; padding: .5rem 0; border-top: 1px solid var(--line); font-size: .88rem; }
.ss-kv .row:first-child { border-top: none; }
.ss-kv .k { color: var(--ink-3); white-space: nowrap; }
.ss-kv .v { color: var(--ink); text-align: right; overflow-wrap: anywhere; }
.ss-kv .v.m { font-family: var(--mono); font-size: .8rem; }
.ss-note { color: var(--ink-3); font-size: .8rem; line-height: 1.5; }

/* ---------- data widgets ---------- */
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: var(--r); }
[data-testid="stPlotlyChart"] { padding-top: .2rem; }
[data-baseweb="tab-list"] { gap: .2rem; }
[data-baseweb="tab"] { font-weight: 600; }
div[role="dialog"] { border-radius: var(--r-lg) !important; }

/* ---------- responsive ---------- */
@media (max-width: 1200px) { .ss-metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); } .ss-m:nth-child(5) { border-left: none; padding-left: .2rem; }
  .ss-m:nth-child(n+5) { border-top: 1px solid var(--line); } .ss-info { grid-template-columns: 140px 1fr; } .ss-info .side { grid-column: 1 / -1; } }
@media (max-width: 900px) { [data-testid="stMainBlockContainer"], .block-container { padding: 0 1rem 4rem !important; }
  .st-key-topbar { margin: 0 -1rem 1.2rem; padding: .6rem 1rem; } .ss-info { grid-template-columns: 1fr; } .ss-info .poster { display: none; }
  .ss-metrics, .ss-metrics.five { grid-template-columns: repeat(2, minmax(0, 1fr)); } .ss-m { border-left: none !important; border-top: 1px solid var(--line); padding-left: .2rem; }
  .ss-hero h1 { font-size: 1.6rem; } .ss-inc { grid-template-columns: 104px 1fr; } }
</style>
"""

# Fullscreen for the player and fade-out of the overlay controls while a clip is playing and the mouse is still.
JS = """
<script>
(() => {
  const w = window.parent && window.parent.document ? window.parent : window;
  const doc = w.document;
  if (w.__ssPlayer) return;
  w.__ssPlayer = true;
  doc.addEventListener('click', (e) => {
    if (!e.target.closest('[data-ss-fs]')) return;
    const p = doc.querySelector('.st-key-player');
    if (!p) return;
    if (doc.fullscreenElement) doc.exitFullscreen(); else p.requestFullscreen && p.requestFullscreen();
  }, true);
  let t = null;
  const wake = () => {
    doc.body.removeAttribute('data-ss-idle');
    clearTimeout(t);
    t = setTimeout(() => {
      const live = doc.querySelector('.ss-ptop[data-state="live"]');
      const menu = doc.querySelector('[data-testid="stPopoverBody"]');
      if (live && !menu) doc.body.setAttribute('data-ss-idle', '1');
    }, 2600);
  };
  ['mousemove', 'keydown', 'touchstart', 'scroll'].forEach(ev => doc.addEventListener(ev, wake, {passive: true, capture: true}));
  wake();
})();
</script>
"""

PLAY_SVG = '<svg viewBox="0 0 24 24"><path d="M7 4.5v15l13-7.5z"/></svg>'
FS_SVG = '<svg viewBox="0 0 24 24"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>'
CAM_SVG = '<svg viewBox="0 0 24 24"><rect x="2.5" y="6" width="14" height="12" rx="2"/><path d="M16.5 10.5l5-3v9l-5-3"/></svg>'
LOGO_SVG = ('<svg width="24" height="24" viewBox="0 0 28 28"><g fill="none" stroke="#EDEAE5" stroke-width="2" stroke-linecap="square">'
            '<path d="M2 8V2h6M20 2h6v6M26 20v6h-6M8 26H2v-6"/></g><path d="M8.5 15.5a5.5 5.5 0 0 1 11 0z" fill="#EDEAE5"/>'
            '<rect x="7" y="15.5" width="14" height="2" rx="1" fill="#EDEAE5"/></svg>')


def inject():
    st.markdown(CSS, unsafe_allow_html=True)
    st.html(JS, unsafe_allow_javascript=True)


def esc(x):
    return html.escape(str(x))


def missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v) in ("", "None", "nan", "NaT")


def show(v, unit=""):
    return "—" if missing(v) else f"{v}{unit}"


def when(iso, seconds=True):
    if missing(iso):
        return "—"
    try:
        d = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    return f"{d.day} {d:%b} {d:%H:%M:%S}" if seconds else f"{d.day} {d:%b} {d:%H:%M}"


def clock(seconds):
    seconds = max(0, int(round(seconds or 0)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def h2(title, aside="", anchor=None):
    a = f' id="{anchor}"' if anchor else ""
    st.markdown(f'<div class="ss-h2"{a}><h2>{esc(title)}</h2><span>{esc(aside)}</span></div>', unsafe_allow_html=True)


def h3(text, target=None):
    (target or st).markdown(f'<div class="ss-h3">{esc(text)}</div>', unsafe_allow_html=True)


def badge(text, color=None):
    style = f' style="--c:{color}"' if color else ""
    return f'<span class="ss-badge"{style}>{esc(text)}</span>'


def type_badge(t):
    return badge("No helmet" if t == "NO_HELMET" else "Zone", BAD if t == "NO_HELMET" else ZONE)


def status_badge(s):
    return badge(str(s).replace("_", " ").title(), STATUS_COLOR.get(s))


def pill(text, value=None, live=False, color=None):
    v = f" <b>{esc(value)}</b>" if value is not None else ""
    c = f' style="--c:{color}"' if color else ""
    return f'<span class="ss-pill{" live" if live else ""}"{c}><span class="dot"></span>{esc(text)}{v}</span>'


def metric(label, value, note="", color=None, unit="", dim=False):
    dot = f'<i style="--c:{color}"></i>' if color else ""
    u = f"<small>{esc(unit)}</small>" if unit else ""
    return (f'<div class="ss-m{" dim" if dim else ""}"><div class="l">{dot}{esc(label)}</div>'
            f'<div class="v">{esc(value)}{u}</div><div class="n">{esc(note)}</div></div>')


def metrics(items, five=False, target=None):
    body = "".join(metric(*m) if isinstance(m, tuple) else m for m in items)
    (target or st).markdown(f'<div class="ss-metrics{" five" if five else ""}">{body}</div>', unsafe_allow_html=True)


def kv(rows, target=None):
    body = "".join(f'<div class="row"><span class="k">{esc(k)}</span><span class="v{" m" if m else ""}">{v}</span></div>' for k, v, m in rows)
    (target or st).markdown(f'<div class="ss-kv">{body}</div>', unsafe_allow_html=True)


def empty(text, title=None, target=None):
    t = f"<b>{esc(title)}</b>" if title else ""
    (target or st).markdown(f'<div class="ss-empty">{t}{esc(text)}</div>', unsafe_allow_html=True)


def alert_html(a):
    nh = a["type"] == "NO_HELMET"
    kind = "No helmet" if nh else f"Zone · {a['zone']}"
    return (f'<div class="ss-alert" style="--c:{BAD if nh else ZONE}">{type_badge(a["type"])}'
            f'<span class="w">W{esc(a["worker_id"])}</span><span style="color:var(--ink-2)">{esc(kind)}</span>'
            f'<span class="t">{a["video_t"]} s · {esc(a["incident_id"])}</span></div>')


def style_fig(fig, height=300):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=INK_2, size=12, family=FONT), margin=dict(l=6, r=10, t=30, b=6),
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=12, color=INK_2), bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=RAISED, bordercolor=LINE_STRONG, font=dict(color=INK, family=FONT, size=12)), bargap=0.45)
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE_STRONG, linecolor=LINE_STRONG, tickcolor=LINE_STRONG, color=INK_3,
                     title_font=dict(size=12, color=INK_3), automargin=True)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE_STRONG, linecolor="rgba(0,0,0,0)", color=INK_3,
                     title_font=dict(size=12, color=INK_3), automargin=True)
    return fig
