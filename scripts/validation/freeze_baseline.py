"""Engineering baseline record: what the code, model, configuration, labels and historical results were at a point in
time, so that a later milestone can prove it damaged none of them.

    python scripts/validation/freeze_baseline.py record [--tests "211 passed in 230 s"] [--out reports/validation/m3_baseline]
    python scripts/validation/freeze_baseline.py verify [--against reports/validation/m3_baseline/baseline_record.json]

`record` writes baseline_record.json and refuses to replace an existing one. It never opens the dashboard database
(logs/incidents/incidents.db): it records only the sizes and modification times of its files, because opening a WAL
database can write to it. `verify` re-hashes everything and lists what changed: protected artifacts (model, label sets
and locks, historical evaluation results, benchmarks) must be unchanged; new files are reported as additions. A
protected document that only gained a pointer note between `<!-- M3 note start -->` and `<!-- M3 note end -->` passes
if removing the note restores its recorded hash exactly.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "reports" / "validation" / "m3_baseline"
# Historical artifacts that no later milestone may change (verify fails if one does)
PROTECTED = ["models/best.pt", "models/model_config.yaml", "models/runtime_config.json", "reports/validation", "reports/runtime"]
PROTECTED_SKIP = ("reports/validation/m3_baseline/",)  # this record itself
CONFIGS = ["models/runtime_config.json", "inference/bytetrack_safesight.yaml", "config/runtime.demo.yaml",
           "config/runtime.demo_handheld.yaml", "config/runtime.example.yaml", "config/ppe_policy.example.json",
           "docs/product_research/17_ANNOTATION_PROTOCOL.md"]
DASHBOARD_DB = ROOT / "logs" / "incidents"


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def tree_hashes(paths) -> dict:
    out = {}
    for name in paths:
        p = ROOT / name
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file()) if p.exists() else []
        for f in files:
            r = rel(f)
            if not r.startswith(PROTECTED_SKIP) and "__pycache__" not in r:
                out[r] = sha(f)
    return out


def schema_fingerprint() -> dict:
    from database import database as d

    ddl = [d.SCHEMA, d.SESSIONS, d.ASSESSMENTS, *d.RUNTIME, *d.LIFECYCLE, *d.VIEW] + [getattr(d, "REVIEWS", "")]  # REVIEWS: M3
    ddl = [q for q in ddl if q]
    tables = [q.split("EXISTS", 1)[1].split("(", 1)[0].strip() for q in ddl]
    return {"tables": tables, "ddl_sha256": hashlib.sha256("\n".join(ddl).encode()).hexdigest().upper(),
            "versioning": "no PRAGMA user_version; additive CREATE TABLE IF NOT EXISTS only (the DDL hash is the version)"}


def label_locks() -> dict:
    from intelligence.annotations import verify_lock

    out = {}
    base = ROOT / "reports" / "validation" / "annotations"
    for lock in sorted(base.glob("*.lock.json")):
        name = lock.name[: -len(".lock.json")]
        try:
            m = verify_lock(base / name)
            out[name] = {"combined_sha256": m["combined_sha256"], "statuses": m["statuses"], "ground_truth": m["ground_truth"],
                         "verifies": True}
        except (ValueError, FileNotFoundError) as e:
            out[name] = {"verifies": False, "error": str(e)}
    return out


def policies() -> dict:
    from intelligence.risk import load_policy

    pol = load_policy()
    ppe = ROOT / "config" / "ppe_policy.json"
    ex = json.loads((ROOT / "config" / "ppe_policy.example.json").read_text(encoding="utf-8"))
    return {"risk_policy": {"version": pol["version"], "status": pol["status"]},
            "ppe_policy_in_use": "config/ppe_policy.json present" if ppe.exists() else "none (every PPE requirement is unconfigured)",
            "ppe_policy_example": {"version": ex.get("version"), "status": ex.get("status")}}


def benchmarks() -> dict:
    out = {}
    for p in sorted((ROOT / "reports" / "runtime").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[rel(p)] = {"sha256": sha(p), "created": d.get("created_utc") or d.get("created") or d.get("date")}
    return out


def dashboard_db() -> dict:
    return {p.name: {"bytes": p.stat().st_size, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
            for p in sorted(DASHBOARD_DB.glob("incidents.db*"))}


def model() -> dict:
    cfg = (ROOT / "models" / "model_config.yaml").read_text(encoding="utf-8")
    h = sha(ROOT / "models" / "best.pt")
    return {"file": "models/best.pt", "sha256": h, "matches_model_config": h in cfg.upper()}


def record(tests=None, out=OUT):
    out = Path(out)
    dest = out / "baseline_record.json"
    if dest.exists():
        raise SystemExit(f"{rel(dest)} exists; a baseline record is never replaced (choose another --out)")
    status = git("status", "--porcelain").splitlines()
    untracked = [ln[3:] for ln in status if ln.startswith("??")]
    rec = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "Reference baseline before milestone M3 (verified safety validation and pilot readiness)",
        "git": {"head": git("rev-parse", "HEAD").strip(), "branch": git("branch", "--show-current").strip(),
                "modified_tracked": [ln[3:] for ln in status if not ln.startswith("??")], "untracked": untracked,
                "tracked_diff_sha256": hashlib.sha256(git("diff", "HEAD").encode()).hexdigest().upper(),
                "note": "Uncommitted by design: the maintainer commits and pushes"},
        "model": model(),
        "tests": tests or "not recorded",
        "benchmarks": benchmarks(),
        "configuration": {"files": {c: sha(ROOT / c) for c in CONFIGS if (ROOT / c).exists()}, **policies()},
        "database_schema": schema_fingerprint(),
        "dashboard_database_files": dashboard_db(),
        "label_locks": label_locks(),
        "code_sha256": tree_hashes(["inference", "intelligence", "runtime", "database", "app", "scripts"]),
        "protected_sha256": tree_hashes(PROTECTED),
    }
    out.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(f"recorded {rel(dest)}: {len(rec['protected_sha256'])} protected files, model {rec['model']['sha256'][:8]}…, "
          f"{len(rec['label_locks'])} label locks")
    return rec


NOTE_START, NOTE_END = b"<!-- M3 note start -->", b"<!-- M3 note end -->\n"


def without_notes(data: bytes) -> bytes:
    """The file with every marked milestone note removed (marker lines included). A protected document may receive a
    pointer note between these markers; removing it must give back the original bytes exactly."""
    while NOTE_START in data and NOTE_END in data.split(NOTE_START, 1)[1]:
        head, rest = data.split(NOTE_START, 1)
        data = head + rest.split(NOTE_END, 1)[1]
    return data


def verify(against=OUT / "baseline_record.json") -> dict:
    rec = json.loads(Path(against).read_text(encoding="utf-8"))
    now = tree_hashes(PROTECTED)
    before = rec["protected_sha256"]
    changed = sorted(k for k in before if k in now and now[k] != before[k])
    noted = [k for k in changed if hashlib.sha256(without_notes((ROOT / k).read_bytes())).hexdigest().upper() == before[k]]
    changed = [k for k in changed if k not in noted]
    missing = sorted(set(before) - set(now))
    added = sorted(set(now) - set(before))
    locks = label_locks()
    res = {"model_unchanged": model()["sha256"] == rec["model"]["sha256"], "protected_changed": changed,
           "protected_with_marked_note_only": noted,
           "protected_missing": missing, "added": added,
           "label_locks_verify": {k: v["verifies"] for k, v in locks.items()},
           "label_locks_unchanged": all(locks.get(k, {}).get("combined_sha256") == v.get("combined_sha256")
                                        for k, v in rec["label_locks"].items()),
           "dashboard_database_unchanged": dashboard_db() == rec["dashboard_database_files"]}
    res["ok"] = res["model_unchanged"] and not changed and not missing and res["label_locks_unchanged"] and \
        res["dashboard_database_unchanged"]
    print(json.dumps(res, indent=1))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["record", "verify"])
    ap.add_argument("--tests", help="test result summary to store with the record, e.g. '211 passed in 230 s'")
    ap.add_argument("--out", help="folder for the record (default reports/validation/m3_baseline)")
    ap.add_argument("--against", help="record to verify against")
    a = ap.parse_args()
    if a.command == "record":
        record(a.tests, ROOT / a.out if a.out else OUT)
    else:
        sys.exit(0 if verify(ROOT / a.against if a.against else OUT / "baseline_record.json")["ok"] else 1)


if __name__ == "__main__":
    main()
