"""
Persistent SQLite layer.
IMPORTANT: rows are never DELETEd from here. Expiry / rejection / ban are
handled by flipping a `status` column so history + "data safety" is kept
forever, exactly as requested.
"""
import sqlite3
import random
import string
import threading
from datetime import datetime, timedelta

import config

_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _lock, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                joined_at   TEXT,
                banned      INTEGER DEFAULT 0,
                banned_at   TEXT,
                ban_reason  TEXT,
                bonus_days  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id   INTEGER,
                referred_id   INTEGER,
                created_at    TEXT,
                rewarded      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS violations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                reason      TEXT,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS keys (
                key_code        TEXT PRIMARY KEY,
                assigned_username TEXT,
                category        TEXT DEFAULT 'bot',   -- bot / api / website
                days            INTEGER,
                price           REAL DEFAULT 0,        -- days * rate_per_day at creation time
                max_devices     INTEGER,
                created_at      TEXT,
                created_by      INTEGER,
                activated_by    INTEGER,
                activated_at    TEXT,
                expires_at      TEXT,
                status          TEXT DEFAULT 'unused', -- unused / active / expired / banned
                priority        INTEGER DEFAULT 0,     -- 1 = jumps the waitlist queue
                vip             INTEGER DEFAULT 0,     -- 1 = priority + bigger resource limit
                is_trial        INTEGER DEFAULT 0      -- 1 = free trial key
            );

            CREATE TABLE IF NOT EXISTS hostings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                key_code      TEXT,
                category      TEXT DEFAULT 'bot',
                filename      TEXT,
                filepath      TEXT,
                language      TEXT,
                status        TEXT DEFAULT 'pending', -- pending/running/stopped/rejected/expired
                pid           INTEGER,
                port          INTEGER,
                slot_number   INTEGER,
                requested_at  TEXT,
                approved_at   TEXT,
                expires_at    TEXT,
                reminded      INTEGER DEFAULT 0,
                priority      INTEGER DEFAULT 0,
                vip           INTEGER DEFAULT 0,
                is_trial      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS web_verifications (
                telegram_id  INTEGER PRIMARY KEY,
                pin          TEXT,
                expires_at   TEXT,
                attempts     INTEGER DEFAULT 0,
                created_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS trial_claims (
                token        TEXT PRIMARY KEY,
                telegram_id  INTEGER,
                status       TEXT DEFAULT 'pending_task', -- pending_task / task_done / completed
                created_at   TEXT,
                expires_at   TEXT
            );
            """
        )
        # lightweight migration for DBs created before the `reminded` column existed
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(hostings)").fetchall()}
        if "reminded" not in cols:
            conn.execute("ALTER TABLE hostings ADD COLUMN reminded INTEGER DEFAULT 0")

        ucols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        for col, decl in (("banned", "INTEGER DEFAULT 0"), ("banned_at", "TEXT"), ("ban_reason", "TEXT"),
                          ("bonus_days", "INTEGER DEFAULT 0"), ("trial_used", "INTEGER DEFAULT 0")):
            if col not in ucols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")

        kcols = {r["name"] for r in conn.execute("PRAGMA table_info(keys)").fetchall()}
        for col in ("priority", "vip", "is_trial"):
            if col not in kcols:
                conn.execute(f"ALTER TABLE keys ADD COLUMN {col} INTEGER DEFAULT 0")

        hcols = {r["name"] for r in conn.execute("PRAGMA table_info(hostings)").fetchall()}
        for col in ("priority", "vip", "is_trial"):
            if col not in hcols:
                conn.execute(f"ALTER TABLE hostings ADD COLUMN {col} INTEGER DEFAULT 0")
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')"
        )
        conn.commit()


# ---------- users ----------
def upsert_user(user_id: int, username: str) -> bool:
    """Returns True if this user_id is brand new (first /start)."""
    with _lock, _conn() as conn:
        existing = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.execute(
            "INSERT INTO users (user_id, username, joined_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username or "", datetime.utcnow().isoformat()),
        )
        conn.commit()
        return existing is None


def find_user_by_username(username: str):
    username = username.lstrip("@")
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return row


# ---------- referrals & bonus days ----------
def record_referral(referrer_id: int, referred_id: int):
    """Only records once per referred user (their very first /start with a ref link)."""
    if referrer_id == referred_id:
        return
    with _lock, _conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_id=?", (referred_id,)
        ).fetchone()
        if existing:
            return
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id, created_at, rewarded) VALUES (?,?,?,0)",
            (referrer_id, referred_id, datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_unrewarded_referral(referred_id: int):
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT * FROM referrals WHERE referred_id=? AND rewarded=0", (referred_id,)
        ).fetchone()


def mark_referral_rewarded(referral_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE referrals SET rewarded=1 WHERE id=?", (referral_id,))
        conn.commit()


def add_bonus_days(user_id: int, days: int):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET bonus_days = COALESCE(bonus_days,0) + ? WHERE user_id=?",
            (days, user_id),
        )
        conn.commit()


def pop_bonus_days(user_id: int) -> int:
    """Returns the user's banked free days and resets them to 0 (call when generating their key)."""
    with _lock, _conn() as conn:
        row = conn.execute("SELECT bonus_days FROM users WHERE user_id=?", (user_id,)).fetchone()
        bonus = row["bonus_days"] if row else 0
        if bonus:
            conn.execute("UPDATE users SET bonus_days=0 WHERE user_id=?", (user_id,))
            conn.commit()
        return bonus or 0


def get_bonus_days(user_id: int) -> int:
    """Peek at banked free days without resetting them (for display)."""
    with _lock, _conn() as conn:
        row = conn.execute("SELECT bonus_days FROM users WHERE user_id=?", (user_id,)).fetchone()
        return (row["bonus_days"] if row else 0) or 0


def has_previous_key(username: str, category: str) -> bool:
    """True if this username has ever had a non-unused key in this category (i.e. this is a renewal)."""
    username = username.lstrip("@")
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM keys WHERE assigned_username=? COLLATE NOCASE AND category=? "
            "AND status != 'unused' LIMIT 1",
            (username, category),
        ).fetchone()
        return row is not None


