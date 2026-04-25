from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Json

from bot.config import settings


DEFAULT_MODE = "career"
DEFAULT_IELTS_STATE = {
    "track": "speaking",
    "last_question": "",
    "estimated_band": None,
    "practice_counts": {
        "speaking_part_1": 0,
        "speaking_part_2": 0,
        "speaking_part_3": 0,
        "writing_task_1": 0,
        "writing_task_2": 0,
    },
}


class SQLiteMemoryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_state (
                    chat_id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL DEFAULT 'career',
                    ielts_state TEXT NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def ensure_chat(self, chat_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_state (chat_id, mode, ielts_state)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (chat_id, DEFAULT_MODE, json.dumps(DEFAULT_IELTS_STATE)),
            )

    def get_mode(self, chat_id: int) -> str:
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mode FROM chat_state WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return row["mode"] if row else DEFAULT_MODE

    def set_mode(self, chat_id: int, mode: str) -> None:
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chat_state
                SET mode = ?, updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
                """,
                (mode, chat_id),
            )

    def get_ielts_state(self, chat_id: int) -> dict[str, Any]:
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ielts_state FROM chat_state WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if not row or not row["ielts_state"]:
            return DEFAULT_IELTS_STATE.copy()
        try:
            state = json.loads(row["ielts_state"])
        except json.JSONDecodeError:
            return DEFAULT_IELTS_STATE.copy()
        return _merge_ielts_state(state)

    def update_ielts_state(self, chat_id: int, state: dict[str, Any]) -> None:
        merged = _merge_ielts_state(state)
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chat_state
                SET ielts_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
                """,
                (json.dumps(merged), chat_id),
            )

    def append_message(self, chat_id: int, role: str, content: str) -> None:
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )

    def get_recent_messages(self, chat_id: int, limit: int = 12) -> list[dict[str, str]]:
        self.ensure_chat(chat_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_chat(self, chat_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            conn.execute(
                """
                INSERT INTO chat_state (chat_id, mode, ielts_state)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    mode = excluded.mode,
                    ielts_state = excluded.ielts_state,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, DEFAULT_MODE, json.dumps(DEFAULT_IELTS_STATE)),
            )


class PostgresMemoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._init_db()

    def _connect(self):
        return connect(self.database_url, row_factory=dict_row)

    def _init_db(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_state (
                    chat_id BIGINT PRIMARY KEY,
                    mode TEXT NOT NULL DEFAULT 'career',
                    ielts_state JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id
                ON messages (chat_id, id DESC)
                """
            )
            conn.commit()

    def ensure_chat(self, chat_id: int) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_state (chat_id, mode, ielts_state)
                VALUES (%s, %s, %s)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (chat_id, DEFAULT_MODE, Json(DEFAULT_IELTS_STATE)),
            )
            conn.commit()

    def get_mode(self, chat_id: int) -> str:
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT mode FROM chat_state WHERE chat_id = %s", (chat_id,))
            row = cur.fetchone()
        return row["mode"] if row else DEFAULT_MODE

    def set_mode(self, chat_id: int, mode: str) -> None:
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_state
                SET mode = %s, updated_at = NOW()
                WHERE chat_id = %s
                """,
                (mode, chat_id),
            )
            conn.commit()

    def get_ielts_state(self, chat_id: int) -> dict[str, Any]:
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT ielts_state FROM chat_state WHERE chat_id = %s",
                (chat_id,),
            )
            row = cur.fetchone()
        if not row or not row["ielts_state"]:
            return DEFAULT_IELTS_STATE.copy()
        return _merge_ielts_state(row["ielts_state"])

    def update_ielts_state(self, chat_id: int, state: dict[str, Any]) -> None:
        merged = _merge_ielts_state(state)
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_state
                SET ielts_state = %s, updated_at = NOW()
                WHERE chat_id = %s
                """,
                (Json(merged), chat_id),
            )
            conn.commit()

    def append_message(self, chat_id: int, role: str, content: str) -> None:
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (chat_id, role, content) VALUES (%s, %s, %s)",
                (chat_id, role, content),
            )
            conn.commit()

    def get_recent_messages(self, chat_id: int, limit: int = 12) -> list[dict[str, str]]:
        self.ensure_chat(chat_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE chat_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (chat_id, limit),
            )
            rows = cur.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_chat(self, chat_id: int) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE chat_id = %s", (chat_id,))
            cur.execute(
                """
                INSERT INTO chat_state (chat_id, mode, ielts_state)
                VALUES (%s, %s, %s)
                ON CONFLICT(chat_id) DO UPDATE SET
                    mode = excluded.mode,
                    ielts_state = excluded.ielts_state,
                    updated_at = NOW()
                """,
                (chat_id, DEFAULT_MODE, Json(DEFAULT_IELTS_STATE)),
            )
            conn.commit()


MemoryStore = SQLiteMemoryStore | PostgresMemoryStore


def create_memory_store() -> MemoryStore:
    if settings.database_url:
        return PostgresMemoryStore(settings.database_url)
    return SQLiteMemoryStore(settings.memory_db_path)


def _merge_ielts_state(state: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_IELTS_STATE))
    merged.update({k: v for k, v in state.items() if k != "practice_counts"})
    merged["practice_counts"].update(state.get("practice_counts", {}))
    return merged
