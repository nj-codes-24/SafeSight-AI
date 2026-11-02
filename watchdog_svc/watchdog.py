"""Independent training watchdog. Runs as its own process and survives the trainer dying, and vice versa.

Every --poll seconds: light check (process alive, heartbeat age, loss finite, disk/RAM/GPU).
Every --audit-interval seconds (default 2 h): full audit including checkpoint load and prediction test.
Failures are recovered from the last verified checkpoint with bounded retries and a fallback ladder.
Jobs come from runs/control/queue.json and run one at a time; state lives in runs/control/state.json,
so a restarted watchdog re-adopts a trainer that is still running.
"""
import argparse
import faulthandler
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watchdog_svc import health_checks as hc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FLAGS = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
# attempt -> (batch divisor, workers override). Consecutive failures walk down this ladder, then stop.
LADDER = [(1, None), (1, None), (2, None), (2, 2), (4, 0)]
MIN_DISK_GB = 5


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Watchdog:
    def __init__(self, a):
        self.a = a
        self.control = Path(a.control)
        self.control.mkdir(parents=True, exist_ok=True)
        self.logdir = Path(a.logdir)
        self.logdir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.control / "state.json"
        self.queue_path = self.control / "queue.json"
        self.state = self.load(self.state_path, {"job": None, "events": [], "manual_intervention": False})
        self.last_audit = 0.0
        self.last_audit_result = None

    @staticmethod
    def load(path, default):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return default

    def save(self):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        os.replace(tmp, self.state_path)

    def event(self, kind, msg, **kw):
        rec = {"time": now(), "kind": kind, "msg": msg, **kw}
        self.state["events"].append(rec)
        self.state["events"] = self.state["events"][-200:]
        with open(self.logdir / "events.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        self.save()

    # ---- job control ----------------------------------------------------------------------------------------
    def next_job(self):
        q = self.load(self.queue_path, [])
        if not q:
            return
        job = q.pop(0)
        tmp = self.queue_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(q, indent=1))
        os.replace(tmp, self.queue_path)
        job.update(status="pending", failures=0, restarts=0, start_epoch_at_launch=-1, pid=None, create_time=None)
        self.state["job"] = job
        self.event("job", f"accepted job {job['exp']}")
        self.launch(job, resume=False)

    def exp_dir(self, job):
        return Path(job.get("project", ROOT / "runs")) / job["exp"]

    def launch(self, job, resume):
        div, workers = LADDER[min(job["failures"], len(LADDER) - 1)]
        cmd = [str(Path(sys.executable).with_name("python.exe")), *job["cmd"]]
        if resume:
            cmd.append("--resume")
        if job.get("batch"):
            cmd += ["--batch", str(max(1, job["batch"] // div))]
        if workers is not None:
            cmd += ["--workers", str(workers)]
        log = self.logdir.parent / "training" / f"{job['exp']}_attempt{job['restarts']}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": "8"}
        with open(log, "ab") as f:
            p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT, env=env, creationflags=FLAGS)
        hb = hc.read_heartbeat(self.exp_dir(job)) or {}
        job.update(pid=p.pid, create_time=psutil.Process(p.pid).create_time(), status="running", log=str(log),
                   launched_at=time.time(), start_epoch_at_launch=hb.get("last_good_epoch", -1), cmd_used=cmd)
        self.event("launch", f"started {job['exp']} pid={p.pid} resume={resume} attempt={job['restarts']}", cmd=cmd)

    def recover(self, job, reason):
        """Record, kill anything left over, and restart from last_good.pt if retries remain."""
        hb = hc.read_heartbeat(self.exp_dir(job)) or {}
        errs = hc.log_tail_errors(Path(job.get("log", "")))
        progressed = hb.get("last_good_epoch", -1) > job.get("start_epoch_at_launch", -1)
        job["failures"] = 0 if progressed else job["failures"] + 1
        self.event("failure", reason, exp=job["exp"], failures=job["failures"], log_errors=errs,
                   last_good_epoch=hb.get("last_good_epoch"))
        hc.kill_tree(job.get("pid"))
        if job["failures"] >= len(LADDER):
            job["status"] = "failed"
            self.state["manual_intervention"] = True
            self.event("giveup", f"{job['exp']}: {job['failures']} consecutive failures, checkpoints preserved")
            self.finish(job)
            return
        job["restarts"] += 1
        time.sleep(self.a.restart_delay)
        self.launch(job, resume=True)
        self.event("recovery", f"{job['exp']} restarted from last good checkpoint", ladder_step=job["failures"],
                   resume_epoch=hb.get("last_good_epoch"))

    def finish(self, job):
        hist = self.load(self.control / "history.json", [])
        hist.append({k: job.get(k) for k in ("exp", "status", "restarts", "failures")} | {"time": now()})
        (self.control / "history.json").write_text(json.dumps(hist, indent=1))
        self.state["job"] = None
        self.save()

    # ---- checks ---------------------------------------------------------------------------------------------
    def check_job(self):
        job = self.state.get("job")
        if not job:
            return
        hb = hc.read_heartbeat(self.exp_dir(job)) or {}
        alive = hc.process_status(job["pid"], job["create_time"]) == "alive"
        # job["pid"] is the venv launcher; the heartbeat carries its child's pid, so match on time, not pid.
        fresh = hb.get("time", 0) >= job["launched_at"]
        if hb.get("status") == "completed" and fresh and not alive:
            job["status"] = "completed"
            self.event("complete", f"{job['exp']} finished", epoch=hb.get("epoch"))
            self.write_report("job_complete")
            self.finish(job)
        elif not alive:
            self.recover(job, f"process {job['pid']} dead (heartbeat status={hb.get('status')})")
        elif not fresh:
            if time.time() - job["launched_at"] > self.a.start_grace:
                self.recover(job, "no heartbeat from trainer after start grace period")
        elif hb.get("nonfinite", 0) >= self.a.nan_limit:
            self.recover(job, f"loss non-finite for {hb['nonfinite']} consecutive batches")
        elif hb.get("status") != "completed" and time.time() - hb.get("time", 0) > self.a.stall:
            self.recover(job, f"stalled: heartbeat {time.time() - hb['time']:.0f}s old in phase {hb.get('phase')}, "
                              f"epoch {hb.get('epoch')} batch {hb.get('batch')}")

    def write_report(self, trigger):
        job = self.state.get("job")
        exp = self.exp_dir(job) if job else None
        hb = hc.read_heartbeat(exp) if exp else None
        ck = exp / "checkpoints" if exp else None
        rep = {
            "generated": now(), "trigger": trigger, "watchdog_pid": os.getpid(),
            "training_status": job.get("status") if job else "idle", "experiment": job.get("exp") if job else None,
            "trainer_pid": job.get("pid") if job else None,
            "process": hc.process_status(job["pid"], job["create_time"]) if job else None,
            "heartbeat": hb, "heartbeat_age_s": round(time.time() - hb["time"]) if hb else None,
            "last_good": hc.checkpoint_ok(ck / "last_good.pt") if ck else None,
            "best_good": hc.checkpoint_ok(ck / "best_good.pt") if ck else None,
            "metrics": hc.results_summary(exp) if exp else {},
            "gpu": hc.gpu_stats(), "system": hc.system_stats(ROOT),
            "log_bytes": Path(job["log"]).stat().st_size if job and Path(job.get("log", "")).exists() else None,
            "model_audit": self.last_audit_result,
            "recent_events": self.state["events"][-10:],
            "recoveries_attempted": job.get("restarts") if job else 0,
            "manual_intervention_needed": self.state.get("manual_intervention", False),
        }
        problems = []
        if rep["system"]["disk_free_gb"] < MIN_DISK_GB:
            problems.append("low disk")
            self.state["manual_intervention"] = True
        if rep["system"]["ram_free_gb"] < 2:
            problems.append("low RAM")
        if not rep["gpu"].get("ok"):
            problems.append(f"GPU query failed: {rep['gpu'].get('error')}")
        elif rep["gpu"]["temp_c"] > 90:
            problems.append("GPU over 90C")
        if rep["metrics"].get("regression"):
            problems.append("validation mAP regressed over 40% from best")
        if rep["metrics"].get("metrics_finite") is False:
            problems.append("non-finite validation metrics")
        if self.last_audit_result and not self.last_audit_result.get("ok"):
            problems.append("model audit failed")
        rep["problems"] = problems
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        if trigger != "light":
            (self.logdir / f"health_report_{stamp}.json").write_text(json.dumps(rep, indent=1))
        self.write_summary(rep)
        return rep

    def write_summary(self, r):
        hb = r["heartbeat"] or {}
        m = r["metrics"] or {}
        g, s = r["gpu"], r["system"]
        lines = [
            f"SafeSight AI watchdog health summary - {r['generated']} ({r['trigger']})",
            f"Watchdog PID        : {r['watchdog_pid']}",
            f"Training status     : {r['training_status']} [{r['experiment']}] process={r['process']}",
            f"Epoch               : {hb.get('epoch')}/{hb.get('epochs')} batch {hb.get('batch')}/{hb.get('batches')} "
            f"phase={hb.get('phase')} loss={hb.get('loss')}",
            f"Last heartbeat      : {r['heartbeat_age_s']}s ago",
            f"Last good checkpoint: {r['last_good']} (epoch {hb.get('last_good_epoch')})",
            f"Best validation     : mAP50={m.get('best_mAP50')} mAP50-95={m.get('best_mAP50_95')}",
            f"GPU                 : {g.get('util_pct')}% {g.get('mem_used_mb')}/{g.get('mem_total_mb')} MB "
            f"{g.get('temp_c')}C ok={g.get('ok')}",
            f"RAM / disk          : {s['ram_free_gb']} GB free / {s['disk_free_gb']} GB free, CPU {s['cpu_pct']}%",
            f"Last model audit    : {r['model_audit']}",
            f"Recoveries attempted: {r['recoveries_attempted']}",
            f"Problems            : {r['problems'] or 'none'}",
            f"Manual intervention : {'YES' if r['manual_intervention_needed'] else 'no'}",
        ]
        tmp = self.logdir / "latest_health_report.tmp"
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.logdir / "latest_health_report.txt")

    def full_audit(self):
        job = self.state.get("job")
        self.last_audit_result = None
        if job and job.get("data"):
            ck = self.exp_dir(job) / "checkpoints" / "last_good.pt"
            if ck.exists():
                try:
                    r = subprocess.run([sys.executable, str(ROOT / "watchdog_svc" / "deep_audit.py"), str(ck), job["data"]],
                                       capture_output=True, text=True, timeout=600, cwd=str(ROOT),
                                       env={**os.environ, "CUDA_VISIBLE_DEVICES": ""}, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.last_audit_result = json.loads(r.stdout.strip().splitlines()[-1])
                except Exception as e:
                    self.last_audit_result = {"ok": False, "error": repr(e)}
        rep = self.write_report("two_hour_audit")
        self.event("audit", "full health audit complete", problems=rep["problems"])

    def run(self):
        self.event("watchdog", f"watchdog started pid={os.getpid()}")
        (self.control / "watchdog.pid").write_text(str(os.getpid()))
        while True:
            try:
                if not self.state.get("job"):
                    self.next_job()
                self.check_job()
                self.write_report("light")
                if time.time() - self.last_audit >= self.a.audit_interval:
                    self.last_audit = time.time()
                    self.full_audit()
                self.save()
            except Exception as e:  # the watchdog itself must never die from one bad check
                self.event("watchdog_error", repr(e))
            (self.control / "watchdog.alive").write_text(str(time.time()))
            if (self.control / "stop").exists():
                (self.control / "stop").unlink()
                self.event("watchdog", "stop requested; trainer left running")
                return
            time.sleep(self.a.poll)


def detach_from_console():
    """Console control events once killed a cmd-hosted watchdog, so run console-less and ignore them."""
    for name in ("SIGINT", "SIGBREAK"):
        signal.signal(getattr(signal, name), signal.SIG_IGN)
    if sys.stdout is None:  # pythonw has no stdio
        log = open(ROOT / "logs" / "watchdog" / "watchdog_stdout.log", "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = log
        faulthandler.enable(log)


if __name__ == "__main__":
    detach_from_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", default=str(ROOT / "runs" / "control"))
    ap.add_argument("--logdir", default=str(ROOT / "logs" / "watchdog"))
    ap.add_argument("--poll", type=float, default=60)
    ap.add_argument("--audit-interval", type=float, default=7200)
    ap.add_argument("--stall", type=float, default=600)
    ap.add_argument("--start-grace", type=float, default=900)
    ap.add_argument("--nan-limit", type=int, default=50)
    ap.add_argument("--restart-delay", type=float, default=10)
    Watchdog(ap.parse_args()).run()
