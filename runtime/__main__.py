"""Command line for the headless runtime.

    python -m runtime run --config config/runtime.demo.yaml          monitor until Ctrl+C (or SIGTERM)
    python -m runtime validate --config config/runtime.example.yaml  check a configuration without starting anything
    python -m runtime status --config config/runtime.demo.yaml       show camera health from the status file
    python -m runtime view list --config ...                          camera view revisions, events and commands
    python -m runtime view accept --config ... --camera ID --revision N --by NAME [--zones-reviewed]
    python -m runtime view verify-zones --config ... --camera ID --by NAME
    python -m runtime view acknowledge --config ... --camera ID --event VE-... --by NAME
    python -m runtime incident list --config ... [--camera ID]          incidents with lifecycle end and review status
    python -m runtime incident review --config ... --incident INC-... --status REVIEWED|FALSE_ALARM --by NAME [--note ...]

View commands are recorded in the runtime database and applied by the running camera worker within about a second
(or when the runtime next starts); the result is recorded with the command.

Exit codes: 0 clean shutdown, 1 unexpected failure, 2 invalid configuration, 3 startup failure (for example weights).
"""
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
os.environ.setdefault("YOLO_OFFLINE", "true")  # the runtime never contacts the internet

from runtime import config as rconfig  # noqa: E402
from runtime import logs  # noqa: E402


def _run(args) -> int:
    try:
        cfg = rconfig.load(args.config)
    except rconfig.ConfigError as e:
        print(f"invalid configuration: {e}", file=sys.stderr)
        return 2
    log = logs.setup(cfg.log_file, cfg.log_level)
    from runtime.service import Runtime

    rt = Runtime(cfg)
    signals = {"n": 0}

    def on_signal(signum, frame):
        signals["n"] += 1
        if signals["n"] > 1:
            log.error("second stop signal: exiting immediately")
            os._exit(130)
        log.info("stop signal %s received", signal.Signals(signum).name)
        rt.stop_requested.set()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), on_signal)
    try:
        rt.start()
    except Exception as e:
        log.error("startup failed: %s", e)
        rt.stop()
        return 3
    try:
        rt.wait(exit_when_done=args.exit_when_done, duration=args.duration)
    except Exception:
        log.exception("runtime failed")
        rt.stop()
        return 1
    stuck = rt.stop()
    return 1 if stuck else 0


def _validate(args) -> int:
    try:
        cfg = rconfig.load(args.config)
    except rconfig.ConfigError as e:
        print(f"invalid configuration: {e}", file=sys.stderr)
        return 2
    from runtime.sources import make_source

    print(f"configuration OK: {len(cfg.cameras)} camera(s), {cfg.inference.backend} inference, database {cfg.database}")
    if cfg.inference.backend != "null" and not cfg.inference.weights.exists():
        print(f"  warning: model weights not found at {cfg.inference.weights}")
    for c in cfg.cameras:
        src = make_source(c.source, c.id)
        notes = []
        if c.source["type"] == "file" and not src.path.exists():
            notes.append("file not found")
        for k in ("username_env", "password_env"):
            if c.source.get(k) and c.source[k] not in os.environ:
                notes.append(f"environment variable {c.source[k]} not set")
        if c.overrides.get("no_helmet_conf", rconfig.VALIDATED_NO_HELMET) != rconfig.VALIDATED_NO_HELMET:
            notes.append(f"no_helmet_conf {c.overrides['no_helmet_conf']} differs from the validated {rconfig.VALIDATED_NO_HELMET}")
        view = "off" if not c.view.enabled else "on" if c.view.geometry else "blockage-only"
        print(f"  {c.id:<16} {'enabled ' if c.enabled else 'disabled'} site={c.site or '-':<10} {src.describe():<40} "
              f"zones={len(c.zones)} max_fps={c.processing.max_fps} view={view}" + (f"  [{'; '.join(notes)}]" if notes else ""))
    return 0


def _status(args) -> int:
    path = Path(args.status_file) if args.status_file else rconfig.load(args.config).status_file
    if not path.exists():
        print(f"no status file at {path}: the runtime has not run with this configuration")
        return 1
    s = json.loads(path.read_text(encoding="utf-8"))
    rt = s["runtime"]
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(rt["updated_utc"])).total_seconds()
    import psutil

    alive = psutil.pid_exists(rt["pid"])
    stale = rt["state"] == "running" and (not alive or age > 3 * rt["status_interval_s"])
    head = "NOT RUNNING (stale status)" if stale else rt["state"].upper()
    policy = rt.get("risk_policy") or {}
    print(f"runtime {head} · pid {rt['pid']} · updated {age:.0f} s ago · inference {(rt['inference'] or {}).get('mode')} · "
          f"risk policy {policy.get('version', 'not loaded')} ({policy.get('status', '-')})")
    for cid, c in s["cameras"].items():
        mon = "NO (runtime not running)" if stale else c["monitoring"]
        f = c.get("frames", {})
        view = (c.get("view") or {}).get("state", "-")
        print(f"  {cid:<16} {c['state']:<12} view={view:<22} monitoring={mon:<8} processed {c.get('processed_fps', 0):>5} FPS  "
              f"dropped {f.get('dropped_backpressure', 0):>5}  incidents {c.get('incidents_opened', 0):>3}  "
              f"{c.get('reason') or ''}")
    print(rt["note"])
    return 1 if stale else 0


