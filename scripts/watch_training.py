"""Live training view: python watch_training.py   (read-only, Ctrl+C to quit; training is not affected)."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from watchdog_svc import health_checks as hc  # noqa: E402

CONTROL = ROOT / "runs" / "control"


def load(p, default):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def bar(done, total, width=30):
    frac = done / total if total else 0
    fill = int(frac * width)
    return "#" * fill + "-" * (width - fill) + f" {100 * frac:3.0f}%"


def epoch_rows(exp_dir, n=6):
    p = exp_dir / "epoch_metrics.jsonl"
    if not p.exists():
        return [], {}
    by_epoch = {}
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
            by_epoch[r["epoch"]] = r  # a resumed run may repeat an epoch; keep the latest
        except ValueError:
            pass
    rows = [by_epoch[k] for k in sorted(by_epoch)]
    return rows[-n:], by_epoch


def render():
    job = load(CONTROL / "state.json", {}).get("job")
    queue = load(CONTROL / "queue.json", [])
    out = [f"SafeSight AI - live training monitor   {time.strftime('%H:%M:%S')}   (Ctrl+C to quit)", ""]
    if not job:
        out.append("No training running." + (f" Queued: {', '.join(j['exp'] for j in queue)}" if queue else ""))
    else:
        exp = Path(job.get("project", ROOT / "runs")) / job["exp"]
        hb = hc.read_heartbeat(exp) or {}
        age = time.time() - hb.get("time", 0)
        epoch, epochs = hb.get("epoch", -1) + 1, hb.get("epochs", 0)
        rows, all_rows = epoch_rows(exp)
        best = max(all_rows.values(), key=lambda r: r["fitness"] or 0, default=None)
        out += [f"Experiment : {job['exp']}   restarts: {job.get('restarts', 0)}",
                f"Epoch      : {epoch}/{epochs}  {bar(epoch, epochs)}",
                f"Batch      : {hb.get('batch', 0)}/{hb.get('batches', 0)}  {bar(hb.get('batch', 0), hb.get('batches', 0))}",
                f"Phase      : {hb.get('phase')}    Train loss: {hb.get('loss')}    Heartbeat: {age:.0f}s ago"]
        if len(rows) >= 2:
            per = (rows[-1]["time"] - rows[0]["time"]) / max(rows[-1]["epoch"] - rows[0]["epoch"], 1)
            out.append(f"Speed      : {per:.0f}s per epoch, at most {per * (epochs - epoch) / 60:.0f} min left (early stopping may end it sooner)")
        if best:
            m = best["metrics"]
            out.append(f"Best so far: epoch {best['epoch'] + 1}  mAP50={m.get('metrics/mAP50(B)')}  mAP50-95={m.get('metrics/mAP50-95(B)')}")
        out += ["", " epoch   mAP50   mAP50-95  precision  recall"]
        for r in rows:
            m = r["metrics"]
            out.append(f" {r['epoch'] + 1:5d}  {m.get('metrics/mAP50(B)', 0):.3f}   {m.get('metrics/mAP50-95(B)', 0):.3f}     "
                       f"{m.get('metrics/precision(B)', 0):.3f}      {m.get('metrics/recall(B)', 0):.3f}")
        if queue:
            out += ["", f"Queued next: {', '.join(j['exp'] for j in queue)}"]
    g = hc.gpu_stats()
    if g.get("ok"):
        out += ["", f"GPU {g['util_pct']:.0f}%  {g['mem_used_mb']:.0f}/{g['mem_total_mb']:.0f} MB  {g['temp_c']:.0f}C"]
    return "\n".join(out)


if __name__ == "__main__":
    try:
        while True:
            text = render()
            os.system("cls" if os.name == "nt" else "clear")
            print(text, flush=True)
            time.sleep(3)
    except KeyboardInterrupt:
        pass
