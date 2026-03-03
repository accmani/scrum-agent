"""
Thin SQLite persistence layer.

Tables
------
  manual_blockers  (id TEXT PK, text TEXT, created_at TEXT)
  retro_items      (id TEXT PK, category TEXT, text TEXT, created_at TEXT)

All public functions are async — they delegate synchronous sqlite3 calls to a
thread pool via asyncio.to_thread so the event loop is never blocked.
"""

import asyncio
import datetime
import sqlite3
import uuid
from pathlib import Path

# Database file lives alongside this module (backend/scrum_agent.db)
DB_PATH = Path(__file__).parent / "scrum_agent.db"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safe concurrent reads
    return conn


def _init_sync() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS manual_blockers (
                id         TEXT PRIMARY KEY,
                text       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retro_items (
                id         TEXT PRIMARY KEY,
                category   TEXT NOT NULL CHECK(category IN ('well','improve','action')),
                text       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    await asyncio.to_thread(_init_sync)


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------

def _list_blockers_sync() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, text, created_at FROM manual_blockers ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


async def list_manual_blockers() -> list[dict]:
    return await asyncio.to_thread(_list_blockers_sync)


def _add_blocker_sync(text: str) -> dict:
    record = {"id": str(uuid.uuid4()), "text": text, "created_at": _now()}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO manual_blockers VALUES (:id, :text, :created_at)", record
        )
    return record


async def add_manual_blocker(text: str) -> dict:
    return await asyncio.to_thread(_add_blocker_sync, text)


def _delete_blocker_sync(bid: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM manual_blockers WHERE id = ?", (bid,))
        return cur.rowcount > 0


async def delete_manual_blocker(bid: str) -> bool:
    return await asyncio.to_thread(_delete_blocker_sync, bid)


# ---------------------------------------------------------------------------
# Retro items
# ---------------------------------------------------------------------------

def _list_retro_sync() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, category, text, created_at FROM retro_items ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


async def list_retro_items() -> list[dict]:
    return await asyncio.to_thread(_list_retro_sync)


def _add_retro_sync(category: str, text: str) -> dict:
    record = {
        "id": str(uuid.uuid4()),
        "category": category,
        "text": text,
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO retro_items VALUES (:id, :category, :text, :created_at)", record
        )
    return record


async def add_retro_item(category: str, text: str) -> dict:
    return await asyncio.to_thread(_add_retro_sync, category, text)


def _delete_retro_sync(rid: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM retro_items WHERE id = ?", (rid,))
        return cur.rowcount > 0


async def delete_retro_item(rid: str) -> bool:
    return await asyncio.to_thread(_delete_retro_sync, rid)