# ---------- rules / violations / bans ----------
def add_violation(user_id: int, reason: str) -> int:
    """Records a rule-violation strike and returns the user's total strike count."""
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO violations (user_id, reason, created_at) VALUES (?,?,?)",
            (user_id, reason, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return conn.execute(
            "SELECT COUNT(*) c FROM violations WHERE user_id=?", (user_id,)
        ).fetchone()["c"]


def violation_count(user_id: int) -> int:
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM violations WHERE user_id=?", (user_id,)
        ).fetchone()["c"]


def ban_user(user_id: int, reason: str):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET banned=1, banned_at=?, ban_reason=? WHERE user_id=?",
            (datetime.utcnow().isoformat(), reason, user_id),
        )
        conn.commit()


def unban_user(user_id: int):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE users SET banned=0, banned_at=NULL, ban_reason=NULL WHERE user_id=?",
            (user_id,),
        )
        conn.commit()


def is_banned(user_id: int) -> bool:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["banned"])


def banned_users():
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM users WHERE banned=1").fetchall()


# ---------- keys ----------
def generate_key_code(length: int = 8) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_key(days: int, max_devices: int, assigned_username: str, created_by: int,
                category: str = "bot", price: float = 0,
                priority: int = 0, vip: int = 0, is_trial: int = 0, key_length: int = 8) -> str:
    code = generate_key_code(key_length)
    with _lock, _conn() as conn:
        # ensure uniqueness
        while conn.execute("SELECT 1 FROM keys WHERE key_code=?", (code,)).fetchone():
            code = generate_key_code(key_length)
        conn.execute(
            "INSERT INTO keys (key_code, assigned_username, category, days, price, "
            "max_devices, created_at, created_by, status, priority, vip, is_trial) "
            "VALUES (?,?,?,?,?,?,?,?, 'unused', ?,?,?)",
            (code, assigned_username.lstrip("@"), category, days, price, max_devices,
             datetime.utcnow().isoformat(), created_by, priority, vip, is_trial),
        )
        conn.commit()
    return code


