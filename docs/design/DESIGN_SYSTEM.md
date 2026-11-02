# SafeSight AI design system (v3, cinematic)

The look takes the cinematic player and the information below it from reference 1, and the multi-source gallery from reference 2. It uses warm graphite surfaces, off-white as the one accent, and safety colours kept for safety meaning.

**Where it lives:**

| File | Contents |
|---|---|
| `.streamlit/config.toml` | Base theme |
| `app/theme.py` | Tokens, CSS, HTML builders, the small player script |
| `app/assets/` | Logo and favicon |

System fonts only, so the app works offline.

## Colour

| Token | Hex | Role |
|---|---|---|
| `bg` | `#0E0D0C` | Page, with one soft warm radial light at the top |
| `surface` / `raised` | `#161514` / `#1E1D1B` | Cards and panels / inputs, menus, chips |
| `line` / `line-strong` | `#262422` / `#34312E` | Hairlines / borders |
| `ink` | `#EDEAE5` | Text, **and the only accent**: primary buttons, the play button, the progress fill, selected tags, chart lines |
| `ink-2` / `ink-3` | `#A9A39B` / `#77716A` | Descriptions / metadata |
| `ok` / `bad` / `warn` | `#22C55E` / `#EF4444` / `#F59E0B` | COMPLIANT / VIOLATION / UNCERTAIN, the same colours the pipeline draws on the video |
| `zone` | `#A78BFA` | The restricted-zone incident category |

**Why off-white is the accent:**

- **It matches premium players**, which use white controls, and it never competes with a safety colour.
- **Amber always means uncertain** and red always means a violation, because no button or decoration uses them.

## Type

- **Fonts:** Segoe UI Variable Display for titles, Segoe UI Variable Text for text, Cascadia Mono or Consolas for times, IDs and FPS.
- **Base size:** 15 px, larger than before.

| Use | Size |
|---|---|
| Gallery title | 2 rem / 600 |
| Source title in the info strip | 1.7 rem / 700, with a mono superscript type label (`DEMO CLIP`) |
| Section heading (Session, Incidents, History) | 1.45 rem / 600 |
| Metric value | 1.75 rem / 600, tabular |
| Description | 0.94 rem, line height 1.6 |
| Metadata labels | 0.72 rem, uppercase, 0.07 em tracking |

## Shape, depth, motion

- **Radii:** 6 px for controls, 10 px for cards, 14 px for the player and info strip, and pills for tags.
- **Depth:** one deep soft shadow under the player and gallery thumbnails, plus 1 px inner outlines. There are no glows, and the only gradients are the top light and the 45% darkening at the bottom of each thumbnail.
- **Motion:**
  - **Views fade and rise in** over 0.4 s.
  - **Card hover:** the card lifts 3 px, the image scales to 1.035 and brightens, and a play disc fades in.
  - **Player controls** fade after 2.6 s of stillness while a clip plays.
  - **The LIVE dot pulses.**

  Nothing animates inside the video loop.

## Components

| Component | Where | Notes |
|---|---|---|
| Top bar | All views | Sticky and translucent with blur. Logo, Sources, breadcrumb, History anchor, status pill, model chip, settings gear. |
| Source card | Gallery | 16:9 cached frame, type tag, duration, hover play disc, title, readiness line, last run. The whole card is one transparent button. |
| Player | Monitor | `st.image` frames inside a rounded 16:9 frame, capped to the viewport height. Top overlay: state pill (Ready / LIVE / Finished / Busy), title, model chip. |
| Control bar | Player | Blurred translucent strip: play/stop, time, slim progress, FPS, settings popover, fullscreen (via an `st.html` script). |
| Settings menu | Player and top bar | `st.popover` holding four `st.tabs`, real widgets and Save. Disabled during a run. |
| Info strip | Under the player | Poster, title and type, description, tags (type, resolution, fps, duration, zones), metadata lines |
| Metric row | Session, History | One row divided by hairlines. State metrics carry a coloured dot; zero values are dimmed. |
| Incident card | Session | Evidence thumbnail, type and status badges, worker, video time, confidence, timestamp. Opens the inspector dialog. |
| Inspector | Dialog | Large evidence frame, badges, details, review status |
| Alert row | During a run | Left bar in the category colour, badge, worker, video time and ID |

## Responsive rules

- **Gallery:** 3 columns, 2 below 1100 px and 1 below 640 px. Incident cards follow the same steps (3 / 2 / 1).
- **Player:** keeps 16:9, with width capped at `(viewport height − 190 px) × 16/9` so the control bar stays on screen at 1366×768.
- **Metric row:** 8 cells, then 4 per line below 1200 px and 2 below 900 px.
- **Info strip:** goes to two columns, then one.
- **Checked at** 1920×1080, 1440×900, 1366×768, 1024×768 and 768×1024, with no horizontal overflow (`design/responsive_log.txt`).
