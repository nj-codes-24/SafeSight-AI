# 22A — Site data collection checklist

Companion to [`22_INDUSTRIAL_DATA_ACQUISITION_PLAN.md`](22_INDUSTRIAL_DATA_ACQUISITION_PLAN.md). Print it, take it to
the site, and keep the completed copy with the data agreement. **Recording does not start until every item in sections
A and B is ticked and signed.** Items marked ⚖ need the site's legal or data-protection adviser.

Site: ____________________ Site ID (pseudonymous): ________ Visit date: ____________ SafeSight lead: ____________

## A. Authorisation and people (before any camera is touched)

| # | Item | Done | Evidence / reference |
|---|---|---|---|
| A1 | Written data agreement signed by someone with authority (purpose, cameras, period, retention, access, deletion, no publication, evaluation-only unless stated) ⚖ | ☐ | |
| A2 | Legal basis for processing recorded by the site's adviser ⚖ | ☐ | |
| A3 | DPIA (or local equivalent) completed and approved by the site ⚖ | ☐ | |
| A4 | Workers' representatives / works council / union consulted where required ⚖ | ☐ | |
| A5 | Worker information notice issued; notices posted at recorded areas | ☐ | |
| A6 | Named site safety lead who owns PPE rules and zone restrictions | ☐ | Name/role: |
| A7 | Named site IT/OT contact for camera network access | ☐ | |
| A8 | Written statement that footage will not be used for discipline or individual performance evaluation | ☐ | |
| A9 | Withdrawal / deletion request process agreed | ☐ | |
| A10 | Reviewer list (named, confidentiality undertaking signed) | ☐ | |

## B. Security and storage

| # | Item | Done | Notes |
|---|---|---|---|
| B1 | Recording machine on the site network or an isolated segment; outbound internet disabled during recording | ☐ | |
| B2 | Encrypted storage (full-disk encryption); access by named accounts only | ☐ | |
| B3 | No cloud sync, no external annotation tools, no external AI services | ☐ | |
| B4 | Camera credentials supplied through environment variables only (`runtime/sources.py`); never written to files or logs | ☐ | |
| B5 | Retention end date set and calendar reminder created | ☐ | Delete by: |
| B6 | Access log started (who opened which footage, when) | ☐ | |

## C. Site survey

| # | Item | Done | Notes |
|---|---|---|---|
| C1 | Site type (warehouse / DC / factory logistics / manufacturing) and shifts | ☐ | |
| C2 | Hazard areas identified with the safety lead: docks, crossings, vehicle-only aisles, walkways, guarded cells | ☐ | |
| C3 | Documented PPE rules per area (copy of the site rule, issue date, owner) | ☐ | |
| C4 | Documented restricted areas and how authorisation is recorded (permit, access log) | ☐ | |
| C5 | Vehicle types in use (counterbalance, reach truck, pallet truck manual/powered, tugger) and traffic rules | ☐ | |
| C6 | Known exemptions (e.g. religious headwear rules, escorted visitors) recorded by the site | ☐ | |
| C7 | Lighting conditions: daylight ingress, dock doors, night lighting, IR cameras | ☐ | |

## D. Camera inventory (one row per camera)

| Camera ID | Location / view | Make, model, firmware | Stream resolution delivered | FPS delivered | Mount height, tilt | Fixed / PTZ | IR | Distance band of work area | Suitable? (see `23A` §2) |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |
| | | | | | | | | | |

For each camera: photograph the mount (no workers in the photo), save one reference snapshot taken with nobody in view,
and run `python scripts/validation/camera_acceptance.py probe` for at least 10 minutes (`23A` §4). Record the delivered
resolution and frame rate from the probe, not from the camera's menu.

## E. Recording plan

| # | Item | Done | Notes |
|---|---|---|---|
| E1 | Cameras selected (several kinds of view per site) | ☐ | |
| E2 | Schedule covering day, night and shift change; quiet and peak periods; at least 30-minute continuous segments | ☐ | |
| E3 | Split assignment fixed **before labelling**: development or held-out site | ☐ | Split: |
| E4 | Recorder time synchronised (NTP) and camera clock offset noted | ☐ | Offset: |
| E5 | Manifest started: file, camera, UTC start, duration, SHA-256, resolution, FPS | ☐ | |
| E6 | Site incident/near-miss log for the period requested (for later comparison only, never shown to reviewers before they finish) | ☐ | |
| E7 | Natural camera disturbances logged by site staff (bumps, cleaning, PTZ moves, IR switch times) | ☐ | |

## F. Never do

- Do not stage, encourage or tolerate unsafe behaviour to obtain positive examples.
- Do not record audio.
- Do not identify workers by name, face or badge in labels or notes.
- Do not take footage off site or upload it anywhere.
- Do not show model output to reviewers before their labels are locked.
- Do not change thresholds, zones or policies after seeing held-out results.

## G. Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Site safety lead | | | |
| Site data-protection contact | | | |
| SafeSight lead | | | |
