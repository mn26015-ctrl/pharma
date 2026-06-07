"""
PharmAI Database - SQLite with full schema
Handles all DB operations, deduplication, and cache
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime, date
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("DB_PATH", "pharmai.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    -- Users
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT DEFAULT 'Student',
        created_at TEXT DEFAULT (datetime('now')),
        settings TEXT DEFAULT '{}'
    );

    -- PDF Documents
    CREATE TABLE IF NOT EXISTS pdf_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        filename TEXT NOT NULL,
        file_hash TEXT UNIQUE NOT NULL,
        page_count INTEGER DEFAULT 0,
        total_chunks INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        topic TEXT DEFAULT 'General',
        uploaded_at TEXT DEFAULT (datetime('now')),
        processed_at TEXT
    );

    -- Text Chunks
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        content_hash TEXT UNIQUE NOT NULL,
        token_estimate INTEGER DEFAULT 0,
        processed INTEGER DEFAULT 0,
        FOREIGN KEY (doc_id) REFERENCES pdf_documents(id)
    );

    -- Questions (MCQ / TF / Clinical / Flashcard)
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER,
        chunk_id INTEGER,
        type TEXT NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        topic TEXT DEFAULT 'General',
        difficulty TEXT DEFAULT 'medium',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (doc_id) REFERENCES pdf_documents(id),
        FOREIGN KEY (chunk_id) REFERENCES chunks(id)
    );

    -- User Answers (history)
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        question_id INTEGER NOT NULL,
        user_answer TEXT,
        is_correct INTEGER NOT NULL,
        answered_at TEXT DEFAULT (datetime('now')),
        time_taken_sec INTEGER DEFAULT 0,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    -- Spaced Repetition Schedule
    CREATE TABLE IF NOT EXISTS review_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        question_id INTEGER NOT NULL UNIQUE,
        ease_factor REAL DEFAULT 2.5,
        interval_days INTEGER DEFAULT 1,
        repetitions INTEGER DEFAULT 0,
        next_review TEXT DEFAULT (date('now')),
        last_reviewed TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    -- User Performance (daily stats)
    CREATE TABLE IF NOT EXISTS user_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        stat_date TEXT NOT NULL,
        questions_attempted INTEGER DEFAULT 0,
        questions_correct INTEGER DEFAULT 0,
        streak_days INTEGER DEFAULT 0,
        UNIQUE(user_id, stat_date)
    );

    -- AI Response Cache (cost optimization)
    CREATE TABLE IF NOT EXISTS cache_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cache_key TEXT UNIQUE NOT NULL,
        prompt_hash TEXT NOT NULL,
        response_json TEXT NOT NULL,
        model TEXT DEFAULT 'gemini',
        tokens_used INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        hit_count INTEGER DEFAULT 0
    );

    -- Seed default user
    INSERT OR IGNORE INTO users (id, name) VALUES (1, 'Student');
    """)

    conn.commit()
    conn.close()


# ─── File Hash ────────────────────────────────────────────────────────────────
def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


# ─── PDF Documents ────────────────────────────────────────────────────────────
def doc_exists(fhash: str) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM pdf_documents WHERE file_hash = ?", (fhash,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_doc(filename: str, fhash: str, page_count: int, topic: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO pdf_documents (filename, file_hash, page_count, topic, status) VALUES (?,?,?,?,'processing')",
        (filename, fhash, page_count, topic)
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def update_doc_status(doc_id: int, status: str, total_chunks: int = 0):
    conn = get_conn()
    conn.execute(
        "UPDATE pdf_documents SET status=?, total_chunks=?, processed_at=datetime('now') WHERE id=?",
        (status, total_chunks, doc_id)
    )
    conn.commit()
    conn.close()


def get_all_docs() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT d.*, COUNT(q.id) as question_count FROM pdf_documents d "
        "LEFT JOIN questions q ON q.doc_id = d.id "
        "GROUP BY d.id ORDER BY d.uploaded_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Chunks ───────────────────────────────────────────────────────────────────
