"""SQLite incident store. Incidents are append-only; only status and end time change after creation."""
import csv
import io
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "logs" / "incidents" / "incidents.db"
COLUMNS = ["incident_id", "started_at", "ended_at", "incident_type", "worker_id", "confidence", "camera_id",
           "session_id", "zone", "video_time_s", "evidence_path", "status"]
SCHEMA = """CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, incident_type TEXT NOT NULL,
    worker_id INTEGER NOT NULL, confidence REAL, camera_id TEXT, session_id TEXT NOT NULL, zone TEXT,
    video_time_s REAL, evidence_path TEXT, status TEXT NOT NULL DEFAULT 'OPEN')"""


SESSIONS = """CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, source TEXT, frames INTEGER, unique_workers INTEGER,
    compliant INTEGER, violation INTEGER, uncertain INTEGER, avg_fps REAL)"""

# One risk assessment per incident (intelligence/risk.py), kept apart so the incidents table and CSV stay unchanged.
ASSESSMENTS = """CREATE TABLE IF NOT EXISTS risk_assessments (
    incident_id TEXT PRIMARY KEY, hazard_code TEXT NOT NULL, severity INTEGER NOT NULL, exposure_s REAL, exposure_band INTEGER,
    risk_level TEXT NOT NULL, evidence TEXT, requires_review INTEGER, actions TEXT, factors TEXT, policy_version TEXT,
    policy_status TEXT, escalated_at_s REAL, updated_at TEXT NOT NULL)"""

# Headless runtime (runtime/): who produced each session and incident, in UTC, and when a camera was not monitoring.
# Additive tables; the dashboard does not need them. A worker's identity is (camera_id, session_id, worker_id).
RUNTIME = ["""CREATE TABLE IF NOT EXISTS runtime_sessions (
    session_id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, camera_name TEXT, site_id TEXT, source_type TEXT, source TEXT,
    started_utc TEXT NOT NULL, ended_utc TEXT, end_reason TEXT, frames_read INTEGER, frames_processed INTEGER,
    frames_skipped INTEGER, frames_dropped INTEGER, reconnects INTEGER, policy_version TEXT, policy_status TEXT)""",
           """CREATE TABLE IF NOT EXISTS incident_context (
    incident_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, camera_id TEXT NOT NULL, site_id TEXT, worker_ref TEXT,
    opened_utc TEXT NOT NULL, closed_utc TEXT, opened_t REAL, closed_t REAL)""",
           """CREATE TABLE IF NOT EXISTS camera_outages (
    outage_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, camera_id TEXT NOT NULL, started_utc TEXT NOT NULL,
    ended_utc TEXT, reason TEXT)"""]

# Incident lifecycle (inference/incident_lifecycle.py). Additive: the incidents table keeps its meaning for the dashboard.
# incident_lifecycle: detector-level state, why it ended, observed vs unobserved time, PPE classification and requirement.
# incident_events: append-only audit of every lifecycle and grouping decision. alert_groups: incidents believed to be one
# worker's one violation (operator level). notifications: what an operator would be notified of (bursts batched).
# ppe_observations: worker-seconds per PPE category per session. Video times are seconds on the camera's clock.
LIFECYCLE = ["""CREATE TABLE IF NOT EXISTS incident_lifecycle (
    incident_id TEXT PRIMARY KEY, group_id TEXT NOT NULL, session_id TEXT NOT NULL, camera_id TEXT, incident_type TEXT,
    zone TEXT, tracks TEXT, state TEXT NOT NULL, end_reason TEXT, classification TEXT, requirement TEXT, opened_t REAL,
    last_observed_t REAL, ended_t REAL, closed_t REAL, observed_s REAL, unobserved_s REAL, exposure_s REAL, relation TEXT,
    linked_to TEXT, path TEXT, updated_at TEXT NOT NULL)""",
             """CREATE TABLE IF NOT EXISTS incident_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, incident_id TEXT, group_id TEXT,
    event TEXT NOT NULL, video_t REAL, track_id INTEGER, detail TEXT, recorded_at TEXT NOT NULL)""",
             """CREATE TABLE IF NOT EXISTS alert_groups (
    group_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, camera_id TEXT, incident_type TEXT, zone TEXT, classification TEXT,
    state TEXT NOT NULL, first_t REAL, last_t REAL, exposure_s REAL, observed_s REAL, reobserved_s REAL, incidents TEXT,
    risk_level TEXT, notification_id TEXT, updated_at TEXT NOT NULL)""",
             """CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, camera_id TEXT, incident_type TEXT, kind TEXT NOT NULL,
    classification TEXT, created_t REAL, group_ids TEXT, incident_ids TEXT, count INTEGER, updated_at TEXT NOT NULL)""",
             """CREATE TABLE IF NOT EXISTS ppe_observations (
    session_id TEXT NOT NULL, camera_id TEXT, category TEXT NOT NULL, worker_seconds REAL, tracks INTEGER,
    PRIMARY KEY (session_id, category))"""]


