import asyncio
import csv
import io
import json
import os
import zipfile

import aiosqlite

import config
import roles
import timeutil

_db: aiosqlite.Connection | None = None

NOTIFY_KEYS = {
    "events": "notify_events",
    "votes": "notify_votes",
    "emergency": "notify_emergency",
    "team": "notify_team",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id            INTEGER PRIMARY KEY,
    username         TEXT,
    name             TEXT,
    nick             TEXT,
    age              INTEGER,
    hours            INTEGER DEFAULT 0,
    role             TEXT DEFAULT 'member',
    status           TEXT DEFAULT 'new',   -- new | pending | accepted | rejected | banned
    reputation       INTEGER DEFAULT 0,
    warns            INTEGER DEFAULT 0,
    notify_events    INTEGER DEFAULT 1,
    notify_votes     INTEGER DEFAULT 1,
    notify_emergency INTEGER DEFAULT 1,
    notify_team      INTEGER DEFAULT 1,
    game_roles       TEXT DEFAULT '',
    prime_time       TEXT,
    steam_id         TEXT,
    steam_name       TEXT,
    steam_hours      INTEGER,
    steam_synced_at  TEXT,
    hours_source     TEXT DEFAULT 'manual',  -- manual | steam | admin
    inv_items        INTEGER,
    inv_unique       INTEGER,
    inv_marketable   INTEGER,
    inv_updated      TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    name        TEXT,
    nick        TEXT,
    age         INTEGER,
    hours       INTEGER,
    about       TEXT,
    prime_time  TEXT,
    status      TEXT DEFAULT 'pending',  -- pending | accepted | rejected
    admin_id    INTEGER,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS facts_custom (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tier       TEXT NOT NULL,            -- novice | mid | pro
    text       TEXT NOT NULL,
    added_by   INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS steam_dlc (
    appid INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_dlc (
    user_id INTEGER NOT NULL,
    appid   INTEGER NOT NULL,
    PRIMARY KEY (user_id, appid)
);
CREATE TABLE IF NOT EXISTS team_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    text           TEXT NOT NULL,
    post_text      TEXT,
    status         TEXT DEFAULT 'open',   -- open | closed
    channel_msg_id INTEGER,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS team_responses (
    request_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (request_id, user_id)
);
CREATE TABLE IF NOT EXISTS emergencies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS emergency_acks (
    emergency_id INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    PRIMARY KEY (emergency_id, user_id)
);
CREATE TABLE IF NOT EXISTS polls (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    question   TEXT NOT NULL,
    options    TEXT NOT NULL,            -- JSON-список вариантов
    status     TEXT DEFAULT 'open',      -- open | closed
    ends_at    TEXT,                     -- UTC или NULL (без срока)
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS poll_votes (
    poll_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    option_idx INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (poll_id, user_id)
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    place       TEXT,
    starts_at   TEXT NOT NULL,           -- UTC
    created_by  INTEGER,
    reminded    INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS event_rsvp (
    event_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    PRIMARY KEY (event_id, user_id)
);
CREATE TABLE IF NOT EXISTS rep_votes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id    INTEGER NOT NULL,
    to_id      INTEGER NOT NULL,
    value      INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS complaints (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id    INTEGER NOT NULL,
    target_id  INTEGER NOT NULL,
    text       TEXT,
    status     TEXT DEFAULT 'pending',   -- pending | warned | dismissed
    admin_id   INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    status     TEXT DEFAULT 'open',      -- open | closed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ticket_msgs (
    group_msg_id INTEGER PRIMARY KEY,
    ticket_id    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_actions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER NOT NULL,
    action     TEXT NOT NULL,
    target_id  INTEGER,
    details    TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Колонки, которые добавились после первого этапа (для уже существующей bot.db)
USER_MIGRATIONS = {
    "notify_events": "INTEGER DEFAULT 1",
    "notify_votes": "INTEGER DEFAULT 1",
    "notify_emergency": "INTEGER DEFAULT 1",
    "notify_team": "INTEGER DEFAULT 1",
    "game_roles": "TEXT DEFAULT ''",
    "prime_time": "TEXT",
    "steam_id": "TEXT",
    "steam_name": "TEXT",
    "steam_hours": "INTEGER",
    "steam_synced_at": "TEXT",
    "hours_source": "TEXT DEFAULT 'manual'",
    "inv_items": "INTEGER",
    "inv_unique": "INTEGER",
    "inv_marketable": "INTEGER",
    "inv_updated": "TEXT",
}

APP_MIGRATIONS = {"prime_time": "TEXT"}

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_rep ON users(reputation);
CREATE INDEX IF NOT EXISTS idx_rep_votes_from ON rep_votes(from_id, created_at);
CREATE INDEX IF NOT EXISTS idx_rep_votes_pair ON rep_votes(from_id, to_id);
CREATE INDEX IF NOT EXISTS idx_actions_admin ON admin_actions(admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id, status);
CREATE INDEX IF NOT EXISTS idx_apps_user ON applications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(starts_at);
CREATE INDEX IF NOT EXISTS idx_polls_status ON polls(status);
CREATE INDEX IF NOT EXISTS idx_team_user ON team_requests(user_id, status);
"""


async def init() -> None:
    global _db
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")    # чтение не блокируется записью
    await _db.execute("PRAGMA synchronous=FULL")    # максимальная надёжность: запись на диск при каждом коммите
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.executescript(SCHEMA)
    await _migrate("users", USER_MIGRATIONS)
    await _migrate("applications", APP_MIGRATIONS)
    await _db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_steam ON users(steam_id) WHERE steam_id IS NOT NULL"
    )
    await _db.executescript(INDEXES)
    await _db.commit()


async def _migrate(table: str, columns: dict) -> None:
    async with _db.execute(f"PRAGMA table_info({table})") as cur:
        existing = {r["name"] for r in await cur.fetchall()}
    for col, decl in columns.items():
        if col not in existing:
            await _db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


async def seed_owners(ids) -> None:
    """Владельцам из .env даём роль. Статус не трогаем: анкету они заполняют сами."""
    for tg_id in ids:
        await _db.execute(
            "INSERT INTO users (tg_id, role, status) VALUES (?, 'owner', 'new') "
            "ON CONFLICT(tg_id) DO UPDATE SET role = 'owner'",
            (tg_id,),
        )
    await _db.commit()


async def _one(query: str, args: tuple = ()):
    async with _db.execute(query, args) as cur:
        return await cur.fetchone()


async def _all(query: str, args: tuple = ()):
    async with _db.execute(query, args) as cur:
        return await cur.fetchall()


async def _count(query: str, args: tuple = ()) -> int:
    row = await _one(query, args)
    return row[0] if row else 0


# ---------- пользователи ----------

async def get_user(tg_id: int):
    return await _one("SELECT * FROM users WHERE tg_id = ?", (tg_id,))


async def get_level(tg_id: int) -> int:
    row = await get_user(tg_id)
    return roles.level(row["role"]) if row else 0


async def ensure_user(tg_id: int, username: str | None) -> None:
    await _db.execute(
        "INSERT INTO users (tg_id, username) VALUES (?, ?) "
        "ON CONFLICT(tg_id) DO UPDATE SET username = excluded.username",
        (tg_id, username),
    )
    await _db.commit()


async def set_user_status(tg_id: int, status: str) -> None:
    await _db.execute("UPDATE users SET status = ? WHERE tg_id = ?", (status, tg_id))
    await _db.commit()


async def update_nick(tg_id: int, nick: str) -> None:
    await _db.execute("UPDATE users SET nick = ? WHERE tg_id = ?", (nick, tg_id))
    await _db.commit()


async def toggle_notify(tg_id: int, key: str) -> None:
    col = NOTIFY_KEYS[key]  # только значения из белого списка
    await _db.execute(f"UPDATE users SET {col} = 1 - {col} WHERE tg_id = ?", (tg_id,))
    await _db.commit()


# ---------- состав ----------

async def composition() -> dict:
    staff_rows = await _all(
        "SELECT role, COUNT(*) AS c FROM users "
        "WHERE status = 'accepted' AND role != 'member' GROUP BY role"
    )
    return {
        "members": await _count("SELECT COUNT(*) FROM users WHERE status = 'accepted'"),
        "staff": {r["role"]: r["c"] for r in staff_rows},
        "apps_accepted": await _count("SELECT COUNT(*) FROM applications WHERE status = 'accepted'"),
        "apps_pending": await _count("SELECT COUNT(*) FROM applications WHERE status = 'pending'"),
    }


# ---------- анкеты ----------

async def create_application(
    user_id: int, name: str, nick: str, age: int, hours: int, prime_time: str, about: str
) -> int:
    cur = await _db.execute(
        "INSERT INTO applications (user_id, name, nick, age, hours, prime_time, about) VALUES (?,?,?,?,?,?,?)",
        (user_id, name, nick, age, hours, prime_time, about),
    )
    await _db.execute(
        "UPDATE users SET status = 'pending' WHERE tg_id = ? AND status NOT IN ('banned', 'blacklisted')",
        (user_id,),
    )
    await _db.commit()
    return cur.lastrowid


async def get_application(app_id: int):
    return await _one("SELECT * FROM applications WHERE id = ?", (app_id,))


async def decide_application(app_id: int, accepted: bool, admin_id: int, accept_status: str = "onboarding") -> None:
    """accepted=True переводит участника в обучение (onboarding); владелец сразу получает accepted."""
    app = await get_application(app_id)
    status = "accepted" if accepted else "rejected"
    await _db.execute(
        "UPDATE applications SET status = ?, admin_id = ? WHERE id = ?",
        (status, admin_id, app_id),
    )
    if accepted:
        await _db.execute(
            "UPDATE users SET status = ?, name = ?, nick = ?, age = ?, hours = ?, prime_time = ?, "
            "hours_source = CASE WHEN steam_id IS NOT NULL THEN hours_source ELSE 'manual' END "
            "WHERE tg_id = ? AND status NOT IN ('banned', 'blacklisted')",
            (accept_status, app["name"], app["nick"], app["age"], app["hours"], app["prime_time"], app["user_id"]),
        )
    else:
        await _db.execute(
            "UPDATE users SET status='rejected' WHERE tg_id=? AND status NOT IN ('banned', 'blacklisted')",
            (app["user_id"],),
        )
    await _db.commit()


# ---------- настройки бота ----------

async def get_setting(key: str, default: str = "0") -> str:
    row = await _one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    await _db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await _db.commit()


# ---------- управление участниками ----------

LIST_KINDS = {
    "all": "status = 'accepted'",
    "banned": "status = 'banned'",
    "black": "status = 'blacklisted'",
    "staff": "status = 'accepted' AND role != 'member'",
}

ACTIONS_SQL = {
    "warn": "UPDATE users SET warns = warns + 1 WHERE tg_id = ?",
    "unwarn": "UPDATE users SET warns = MAX(warns - 1, 0) WHERE tg_id = ?",
    "ban": "UPDATE users SET status = 'banned', role = 'member' WHERE tg_id = ?",
    "unban": "UPDATE users SET status = CASE WHEN name IS NOT NULL THEN 'accepted' ELSE 'new' END WHERE tg_id = ?",
    "kick": "UPDATE users SET status = 'new', role = 'member' WHERE tg_id = ?",
    "black": "UPDATE users SET status = 'blacklisted', role = 'member' WHERE tg_id = ?",
    "unblack": "UPDATE users SET status = 'new' WHERE tg_id = ?",
}

EDITABLE_FIELDS = {"name", "nick", "age", "hours", "reputation"}


async def search_users(q: str, limit: int = 10):
    """Поиск по id, возрасту, @username, нику и имени (без учёта регистра)."""
    q = q.strip().lstrip("@")
    if not q:
        return []
    found = []
    if q.isdigit():
        n = int(q)
        found.extend(await _all("SELECT * FROM users WHERE tg_id = ? OR age = ?", (n, n)))
    needle = q.casefold()
    rows = await _all("SELECT * FROM users WHERE status != 'new' OR name IS NOT NULL ORDER BY created_at")
    for r in rows:
        if any(needle in (r[c] or "").casefold() for c in ("username", "nick", "name")):
            if all(f["tg_id"] != r["tg_id"] for f in found):
                found.append(r)
    return found[:limit]


async def list_users(kind: str, offset: int, limit: int):
    where = LIST_KINDS[kind]  # kind проверяется по белому списку
    total = await _count(f"SELECT COUNT(*) FROM users WHERE {where}")
    rows = await _all(
        f"SELECT * FROM users WHERE {where} ORDER BY created_at LIMIT ? OFFSET ?", (limit, offset)
    )
    return rows, total


async def apply_action(tg_id: int, action: str) -> None:
    await _db.execute(ACTIONS_SQL[action], (tg_id,))
    await _db.commit()


async def set_role(tg_id: int, role: str) -> None:
    await _db.execute("UPDATE users SET role = ? WHERE tg_id = ?", (role, tg_id))
    await _db.commit()


async def update_field(tg_id: int, field: str, value) -> None:
    if field not in EDITABLE_FIELDS:
        raise ValueError(field)
    await _db.execute(f"UPDATE users SET {field} = ? WHERE tg_id = ?", (value, tg_id))
    await _db.commit()


async def log_action(admin_id: int, action: str, target_id: int | None = None, details: str | None = None) -> None:
    await _db.execute(
        "INSERT INTO admin_actions (admin_id, action, target_id, details) VALUES (?,?,?,?)",
        (admin_id, action, target_id, details),
    )
    await _db.commit()


# ---------- репутация ----------

REP_PER_DAY = 5
MAX_OPEN_COMPLAINTS = 3
MAX_OPEN_TICKETS = 3


async def rep_limit() -> int:
    return int(await get_setting("rep_per_day", str(REP_PER_DAY)))


async def rep_votes_left(from_id: int) -> int:
    used = await _count(
        "SELECT COUNT(*) FROM rep_votes WHERE from_id = ? AND created_at > datetime('now', '-1 day')",
        (from_id,),
    )
    return max(await rep_limit() - used, 0)


async def rep_block_reason(from_id: int, to_id: int) -> str | None:
    if from_id == to_id:
        return "Нельзя оценивать самого себя."
    same = await _count(
        "SELECT COUNT(*) FROM rep_votes WHERE from_id = ? AND to_id = ? "
        "AND created_at > datetime('now', '-1 day')",
        (from_id, to_id),
    )
    if same:
        return "Ты уже оценивал этого участника за последние 24 часа."
    if await rep_votes_left(from_id) <= 0:
        return f"Лимит: {await rep_limit()} оценок в сутки. Попробуй завтра."
    return None


async def add_rep(from_id: int, to_id: int, value: int) -> None:
    await _db.execute(
        "INSERT INTO rep_votes (from_id, to_id, value) VALUES (?,?,?)", (from_id, to_id, value)
    )
    await _db.execute("UPDATE users SET reputation = reputation + ? WHERE tg_id = ?", (value, to_id))
    await _db.commit()


async def top_reputation(limit: int = 10):
    return await _all(
        "SELECT * FROM users WHERE status = 'accepted' ORDER BY reputation DESC, created_at LIMIT ?",
        (limit,),
    )


async def rep_rank(tg_id: int) -> int:
    return await _count(
        "SELECT COUNT(*) + 1 FROM users WHERE status = 'accepted' "
        "AND reputation > (SELECT reputation FROM users WHERE tg_id = ?)",
        (tg_id,),
    )


# ---------- жалобы ----------

async def count_open_complaints(from_id: int) -> int:
    return await _count(
        "SELECT COUNT(*) FROM complaints WHERE from_id = ? AND status = 'pending'", (from_id,)
    )


async def create_complaint(from_id: int, target_id: int, text: str) -> int:
    cur = await _db.execute(
        "INSERT INTO complaints (from_id, target_id, text) VALUES (?,?,?)", (from_id, target_id, text)
    )
    await _db.commit()
    return cur.lastrowid


async def get_complaint(cid: int):
    return await _one("SELECT * FROM complaints WHERE id = ?", (cid,))


async def close_complaint(cid: int, status: str, admin_id: int) -> None:
    await _db.execute(
        "UPDATE complaints SET status = ?, admin_id = ? WHERE id = ?", (status, admin_id, cid)
    )
    await _db.commit()


# ---------- обращения к администрации ----------

async def count_open_tickets(user_id: int) -> int:
    return await _count("SELECT COUNT(*) FROM tickets WHERE user_id = ? AND status = 'open'", (user_id,))


async def create_ticket(user_id: int) -> int:
    cur = await _db.execute("INSERT INTO tickets (user_id) VALUES (?)", (user_id,))
    await _db.commit()
    return cur.lastrowid


async def get_ticket(ticket_id: int):
    return await _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))


async def add_ticket_msg(group_msg_id: int, ticket_id: int) -> None:
    await _db.execute(
        "INSERT OR REPLACE INTO ticket_msgs (group_msg_id, ticket_id) VALUES (?,?)",
        (group_msg_id, ticket_id),
    )
    await _db.commit()


async def get_ticket_by_msg(group_msg_id: int):
    return await _one(
        "SELECT t.* FROM tickets t JOIN ticket_msgs m ON m.ticket_id = t.id WHERE m.group_msg_id = ?",
        (group_msg_id,),
    )


async def close_ticket(ticket_id: int) -> None:
    await _db.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
    await _db.commit()


# ---------- получатели рассылок ----------

async def recipients(key: str) -> list[int]:
    """ID принятых участников, у которых включены уведомления данного типа."""
    col = NOTIFY_KEYS[key]
    rows = await _all(f"SELECT tg_id FROM users WHERE status = 'accepted' AND {col} = 1")
    return [r["tg_id"] for r in rows]


# ---------- голосования ----------

def poll_options(p) -> list[str]:
    return json.loads(p["options"])


def poll_is_open(p) -> bool:
    return p["status"] == "open" and (p["ends_at"] is None or p["ends_at"] > timeutil.now_str())


async def create_poll(question: str, options: list[str], ends_at: str | None, created_by: int) -> int:
    cur = await _db.execute(
        "INSERT INTO polls (question, options, ends_at, created_by) VALUES (?,?,?,?)",
        (question, json.dumps(options, ensure_ascii=False), ends_at, created_by),
    )
    await _db.commit()
    return cur.lastrowid


async def get_poll(pid: int):
    return await _one("SELECT * FROM polls WHERE id = ?", (pid,))


async def active_polls(limit: int = 10):
    return await _all(
        "SELECT * FROM polls WHERE status = 'open' AND (ends_at IS NULL OR ends_at > ?) "
        "ORDER BY id DESC LIMIT ?",
        (timeutil.now_str(), limit),
    )


async def recent_polls(limit: int = 10):
    return await _all("SELECT * FROM polls ORDER BY id DESC LIMIT ?", (limit,))


async def poll_counts(pid: int) -> dict[int, int]:
    rows = await _all(
        "SELECT option_idx, COUNT(*) AS c FROM poll_votes WHERE poll_id = ? GROUP BY option_idx", (pid,)
    )
    return {r["option_idx"]: r["c"] for r in rows}


async def get_vote(pid: int, user_id: int):
    row = await _one("SELECT option_idx FROM poll_votes WHERE poll_id = ? AND user_id = ?", (pid, user_id))
    return row["option_idx"] if row else None


async def add_vote(pid: int, user_id: int, idx: int) -> bool:
    if await get_vote(pid, user_id) is not None:
        return False
    await _db.execute(
        "INSERT OR IGNORE INTO poll_votes (poll_id, user_id, option_idx) VALUES (?,?,?)",
        (pid, user_id, idx),
    )
    await _db.commit()
    return True


async def close_poll(pid: int) -> None:
    await _db.execute("UPDATE polls SET status = 'closed' WHERE id = ?", (pid,))
    await _db.commit()


async def delete_poll(pid: int) -> None:
    await _db.execute("DELETE FROM poll_votes WHERE poll_id = ?", (pid,))
    await _db.execute("DELETE FROM polls WHERE id = ?", (pid,))
    await _db.commit()


# ---------- мероприятия ----------

async def create_event(title: str, description: str, place: str | None, starts_at: str, created_by: int) -> int:
    cur = await _db.execute(
        "INSERT INTO events (title, description, place, starts_at, created_by) VALUES (?,?,?,?,?)",
        (title, description, place, starts_at, created_by),
    )
    await _db.commit()
    return cur.lastrowid


async def get_event(eid: int):
    return await _one("SELECT * FROM events WHERE id = ?", (eid,))


async def events_between(start_utc: str, end_utc: str):
    return await _all(
        "SELECT * FROM events WHERE starts_at >= ? AND starts_at < ? ORDER BY starts_at",
        (start_utc, end_utc),
    )


async def upcoming_events(limit: int = 10):
    """Будущие и начавшиеся не более 2 часов назад."""
    return await _all(
        "SELECT * FROM events WHERE starts_at >= ? ORDER BY starts_at LIMIT ?",
        (timeutil.to_str(timeutil.now_utc() - __import__("datetime").timedelta(hours=2)), limit),
    )


async def delete_event(eid: int) -> None:
    await _db.execute("DELETE FROM event_rsvp WHERE event_id = ?", (eid,))
    await _db.execute("DELETE FROM events WHERE id = ?", (eid,))
    await _db.commit()


async def is_going(eid: int, user_id: int) -> bool:
    return bool(await _count(
        "SELECT COUNT(*) FROM event_rsvp WHERE event_id = ? AND user_id = ?", (eid, user_id)
    ))


async def toggle_rsvp(eid: int, user_id: int) -> bool:
    """Возвращает True, если теперь участник идёт."""
    if await is_going(eid, user_id):
        await _db.execute("DELETE FROM event_rsvp WHERE event_id = ? AND user_id = ?", (eid, user_id))
        going = False
    else:
        await _db.execute("INSERT OR IGNORE INTO event_rsvp (event_id, user_id) VALUES (?,?)", (eid, user_id))
        going = True
    await _db.commit()
    return going


async def rsvp_count(eid: int) -> int:
    return await _count("SELECT COUNT(*) FROM event_rsvp WHERE event_id = ?", (eid,))


async def rsvp_names(eid: int, limit: int = 15) -> list[str]:
    rows = await _all(
        "SELECT u.nick, u.name, u.tg_id FROM event_rsvp r JOIN users u ON u.tg_id = r.user_id "
        "WHERE r.event_id = ? ORDER BY r.rowid LIMIT ?",
        (eid, limit),
    )
    return [r["nick"] or r["name"] or str(r["tg_id"]) for r in rows]


async def rsvp_user_ids(eid: int, only_notify: bool = False) -> list[int]:
    extra = " AND u.notify_events = 1" if only_notify else ""
    rows = await _all(
        "SELECT r.user_id FROM event_rsvp r JOIN users u ON u.tg_id = r.user_id "
        f"WHERE r.event_id = ?{extra}",
        (eid,),
    )
    return [r["user_id"] for r in rows]


async def events_to_remind():
    """События, которые начнутся в ближайший час и ещё не получили напоминание."""
    return await _all(
        "SELECT * FROM events WHERE reminded = 0 AND starts_at > ? AND starts_at <= ?",
        (timeutil.now_str(), timeutil.in_minutes(60)),
    )


async def mark_reminded(eid: int) -> None:
    await _db.execute("UPDATE events SET reminded = 1 WHERE id = ?", (eid,))
    await _db.commit()


# ---------- игровые роли ----------

async def toggle_game_role(tg_id: int, key: str) -> str:
    """-> 'added' | 'removed' | 'limit' | 'invalid'"""
    if key not in roles.GAME_ROLES:
        return "invalid"
    u = await get_user(tg_id)
    current = roles.parse_game_roles(u["game_roles"]) if u else []
    if key in current:
        current.remove(key)
        result = "removed"
    elif len(current) >= roles.MAX_GAME_ROLES:
        return "limit"
    else:
        current.append(key)
        result = "added"
    await _db.execute("UPDATE users SET game_roles = ? WHERE tg_id = ?", (",".join(current), tg_id))
    await _db.commit()
    return result


# ---------- автобан по варнам ----------

async def maybe_autoban(tg_id: int) -> bool:
    if await get_setting("autoban", "0") != "1":
        return False
    u = await get_user(tg_id)
    if u and u["status"] == "accepted" and u["warns"] >= 3:
        await apply_action(tg_id, "ban")
        return True
    return False


# ---------- поиск команды ----------

MAX_OPEN_TEAM = 2


async def create_team_request(user_id: int, text: str) -> int:
    cur = await _db.execute("INSERT INTO team_requests (user_id, text) VALUES (?,?)", (user_id, text))
    await _db.commit()
    return cur.lastrowid


async def set_team_post(rid: int, msg_id: int, post_text: str) -> None:
    await _db.execute(
        "UPDATE team_requests SET channel_msg_id = ?, post_text = ? WHERE id = ?", (msg_id, post_text, rid)
    )
    await _db.commit()


async def get_team_request(rid: int):
    return await _one("SELECT * FROM team_requests WHERE id = ?", (rid,))


async def count_open_team_requests(user_id: int) -> int:
    return await _count(
        "SELECT COUNT(*) FROM team_requests WHERE user_id = ? AND status = 'open'", (user_id,)
    )


async def my_team_requests(user_id: int, limit: int = 10):
    return await _all(
        "SELECT * FROM team_requests WHERE user_id = ? AND status = 'open' ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )


async def add_team_response(rid: int, user_id: int) -> bool:
    exists = await _count(
        "SELECT COUNT(*) FROM team_responses WHERE request_id = ? AND user_id = ?", (rid, user_id)
    )
    if exists:
        return False
    await _db.execute("INSERT OR IGNORE INTO team_responses (request_id, user_id) VALUES (?,?)", (rid, user_id))
    await _db.commit()
    return True


async def team_response_count(rid: int) -> int:
    return await _count("SELECT COUNT(*) FROM team_responses WHERE request_id = ?", (rid,))


async def team_responders(rid: int, limit: int = 10):
    return await _all(
        "SELECT u.* FROM team_responses r JOIN users u ON u.tg_id = r.user_id "
        "WHERE r.request_id = ? ORDER BY r.rowid LIMIT ?",
        (rid, limit),
    )


async def close_team_request(rid: int) -> None:
    await _db.execute("UPDATE team_requests SET status = 'closed' WHERE id = ?", (rid,))
    await _db.commit()


# ---------- экстренные сборы ----------

async def create_emergency(text: str, created_by: int) -> int:
    cur = await _db.execute("INSERT INTO emergencies (text, created_by) VALUES (?,?)", (text, created_by))
    await _db.commit()
    return cur.lastrowid


async def get_emergency(eid: int):
    return await _one("SELECT * FROM emergencies WHERE id = ?", (eid,))


async def recent_emergency(minutes: int = 2) -> bool:
    return bool(await _count(
        "SELECT COUNT(*) FROM emergencies WHERE created_at > ?", (timeutil.in_minutes(-minutes),)
    ))


async def ack_emergency(eid: int, user_id: int) -> bool:
    exists = await _count(
        "SELECT COUNT(*) FROM emergency_acks WHERE emergency_id = ? AND user_id = ?", (eid, user_id)
    )
    if exists:
        return False
    await _db.execute("INSERT OR IGNORE INTO emergency_acks (emergency_id, user_id) VALUES (?,?)", (eid, user_id))
    await _db.commit()
    return True


async def emergency_ack_count(eid: int) -> int:
    return await _count("SELECT COUNT(*) FROM emergency_acks WHERE emergency_id = ?", (eid,))


async def emergency_ack_names(eid: int, limit: int = 30) -> list[str]:
    rows = await _all(
        "SELECT u.nick, u.name, u.tg_id FROM emergency_acks a JOIN users u ON u.tg_id = a.user_id "
        "WHERE a.emergency_id = ? ORDER BY a.rowid LIMIT ?",
        (eid, limit),
    )
    return [r["nick"] or r["name"] or str(r["tg_id"]) for r in rows]


# ---------- статистика админов ----------

async def admin_stats(since: str) -> dict:
    rows = await _all(
        "SELECT admin_id, action, COUNT(*) AS c FROM admin_actions WHERE created_at >= ? "
        "GROUP BY admin_id, action",
        (since,),
    )
    out: dict = {}
    for r in rows:
        out.setdefault(r["admin_id"], {})[r["action"]] = r["c"]
    return out


async def staff_users():
    return await _all("SELECT * FROM users WHERE status = 'accepted' AND role != 'member'")


async def fill_staff_defaults(tg_id: int, full_name: str, username: str | None) -> None:
    """Администрации без анкеты подставляем ник и имя из Telegram, чтобы везде было видно, кто это."""
    await _db.execute(
        "UPDATE users SET nick = COALESCE(nick, ?), name = COALESCE(name, ?) "
        "WHERE tg_id = ? AND role != 'member'",
        (username or full_name, full_name, tg_id),
    )
    await _db.commit()


# ---------- прайм-тайм и часы ----------

async def set_prime_time(tg_id: int, text: str) -> None:
    await _db.execute("UPDATE users SET prime_time = ? WHERE tg_id = ?", (text, tg_id))
    await _db.commit()


async def set_manual_hours(tg_id: int, hours: int) -> None:
    await _db.execute(
        "UPDATE users SET hours = ?, hours_source = 'manual' WHERE tg_id = ? AND steam_id IS NULL",
        (hours, tg_id),
    )
    await _db.commit()


async def mark_hours_verified(tg_id: int) -> None:
    await _db.execute("UPDATE users SET hours_source = 'admin' WHERE tg_id = ?", (tg_id,))
    await _db.commit()


# ---------- Steam ----------

async def steam_id_taken(steam_id: str, tg_id: int) -> bool:
    return bool(await _count(
        "SELECT COUNT(*) FROM users WHERE steam_id = ? AND tg_id != ?", (steam_id, tg_id)
    ))


async def set_steam_link(tg_id: int, steam_id: str, name: str, hours: int | None) -> None:
    await _db.execute(
        "UPDATE users SET steam_id = ?, steam_name = ?, steam_hours = ?, steam_synced_at = ?, "
        "hours = COALESCE(?, hours), "
        "hours_source = CASE WHEN ? IS NOT NULL THEN 'steam' ELSE hours_source END "
        "WHERE tg_id = ?",
        (steam_id, name, hours, timeutil.now_str(), hours, hours, tg_id),
    )
    await _db.commit()


async def update_steam_hours(tg_id: int, hours: int) -> None:
    await _db.execute(
        "UPDATE users SET hours = ?, steam_hours = ?, steam_synced_at = ?, hours_source = 'steam' WHERE tg_id = ?",
        (hours, hours, timeutil.now_str(), tg_id),
    )
    await _db.commit()


async def touch_steam_sync(tg_id: int) -> None:
    await _db.execute("UPDATE users SET steam_synced_at = ? WHERE tg_id = ?", (timeutil.now_str(), tg_id))
    await _db.commit()


async def unlink_steam(tg_id: int) -> None:
    await _db.execute(
        "UPDATE users SET steam_id = NULL, steam_name = NULL, steam_hours = NULL, steam_synced_at = NULL, "
        "hours_source = 'manual', inv_items = NULL, inv_unique = NULL, inv_marketable = NULL, inv_updated = NULL "
        "WHERE tg_id = ?",
        (tg_id,),
    )
    await _db.commit()


async def steam_users_due(before: str):
    return await _all(
        "SELECT tg_id, steam_id FROM users WHERE steam_id IS NOT NULL "
        "AND (steam_synced_at IS NULL OR steam_synced_at < ?)",
        (before,),
    )


async def set_inventory(tg_id: int, items: int, unique: int, marketable: int) -> None:
    await _db.execute(
        "UPDATE users SET inv_items = ?, inv_unique = ?, inv_marketable = ?, inv_updated = ? WHERE tg_id = ?",
        (items, unique, marketable, timeutil.now_str(), tg_id),
    )
    await _db.commit()


async def save_dlc_list(items) -> None:
    for appid, name in items:
        await _db.execute("INSERT OR REPLACE INTO steam_dlc (appid, name) VALUES (?, ?)", (appid, name))
    await _db.commit()


async def get_dlc_list():
    return await _all("SELECT appid, name FROM steam_dlc ORDER BY name")


async def user_dlc_ids(user_id: int) -> set:
    rows = await _all(
        "SELECT u.appid FROM user_dlc u JOIN steam_dlc d ON d.appid = u.appid WHERE u.user_id = ?", (user_id,)
    )
    return {r["appid"] for r in rows}


async def toggle_user_dlc(user_id: int, appid: int) -> bool:
    exists = await _count("SELECT COUNT(*) FROM user_dlc WHERE user_id = ? AND appid = ?", (user_id, appid))
    if exists:
        await _db.execute("DELETE FROM user_dlc WHERE user_id = ? AND appid = ?", (user_id, appid))
    else:
        await _db.execute("INSERT OR IGNORE INTO user_dlc (user_id, appid) VALUES (?, ?)", (user_id, appid))
    await _db.commit()
    return not exists


# ---------- резервные копии и служебное ----------

async def backup_to(path: str) -> None:
    """Целостная копия базы одним файлом (работает, пока бот запущен)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    for attempt in range(5):
        try:
            await _db.commit()
            await _db.execute("VACUUM INTO ?", (path,))
            return
        except Exception:
            if attempt == 4:
                raise
            await asyncio.sleep(0.5)


async def cancel_application(app_id: int, user_id: int) -> None:
    """Откат анкеты, если её не удалось передать администрации."""
    await _db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    await _db.execute(
        "UPDATE users SET status = 'new' WHERE tg_id = ? AND status = 'pending'", (user_id,)
    )
    await _db.commit()


async def db_stats() -> dict:
    return {
        "users": await _count("SELECT COUNT(*) FROM users"),
        "members": await _count("SELECT COUNT(*) FROM users WHERE status = 'accepted'"),
        "pending": await _count("SELECT COUNT(*) FROM applications WHERE status = 'pending'"),
        "open_tickets": await _count("SELECT COUNT(*) FROM tickets WHERE status = 'open'"),
        "steam_linked": await _count("SELECT COUNT(*) FROM users WHERE steam_id IS NOT NULL"),
    }


# ---------- свои факты ----------

async def add_custom_fact(tier: str, text: str, added_by: int) -> int:
    cur = await _db.execute(
        "INSERT INTO facts_custom (tier, text, added_by) VALUES (?,?,?)", (tier, text, added_by)
    )
    await _db.commit()
    return cur.lastrowid


async def custom_facts(tier: str | None = None, limit: int = 200):
    if tier:
        return await _all("SELECT * FROM facts_custom WHERE tier = ? ORDER BY id DESC LIMIT ?", (tier, limit))
    return await _all("SELECT * FROM facts_custom ORDER BY id DESC LIMIT ?", (limit,))


async def get_custom_fact(fid: int):
    return await _one("SELECT * FROM facts_custom WHERE id = ?", (fid,))


async def delete_custom_fact(fid: int) -> None:
    await _db.execute("DELETE FROM facts_custom WHERE id = ?", (fid,))
    await _db.commit()


# ---------- надёжность: выгрузка, проверка, закрытие ----------

EXPORT_TABLES = (
    "users", "applications", "admin_actions", "rep_votes", "complaints", "tickets", "polls",
    "poll_votes", "events", "event_rsvp", "team_requests", "team_responses", "emergencies",
    "emergency_acks", "facts_custom",
)


async def export_csv_zip(path: str) -> None:
    """Все таблицы в CSV внутри одного ZIP (открывается в Excel и Google Таблицах)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for table in EXPORT_TABLES:  # имена только из белого списка
            columns = [r["name"] for r in await _all(f"PRAGMA table_info({table})")]
            rows = await _all(f"SELECT * FROM {table}")
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(columns)
            for r in rows:
                writer.writerow(list(r))
            z.writestr(f"{table}.csv", "\ufeff" + buf.getvalue())  # BOM, чтобы Excel видел кириллицу


async def integrity_ok() -> bool:
    row = await _one("PRAGMA integrity_check")
    return bool(row) and row[0] == "ok"


async def close() -> None:
    """Корректное закрытие базы при остановке бота: все записи сохранены, WAL сведён в основной файл."""
    global _db
    if _db is not None:
        await _db.commit()
        try:
            await _db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        await _db.close()
        _db = None