def revenue_today() -> float:
    today = datetime.utcnow().date().isoformat()
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(price),0) s FROM keys WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()
        return row["s"]


def all_time_revenue() -> float:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(price),0) s FROM keys").fetchone()
        return row["s"]


def all_user_ids():
    with _lock, _conn() as conn:
        return [r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()]


def get_key(code: str):
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM keys WHERE key_code=?", (code,)).fetchone()


def activate_key(code: str, user_id: int):
    now = datetime.utcnow()
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM keys WHERE key_code=?", (code,)).fetchone()
        if not row:
            return None
        expires_at = now + timedelta(days=row["days"])
        conn.execute(
            "UPDATE keys SET status='active', activated_by=?, activated_at=?, "
            "expires_at=? WHERE key_code=?",
            (user_id, now.isoformat(), expires_at.isoformat(), code),
        )
        conn.commit()
        return expires_at


def ban_key(code: str):
    with _lock, _conn() as conn:
        conn.execute("UPDATE keys SET status='banned' WHERE key_code=?", (code,))
        conn.commit()


def keys_created_today():
    today = datetime.utcnow().date().isoformat()
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM keys WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()["c"]


def keys_activated_today():
    today = datetime.utcnow().date().isoformat()
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM keys WHERE activated_at LIKE ?", (f"{today}%",)
        ).fetchone()["c"]


# ---------- hostings ----------
def create_hosting_request(user_id, key_code, filename, filepath, language, category="bot",
                            priority: int = 0, vip: int = 0, is_trial: int = 0):
    with _lock, _conn() as conn:
        cur = conn.execute(
            "INSERT INTO hostings (user_id, key_code, category, filename, filepath, language, "
            "status, requested_at, priority, vip, is_trial) VALUES (?,?,?,?,?,?, 'pending', ?,?,?,?)",
            (user_id, key_code, category, filename, filepath, language,
             datetime.utcnow().isoformat(), priority, vip, is_trial),
        )
        conn.commit()
        return cur.lastrowid


def get_hosting(hosting_id: int):
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM hostings WHERE id=?", (hosting_id,)).fetchone()


def used_slots_count():
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM hostings WHERE status='running'"
        ).fetchone()["c"]


def next_free_slot_number():
    with _lock, _conn() as conn:
        used = {r["slot_number"] for r in conn.execute(
            "SELECT slot_number FROM hostings WHERE status='running'"
        ).fetchall()}
    for n in range(1, config.MAX_SLOTS + 1):
        if n not in used:
            return n
    return None


def approve_hosting(hosting_id: int, pid: int, slot_number: int, expires_at: str, port: int = None):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE hostings SET status='running', pid=?, slot_number=?, port=?, "
            "approved_at=?, expires_at=? WHERE id=?",
            (pid, slot_number, port, datetime.utcnow().isoformat(), expires_at, hosting_id),
        )
        conn.commit()


def reject_hosting(hosting_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE hostings SET status='rejected' WHERE id=?", (hosting_id,))
        conn.commit()


def stop_hosting(hosting_id: int, reason_status="stopped"):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE hostings SET status=?, pid=NULL, slot_number=NULL WHERE id=?",
            (reason_status, hosting_id),
        )
        conn.commit()


def running_hostings():
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM hostings WHERE status='running'").fetchall()


def pending_hostings():
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM hostings WHERE status='pending'").fetchall()


