"""Physical camera acceptance harness (milestone M3, docs/product_research/23A_PHYSICAL_CAMERA_ACCEPTANCE_TEST_PLAN.md).

    python scripts/validation/camera_acceptance.py plan     --camera dock-1 [--out DIR]
    python scripts/validation/camera_acceptance.py probe    --camera dock-1 --rtsp rtsp://10.0.0.21/stream1 \
                                                            [--username-env CAM_USER --password-env CAM_PASS] --seconds 600
    python scripts/validation/camera_acceptance.py probe    --camera bench --file data/demo/track_work_day.mp4 --seconds 30
    python scripts/validation/camera_acceptance.py mark     --camera dock-1 --case V03 --event start [--note "panned 10 deg"]
    python scripts/validation/camera_acceptance.py evaluate --camera dock-1

`plan` writes the test-case catalogue (every case NOT_RUN). `probe` connects to the camera through the runtime's own
source classes (credentials only from environment variables), reads for the given time, runs the view monitor on the
frames exactly as the runtime does, and records stream statistics, outages, reconnections, stream clock against wall
clock, and every view-state transition, with UTC wall times. While it runs, the tester performs the physical actions of
the plan and records each with `mark` (start, and end when the action is undone). `evaluate` joins the marks with the
recorded transitions and fills in results. **Cases without marks stay NOT_RUN; nothing is ever inferred, simulated or
filled in for a case that was not physically performed.** A file source is accepted only to test the harness itself:
its results are labelled `harness self-test`, never camera acceptance.

Output (default reports/validation/camera_acceptance/<camera>/): test_cases.csv, session.jsonl, probe_summary.json,
actions.jsonl, results.csv, acceptance_summary.json. Footage is not stored: only statistics, states and the view
monitor's small grey evidence fingerprints are kept in memory, never written.
"""
import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "reports" / "validation" / "camera_acceptance"

CHANGE, BLOCK, NONE, WARN, STREAM = "view_change", "blocked", "no_event", "warning_only", "stream"
# id, category, procedure, expected, max detection latency (s), operator revalidation required, mandatory for Gate B
CASES = [
    ("S01", "stream", "Connect over RTSP (TCP) and stream 10 minutes untouched", STREAM, None, False, True),
    ("S02", "stream", "Record delivered resolution and frame rate for each configured stream profile", STREAM, None, False, True),
    ("S03", "stream", "Unplug the camera's network cable for 30 s, then reconnect", STREAM, None, False, True),
    ("S04", "stream", "Reboot the camera from its own interface", STREAM, None, False, True),
    ("S05", "stream", "Saturate or throttle the link (switch port limit) for 2 minutes", STREAM, None, False, False),
    ("S06", "stream", "Stream 24 hours continuously (memory, handles, reconnects, clock drift)", STREAM, None, False, True),
    ("S07", "stream", "Compare the camera's clock (overlay/stream time) with NTP-synchronised recorder time at start and end of S06", STREAM, None, False, True),
    ("V01", "movement", "Knock the camera so the view shifts by about 2-5 % of the width and stays there", CHANGE, 8.0, True, True),
    ("V02", "movement", "Re-aim the camera by 10-20 degrees (pan) and leave it", CHANGE, 8.0, True, True),
    ("V03", "movement", "Tilt the camera by 5-10 degrees and leave it", CHANGE, 8.0, True, True),
    ("V04", "movement", "Change zoom (varifocal or PTZ preset) and leave it", CHANGE, 8.0, True, True),
    ("V05", "movement", "Move the camera away and back to its exact original aim within 3 s", NONE, None, False, False),
    ("V06", "movement", "PTZ: go to another preset, then return to the home preset", CHANGE, 8.0, True, False),
    ("V07", "movement", "Slow drift: move the aim by about 1 % of the width over 10 minutes", WARN, None, False, False),
    ("B01", "blockage", "Cover the lens completely with a hand or card for 15 s, then remove", BLOCK, 8.0, False, True),
    ("B02", "blockage", "Cover half the lens for 15 s", BLOCK, 8.0, False, True),
    ("B03", "blockage", "Spray-paint simulation: translucent film over the lens for 15 s", BLOCK, 8.0, False, False),
    ("B04", "blockage", "Park a vehicle or pallet stack in front of the camera covering most of the view for 30 s", BLOCK, 8.0, False, False),
    ("B05", "blockage", "Person stands close to the lens for 3 s and walks away (must NOT be reported)", NONE, None, False, True),
    ("N01", "normal", "Normal traffic: workers and forklifts crossing the full view for 30 minutes", NONE, None, False, True),
    ("L01", "lighting", "Switch the area lights off and on (indoor) during operation", NONE, None, False, True),
    ("L02", "lighting", "Dock door opened to daylight and closed", NONE, None, False, False),
    ("L03", "lighting", "IR day/night switch at dusk (or forced from the camera interface)", WARN, None, True, True),
    ("L04", "lighting", "Automatic exposure swing (bright object, headlights into the lens)", NONE, None, False, False),
    ("F01", "focus", "Defocus the lens (or trigger autofocus hunting) for 15 s", WARN, None, False, False),
    ("E01", "environment", "Vibration: run nearby machinery or a vehicle past the mount for 5 minutes", WARN, None, False, True),
    ("E02", "environment", "Rain or water spray on the housing window (outdoor/semi-outdoor cameras)", WARN, None, False, False),
    ("E03", "environment", "Dust or condensation on the housing window (observe naturally; do not damage the camera)", WARN, None, False, False),
]
BLOCK_KINDS = {"camera_blocked"}
CHANGE_KINDS = {"camera_view_changed", "camera_scene_switched", "camera_view_unverified"}


