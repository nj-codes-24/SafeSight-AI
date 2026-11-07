# 23A — Physical camera and RTSP acceptance test plan

Milestone M3, 6 November 2026. **Status: prepared, not run. No physical camera or RTSP stream has been tested.** Every
camera-view result to date comes from synthetic transformations and demo footage (`21` §12, §14). Camera-view
detection must not be described as industrially validated until this plan has been executed on real cameras.

Harness: `scripts/validation/camera_acceptance.py` (tests: `tests/test_camera_acceptance.py`, which exercise the
harness only, on a generated file and synthetic logs).

## 1. What is being accepted

| Layer | Question | Evidence the plan produces |
|---|---|---|
| Stream | Does the runtime connect, stay connected, and recover from outages for this camera model and firmware? | Delivered resolution and FPS, frame-interval jitter, read failures, reconnect count and outage durations, 24 h stability |
| Clock | How far does the camera's stream clock drift from NTP time? | Drift in seconds per hour (stream timestamps against wall time), overlay time against recorder time |
| View integrity | Does the view monitor detect real movement and blockage within the latency target, and stay quiet for normal operation, lighting changes and people near the lens? | Per test case: expected outcome, observed state transitions, latency, recovery time |
| Revalidation | Which physical conditions must force an operator to re-verify zones (and, later, calibration)? | Cases marked `revalidation_required` in the catalogue, checked against what the monitor did |

## 2. Hardware requirement (none available today)

| Item | Minimum | Why |
|---|---|---|
| Fixed IP cameras | At least 3 models from different manufacturers (for example one each from two major CCTV brands plus one low-cost model), ONVIF Profile S, RTSP over TCP | RTSP behaviour, encoders and exposure logic differ by manufacturer and firmware |
| Profiles | Each camera configured at 1080p and 720p, 10–25 FPS, H.264 (and H.265 if the site uses it) | Resolution and frame-rate effects on head size and on the view monitor |
| Night mode | At least one camera with IR illumination and automatic day/night switching | IR switching changes the image completely |
| Optics | One varifocal or PTZ camera | Zoom and preset changes |
| Mount | Rigid wall or pole mount at 3–6 m, plus one mount on a structure that vibrates (near a door, a conveyor or a vehicle route) | Fixed-mount assumption and vibration |
| Network | PoE switch with a port that can be disabled or rate-limited; NTP server | Outage, reconnection and throttling tests; time reference |
| Recorder | The SafeSight edge machine (or equivalent) running `python -m runtime` | The same code path as deployment |
| Test space | Indoor area with controllable lights and space for staged movement in front of the camera; staff to walk and move objects | Lighting, occlusion and normal-traffic cases |
| Outdoor or semi-outdoor position (optional) | Housing exposed to weather or a water spray | Rain and dust cases |

Credentials are supplied only through environment variables (`--username-env`, `--password-env`), as in the runtime.

## 3. Test-case catalogue

`camera_acceptance.py plan --camera <id>` writes this catalogue per camera to
`reports/validation/camera_acceptance/<id>/test_cases.csv`. Latency limit: the view monitor's confirmation time (5 s by
default) plus 3 s for check spacing and marking delay.

