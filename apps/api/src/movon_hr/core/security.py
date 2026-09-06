"""Password hashing and credential helpers for Teamku.

Uses Argon2id (via ``argon2-cffi``) for password storage. Kept dependency-free
of the request layer so it can be reused by the API, seeds, and future admin
tooling.
"""

from __future__ import annotations

import re
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

# Argon2id with library defaults (sensible time/memory cost for a web app).
_hasher = PasswordHasher()

# Password policy shared by login, employee creation, and password changes.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    """Return an Argon2id hash for ``password``."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time verification of ``password`` against a stored hash.

    Returns ``False`` for empty/invalid hashes instead of raising, so callers
    can treat every failure path identically (avoiding user enumeration).
    """
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when a stored hash should be upgraded to the current parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


def password_policy_error(password: str) -> str | None:
    """Return a human-readable reason when ``password`` is too weak, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Kata sandi minimal {MIN_PASSWORD_LENGTH} karakter."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Kata sandi maksimal {MAX_PASSWORD_LENGTH} karakter."
    if not re.search(r"[A-Za-z]", password):
        return "Kata sandi harus mengandung minimal satu huruf."
    if not re.search(r"\d", password):
        return "Kata sandi harus mengandung minimal satu angka."
    return None


def generate_temporary_password(length: int = 12) -> str:
    """Generate a random password that satisfies the password policy."""
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if password_policy_error(candidate) is None:
            return candidate


__all__ = [
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "generate_temporary_password",
    "hash_password",
    "needs_rehash",
    "password_policy_error",
    "verify_password",
]