def _utc(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).isoformat(timespec="milliseconds")


def _dir(camera, out=None):
    d = Path(out) if out else OUT / camera
    d.mkdir(parents=True, exist_ok=True)
    return d


def plan(camera, out=None):
    d = _dir(camera, out)
    p = d / "test_cases.csv"
    if p.exists():
        raise SystemExit(f"{p} exists; the plan is never overwritten (it may already hold results)")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "category", "procedure", "expected", "max_latency_s", "revalidation_required", "mandatory_gate_b"])
        for c in CASES:
            w.writerow([c[0], c[1], c[2], c[3], c[4] if c[4] is not None else "", "yes" if c[5] else "no", "yes" if c[6] else "no"])
    print(f"plan written: {p} ({len(CASES)} cases, all NOT_RUN)")
    return p


def mark(camera, case, event, note="", out=None, now=None):
    if case not in {c[0] for c in CASES}:
        raise SystemExit(f"unknown case {case}")
    if event not in ("start", "end"):
        raise SystemExit("event must be start or end")
    rec = {"utc": _utc(now), "wall": time.time() if now is None else now, "case": case, "event": event, "note": note}
    with open(_dir(camera, out) / "actions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"{case} {event} at {rec['utc']}")
    return rec


def _source(args):
    from runtime.sources import make_source

    if args.file:
        return make_source({"type": "file", "path": args.file, "realtime": False}, args.camera), "harness self-test (file)"
    opts = {"type": "rtsp", "url": args.rtsp, "transport": args.transport}
    for k in ("username_env", "password_env"):
        if getattr(args, k):
            opts[k] = getattr(args, k)
    return make_source(opts, args.camera), "physical camera (rtsp)"


def probe(args, clock=time.time):
    """Read the source for args.seconds of wall time (or until a file ends), with reconnection, and record everything."""
    import cv2

    from inference.view_monitor import ViewMonitor
    from runtime.sources import SourceError

    d = _dir(args.camera, args.out)
    src, kind = _source(args)
    vm = ViewMonitor()
    log = open(d / "session.jsonl", "a", encoding="utf-8")

    def emit(rec):
        log.write(json.dumps({"utc": _utc(), "wall": clock(), **rec}) + "\n")
        log.flush()

    start = clock()
    emit({"type": "probe_start", "camera": args.camera, "source": src.describe(), "kind": kind, "seconds": args.seconds})
    frames, fails, reconnects, outages, gaps, sizes, pts = 0, 0, 0, [], [], set(), []
    last_frame_wall, down_since, connected = None, None, False
    deadline = start + args.seconds
    while clock() < deadline:
        if not connected:
            try:
                src.open()
                connected = True
                if down_since is not None:
                    outages.append(round(clock() - down_since, 3))
                    emit({"type": "reconnected", "outage_s": outages[-1]})
                    down_since = None
                emit({"type": "connected", "nominal_fps": src.fps})
            except SourceError as e:
                if getattr(e, "fatal", False):
                    emit({"type": "fatal", "error": str(e)})
                    break
                down_since = down_since or clock()
                emit({"type": "connect_failed", "error": str(e)})
                time.sleep(min(2.0, max(0.0, deadline - clock())))
                continue
        try:
            frame = src.read()
        except SourceError as e:
            fails += 1
            reconnects += 1
            connected = False
            down_since = clock()
            emit({"type": "read_failed", "error": str(e)})
            src.close()
            continue
        if frame is None:  # end of a file
            emit({"type": "end_of_source"})
            break
        now = clock()
        frames += 1
        sizes.add(f"{frame.shape[1]}x{frame.shape[0]}")
        if last_frame_wall is not None:
            gaps.append(now - last_frame_wall)
        last_frame_wall = now
        cap = getattr(src, "cap", None)
        if cap is not None:
            pts.append((now, cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0))
        t = (now - start) if kind.startswith("physical") else frames / (src.fps or 25.0)
        disc = src.take_discontinuity() or (len(gaps) > 0 and gaps[-1] > 2.0)
        if vm.due(t, disc):
            for tr in vm.observe(frame, t, disc):
                emit({"type": "view_transition", "t": round(t, 3), "from": tr.previous, "to": tr.state, "kind": tr.kind,
                      "cause": tr.cause, "reliable_t": tr.reliable_t})
        if args.pace and src.fps:
            time.sleep(max(0.0, 1.0 / src.fps - (clock() - now)))
    src.close()
    elapsed = clock() - start
    gs = sorted(gaps)
    drift = None
    if len(pts) > 10 and pts[-1][1] > pts[0][1]:
        drift = round(((pts[-1][1] - pts[0][1]) - (pts[-1][0] - pts[0][0])) / max(pts[-1][0] - pts[0][0], 1e-6) * 3600, 2)
    summary = {"camera": args.camera, "kind": kind, "source": src.describe(), "started_utc": _utc(start), "elapsed_s": round(elapsed, 1),
               "frames": frames, "resolutions": sorted(sizes), "nominal_fps": src.fps,
               "measured_fps": round(frames / elapsed, 2) if elapsed else None,
               "frame_interval_s": {"p50": round(statistics.median(gs), 4), "p95": round(gs[int(0.95 * (len(gs) - 1))], 4),
                                    "max": round(gs[-1], 4)} if gs else None,
               "read_failures": fails, "reconnects": reconnects, "outages_s": outages,
               "stream_clock_drift_s_per_hour": drift, "final_view_state": vm.state, "view_checks": vm.checks,
               "view_warnings": vm.warnings,
               "note": "Statistics only; no footage stored." + (" HARNESS SELF-TEST: not a camera acceptance result."
                                                                 if not kind.startswith("physical") else "")}
    emit({"type": "probe_end", **{k: summary[k] for k in ("frames", "elapsed_s", "final_view_state")}})
    log.close()
    (d / "probe_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary


def _read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []


def evaluate(camera, out=None):
    """Join physical-action marks with recorded view transitions. A case is PASS, FAIL, or NOT_RUN (no start mark).
    Stream cases are measured by the probe summary and need a human verdict (REVIEW); they are never auto-passed."""
    d = _dir(camera, out)
    cases = list(csv.DictReader(open(d / "test_cases.csv", encoding="utf-8")))
    actions, session = _read_jsonl(d / "actions.jsonl"), _read_jsonl(d / "session.jsonl")
    kinds = {r["kind"] for r in session if r["type"] == "probe_start"}
    self_test = not any(k.startswith("physical") for k in kinds)
    trans = [r for r in session if r["type"] == "view_transition"]
    rows = []
    for c in cases:
        starts = [a for a in actions if a["case"] == c["case"] and a["event"] == "start"]
        if not starts:
            rows.append({**c, "status": "NOT_RUN", "observed": "", "latency_s": "", "detail": "no physical action recorded"})
            continue
        s = starts[-1]["wall"]
        ends = [a["wall"] for a in actions if a["case"] == c["case"] and a["event"] == "end" and a["wall"] >= s]
        e = ends[0] if ends else None
        lim = float(c["max_latency_s"]) if c["max_latency_s"] else 30.0
        window = [r for r in trans if s <= r["wall"] <= (e if e else s) + lim]
        events = [r for r in window if r.get("kind")]
        first = events[0] if events else None
        exp = c["expected"]
        if exp == STREAM:
            status, observed, detail = "REVIEW", "", "measured in probe_summary.json and session.jsonl; a person decides"
        elif exp == NONE:
            status = "PASS" if not events else "FAIL"
            observed = first["kind"] if first else "no event"
            detail = f"{len(window)} transition(s), {len(events)} event(s) in the window"
        elif exp == WARN:
            status = "PASS" if not events else "FAIL"  # a warning is allowed; a relocation or blockage event is not
            observed = first["kind"] if first else "no event"
            detail = "warnings are in probe_summary.json view_warnings"
        else:
            want = BLOCK_KINDS if exp == BLOCK else CHANGE_KINDS
            hit = next((r for r in events if r["kind"] in want), None)
            observed = (hit or first or {}).get("kind") or "no event"
            lat = round(hit["wall"] - s, 2) if hit else None
            status = "PASS" if hit and lat <= lim else "FAIL"
            detail = f"latency {lat} s (limit {lim} s)" if hit else "expected event not recorded in the window"
            if hit and exp == BLOCK and e:
                rec = [r for r in trans if r["wall"] >= e and r["to"] == "VIEW_STABLE"]
                detail += f"; recovered to VIEW_STABLE {round(rec[0]['wall'] - e, 2)} s after removal" if rec else "; no recovery recorded"
            rows.append({**c, "status": status, "observed": observed, "latency_s": lat if lat is not None else "", "detail": detail})
            continue
        rows.append({**c, "status": status, "observed": observed, "latency_s": "", "detail": detail})
    with open(d / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    mandatory = [r for r in rows if r["mandatory_gate_b"] == "yes"]
    verdict = ("NOT STARTED: no probe recorded" if not kinds else
               "HARNESS SELF-TEST ONLY: not a camera acceptance result" if self_test else
               "INCOMPLETE" if any(r["status"] in ("NOT_RUN", "REVIEW") for r in mandatory) else
               "FAILED" if any(r["status"] == "FAIL" for r in mandatory) else "MANDATORY CASES PASSED")
    summary = {"camera": camera, "evaluated_utc": _utc(), "self_test": self_test, "verdict": verdict,
               "counts": {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "REVIEW", "NOT_RUN")},
               "mandatory_not_run": [r["case"] for r in mandatory if r["status"] == "NOT_RUN"]}
    (d / "acceptance_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["plan", "probe", "mark", "evaluate"])
    ap.add_argument("--camera", required=True)
    ap.add_argument("--out")
    ap.add_argument("--rtsp")
    ap.add_argument("--file", help="harness self-test only")
    ap.add_argument("--username-env")
    ap.add_argument("--password-env")
    ap.add_argument("--transport", default="tcp", choices=["tcp", "udp"])
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--pace", action="store_true", help="file self-test: replay at the file's frame rate")
    ap.add_argument("--case")
    ap.add_argument("--event", choices=["start", "end"])
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if a.command == "plan":
        plan(a.camera, a.out)
    elif a.command == "mark":
        mark(a.camera, a.case, a.event, a.note, a.out)
    elif a.command == "probe":
        if bool(a.rtsp) == bool(a.file):
            raise SystemExit("give exactly one of --rtsp or --file")
        probe(a)
    else:
        evaluate(a.camera, a.out)


if __name__ == "__main__":
    main()
