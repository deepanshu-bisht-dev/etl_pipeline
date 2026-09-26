"""
Control-plane storage for the ETL system.

This is deliberately plain sqlite3 (no ORM) so the whole project runs with
nothing but the Python standard library plus pandas/Flask — no database
server, no extra services, nothing to install beyond `pip install -r
requirements.txt`.

Two SQLite files are used:
  - control.db    pipeline run history, stage timings, log lines
  - warehouse.db  the actual cleaned/loaded data (written by etl/load.py)
"""
import sqlite3
import os
import threading
from datetime import datetime, timezone

import config

_lock = threading.Lock()


def _connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def get_control_conn():
    return _connect(config.CONTROL_DB)


def get_warehouse_conn():
    return _connect(config.WAREHOUSE_DB)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db():
    """Create control-plane tables if they don't exist yet."""
    with _lock:
        conn = get_control_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at    TEXT NOT NULL,
                finished_at   TEXT,
                status        TEXT NOT NULL DEFAULT 'running',
                trigger       TEXT NOT NULL DEFAULT 'manual',
                rows_extracted   INTEGER DEFAULT 0,
                rows_loaded      INTEGER DEFAULT 0,
                rows_rejected    INTEGER DEFAULT 0,
                duration_ms   INTEGER,
                error         TEXT
            );

            CREATE TABLE IF NOT EXISTS stage_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id        INTEGER NOT NULL,
                source_name   TEXT NOT NULL,
                stage         TEXT NOT NULL,   -- extract | transform | validate | load
                status        TEXT NOT NULL,   -- ok | warning | error
                rows_in       INTEGER DEFAULT 0,
                rows_out      INTEGER DEFAULT 0,
                duration_ms   INTEGER DEFAULT 0,
                detail        TEXT,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs (id)
            );

            CREATE TABLE IF NOT EXISTS logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id        INTEGER,
                ts            TEXT NOT NULL,
                level         TEXT NOT NULL,   -- info | warn | error | success
                message       TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()


# --------------------------------------------------------------------------
# Run lifecycle
# --------------------------------------------------------------------------

def start_run(trigger="manual"):
    with _lock:
        conn = get_control_conn()
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_at, status, trigger) VALUES (?, 'running', ?)",
            (now_iso(), trigger),
        )
        conn.commit()
        run_id = cur.lastrowid
        conn.close()
    return run_id


def finish_run(run_id, status, rows_extracted=0, rows_loaded=0, rows_rejected=0,
               duration_ms=0, error=None):
    with _lock:
        conn = get_control_conn()
        conn.execute(
            """UPDATE pipeline_runs
               SET finished_at=?, status=?, rows_extracted=?, rows_loaded=?,
                   rows_rejected=?, duration_ms=?, error=?
               WHERE id=?""",
            (now_iso(), status, rows_extracted, rows_loaded, rows_rejected,
             duration_ms, error, run_id),
        )
        conn.commit()
        conn.close()


def record_stage(run_id, source_name, stage, status, rows_in=0, rows_out=0,
                  duration_ms=0, detail=None):
    with _lock:
        conn = get_control_conn()
        conn.execute(
            """INSERT INTO stage_runs
               (run_id, source_name, stage, status, rows_in, rows_out, duration_ms, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source_name, stage, status, rows_in, rows_out, duration_ms, detail),
        )
        conn.commit()
        conn.close()


def log(run_id, level, message):
    with _lock:
        conn = get_control_conn()
        conn.execute(
            "INSERT INTO logs (run_id, ts, level, message) VALUES (?, ?, ?, ?)",
            (run_id, now_iso(), level, message),
        )
        conn.commit()
        conn.close()


# --------------------------------------------------------------------------
# Reads for the dashboard
# --------------------------------------------------------------------------

def get_recent_runs(limit=25):
    conn = get_control_conn()
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run(run_id):
    conn = get_control_conn()
    row = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stages_for_run(run_id):
    conn = get_control_conn()
    rows = conn.execute(
        "SELECT * FROM stage_runs WHERE run_id=? ORDER BY id ASC", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_logs(limit=100, run_id=None):
    conn = get_control_conn()
    if run_id:
        rows = conn.execute(
            "SELECT * FROM logs WHERE run_id=? ORDER BY id DESC LIMIT ?", (run_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_stats():
    conn = get_control_conn()
    total = conn.execute("SELECT COUNT(*) c FROM pipeline_runs").fetchone()["c"]
    succeeded = conn.execute(
        "SELECT COUNT(*) c FROM pipeline_runs WHERE status='success'"
    ).fetchone()["c"]
    failed = conn.execute(
        "SELECT COUNT(*) c FROM pipeline_runs WHERE status='failed'"
    ).fetchone()["c"]
    total_rows = conn.execute(
        "SELECT COALESCE(SUM(rows_loaded),0) s FROM pipeline_runs WHERE status='success'"
    ).fetchone()["s"]
    avg_duration = conn.execute(
        "SELECT AVG(duration_ms) a FROM pipeline_runs WHERE status IN ('success','failed')"
    ).fetchone()["a"]
    last_run = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    success_rate = round((succeeded / total) * 100, 1) if total else 0.0
    return {
        "total_runs": total,
        "succeeded": succeeded,
        "failed": failed,
        "success_rate": success_rate,
        "total_rows_loaded": total_rows,
        "avg_duration_ms": round(avg_duration) if avg_duration else 0,
        "last_run": dict(last_run) if last_run else None,
    }


def get_run_history_series(limit=20):
    """Rows loaded per run, oldest first — feeds the trend chart."""
    conn = get_control_conn()
    rows = conn.execute(
        "SELECT id, started_at, rows_loaded, status, duration_ms FROM pipeline_runs "
        "WHERE status IN ('success','failed') ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