# Camera view monitoring (inference/view_monitor.py, runtime/view.py). Additive, operational records kept apart from worker
# safety incidents. camera_view_revisions: each reference view a camera has had (the fingerprint is a small grey PNG),
# which one is active, and whether its zone geometry was verified; old revisions are never deleted. camera_view_events:
# one row per confirmed view change, scene switch or blockage, with the incidents it interrupted. camera_view_commands:
# operator decisions (accept a view, verify zones, acknowledge an event), applied by the running camera worker.
VIEW = ["""CREATE TABLE IF NOT EXISTS camera_view_revisions (
    camera_id TEXT NOT NULL, revision INTEGER NOT NULL, status TEXT NOT NULL, fingerprint BLOB NOT NULL, width INTEGER,
    height INTEGER, created_utc TEXT NOT NULL, basis TEXT, established_by TEXT, session_id TEXT, source_event TEXT,
    zones_hash TEXT, zones_status TEXT, zones_verified_by TEXT, zones_verified_utc TEXT, updated_at TEXT NOT NULL,
    PRIMARY KEY (camera_id, revision))""",
        """CREATE TABLE IF NOT EXISTS camera_view_events (
    event_id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, site_id TEXT, session_id TEXT NOT NULL, event_type TEXT NOT NULL,
    cause TEXT, state TEXT NOT NULL, previous_revision INTEGER, candidate_revision INTEGER, accepted_revision INTEGER,
    first_suspected_t REAL, first_suspected_utc TEXT, last_reliable_t REAL, last_reliable_utc TEXT, confirmed_t REAL,
    confirmed_utc TEXT, recovered_t REAL, recovered_utc TEXT, outcome TEXT, evidence_quality TEXT, evidence TEXT,
    affected_incidents TEXT, snapshots TEXT, linked_event TEXT, acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT, acknowledged_utc TEXT, updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS camera_view_commands (
    command_id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT NOT NULL, command TEXT NOT NULL, revision INTEGER,
    event_id TEXT, zones_reviewed INTEGER, requested_by TEXT NOT NULL, note TEXT, requested_utc TEXT NOT NULL,
    applied_utc TEXT, result TEXT)"""]


