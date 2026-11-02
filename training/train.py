"""Reproducible YOLO training entry point with heartbeat and atomic, verified checkpoints.

Started by the watchdog (watchdog_svc/watchdog.py) so a crash can be resumed from the last good state:
    python training/train.py --exp NAME --config training/configs/NAME.yaml [--resume] [--batch N] [--workers N]
"""
import argparse
import json
import math
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
from ultralytics import YOLO  # noqa: E402
from ultralytics.utils import SETTINGS  # noqa: E402

SETTINGS.update({"sync": False})
BEAT_SECONDS = 15


def atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    for _ in range(20):  # a reader briefly holding the file makes os.replace fail on Windows
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)


def atomic_copy(src: Path, dst: Path) -> bool:
    """Copy src over dst only if the copy is a readable zip; the previous dst survives any failure."""
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copyfile(src, tmp)
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:
            tmp.unlink()
            return False
    os.replace(tmp, dst)
    return True


class Heartbeat:
    def __init__(self, exp_dir: Path, snapshot_every: int):
        self.path = exp_dir / "heartbeat.json"
        self.exp_dir = exp_dir
        self.snapshot_every = snapshot_every
        self.state = dict(pid=os.getpid(), status="starting", phase="setup", epoch=-1, epochs=0, batch=0,
                          batches=0, loss=None, nonfinite=0, last_good_epoch=-1)
        self.last = 0.0
        self.seen_batches = 0
        self.write()

    def write(self):
        self.state["time"] = time.time()
        atomic_json(self.path, self.state)
        self.last = time.time()

    def beat(self, **kw):
        self.state.update(kw)
        if time.time() - self.last >= BEAT_SECONDS:
            self.write()

    def on_train_start(self, t):
        self.state.update(status="running", phase="train", epochs=t.epochs, epoch=t.start_epoch)
        self.write()

    def on_train_batch_end(self, t):
        items = t.tloss.values() if isinstance(t.tloss, dict) else [t.tloss]
        loss = sum(float(v.sum()) for v in items if v is not None)
        bad = not math.isfinite(loss)
        self.state["nonfinite"] = self.state["nonfinite"] + 1 if bad else 0
        self.seen_batches = 0 if self.state["epoch"] != t.epoch else self.seen_batches + 1
        self.beat(phase="train", epoch=t.epoch, batch=self.seen_batches, batches=len(t.train_loader),
                  loss=None if bad else round(loss, 4))

    def on_val_batch_end(self, v):
        self.beat(phase="val")

    def on_fit_epoch_end(self, t):
        rec = {"epoch": t.epoch, "time": time.time(),
               "metrics": {k: round(float(v), 5) for k, v in (t.metrics or {}).items()},
               "fitness": None if t.fitness is None else round(float(t.fitness), 5),
               "best_fitness": None if t.best_fitness is None else round(float(t.best_fitness), 5)}
        with open(self.exp_dir / "epoch_metrics.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        self.beat(phase="save")

    def on_model_save(self, t):
        ckpts = self.exp_dir / "checkpoints"
        ckpts.mkdir(exist_ok=True)
        if atomic_copy(t.last, ckpts / "last_good.pt"):
            self.state["last_good_epoch"] = t.epoch
        if t.best_fitness == t.fitness and t.best.exists():
            atomic_copy(t.best, ckpts / "best_good.pt")
        if self.snapshot_every and (t.epoch + 1) % self.snapshot_every == 0:
            atomic_copy(t.last, ckpts / f"epoch{t.epoch + 1:03d}.pt")
        self.write()

    def on_train_end(self, t):
        self.state.update(status="completed", phase="done")
        self.write()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--batch", type=int)
    ap.add_argument("--workers", type=int)
    a = ap.parse_args()

    cfg = yaml.safe_load(Path(a.config).read_text())
    snapshot_every = cfg.pop("snapshot_every", 10)
    if a.batch:
        cfg["batch"] = a.batch
    if a.workers is not None:
        cfg["workers"] = a.workers
    project = ROOT / "runs"
    exp_dir = project / a.exp
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "config_used.yaml").write_text(yaml.safe_dump(cfg))

    last = exp_dir / "weights" / "last.pt"
    good = exp_dir / "checkpoints" / "last_good.pt"
    hb = Heartbeat(exp_dir, snapshot_every)
    if a.resume:
        if not good.exists():
            print("resume requested but no last_good.pt exists; starting fresh", flush=True)
            a.resume = False
        else:
            # A partly written last.pt is kept aside for diagnosis; only the verified copy is resumed.
            if last.exists() and not zipfile.is_zipfile(last):
                shutil.copyfile(last, exp_dir / f"last_corrupt_{int(time.time())}.pt")
            shutil.copyfile(good, last)

    if a.resume:
        model = YOLO(str(last))
        kw = {k: cfg[k] for k in ("batch", "workers") if k in cfg}
        register(model, hb)
        model.train(resume=True, data=cfg["data"], **kw)
    else:
        model = YOLO(cfg.pop("model"))
        register(model, hb)
        model.train(project=str(project), name=a.exp, exist_ok=True, **cfg)
    hb.state.update(status="completed", phase="done")
    hb.write()
    print("training finished", flush=True)


def guarded(fn):
    """Monitoring must never be the thing that kills a training run; the stale heartbeat will expose the fault."""
    def wrapper(obj):
        try:
            fn(obj)
        except Exception as e:
            print(f"heartbeat callback {fn.__name__} failed: {e!r}", flush=True)
    return wrapper


def register(model, hb):
    for ev in ("on_train_start", "on_train_batch_end", "on_val_batch_end", "on_fit_epoch_end",
               "on_model_save", "on_train_end"):
        model.add_callback(ev, guarded(getattr(hb, ev)))


if __name__ == "__main__":
    sys.exit(main())
