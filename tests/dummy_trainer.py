"""Fake trainer for watchdog drills. Writes the same heartbeat as training/train.py, then misbehaves on request."""
import argparse
import json
import os
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--mode", choices=["ok", "crash", "stall", "nan", "silent"], required=True)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--batch", type=int)
ap.add_argument("--workers", type=int)
a = ap.parse_args()
d = Path(a.dir)
d.mkdir(parents=True, exist_ok=True)
with open(d / "launches.jsonl", "a") as f:
    f.write(json.dumps({"resume": a.resume, "batch": a.batch, "workers": a.workers}) + "\n")
launches = sum(1 for _ in open(d / "launches.jsonl"))
misbehave = launches == 1 or a.mode == "crash"  # recover on the 2nd launch, except 'crash' which always fails


def beat(status="running", epoch=0, nonfinite=0):
    tmp = d / "hb.tmp"
    tmp.write_text(json.dumps(dict(pid=os.getpid(), status=status, phase="train", epoch=epoch, epochs=3, batch=1, batches=5,
                                   loss=0.5, nonfinite=nonfinite, last_good_epoch=epoch - 1, time=time.time())))
    os.replace(tmp, d / "heartbeat.json")


if misbehave and a.mode == "silent":
    time.sleep(600)
beat()
if misbehave and a.mode == "crash":
    raise SystemExit(1)
if misbehave and a.mode == "stall":
    time.sleep(600)
if misbehave and a.mode == "nan":
    beat(nonfinite=100)
    time.sleep(600)
for e in range(3):
    beat(epoch=e)
    time.sleep(1)
beat("completed", 2)