# Operator decisions on incidents (milestone M3): append-only, one row per status change, with who decided, when and
# why. incidents.status keeps the current decision for the dashboard; this table is the audit trail behind it.
REVIEWS = """CREATE TABLE IF NOT EXISTS incident_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, previous_status TEXT, status TEXT NOT NULL,
    reviewer TEXT, note TEXT, source TEXT, reviewed_utc TEXT NOT NULL)"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class IncidentDB:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Switching a new database to WAL ignores the busy timeout: when several cameras open it at the same moment, all
        # but one can get "database is locked" at once. The mode is persistent, so a short retry always succeeds.
        for attempt in range(100):
            try:
                self.conn.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as e:
                if "locked" not in str(e) or attempt == 99:
                    raise
                time.sleep(0.02)
        self.conn.execute(SCHEMA)
        self.conn.execute(SESSIONS)
        self.conn.execute(ASSESSMENTS)
        for q in RUNTIME + LIFECYCLE + VIEW + [REVIEWS]:
            self.conn.execute(q)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def save_session(self, session_id, source, frames, unique_workers, compliant, violation, uncertain, avg_fps):
        self.conn.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                          (session_id, datetime.now().isoformat(timespec="seconds"), source, frames, unique_workers,
                           compliant, violation, uncertain, avg_fps))
        self.conn.commit()

    def sessions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM sessions ORDER BY started_at")]

    def add(self, incident_type, worker_id, confidence, camera_id, session_id, zone=None, video_time_s=None,
            evidence_path=None) -> str:
        for attempt in range(5):  # 32 random bits per day can collide on a busy multi-camera site: retry, never lose it
            iid = f"INC-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
            try:
                self.conn.execute(
                    "INSERT INTO incidents (incident_id, started_at, incident_type, worker_id, confidence, camera_id, "
                    "session_id, zone, video_time_s, evidence_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (iid, datetime.now().isoformat(timespec="seconds"), incident_type, int(worker_id), confidence, camera_id,
                     session_id, zone, video_time_s, str(evidence_path) if evidence_path else None))
            except sqlite3.IntegrityError:
                if attempt == 4:
                    raise
                continue
            self.conn.commit()
            return iid

    def set_evidence(self, iid, path):
        self.conn.execute("UPDATE incidents SET evidence_path=? WHERE incident_id=?", (str(path), iid))
        self.conn.commit()

    def close_incident(self, iid, status="CLOSED"):
        """Detector-level end. An operator's review (REVIEWED, FALSE_ALARM) made while the incident was open is kept:
        detection closing and human acknowledgement are separate decisions."""
        self.conn.execute("UPDATE incidents SET ended_at=?, status=CASE WHEN status='OPEN' THEN ? ELSE status END "
                          "WHERE incident_id=? AND ended_at IS NULL", (datetime.now().isoformat(timespec="seconds"), status, iid))
        self.conn.commit()

    def set_status(self, iid, status, reviewer=None, note=None, source="dashboard"):
        """An operator's decision. The change is also appended to incident_reviews with the previous status, who
        decided (None when the interface has no user identity, recorded as such), the reason and the time."""
        row = self.conn.execute("SELECT status FROM incidents WHERE incident_id=?", (iid,)).fetchone()
        if row is None:
            raise KeyError(f"no incident {iid}")
        self.conn.execute("UPDATE incidents SET status=? WHERE incident_id=?", (status, iid))
        self.conn.execute("INSERT INTO incident_reviews (incident_id, previous_status, status, reviewer, note, source, "
                          "reviewed_utc) VALUES (?,?,?,?,?,?,?)", (iid, row["status"], status, reviewer, note, source, _utc()))
        self.conn.commit()

    def reviews(self, iid=None) -> list[dict]:
        q = "SELECT * FROM incident_reviews" + (" WHERE incident_id=?" if iid else "") + " ORDER BY review_id"
        return [dict(r) for r in self.conn.execute(q, (iid,) if iid else ())]

    def rows(self, session_id=None) -> list[dict]:
        q = "SELECT * FROM incidents" + (" WHERE session_id=?" if session_id else "") + " ORDER BY started_at DESC"
        return [dict(r) for r in self.conn.execute(q, (session_id,) if session_id else ())]

    def save_assessment(self, iid, a: dict, escalated_at_s=None):
        """Insert or update the assessment of an incident; an earlier escalation time is kept."""
        self.conn.execute(
            "INSERT INTO risk_assessments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(incident_id) DO UPDATE SET "
            "hazard_code=excluded.hazard_code, severity=excluded.severity, exposure_s=excluded.exposure_s, "
            "exposure_band=excluded.exposure_band, risk_level=excluded.risk_level, evidence=excluded.evidence, "
            "requires_review=excluded.requires_review, actions=excluded.actions, factors=excluded.factors, "
            "policy_version=excluded.policy_version, policy_status=excluded.policy_status, "
            "escalated_at_s=COALESCE(risk_assessments.escalated_at_s, excluded.escalated_at_s), updated_at=excluded.updated_at",
            (iid, a["hazard"], a["severity"], a["exposure_s"], a["exposure_band"], a["level"], a["evidence"],
             int(a["requires_review"]), json.dumps(a["actions"]), json.dumps(a["factors"]), a["policy_version"],
             a["policy_status"], escalated_at_s, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def assessments(self, session_id=None) -> list[dict]:
        q = ("SELECT a.*, i.session_id, i.incident_type, i.zone, i.video_time_s FROM risk_assessments a "
             "JOIN incidents i USING (incident_id)" + (" WHERE i.session_id=?" if session_id else "") + " ORDER BY i.started_at")
        out = []
        for r in self.conn.execute(q, (session_id,) if session_id else ()):
            d = dict(r)
            d["actions"], d["factors"], d["requires_review"] = json.loads(d["actions"]), json.loads(d["factors"]), bool(d["requires_review"])
            out.append(d)
        return out

    def start_runtime_session(self, session_id, camera_id, camera_name, site_id, source_type, source, started_utc,
                              policy_version=None, policy_status=None):
        self.conn.execute("INSERT INTO runtime_sessions (session_id, camera_id, camera_name, site_id, source_type, source, "
                          "started_utc, policy_version, policy_status) VALUES (?,?,?,?,?,?,?,?,?)",
                          (session_id, camera_id, camera_name, site_id, source_type, source, started_utc, policy_version,
                           policy_status))
        self.conn.commit()

    def end_runtime_session(self, session_id, ended_utc, end_reason, frames_read, frames_processed, frames_skipped,
                            frames_dropped, reconnects):
        self.conn.execute("UPDATE runtime_sessions SET ended_utc=?, end_reason=?, frames_read=?, frames_processed=?, "
                          "frames_skipped=?, frames_dropped=?, reconnects=? WHERE session_id=?",
                          (ended_utc, end_reason, frames_read, frames_processed, frames_skipped, frames_dropped, reconnects,
                           session_id))
        self.conn.commit()

    def runtime_sessions(self, camera_id=None) -> list[dict]:
        q = "SELECT * FROM runtime_sessions" + (" WHERE camera_id=?" if camera_id else "") + " ORDER BY started_utc"
        return [dict(r) for r in self.conn.execute(q, (camera_id,) if camera_id else ())]

    def add_incident_context(self, iid, session_id, camera_id, site_id, worker_ref, opened_utc, opened_t):
        self.conn.execute("INSERT INTO incident_context (incident_id, session_id, camera_id, site_id, worker_ref, opened_utc, "
                          "opened_t) VALUES (?,?,?,?,?,?,?)", (iid, session_id, camera_id, site_id, worker_ref, opened_utc, opened_t))
        self.conn.commit()

    def close_incident_context(self, iid, closed_utc, closed_t):
        self.conn.execute("UPDATE incident_context SET closed_utc=?, closed_t=? WHERE incident_id=? AND closed_utc IS NULL",
                          (closed_utc, closed_t, iid))
        self.conn.commit()

    def incident_context(self, session_id=None) -> list[dict]:
        q = "SELECT * FROM incident_context" + (" WHERE session_id=?" if session_id else "") + " ORDER BY opened_utc"
        return [dict(r) for r in self.conn.execute(q, (session_id,) if session_id else ())]

    def add_outage(self, session_id, camera_id, started_utc, reason) -> int:
        cur = self.conn.execute("INSERT INTO camera_outages (session_id, camera_id, started_utc, reason) VALUES (?,?,?,?)",
                                (session_id, camera_id, started_utc, reason))
        self.conn.commit()
        return cur.lastrowid

    def end_outage(self, outage_id, ended_utc):
        self.conn.execute("UPDATE camera_outages SET ended_utc=? WHERE outage_id=? AND ended_utc IS NULL", (ended_utc, outage_id))
        self.conn.commit()

    def outages(self, camera_id=None) -> list[dict]:
        q = "SELECT * FROM camera_outages" + (" WHERE camera_id=?" if camera_id else "") + " ORDER BY started_utc"
        return [dict(r) for r in self.conn.execute(q, (camera_id,) if camera_id else ())]

    # ------------------------------------------------------------------ incident lifecycle (additive)
    def _upsert(self, table, key, row: dict):
        row = {k: (json.dumps(v) if isinstance(v, (list, dict, tuple)) else v) for k, v in row.items()}
        row["updated_at"] = _now()
        cols = list(row)
        self.conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) ON CONFLICT({key}) "
                          f"DO UPDATE SET {','.join(f'{c}=excluded.{c}' for c in cols if c != key)}", [row[c] for c in cols])
        self.conn.commit()

    def save_lifecycle(self, row: dict):
        self._upsert("incident_lifecycle", "incident_id", row)

    def save_group(self, row: dict):
        self._upsert("alert_groups", "group_id", row)

    def save_notification(self, row: dict):
        self._upsert("notifications", "notification_id", row)

    def add_event(self, session_id, event, incident_id=None, group_id=None, video_t=None, track_id=None, detail=None):
        self.conn.execute("INSERT INTO incident_events (session_id, incident_id, group_id, event, video_t, track_id, detail, "
                          "recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                          (session_id, incident_id, group_id, event, None if video_t is None else round(video_t, 3),
                           None if track_id is None else int(track_id), json.dumps(detail) if detail else None, _now()))
        self.conn.commit()

    def save_ppe_observations(self, session_id, camera_id, seconds: dict, tracks: dict):
        for cat, s in seconds.items():
            self.conn.execute("INSERT OR REPLACE INTO ppe_observations VALUES (?,?,?,?,?)",
                              (session_id, camera_id, cat, round(s, 2), tracks.get(cat, 0)))
        self.conn.commit()

    def _select(self, table, session_id=None, order="rowid"):
        q = f"SELECT * FROM {table}" + (" WHERE session_id=?" if session_id else "") + f" ORDER BY {order}"
        out = []
        for r in self.conn.execute(q, (session_id,) if session_id else ()):
            d = dict(r)
            for k in ("tracks", "requirement", "incidents", "group_ids", "incident_ids", "detail", "path"):
                if isinstance(d.get(k), str) and d[k][:1] in "[{":
                    d[k] = json.loads(d[k])
            out.append(d)
        return out

    def lifecycle(self, session_id=None) -> list[dict]:
        return self._select("incident_lifecycle", session_id, "opened_t")

    def events(self, session_id=None) -> list[dict]:
        return self._select("incident_events", session_id, "event_id")

    def groups(self, session_id=None) -> list[dict]:
        return self._select("alert_groups", session_id, "first_t")

    def notifications(self, session_id=None) -> list[dict]:
        return self._select("notifications", session_id, "created_t")

    def ppe_observations(self, session_id=None) -> list[dict]:
        return self._select("ppe_observations", session_id, "category")

    # ------------------------------------------------------------------ camera view monitoring (additive)
    def view_revisions(self, camera_id=None, status=None) -> list[dict]:
        """Revisions without their fingerprint image (view_fingerprint() reads it)."""
        q = ("SELECT camera_id, revision, status, width, height, created_utc, basis, established_by, session_id, source_event, "
             "zones_hash, zones_status, zones_verified_by, zones_verified_utc, updated_at FROM camera_view_revisions WHERE 1=1"
             + (" AND camera_id=?" if camera_id else "") + (" AND status=?" if status else "") + " ORDER BY camera_id, revision")
        return [dict(r) for r in self.conn.execute(q, tuple(x for x in (camera_id, status) if x))]

    def view_fingerprint(self, camera_id, revision) -> bytes | None:
        r = self.conn.execute("SELECT fingerprint FROM camera_view_revisions WHERE camera_id=? AND revision=?",
                              (camera_id, revision)).fetchone()
        return None if r is None else bytes(r[0])

    def add_view_revision(self, camera_id, png: bytes, width, height, status, basis, established_by, session_id=None,
                          source_event=None, zones_hash=None, zones_status=None) -> int:
        """A new revision; making it active supersedes the previous active one (kept, never deleted)."""
        with self.conn:
            rev = self.conn.execute("SELECT COALESCE(MAX(revision), 0) + 1 FROM camera_view_revisions WHERE camera_id=?",
                                    (camera_id,)).fetchone()[0]
            if status == "active":
                self.conn.execute("UPDATE camera_view_revisions SET status='superseded', updated_at=? WHERE camera_id=? AND "
                                  "status='active'", (_now(), camera_id))
            self.conn.execute("INSERT INTO camera_view_revisions (camera_id, revision, status, fingerprint, width, height, "
                              "created_utc, basis, established_by, session_id, source_event, zones_hash, zones_status, updated_at) "
                              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (camera_id, rev, status, sqlite3.Binary(png), width, height, _utc(), basis, established_by,
                               session_id, source_event, zones_hash, zones_status, _now()))
        return rev

    def activate_view_revision(self, camera_id, revision):
        with self.conn:
            self.conn.execute("UPDATE camera_view_revisions SET status='superseded', updated_at=? WHERE camera_id=? AND "
                              "status='active' AND revision<>?", (_now(), camera_id, revision))
            self.conn.execute("UPDATE camera_view_revisions SET status='active', updated_at=? WHERE camera_id=? AND revision=?",
                              (_now(), camera_id, revision))

    def set_view_revision_status(self, camera_id, revision, status):
        self.conn.execute("UPDATE camera_view_revisions SET status=?, updated_at=? WHERE camera_id=? AND revision=?",
                          (status, _now(), camera_id, revision))
        self.conn.commit()

    def set_view_zones(self, camera_id, revision, zones_status, zones_hash=None, verified_by=None):
        self.conn.execute("UPDATE camera_view_revisions SET zones_status=?, zones_hash=COALESCE(?, zones_hash), "
                          "zones_verified_by=COALESCE(?, zones_verified_by), zones_verified_utc=CASE WHEN ? IS NULL THEN "
                          "zones_verified_utc ELSE ? END, updated_at=? WHERE camera_id=? AND revision=?",
                          (zones_status, zones_hash, verified_by, verified_by, _utc(), _now(), camera_id, revision))
        self.conn.commit()

    def save_view_event(self, row: dict):
        self._upsert("camera_view_events", "event_id", row)

    def view_events(self, camera_id=None, session_id=None) -> list[dict]:
        q = "SELECT * FROM camera_view_events WHERE 1=1" + (" AND camera_id=?" if camera_id else "") + \
            (" AND session_id=?" if session_id else "") + " ORDER BY confirmed_utc"
        out = []
        for r in self.conn.execute(q, tuple(x for x in (camera_id, session_id) if x)):
            d = dict(r)
            for k in ("evidence", "affected_incidents", "snapshots"):
                if isinstance(d.get(k), str):
                    d[k] = json.loads(d[k])
            out.append(d)
        return out

    def add_view_command(self, camera_id, command, requested_by, revision=None, event_id=None, zones_reviewed=False,
                         note=None) -> int:
        cur = self.conn.execute("INSERT INTO camera_view_commands (camera_id, command, revision, event_id, zones_reviewed, "
                                "requested_by, note, requested_utc) VALUES (?,?,?,?,?,?,?,?)",
                                (camera_id, command, revision, event_id, int(bool(zones_reviewed)), requested_by, note, _utc()))
        self.conn.commit()
        return cur.lastrowid

    def view_commands(self, camera_id=None, pending=False) -> list[dict]:
        q = "SELECT * FROM camera_view_commands WHERE 1=1" + (" AND camera_id=?" if camera_id else "") + \
            (" AND applied_utc IS NULL" if pending else "") + " ORDER BY command_id"
        return [dict(r) for r in self.conn.execute(q, (camera_id,) if camera_id else ())]

    def finish_view_command(self, command_id, result):
        self.conn.execute("UPDATE camera_view_commands SET applied_utc=?, result=? WHERE command_id=?", (_utc(), result, command_id))
        self.conn.commit()

    def to_csv(self, session_id=None) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, COLUMNS)
        w.writeheader()
        w.writerows(self.rows(session_id))
        return buf.getvalue()