def waitlist_hosting(hosting_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE hostings SET status='waitlisted' WHERE id=?", (hosting_id,))
        conn.commit()


def next_waitlisted():
    """Priority/VIP requests jump ahead; otherwise FIFO — 'ek-ek karke line'."""
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT * FROM hostings WHERE status='waitlisted' "
            "ORDER BY (vip OR priority) DESC, vip DESC, requested_at ASC LIMIT 1"
        ).fetchone()


def move_waitlisted_to_pending(hosting_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE hostings SET status='pending' WHERE id=?", (hosting_id,))
        conn.commit()


def hostings_started_today():
    today = datetime.utcnow().date().isoformat()
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM hostings WHERE approved_at LIKE ?", (f"{today}%",)
        ).fetchone()["c"]


def hostings_expiring_soon(hours: int = 24):
    """Running hostings that expire within `hours` and haven't been reminded yet."""
    cutoff = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    now = datetime.utcnow().isoformat()
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT * FROM hostings WHERE status='running' AND reminded=0 "
            "AND expires_at IS NOT NULL AND expires_at <= ? AND expires_at > ?",
            (cutoff, now),
        ).fetchall()


def mark_reminded(hosting_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE hostings SET reminded=1 WHERE id=?", (hosting_id,))
        conn.commit()


# ---------- settings ----------
def get_setting(key: str, default=None):
    with _lock, _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


# ---------- free trial ----------
def has_used_trial(user_id: int) -> bool:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT trial_used FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["trial_used"])


def mark_trial_used(user_id: int):
    with _lock, _conn() as conn:
        conn.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (user_id,))
        conn.commit()


def running_trial_count() -> int:
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM hostings WHERE status='running' AND is_trial=1"
        ).fetchone()["c"]


# ---------- website PIN verification ----------
def find_user_by_id(user_id: int):
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def create_pin(telegram_id: int, pin: str, expires_at: str):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO web_verifications (telegram_id, pin, expires_at, attempts, created_at) "
            "VALUES (?,?,?,0,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET pin=excluded.pin, expires_at=excluded.expires_at, "
            "attempts=0, created_at=excluded.created_at",
            (telegram_id, pin, expires_at, datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_pin(telegram_id: int):
    with _lock, _conn() as conn:
        return conn.execute(
            "SELECT * FROM web_verifications WHERE telegram_id=?", (telegram_id,)
        ).fetchone()


def clear_pin(telegram_id: int):
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM web_verifications WHERE telegram_id=?", (telegram_id,))
        conn.commit()


def increment_pin_attempts(telegram_id: int) -> int:
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE web_verifications SET attempts = attempts + 1 WHERE telegram_id=?",
            (telegram_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT attempts FROM web_verifications WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
        return row["attempts"] if row else 0


# ---------- trial claim tokens (link-locker task tracking) ----------
def create_trial_claim(telegram_id: int, expires_seconds: int) -> str:
    token = "".join(random.choices(string.ascii_lowercase + string.digits, k=24))
    expires_at = (datetime.utcnow() + timedelta(seconds=expires_seconds)).isoformat()
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO trial_claims (token, telegram_id, status, created_at, expires_at) "
            "VALUES (?,?, 'pending_task', ?, ?)",
            (token, telegram_id, datetime.utcnow().isoformat(), expires_at),
        )
        conn.commit()
    return token


def get_trial_claim(token: str):
    with _lock, _conn() as conn:
        return conn.execute("SELECT * FROM trial_claims WHERE token=?", (token,)).fetchone()


def mark_trial_claim_task_done(token: str):
    with _lock, _conn() as conn:
        conn.execute("UPDATE trial_claims SET status='task_done' WHERE token=?", (token,))
        conn.commit()


def mark_trial_claim_completed(token: str):
    with _lock, _conn() as conn:
        conn.execute("UPDATE trial_claims SET status='completed' WHERE token=?", (token,))
        conn.commit()