def _view(args) -> int:
    try:
        cfg = rconfig.load(args.config)
    except rconfig.ConfigError as e:
        print(f"invalid configuration: {e}", file=sys.stderr)
        return 2
    from database.database import IncidentDB

    if args.action != "list" and (not args.camera or not args.by):
        print("--camera and --by are required", file=sys.stderr)
        return 2
    if args.camera and args.camera not in {c.id for c in cfg.cameras}:
        print(f"no camera '{args.camera}' in the configuration", file=sys.stderr)
        return 2
    db = IncidentDB(cfg.database)
    try:
        if args.action == "list":
            for r in db.view_revisions(args.camera):
                print(f"revision {r['camera_id']}#{r['revision']:<3} {r['status']:<10} zones {r['zones_status'] or '-':<15} "
                      f"{r['created_utc']}  {r['basis']}" + (f" (event {r['source_event']})" if r["source_event"] else ""))
            for e in db.view_events(args.camera):
                print(f"event    {e['event_id']} {e['event_type']:<22} {e['state']:<16} confirmed {e['confirmed_utc']} "
                      f"recovered {e['recovered_utc'] or '-'}  incidents ended {len(e['affected_incidents'] or [])}  "
                      f"{'acknowledged' if e['acknowledged'] else 'NOT acknowledged'}  {e['outcome'] or ''}")
                for k, p in (e["snapshots"] or {}).items():
                    print(f"           {k:<14} {p}")
            for c in db.view_commands(args.camera):
                print(f"command  {c['command_id']} {c['camera_id']} {c['command']} by {c['requested_by']} at {c['requested_utc']}: "
                      f"{c['result'] or 'pending'}")
            return 0
        if args.action == "accept" and args.revision is None:
            print("--revision is required (python -m runtime view list shows the candidates)", file=sys.stderr)
            return 2
        if args.action == "acknowledge" and not args.event:
            print("--event is required", file=sys.stderr)
            return 2
        cid = db.add_view_command(args.camera, args.action, args.by, args.revision, args.event, args.zones_reviewed, args.note)
        print(f"command {cid} recorded; the camera worker applies it within about a second (or at the next start). "
              f"Check the result with: python -m runtime view list --config {args.config}")
        return 0
    finally:
        db.close()


def _incident(args) -> int:
    """Operator acknowledgement for headless sites: the decision goes to incidents.status and the audit trail
    (incident_reviews), exactly as the dashboard's review control does, but with a required reviewer."""
    try:
        cfg = rconfig.load(args.config)
    except rconfig.ConfigError as e:
        print(f"invalid configuration: {e}", file=sys.stderr)
        return 2
    from database.database import IncidentDB

    db = IncidentDB(cfg.database)
    try:
        if args.action == "list":
            life = {r["incident_id"]: r for r in db.conn.execute("SELECT incident_id, end_reason, classification "
                                                                 "FROM incident_lifecycle")}
            for r in db.rows():
                if args.camera and r["camera_id"] != args.camera:
                    continue
                lr = life.get(r["incident_id"], {})
                end = lr["end_reason"] if lr else None
                print(f"{r['incident_id']} {r['camera_id']:<14} {r['incident_type']:<15} {r['started_at']}  "
                      f"{(lr['classification'] if lr else '-') or '-':<16} end={end or ('open' if not r['ended_at'] else '-'):<22} "
                      f"status={r['status']}")
            return 0
        if not (args.incident and args.status and args.by):
            print("--incident, --status and --by are required", file=sys.stderr)
            return 2
        try:
            db.set_status(args.incident, args.status, reviewer=args.by, note=args.note, source="runtime-cli")
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"{args.incident}: {args.status} by {args.by} recorded")
        return 0
    finally:
        db.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m runtime", description="SafeSight headless multi-camera runtime")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="monitor the configured cameras until stopped")
    r.add_argument("--config", required=True)
    r.add_argument("--exit-when-done", action="store_true", help="exit when every camera has finished (finite files)")
    r.add_argument("--duration", type=float, help="stop after this many seconds")
    v = sub.add_parser("validate", help="check a configuration")
    v.add_argument("--config", required=True)
    st = sub.add_parser("status", help="print camera health from the status file")
    g = st.add_mutually_exclusive_group(required=True)
    g.add_argument("--config")
    g.add_argument("--status-file")
    vw = sub.add_parser("view", help="camera view revisions and events; operator revalidation")
    vw.add_argument("action", choices=["list", "accept", "verify-zones", "acknowledge"])
    vw.add_argument("--config", required=True)
    vw.add_argument("--camera")
    vw.add_argument("--revision", type=int, help="accept: the candidate revision to make the camera's reference")
    vw.add_argument("--event", help="acknowledge: the view event ID")
    vw.add_argument("--by", help="who decided (recorded)")
    vw.add_argument("--zones-reviewed", action="store_true",
                    help="accept: the zones were checked against the new view (otherwise they wait for verify-zones)")
    vw.add_argument("--note")
    inc = sub.add_parser("incident", help="list incidents; record an operator's review decision (audited)")
    inc.add_argument("action", choices=["list", "review"])
    inc.add_argument("--config", required=True)
    inc.add_argument("--camera")
    inc.add_argument("--incident")
    inc.add_argument("--status", choices=["REVIEWED", "FALSE_ALARM"])
    inc.add_argument("--by", help="who decided (recorded)")
    inc.add_argument("--note")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    code = {"run": _run, "validate": _validate, "status": _status, "view": _view, "incident": _incident}[args.cmd](args)
    if args.cmd == "run":
        logs.get().info("exit code %d after %.1f s", code, time.monotonic() - t0)
    return code


if __name__ == "__main__":
    sys.exit(main())
