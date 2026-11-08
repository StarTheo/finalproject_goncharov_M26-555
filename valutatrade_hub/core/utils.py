"""Вспомогательные функции бизнес-логики."""

import hashlib

MIN_PASSWORD_LENGTH = 4
PASSWORD_HASH_ITERATIONS = 200_000
PASSWORD_SALT_BYTES = 16


def hash_password(password, salt):
    """Вычисляет хеш пароля с солью через PBKDF2-HMAC-SHA256."""
    if not isinstance(password, str):
        raise ValueError("Пароль должен быть строкой.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Пароль должен содержать минимум {MIN_PASSWORD_LENGTH} символа."
        )

    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
