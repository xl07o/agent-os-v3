"""
بحث بكل المحادثات السابقة — نفس فكرة session_search بـHermes Agent:
SQLite FTS5 فوق كل رسائل الغرف (منك، من الرئيس التنفيذي، من الموظفين).

- كل rooms.post() تنفهرس هنا تلقائياً.
- الرئيس التنفيذي يستلم أقرب مقتطفات من محادثات قديمة مع كل طلب
  ("وش اتفقنا عليه الشهر الماضي؟" يلقاه).
- أداة session_search للموظفين — قراءة فقط.

النتائج نص الرسائل الأصلي من القاعدة، بدون تلخيص من الذكاء (نفس Hermes:
"Results are actual DB messages"). المطابقة بعد تطبيع عربي (textnorm).
"""

import json
import os
import sqlite3
import threading

from . import textnorm

_DB = os.path.join(os.path.dirname(__file__), "data", "sessions.db")
_lock = threading.Lock()
_MAX_TEXT = 1200


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    conn = sqlite3.connect(_DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS msgs (id INTEGER PRIMARY KEY, room TEXT, speaker TEXT, at TEXT, text TEXT)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS msgs_fts USING fts5(norm)")
    return conn


def _norm(text: str) -> str:
    return " ".join(sorted(textnorm.words(text, min_len=2)))


def index(room: str, speaker: str, text: str, at: str) -> None:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("INSERT INTO msgs (room, speaker, at, text) VALUES (?, ?, ?, ?)", (room, speaker, at, text))
            conn.execute("INSERT INTO msgs_fts (rowid, norm) VALUES (?, ?)", (cur.lastrowid, _norm(text)))
            conn.commit()
        finally:
            conn.close()


def backfill(rooms_file: str) -> int:
    """يفهرس سجل الغرف القديم مرة وحدة (لو القاعدة فاضية)."""
    if not os.path.exists(rooms_file):
        return 0
    with _lock:
        conn = _connect()
        try:
            if conn.execute("SELECT COUNT(*) FROM msgs").fetchone()[0]:
                return 0
        finally:
            conn.close()
    with open(rooms_file, encoding="utf-8") as f:
        entries = json.load(f)
    for e in entries:
        index(e.get("room", ""), e.get("speaker", ""), e.get("text", ""), e.get("at", ""))
    return len(entries)


def search(query: str, limit: int = 3, exclude_ids: set[int] | None = None) -> list[dict]:
    terms = sorted(textnorm.words(query, min_len=2))
    if not terms:
        return []
    match = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
    limit = max(1, min(int(limit), 10))
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT m.id, m.room, m.speaker, m.at, m.text FROM msgs_fts f JOIN msgs m ON m.id = f.rowid "
            "WHERE msgs_fts MATCH ? ORDER BY bm25(msgs_fts) LIMIT ?",
            (match, limit + len(exclude_ids or ())),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    out = []
    for mid, room, speaker, at, text in rows:
        if exclude_ids and mid in exclude_ids:
            continue
        out.append({"id": mid, "room": room, "speaker": speaker, "at": at, "text": text[:_MAX_TEXT]})
        if len(out) >= limit:
            break
    return out


def recent_ids(room: str, n: int) -> set[int]:
    conn = _connect()
    try:
        return {r[0] for r in conn.execute("SELECT id FROM msgs WHERE room = ? ORDER BY id DESC LIMIT ?", (room, n))}
    finally:
        conn.close()


def prompt_block(query: str, skip_recent_room: str | None = None, skip_n: int = 0) -> str:
    skip = recent_ids(skip_recent_room, skip_n) if skip_recent_room else set()
    hits = search(query, limit=3, exclude_ids=skip)
    if not hits:
        return ""
    return "من محادثات سابقة ذات صلة (نص أصلي من السجل):\n" + "\n".join(
        f"- [{h['at']} · غرفة {h['room']} · {h['speaker']}] {h['text'][:400]}" for h in hits
    )
