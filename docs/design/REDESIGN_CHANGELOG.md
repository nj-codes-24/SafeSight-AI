# UI redesign changelog

## v3: cinematic gallery and player (2 November 2026, evening)

This release replaces the five-page dashboard with two views: a source gallery and a monitoring player, with everything else below the player. It changes only the UI.

- **Unchanged:** model weights, thresholds (no-helmet 0.60), the pipeline, the database schema and the evaluation files.
- **Same launch command:** `.venv\Scripts\python.exe launch.py`.

**Protection steps:**

- **Backup:** the v2 dashboard was copied to `design/backup_v2_dashboard/` first. The original UI is still in `design/backup_pre_redesign/`.
- **Checksums:** after the work, every manifest entry outside `app/` matches, and `models/best.pt` is still `E9B2583D…CC3C7534`.
- **Settings file restored:** `models/runtime_config.json` was restored byte for byte after the settings save test (cooldown 30 → 35 s).
- **Test upload removed:** the QA test upload was deleted from `data/demo/uploads`. Its real run stays in the database as session `S20261102-171724` and earlier (`qa_upload_framing.mp4`).
- **Tests:** `pytest tests`: 32 passed.

| File | v3 change | SHA-256 |
|---|---|---|
| `app/main.py` | Single page. Top bar; routes between gallery and player by `?source=`; no `st.navigation`. | `356C9CF1…8C6D6797` |
| `app/theme.py` | New design system: warm graphite, off-white accent, cinematic player CSS, responsive rules, fullscreen and idle-fade script | `5EB1FD3A…30E6EEA` |
| `app/sources.py` | New. Demo, upload and webcam sources; OpenCV thumbnails cached in `data/cache/thumbnails`; video info; evidence thumbnails; last-session lookup | `6D4DA3A8…C2CA03` |
| `app/runlock.py` | New. One monitoring run per server, with a heartbeat. | `CB883908…68649B04` |
| `app/views/gallery.py` | New. Gallery view. | `7B89795F…2D37AB02` |
| `app/views/player.py` | New. Player, control bar, info strip, live loop (same `Pipeline` calls, change-only UI updates) | `B3ED311E…2352024B`* |
| `app/views/insights.py` | New. Session figures, incident cards, inspector dialog, session analytics, history, incident log, CSV export | `D68F2370…304077D` |
| `app/views/settings.py` | New. The settings menu, using the same `load_config` and `save_config` and the same zone editor logic as the old Configuration page | `96E0087C…2024B` |
| `app/pages/*` | Removed. Their functions moved to `app/views/`, and copies are in both backups. | — |
| `.streamlit/config.toml` | New palette and 15 px base size | `06A6296A…E36EF3B` |

\*The full hashes are listed in `REDESIGN_QA.md`.

**Visible changes:**

- **Navigation:**
  - There is no sidebar. The app opens on the gallery.
  - Overview, Incidents, Analytics and Configuration are now sections of the monitor page plus the settings menu.
- **Gallery:**
  - Demo, upload and webcam sources appear as cards with real thumbnails.
  - Uploaded videos are listed and can be reopened.
- **Player:**
  - A cinematic player with a translucent control bar, fullscreen and fading controls.
  - The settings gear lives inside the player.
- **Incidents and analytics:**
  - Incidents are cards with evidence thumbnails, opening into an inspector dialog.
  - New session analytics: a compliance-over-time chart, recorded during the run.
- **Safety rails:**
  - A single-run lock across browser tabs, which fixes the two-tab interference found in the readiness audit.
  - Navigation is disabled during a run.

**Superseded test scripts:** `demo_audit/cdp_demo.py` and `design/capture_pages.py` drive the v2 sidebar UI and no longer match. The v3 equivalents are `design/qa_flow.py` and `design/responsive_check.py`.

---

## v2: dashboard polish (earlier the same day)

2 November 2026. This was a visual and interaction redesign of the Streamlit dashboard only.

- No model, weight, threshold, pipeline, database schema or evaluation file was changed.
- The application threshold stays at 0.60.
- The launch command is unchanged: `.venv\Scripts\python.exe launch.py`.

## Protection steps taken

1. **Read `FREEZE_MANIFEST.txt` before editing.**
2. **Backed up every UI file** to `design/backup_pre_redesign/` (`app/` and `launch.py`) before the first change.
3. **Checked every protected file against the manifest after the redesign.** All entries under `models/`, `inference/`, `database/`, `training/`, `watchdog_svc/`, `reports/` and `data/` match.
   - The only manifest entries that differ are the seven `app/` files listed below, as authorised.
   - `models/best.pt` is still `E9B2583D…CC3C7534`.
4. **Restored `models/runtime_config.json` byte for byte** after testing **Save rules**. I changed the cooldown to 35 s, saved it, set it back to 30 s and saved again.
5. **Ran `pytest tests` on the final code:** 32 passed.

## Changed files (UI revision manifest)

SHA-256 of the files as they now stand:

