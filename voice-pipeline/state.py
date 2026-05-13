"""SQLite state-store for voice-pipeline.

Holder oversikt over prosesserte filer, statuser og feil — slik at launchd-
trigger som fyrer mange ganger ikke re-prosesserer samme fil.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_path TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    input_size INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT,
    output_md TEXT,
    UNIQUE(input_hash)
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_file(path: Path, chunk_size: int = 65536) -> str:
    """Raskt SHA-256 av fil-innhold. Brukes for idempotens.

    Retry ved OSError (iCloud Drive kan gi EDEADLK under sync)."""
    import time as _time
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            h = hashlib.sha256()
            with path.open("rb") as f:
                while chunk := f.read(chunk_size):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as e:
            last_err = e
            _time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Kunne ikke hashe {path} etter 5 forsøk: {last_err}")


class State:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def already_processed(self, input_path: Path) -> bool:
        """Returner True hvis denne fila (innholdshash) er fullført tidligere."""
        h = _hash_file(input_path)
        row = self.conn.execute(
            "SELECT status FROM runs WHERE input_hash = ? AND status = 'done'", (h,),
        ).fetchone()
        return row is not None

    def start(self, input_path: Path) -> int:
        """Start en ny run. Returner run_id. Hvis samme hash allerede finnes,
        oppdater raden og returner id."""
        h = _hash_file(input_path)
        size = input_path.stat().st_size
        now = _now()
        cur = self.conn.execute(
            """INSERT INTO runs (input_path, input_hash, input_size, status, created_at, updated_at)
               VALUES (?, ?, ?, 'starting', ?, ?)
               ON CONFLICT(input_hash) DO UPDATE SET
                   status = 'starting',
                   updated_at = excluded.updated_at,
                   error = NULL
               RETURNING id""",
            (str(input_path), h, size, now, now),
        )
        row = cur.fetchone()
        return int(row[0])

    def update(self, run_id: int, status: str) -> None:
        self.conn.execute(
            "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), run_id),
        )

    def complete(self, run_id: int, output_md: Path) -> None:
        now = _now()
        self.conn.execute(
            """UPDATE runs SET status = 'done', updated_at = ?, completed_at = ?, output_md = ?
               WHERE id = ?""",
            (now, now, str(output_md), run_id),
        )

    def fail(self, run_id: int, error: str) -> None:
        self.conn.execute(
            "UPDATE runs SET status = 'failed', updated_at = ?, error = ? WHERE id = ?",
            (_now(), error[:2000], run_id),
        )

    def recent(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall())
