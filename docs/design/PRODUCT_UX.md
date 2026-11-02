# SafeSight AI: product experience

Two views on one page. There is no sidebar.

## Flow

```
Open app ──► SOURCE GALLERY ──(select a card)──► MONITOR ──(play)──► live run ──► results below the player
                 ▲                                   │
                 └────────── All sources / Sources ──┘   (disabled while a run is active)
```

1. **Open.** The app opens on the gallery (`http://localhost:8501`).
   - A minimal top bar shows the logo, *Sources*, the run status (Idle, or Monitoring with the source name), the active model chip (`M5 · no-helmet 0.60`) and a settings gear.
2. **Choose a source.** Three tabs:
   - **Demo footage:** the clips listed in `data/demo/demo_clips.json`.
   - **Upload video:** the original file uploader. Files are saved to `data/demo/uploads` and listed as cards.
   - **Webcam:** device 0, opened only when you press play.
   - Each card is a real frame from its clip with type, duration, resolution and fps, plus a "Last run" line read from the database. Clicking a card only opens the monitor. Nothing is processed and the model is not loaded.
3. **Monitor.** A large 16:9 player shows the source's poster frame with a centred play button. The URL becomes `?source=…`, so a refresh or bookmark reopens the same source.
4. **Play.** Pressing play starts the existing pipeline: detection, ByteTrack, PPE association, zones and incidents.
   - Frames with the real overlays stream into the player.
   - The translucent control bar shows stop, elapsed time over duration, a progress bar, processing FPS, the settings gear and fullscreen. It fades after about 2.6 s without mouse movement and returns on movement.
5. **Scroll down.**
   - **Source information:** poster, title, description, tags, model, thresholds, footage attribution, last run.
   - **Session:** eight figures, live during the run and final afterwards.
   - **Incidents:** this session's evidence cards; click one to open the inspector.
   - **Session analytics:** worker states, compliance during the run, incident timeline, zone intrusions.
   - **History:** all sessions and sources, with trend charts, the incident log, CSV export and session records.
6. **Settings.** The gear in the player, or in the top bar, opens a menu like a video player's settings, with four tabs:
   - **Detection:** worker, helmet and no-helmet confidence.
   - **Safety alerts:** confirmation time and duplicate cooldown, plus a plain-language rule description.
   - **Restricted zones:** camera view, zone, name, corner editor, live preview, save and delete.
   - **Model:** M5, YOLO26n, the experiment, a SHA-256 check against the frozen record, the application threshold and the tracker.

   Saving writes `models/runtime_config.json` as before, and changes apply from the next run.
7. **Return.** *All sources* (above the player) or *Sources* (top bar) returns to the gallery.

## What a "session" means on the monitor

| Situation | What the Session section shows |
|---|---|
| A run made in this browser tab | That run. While it runs, the figures cover workers in view now. When it finishes, they become the final state of each confirmed track (the database record), and a compliance-over-time chart recorded during the run is added. |
| No run in this tab yet | The last recorded session of this source, labelled "from history". Figures not recorded for past runs (active tracks, the time series) are shown as "—" or an empty state, never estimated. |
| Never run | An empty state that says to press play. |

**Counting tracks:** *Active tracks* are visible now. *Confirmed tracks* were seen for at least 1 s. Neither is a headcount.

## Single-run protection

- **One run per server.** All tabs share one detector and tracker, so only one run may be active at a time (`app/runlock.py`).
  - A tab that tries to start while another is running sees a disabled play button, a **Busy** state and the message "Monitoring is running in another browser tab".
  - The top bar in every tab shows *Monitoring · <source>*.
  - The lock frees itself if the running tab disappears; its heartbeat expires after 4 s.
- **During a run, navigation is disabled** (All sources, Sources), so a stray click cannot cut the run short. The settings controls are read-only until the run stops.
- **Stop ends the run cleanly.** Open incidents are closed and the session is saved, exactly as before.
- **The gallery never processes video.** Thumbnails are read from cached JPEGs.

## Honest limits

- **The player shows processed frames, not a seekable video.** The progress bar reports position and cannot be dragged. Pause is not offered, because pausing would have to restart the tracker; stop and play are the real controls.
- **No volume control.** The processed stream has no audio.
- **Processing runs faster than real time** on short clips. The alert cards, incident list and compliance chart keep every event.