| File | Change | SHA-256 |
|---|---|---|
| `app/theme.py` | Rewritten as the design system: tokens, global CSS, components, formatting helpers. The Google Fonts import is gone. | `1A270DBBB53F88B7CC2FB6C52D79D61CAFE5AC9CDE9FED90F3E4A258EAAFB535` |
| `app/main.py` | Logo, favicon, navigation icons, sidebar system panel (model, threshold read from config, tracker, mode) | `D4464D1DC0A05CD0A70EEBC52663A781873CF7017B5C4E592576C983D8F2BB37` |
| `app/pages/overview.py` | Header with status pill, two metric strips, recent-incident list, activity chart | `AC443E7367BE33C304816ED6E88E5075E1126B80E381798051F06117ED0A51CC` |
| `app/pages/live.py` | Viewport bar and placeholder, larger video column, state counters, session panel, alert feed, run summary. Rail updates are change-only. | `C7FE749282ECFC49F56539AC09C29B4FD2962D5365DAAE4061276DFFDDC24C37` |
| `app/pages/incidents.py` | Status filter, formatted log with row selection, inspector with badges and detail panel; Update status is disabled when unchanged | `7477C3643554799B82B2DE0600EA2E82ED972664BBC1BC686D60D3E09AABE9F2` |
| `app/pages/analytics.py` | Detection-statistics strip, compliance trend, worker states, incidents by session and by clip, timeline, session history | `80325199E5B4637546ED8B7BD7ADAB12458F3A78C7F7C55A48B42A031D9FB8DA` |
| `app/pages/configuration.py` | Active-model panel with a live checksum check, grouped settings with descriptions, change-aware Save, a warning if no-helmet ≠ 0.60, destructive Delete zone | `C84537CD4BD97990747E1A91A4AD621AA78BBF1876DC6C44EEAE04234375141B` |
| `app/assets/logo.svg`, `app/assets/mark.svg` | New: local wordmark and favicon | `C6289072…B6930BD`, `D1600DA8…16126882E` |
| `.streamlit/config.toml` | New: theme colours, system fonts, radii | `87D1046800760C30ABCAF713DCC2F1504E67D030FC1D8529C6D9B02E2FC234A5` |
| `launch.py` | Removed the orange theme flags; the theme now comes from `config.toml`. Same command. | `5ABF3EFC0F62C7018D5FEDFEDB0A7AC6CFD88143E7183FC6D3D459460F6D8EC3` |
| `README.md` | Three layout rows: `app/theme.py`, `.streamlit/config.toml`, `design/` | `9C89441FCF1257F35649730AEC78CADD59D948FEBBFD5E0E07FE89B3ED7E21CF` |
| `DEMO_OPERATOR_GUIDE.md` | Steps 2, 3, 7 and 8 reworded for the new screens | — |

**Not changed:** `app/components/shared.py`, the overlay colours drawn into video and evidence (`inference/tracker.py`), and every model and data artifact.

## Behaviour changes visible to a user

- **No more "Zone nan".** Missing values now show "—", so the cosmetic bug from the readiness audit is gone.
- **Formatted values.** Dates read "2 Nov 16:04:11", times carry units ("0.46 s"), and confidence shows as a bar.
- **Live keeps its viewport while the model loads.** It shows "Starting"; before, the panel collapsed for about a second.
- **The FPS readout moved** to the viewport bar and updates twice a second.
- **Incidents can be inspected by clicking a table row,** as well as from the picker, and can be filtered by status.
- **Configuration shows whether `best.pt` matches the frozen checksum.** Save is disabled until a value changes.
- **"Repeated violations, top workers" was replaced by "Incidents by clip".** The old chart was all ones and listed temporary IDs. All other Analytics charts use the same records as before.
- **The app no longer requests fonts from Google.** Network inspection showed every request going to localhost.

## Verification in a real browser

Headless Edge was driven by `design/capture_pages.py` and `demo_audit/cdp_demo.py`, and the in-app browser was also used.

- **All five pages loaded.** Ten page switches gave 0 exceptions, at 1600×1000 and at 1280×800.
- **Same results as before the redesign.** The full demo sequence (helmet, night, track, ballast) gave the same incidents, IDs, times and confidences:
  - helmet: W1 at 0.46 s, 0.814
  - night: zone W1, W2, W3 and no-helmet W8 at 11.18 s
  - track: zone W2
  - ballast: 0 incidents
- **The violation-to-compliant transition, zone alerts and evidence images** all rendered.
- **CSV export downloaded** a header plus one row per incident.
- **Configuration save** was written to disk and then reverted.
- **Incident status review** (Closed → Reviewed → Closed) was written to the database and then reverted.
- **Row selection** opened the selected incident in the inspector.
- **The dashboard matches the database.** The Overview totals were compared with direct database queries.

## Performance

**Throughput** is frames divided by wall time, from the database.

| Test | Original UI | Redesigned UI |
|---|---|---|
| Night clip, 1600×1000, earlier the same day | about 37 FPS | 37–41 FPS |
| Night clip, 1280×800, interleaved A/B, 3 rounds each (`design/perf_check/ab_1280x800.json`) | 15.7 FPS mean | 16.5 FPS mean |

The A/B rounds ran while the whole machine was slower. Model-only speed at that time was 58 FPS against about 80 earlier, because the GPU wasn't boosting fully, and another user session was running clips from an Edge window. Both UIs slowed equally, so the redesign adds no measurable cost. Absolute FPS on presentation day will depend on the machine's state.

## Known limitations

- **The full-page screenshots** in `BEFORE_AFTER/` were taken with "capture beyond viewport". On long pages the sidebar can look clipped; that is a capture artefact, not the app.
- **The two-tab caveat from the readiness audit still applies:** browser sessions share one tracker, so run the demo from one tab.
- **Streamlit's own header** (the running indicator, the ⋮ menu) is kept, because it provides Stop and the sidebar toggle.
