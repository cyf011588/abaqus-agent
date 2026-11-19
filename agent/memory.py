# -*- coding: utf-8 -*-
"""记忆层：技能事实、已生成算例、会话记录，持久化到 SQLite（仅标准库）。

- facts：技能级长期事实/经验教训（对应「长短期记忆」）
- cases：已生成的算例（参数 + 结果摘要），支持「查历史算例」
- session_log：会话流水（可选）
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from . import config as _cfg_mod


def _db_path() -> Path:
    cfg = _cfg_mod.load_config()
    mem_dir = Path(cfg["agent"].get("memory_dir", "./data"))
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir / "memory.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facts (
            skill TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at REAL,
            PRIMARY KEY (skill, key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill TEXT NOT NULL,
            job TEXT NOT NULL,
            params TEXT,
            status TEXT,
            summary TEXT,
            created_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            role TEXT,
            content TEXT
        )
        """
    )
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """旧库用 project 列，新库统一用 skill 列；幂等迁移。"""
    for table in ("facts", "cases"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "project" in cols and "skill" not in cols:
            conn.execute(f"ALTER TABLE {table} RENAME COLUMN project TO skill")
    conn.commit()


# --------------------------------------------------------------------------- facts
def remember_fact(skill: str, fact: str, key: Optional[str] = None) -> None:
    key = key or _fact_key(fact)
    conn = _conn()
    conn.execute(
        "INSERT INTO facts(skill, key, value, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(skill, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (skill, key, fact, time.time()),
    )
    conn.commit()
    conn.close()


def get_facts(skill: str, limit: int = 50) -> List[str]:
    conn = _conn()
    rows = conn.execute(
        "SELECT value FROM facts WHERE skill=? ORDER BY updated_at DESC LIMIT ?",
        (skill, limit),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _fact_key(fact: str) -> str:
    # 用前 48 个字符做 key，保证同一句事实去重，又不依赖 hash
    return fact.strip()[:48]


# --------------------------------------------------------------------------- cases
def remember_case(skill: str, job: str, params: str, status: str, summary: str) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO cases(skill, job, params, status, summary, created_at) VALUES(?,?,?,?,?,?)",
        (skill, job, params, status, summary[:4000], time.time()),
    )
    conn.commit()
    conn.close()


def list_cases(skill: str, limit: int = 20) -> List[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT job, params, status, created_at FROM cases WHERE skill=? "
        "ORDER BY id DESC LIMIT ?",
        (skill, limit),
    ).fetchall()
    conn.close()
    out = []
    for job, params, status, ts in rows:
        out.append({"job": job, "params": params, "status": status, "created_at": ts})
    return out


# --------------------------------------------------------------------------- session
def append_log(role: str, content: str) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO session_log(ts, role, content) VALUES(?,?,?)",
        (time.time(), role, content[:8000]),
    )
    conn.commit()
    conn.close()


def recent_log(limit: int = 20) -> List[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT role, content, ts FROM session_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "ts": r[2]} for r in rows]