def insert_chunk(doc_id: int, index: int, content: str) -> Optional[int]:
    chash = text_hash(content)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO chunks (doc_id, chunk_index, content, content_hash, token_estimate) VALUES (?,?,?,?,?)",
            (doc_id, index, content, chash, len(content) // 4)
        )
        chunk_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        chunk_id = None
    conn.close()
    return chunk_id


def get_unprocessed_chunks(doc_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chunks WHERE doc_id=? AND processed=0 ORDER BY chunk_index",
        (doc_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_chunk_processed(chunk_id: int):
    conn = get_conn()
    conn.execute("UPDATE chunks SET processed=1 WHERE id=?", (chunk_id,))
    conn.commit()
    conn.close()


# ─── Questions ────────────────────────────────────────────────────────────────
def insert_question(q: Dict) -> int:
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO questions
        (doc_id, chunk_id, type, question, option_a, option_b, option_c, option_d,
         correct_answer, explanation, topic, difficulty)
        VALUES (:doc_id, :chunk_id, :type, :question, :option_a, :option_b, :option_c, :option_d,
                :correct_answer, :explanation, :topic, :difficulty)
    """, q)
    qid = cur.lastrowid
    conn.commit()

    # Auto-schedule for spaced repetition
    conn.execute(
        "INSERT OR IGNORE INTO review_schedule (user_id, question_id) VALUES (1, ?)",
        (qid,)
    )
    conn.commit()
    conn.close()
    return qid


def get_questions(
    doc_id: Optional[int] = None,
    q_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    conn = get_conn()
    conditions = ["1=1"]
    params = []
    if doc_id:
        conditions.append("doc_id = ?"); params.append(doc_id)
    if q_type:
        conditions.append("type = ?"); params.append(q_type)
    if difficulty:
        conditions.append("difficulty = ?"); params.append(difficulty)
    if topic:
        conditions.append("topic LIKE ?"); params.append(f"%{topic}%")
    params += [limit, offset]
    rows = conn.execute(
        f"SELECT * FROM questions WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_questions(**kwargs) -> int:
    conn = get_conn()
    conditions = ["1=1"]
    params = []
    if kwargs.get("doc_id"):
        conditions.append("doc_id = ?"); params.append(kwargs["doc_id"])
    if kwargs.get("q_type"):
        conditions.append("type = ?"); params.append(kwargs["q_type"])
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM questions WHERE {' AND '.join(conditions)}",
        params
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_distinct_topics() -> List[str]:
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT topic FROM questions WHERE topic IS NOT NULL ORDER BY topic").fetchall()
    conn.close()
    return [r["topic"] for r in rows]


# ─── Daily Test Queue ─────────────────────────────────────────────────────────
def get_due_questions(user_id: int = 1, limit: int = 20) -> List[Dict]:
    """Get questions due for review today (spaced repetition)"""
    conn = get_conn()
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT q.*, rs.ease_factor, rs.interval_days, rs.repetitions
        FROM questions q
        JOIN review_schedule rs ON rs.question_id = q.id
        WHERE rs.user_id = ? AND rs.next_review <= ?
        ORDER BY rs.next_review ASC, RANDOM()
        LIMIT ?
    """, (user_id, today, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_new_questions(user_id: int = 1, limit: int = 10) -> List[Dict]:
    """Get questions never reviewed"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT q.* FROM questions q
        JOIN review_schedule rs ON rs.question_id = q.id
        WHERE rs.user_id = ? AND rs.repetitions = 0
        ORDER BY RANDOM() LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mistake_questions(user_id: int = 1, limit: int = 10) -> List[Dict]:
    """Get most recently wrong questions"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT q.* FROM questions q
        JOIN answers a ON a.question_id = q.id
        WHERE a.user_id = ? AND a.is_correct = 0
        GROUP BY q.id ORDER BY MAX(a.answered_at) DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Spaced Repetition (SM-2 Algorithm) ──────────────────────────────────────
def update_spaced_repetition(question_id: int, quality: int, user_id: int = 1):
    """
    quality: 0-5 (0=complete blackout, 5=perfect)
    SM-2 algorithm implementation
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM review_schedule WHERE user_id=? AND question_id=?",
        (user_id, question_id)
    ).fetchone()

    if not row:
        conn.close()
        return

    ef = row["ease_factor"]
    n = row["repetitions"]
    interval = row["interval_days"]

    # SM-2 formula
    if quality >= 3:
        if n == 0:
            interval = 1
        elif n == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        n += 1
    else:
        n = 0
        interval = 1

    ef = max(1.3, ef + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

    from datetime import timedelta
    next_review = (date.today() + timedelta(days=interval)).isoformat()

    conn.execute("""
        UPDATE review_schedule
        SET ease_factor=?, interval_days=?, repetitions=?, next_review=?, last_reviewed=date('now')
        WHERE user_id=? AND question_id=?
    """, (ef, interval, n, next_review, user_id, question_id))
    conn.commit()
    conn.close()


# ─── Answers ─────────────────────────────────────────────────────────────────
def record_answer(user_id: int, question_id: int, user_answer: str,
                  is_correct: bool, time_taken: int = 0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO answers (user_id, question_id, user_answer, is_correct, time_taken_sec) VALUES (?,?,?,?,?)",
        (user_id, question_id, user_answer, int(is_correct), time_taken)
    )

    today = date.today().isoformat()
    conn.execute("""
        INSERT INTO user_performance (user_id, stat_date, questions_attempted, questions_correct)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id, stat_date) DO UPDATE SET
            questions_attempted = questions_attempted + 1,
            questions_correct = questions_correct + ?
    """, (user_id, today, int(is_correct), int(is_correct)))
    conn.commit()
    conn.close()


# ─── Stats ────────────────────────────────────────────────────────────────────
def get_stats(user_id: int = 1) -> Dict:
    conn = get_conn()
    total_q = conn.execute("SELECT COUNT(*) as c FROM questions").fetchone()["c"]
    total_docs = conn.execute("SELECT COUNT(*) as c FROM pdf_documents WHERE status='done'").fetchone()["c"]
    total_ans = conn.execute("SELECT COUNT(*) as c FROM answers WHERE user_id=?", (user_id,)).fetchone()["c"]
    correct_ans = conn.execute("SELECT COUNT(*) as c FROM answers WHERE user_id=? AND is_correct=1", (user_id,)).fetchone()["c"]
    due_today = conn.execute(
        "SELECT COUNT(*) as c FROM review_schedule WHERE user_id=? AND next_review<=date('now')",
        (user_id,)
    ).fetchone()["c"]
    perf_rows = conn.execute(
        "SELECT * FROM user_performance WHERE user_id=? ORDER BY stat_date DESC LIMIT 30",
        (user_id,)
    ).fetchall()
    mistakes_count = conn.execute(
        "SELECT COUNT(DISTINCT question_id) as c FROM answers WHERE user_id=? AND is_correct=0",
        (user_id,)
    ).fetchone()["c"]
    conn.close()
    return {
        "total_questions": total_q,
        "total_docs": total_docs,
        "total_answered": total_ans,
        "total_correct": correct_ans,
        "accuracy": round(correct_ans / total_ans * 100, 1) if total_ans else 0,
        "due_today": due_today,
        "mistakes_count": mistakes_count,
        "performance": [dict(r) for r in perf_rows]
    }


# ─── Cache ────────────────────────────────────────────────────────────────────
def cache_get(key: str) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cache_store WHERE cache_key=?", (key,)).fetchone()
    if row:
        conn.execute("UPDATE cache_store SET hit_count=hit_count+1 WHERE cache_key=?", (key,))
        conn.commit()
    conn.close()
    return json.loads(row["response_json"]) if row else None


def cache_set(key: str, prompt_hash: str, data: Dict, tokens: int = 0):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO cache_store (cache_key, prompt_hash, response_json, tokens_used)
        VALUES (?, ?, ?, ?)
    """, (key, prompt_hash, json.dumps(data, ensure_ascii=False), tokens))
    conn.commit()
    conn.close()


def cache_stats() -> Dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as entries, SUM(hit_count) as hits, SUM(tokens_used) as tokens FROM cache_store"
    ).fetchone()
    conn.close()
    return dict(row) if row else {}
