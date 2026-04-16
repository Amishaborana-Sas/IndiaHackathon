"""
Module 1 — Encrypted Token Vault
================================
Persists pseudonymisation mappings (token -> original value) so authorised
reviewers can re-link records when needed (e.g. for SAE follow-up).

Encryption: Fernet (AES-128-CBC + HMAC-SHA256, from `cryptography`).
Storage:    SQLite, single file, easy to back up.

The vault key is independent of the HMAC secret used for token generation,
so the two can be rotated and held by different roles.
"""

from __future__ import annotations

import base64
import os
import sqlite3
from pathlib import Path
from typing import Iterable

from cryptography.fernet import Fernet

_KEY_ENV = "ANON_VAULT_KEY"


def _load_key() -> bytes:
    """Load or generate a Fernet key. For demos we persist a key file next
    to the vault DB; in production this MUST come from a KMS."""
    key_b64 = os.environ.get(_KEY_ENV)
    if key_b64:
        return key_b64.encode()
    key_path = Path(__file__).with_name("vault.key")
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


class TokenVault:
    """Encrypted key-value store for pseudonymisation tokens."""

    def __init__(self, db_path: str | os.PathLike = "vault.db"):
        self.db_path = Path(db_path)
        self._fernet = Fernet(_load_key())
        self._init_db()

    def _init_db(self):
        """Create the vault table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault (
                token       TEXT PRIMARY KEY,
                ciphertext  BLOB NOT NULL,
                entity      TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    def _get_conn(self):
        """Get a thread-safe connection (new connection per call)."""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    # ----- write ----------------------------------------------------------- #
    def store(self, token: str, original: str, entity: str) -> None:
        ct = self._fernet.encrypt(original.encode())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO vault(token, ciphertext, entity) VALUES (?,?,?)",
                (token, ct, entity),
            )
            conn.commit()
        finally:
            conn.close()

    def store_many(self, items: Iterable[tuple[str, str, str]]) -> None:
        rows = [
            (tok, self._fernet.encrypt(orig.encode()), ent)
            for tok, orig, ent in items
        ]
        if not rows:
            return
        conn = self._get_conn()
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO vault(token, ciphertext, entity) VALUES (?,?,?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()

    # ----- read ------------------------------------------------------------ #
    def reveal(self, token: str) -> str | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT ciphertext FROM vault WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                return None
            return self._fernet.decrypt(row[0]).decode()
        finally:
            conn.close()

    def __contains__(self, token: str) -> bool:
        return self.reveal(token) is not None

    def __len__(self) -> int:
        conn = self._get_conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM vault").fetchone()[0]
        finally:
            conn.close()

    def close(self) -> None:
        pass  # connections are per-call now


if __name__ == "__main__":
    # Smoke test
    v = TokenVault("vault.db")
    v.store("<PERSON_abc123>", "Rajesh Kumar", "PERSON")
    print("Reveal:", v.reveal("<PERSON_abc123>"))
    print("Vault size:", len(v))
    v.close()
