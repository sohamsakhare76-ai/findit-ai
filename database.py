"""SQLite visual memory for FindIt AI."""
import sqlite3
from contextlib import closing
from datetime import datetime
from functools import wraps
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "findit.db"


class DatabaseError(Exception):
    """Raised for any SQLite problem so the web layer can show a friendly message."""


def _wrap(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Database error: {exc}") from exc
    return inner


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@_wrap
def init_db():
    with closing(get_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                image_filename TEXT NOT NULL,
                location       TEXT NOT NULL,
                timestamp      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS detections (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id     INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                object_name TEXT NOT NULL,
                confidence  REAL NOT NULL,
                x1 REAL NOT NULL, y1 REAL NOT NULL,
                x2 REAL NOT NULL, y2 REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_det_object ON detections(object_name);
            CREATE INDEX IF NOT EXISTS idx_det_scan   ON detections(scan_id);
            """
        )


@_wrap
def create_scan(filename, location, detections):
    """Insert a scan and all its detections in one transaction. Returns scan id."""
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO scans (image_filename, location, timestamp) VALUES (?, ?, ?)",
            (filename, location, datetime.now().isoformat(timespec="seconds")),
        )
        scan_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO detections (scan_id, object_name, confidence, x1, y1, x2, y2) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (scan_id, d["object_name"], d["confidence"], d["x1"], d["y1"], d["x2"], d["y2"])
                for d in detections
            ],
        )
    return scan_id


@_wrap
def get_scan(scan_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return dict(row) if row else None


@_wrap
def get_detections(scan_id):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM detections WHERE scan_id = ? ORDER BY confidence DESC", (scan_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@_wrap
def recent_scans(limit=8):
    with closing(get_conn()) as conn:
        scans = conn.execute(
            "SELECT id, image_filename, location, timestamp FROM scans "
            "ORDER BY timestamp DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for s in scans:
            objs = conn.execute(
                "SELECT object_name AS name, COUNT(*) AS count FROM detections "
                "WHERE scan_id = ? GROUP BY object_name ORDER BY count DESC, name",
                (s["id"],),
            ).fetchall()
            item = dict(s)
            item["objects"] = [dict(o) for o in objs]
            result.append(item)
    return result


@_wrap
def get_stats():
    with closing(get_conn()) as conn:
        scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        objects = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        kinds = conn.execute("SELECT COUNT(DISTINCT object_name) FROM detections").fetchone()[0]
    return {"scans": scans, "objects": objects, "kinds": kinds}


@_wrap
def find_sightings(object_name, limit=6):
    """Most recent scan first; within a scan, highest confidence first."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT d.id AS detection_id, d.scan_id, d.object_name, d.confidence,
                   d.x1, d.y1, d.x2, d.y2,
                   s.image_filename, s.location, s.timestamp
            FROM detections d
            JOIN scans s ON s.id = d.scan_id
            WHERE d.object_name = ?
            ORDER BY s.timestamp DESC, s.id DESC, d.confidence DESC
            LIMIT ?
            """,
            (object_name, limit),
        ).fetchall()
    return [dict(r) for r in rows]
