"""
Company accounts and sign-in.

- Accounts live in a small SQLite file (storage/users.db); no extra packages.
- Passwords are never stored: only a salted PBKDF2-SHA256 hash.
- Signing in creates a random session token, kept in an HttpOnly cookie.

All signed-in companies share the same tables and documents (one workspace).
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time

import config

DB_PATH = config.STORAGE_DIR / "users.db"
COOKIE_NAME = "datamind_session"
SESSION_DAYS = 7
PBKDF2_ROUNDS = 200_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init() -> None:
    with _lock, _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL)""")


# ------------------------------------------------------------- passwords
def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    candidate = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest_hex)


# --------------------------------------------------------------- accounts
class AuthError(ValueError):
    """A message that is safe to show to the user."""


def create_user(company: str, name: str, email: str, password: str) -> dict:
    company, name, email = company.strip(), name.strip(), email.strip().lower()
    if not company or not name:
        raise AuthError("Enter your company name and your name.")
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    if len(password) < 8:
        raise AuthError("Use a password of at least 8 characters.")
    with _lock, _db() as con:
        if con.execute("SELECT 1 FROM users WHERE email = ?", [email]).fetchone():
            raise AuthError("An account with this email already exists. Sign in instead.")
        cur = con.execute(
            "INSERT INTO users (company, name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
            [company, name, email, _hash_password(password), int(time.time())])
        return {"id": cur.lastrowid, "company": company, "name": name, "email": email}


def authenticate(email: str, password: str) -> dict:
    with _lock, _db() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", [email.strip().lower()]).fetchone()
    if not row or not _check_password(password, row["password_hash"]):
        raise AuthError("Email or password is incorrect.")
    return {"id": row["id"], "company": row["company"], "name": row["name"], "email": row["email"]}


# --------------------------------------------------------------- sessions
def start_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with _lock, _db() as con:
        con.execute("DELETE FROM sessions WHERE expires_at < ?", [now])
        con.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                    [token, user_id, now + SESSION_DAYS * 86400])
    return token


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    with _lock, _db() as con:
        row = con.execute(
            "SELECT u.id, u.company, u.name, u.email FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.expires_at > ?", [token, int(time.time())]).fetchone()
    return dict(row) if row else None


def end_session(token: str | None) -> None:
    if token:
        with _lock, _db() as con:
            con.execute("DELETE FROM sessions WHERE token = ?", [token])


def cookie_settings() -> dict:
    return {"key": COOKIE_NAME, "httponly": True, "samesite": "lax",
            "max_age": SESSION_DAYS * 86400, "path": "/"}