| Case | Procedure | Expected | Max latency | Operator revalidation | Gate B mandatory |
|---|---|---|---|---|---|
| S01 | Connect over RTSP (TCP), stream 10 min untouched | Stream stable | — | no | yes |
| S02 | Record delivered resolution and FPS for each stream profile | Measured | — | no | yes |
| S03 | Unplug the network cable 30 s, reconnect | Reconnects; incidents end as camera interrupted; no stuck worker | — | no | yes |
| S04 | Reboot the camera | As S03 | — | no | yes |
| S05 | Throttle the link for 2 min | Degraded state reported; no crash | — | no | no |
| S06 | Stream 24 h | No leak, no stuck camera, reconnects logged | — | no | yes |
| S07 | Camera clock vs NTP at start and end of S06 | Drift measured | — | no | yes |
| V01 | Knock: view shifts 2–5 % of width and stays | View change | 8 s | **yes** | yes |
| V02 | Re-aim 10–20° pan | View change | 8 s | **yes** | yes |
| V03 | Tilt 5–10° | View change | 8 s | **yes** | yes |
| V04 | Zoom change | View change | 8 s | **yes** | yes |
| V05 | Move away and back to the exact aim within 3 s | No event (transient) | — | no | no |
| V06 | PTZ preset away and back | View change, then recovery | 8 s | **yes** | no |
| V07 | Slow drift of about 1 % over 10 min | Warning at most | — | no (but report) | no |
| B01 | Cover the lens fully 15 s | Blocked, then recovery | 8 s | no | yes |
| B02 | Cover half the lens 15 s | Blocked | 8 s | no | yes |
| B03 | Translucent film 15 s | Blocked | 8 s | no | no |
| B04 | Vehicle or stack covering most of the view 30 s | Blocked (the safe answer) | 8 s | no | no |
| B05 | Person close to the lens 3 s | **No event** | — | no | yes |
| N01 | 30 min of normal traffic, workers and forklifts | **No event** | — | no | yes |
| L01 | Lights off and on | No event (blockage while dark is acceptable if documented) | — | no | yes |
| L02 | Dock door open/closed | No event | — | no | no |
| L03 | IR day/night switch | Warning at most; zones re-verified at night once | — | **yes** (first switch) | yes |
| L04 | Exposure swing (headlights) | No event | — | no | no |
| F01 | Defocus 15 s | Warning (focus), not a relocation | — | no | no |
| E01 | Vibration 5 min | Warning (vibration), not a relocation | — | no | yes |
| E02 | Water spray on housing | Warning or blocked; never a silent pass | — | no | no |
| E03 | Dust or condensation (observed naturally) | Warning or blocked | — | no | no |

**Which conditions require operator revalidation** (zones, and later calibration): any confirmed view change (V01–V04,
V06), any IR mode the zones were not verified in (L03, once per camera), any change of lens, mount or stream
resolution, and any blockage after which the view does not return to `VIEW_STABLE` by itself. Revalidation is the
existing operator workflow (`python -m runtime view accept | verify-zones`, `21` §10). Blockage that recovers to the
registered view does not need revalidation.

## 4. Procedure

```bash
# once per camera
python scripts/validation/camera_acceptance.py plan --camera dock-1
# terminal 1: record for the whole session (here 2 hours)
set CAM_USER=...   &   set CAM_PASS=...          (never written to files)
python scripts/validation/camera_acceptance.py probe --camera dock-1 --rtsp rtsp://10.0.0.21/stream1 \
    --username-env CAM_USER --password-env CAM_PASS --seconds 7200
# terminal 2: mark each physical action as it is done, and when it is undone
python scripts/validation/camera_acceptance.py mark --camera dock-1 --case B01 --event start
python scripts/validation/camera_acceptance.py mark --camera dock-1 --case B01 --event end
# afterwards
python scripts/validation/camera_acceptance.py evaluate --camera dock-1
```

Rules:
- Perform each case at least 3 times, at different times of the session, before calling it passed. The harness
  scores the last attempt of each case; keep the session log of all attempts.
- Wait at least 30 s between cases so that each starts from `VIEW_STABLE`.
- Run the movement cases with someone walking in the scene as well as with an empty scene.
- Separately, run the full runtime (`python -m runtime run`) on the same camera for N01 and S06 with a real zone and the
  configured PPE policy, and confirm that incidents open before a staged view change end with `camera_view_changed` at
  the last reliable observation (`python -m runtime incident list`).
- Record the camera make, model, firmware, lens, mount height and stream settings in the results folder.

## 5. Acceptance criteria (per camera model, before Gate B)

| Criterion | Target |
|---|---|
| Mandatory cases run | All, each at least 3 times |
| Movement and blockage detection (V01–V04, B01, B02) | Detected in every attempt within the latency limit |
| False view events (B05, N01, L01, E01) | None in the mandatory cases; any false event is investigated and documented before Gate B |
| Recovery after blockage | Back to `VIEW_STABLE` within 5 s of removal |
| Stream | S03/S04 reconnect without operator action; S06 runs 24 h without a stuck camera or unbounded memory growth |
| Clock | Drift measured and recorded; if over 1 s per day, the site enables NTP on the camera or the runtime uses receive time only |

Thresholds (`max_shift`, confirmation times) may be adjusted on this physical test data only, never on held-out site
data, and any change is recorded with its reason.

## 6. What this plan cannot show

- It does not validate safety detection (PPE, zones); only the camera and view-integrity layers.
- Three camera models are not the market; each new model at a site needs at least the mandatory cases.
- Weather cases on a test rig are approximations of real outdoor exposure.
