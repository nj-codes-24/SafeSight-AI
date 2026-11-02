"""SQLite incident store. Incidents are append-only; only status and end time change after creation."""
import csv
import io
import sqlite3
import uuid
from datetime import datetime
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


class IncidentDB:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(SCHEMA)
        self.conn.execute(SESSIONS)
        self.conn.commit()

    def save_session(self, session_id, source, frames, unique_workers, compliant, violation, uncertain, avg_fps):
        self.conn.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                          (session_id, datetime.now().isoformat(timespec="seconds"), source, frames, unique_workers,
                           compliant, violation, uncertain, avg_fps))
        self.conn.commit()

    def sessions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM sessions ORDER BY started_at")]

    def add(self, incident_type, worker_id, confidence, camera_id, session_id, zone=None, video_time_s=None,
            evidence_path=None) -> str:
        iid = f"INC-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        self.conn.execute(
            "INSERT INTO incidents (incident_id, started_at, incident_type, worker_id, confidence, camera_id, "
            "session_id, zone, video_time_s, evidence_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (iid, datetime.now().isoformat(timespec="seconds"), incident_type, int(worker_id), confidence, camera_id,
             session_id, zone, video_time_s, str(evidence_path) if evidence_path else None))
        self.conn.commit()
        return iid

    def set_evidence(self, iid, path):
        self.conn.execute("UPDATE incidents SET evidence_path=? WHERE incident_id=?", (str(path), iid))
        self.conn.commit()

    def close_incident(self, iid, status="CLOSED"):
        self.conn.execute("UPDATE incidents SET ended_at=?, status=? WHERE incident_id=? AND ended_at IS NULL",
                          (datetime.now().isoformat(timespec="seconds"), status, iid))
        self.conn.commit()

    def set_status(self, iid, status):
        self.conn.execute("UPDATE incidents SET status=? WHERE incident_id=?", (status, iid))
        self.conn.commit()

    def rows(self, session_id=None) -> list[dict]:
        q = "SELECT * FROM incidents" + (" WHERE session_id=?" if session_id else "") + " ORDER BY started_at DESC"
        return [dict(r) for r in self.conn.execute(q, (session_id,) if session_id else ())]

    def to_csv(self, session_id=None) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, COLUMNS)
        w.writeheader()
        w.writerows(self.rows(session_id))
        return buf.getvalue()
