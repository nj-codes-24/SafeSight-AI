# SafeSight AI: visual audit, before the redesign

All five pages were inspected in a real browser (headless Edge at 1600×1000), with real runs of the helmet and night clips. The screenshots are in `BEFORE_AFTER/before/`.

## What it looks like now

A dark Streamlit app: a flat charcoal sidebar with five text links and a "SAFESIGHT AI" wordmark below them, and a 1500 px content column on the right.

| Page | Current state |
|---|---|
| **Overview** | Two rows of five identical tiles (current session, historical totals), each with a coloured left edge, then a raw dataframe of the latest incidents. |
| **Live** | A 3:1 split. The video sits left at about 850 px wide. On the right are a radio group, the clip dropdown, a full-width orange **Start** button, a **Stop** button, a status paragraph in markdown, and red-edged alert cards. |
| **Incidents** | Filters and Export CSV in one row, a 10-column raw dataframe (`incident_id`, `video_time_s`, `None`, …), then an "Evidence" section with a full-width dropdown, a large evidence image and a plain-text detail list. |
| **Analytics** | Five Plotly charts in a 2-2-1 grid on lighter panels, plus a table expander. |
| **Configuration** | Sliders and number inputs in four uneven columns (the no-helmet slider sits under the helmet slider), an orange **Save rules** button, then the zone editor. |

## What feels generic or dated

- **Default Streamlit chrome everywhere.** Radio buttons, full-width orange primary buttons, the default dataframe look, an empty header bar with a ⋮ menu, the running-man indicator, and the sidebar collapse chevron.
- **Tiles all look the same.** Ten bordered boxes with coloured left edges carry equal weight. Live state and history look identical, and the colour edges are decorative (orange "Compliance rate", amber "Zone incidents").
- **Orange is the brand accent and also the warning colour.** The Start button, sliders, multiselect chips and the AI wordmark are all safety-amber, so warnings lose meaning.
- **Raw data shown to supervisors.** Snake_case column names, `None` and `nan` values ("Zone nan"), `0.46` seconds without units, and ISO timestamps with a `T`.
- **Live status is a paragraph.** "Active tracks 2 · Confirmed tracks 4 of 4 IDs" wraps across lines. COMPLIANT, VIOLATION and UNCERTAIN are words in a sentence, with no colour or shape. FPS sits on the same level as everything else.
- **The video is under-sized.** About 850 of 1600 px, with large dead space below. There's no frame around it, no source label and no running indicator.
- **Brand is weak.** The wordmark sits below the navigation. There are no icons and no sense of system state (model, threshold, running or idle).
- **External font import.** `theme.py` loads IBM Plex from Google Fonts, so the app depends on the internet, and offline it silently falls back.
- **Analytics panels clash.** A lighter grey panel (`#1a1a19`) sits on the near-black page, so charts read as pasted-in images. The "Repeated violations" chart lists every temporary ID with value 1, which is noise.
- **Configuration has no grouping.** It has no descriptions, no read-only model information, and nothing that marks consequential actions like Save or Delete zone.

## What works and should be kept

- **The dark theme and restrained density** suit a control room.
- **Clear safety vocabulary:** COMPLIANT, VIOLATION and UNCERTAIN, plus "temporary ID" and "not a headcount".
- **The overlay colours drawn into the video** (green, red, amber) are clear and already used in the evidence images. They live in the frozen pipeline and stay unchanged; the UI is aligned to them.
- **Monospace for incident IDs and times**, and the honest caption "Every chart is computed from recorded sessions".
- **Performance design:** UI updates are throttled to about 12 per second, and torch only loads on Start.

## What needs to change

1. **Make the video the centre of Live.** Use a larger viewport, a framed header (source, LIVE/IDLE state, FPS), and a compact rail of state counters and alerts.
2. **Fix the colour roles.** A cool blue accent for interaction. Green, red and amber used only for worker state. Incident type shown as a labelled badge (PPE or Zone), not just a colour edge.
3. **A metric strip instead of tile grids.** One quiet surface, divided by hairlines, with tabular numerals. Live session and history are set apart by a section header and a status pill.
4. **Human-readable tables.** Readable column names, `—` for missing values, units (`0.46 s`), dates without the `T`, and status shown as badges.
5. **A designed incident inspector.** A detail panel with typed metadata, the evidence image in a frame, and status actions.
6. **Charts on the page surface,** with hairline grids, fewer charts that each answer one question, and no all-ones bar chart.
7. **Configuration grouped into sections** with descriptions, a read-only "Active model" summary, and Delete visually set apart.
8. **Offline system fonts.** Segoe UI Variable with a system-ui fallback, and Cascadia Mono or Consolas for data.

## Direction

A quiet, precise control-room interface:

- Near-black surfaces separated by 1 px hairlines rather than boxes.
- One cool accent (`#6E9EF5`) for interaction and focus.
- Safety colours kept for safety meaning only.
- A compact type scale with tabular numbers.

Live monitoring becomes an instrument: a big feed, a thin header strip, and a right rail that reads at a glance. Nothing animates except a small pulsing "LIVE" dot while a clip is being processed.
