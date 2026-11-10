"""SQLite 持久层。

演示环境使用单文件 SQLite；租户归属通过 trainees/runs 的 tenant_id 表达，
消息通过 run_id 从属；查询先校验上层实体所属租户，为后续切换 PostgreSQL
与行级隔离预留结构。
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'enterprise',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trainees (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    avatar TEXT NOT NULL DEFAULT '🎮',
    created_at TEXT NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    is_seed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_trainees_tenant ON trainees(tenant_id);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    trainee_id TEXT NOT NULL,
    level_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    turn_count INTEGER NOT NULL DEFAULT 0,
    total_score REAL,
    passed INTEGER,
    scores_json TEXT,
    judge_json TEXT,
    hints_used INTEGER NOT NULL DEFAULT 0,
    xp_awarded INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms REAL,
    emotion INTEGER NOT NULL DEFAULT 0,
    last_player_at TEXT,
    is_seed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_trainee ON runs(trainee_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    latency_ms REAL,
    analysis_json TEXT,
    seq INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_run ON messages(run_id, seq);
"""


def now_iso() -> str:
    """统一使用 UTC 时间，前端负责转本地时区。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:14]


class Database:
    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self._lock:
            self.conn.executemany(sql, rows)
            self.conn.commit()

    def one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self.conn.close()


db = Database()
