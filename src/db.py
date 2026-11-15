"""Подключение к SQLite и инициализация базы."""
import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, g

SCHEMA_VERSION = 2
SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")


def _lower(value):
    return value.lower() if isinstance(value, str) else value


def connect(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Встроенный LOWER в SQLite не понимает кириллицу, поэтому регистрируем свой.
    conn.create_function("PYLOWER", 1, _lower, deterministic=True)
    return conn


def get_db():
    """Одно соединение на HTTP-запрос. Закрывается автоматически в close_db."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.rollback()  # незавершённые изменения отменяются, база не остаётся заблокированной
        conn.close()


@contextmanager
def transaction():
    """Все изменения внутри блока сохраняются вместе или не сохраняются вовсе."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _run_script(conn, name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as f:
        conn.executescript(f.read())


def init_db(path, reset=False):
    """Создаёт базу из db/schema.sql и db/seed.sql, если её нет или у неё старая схема.

    Возвращает True, если база была (пере)создана.
    """
    conn = connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if reset or version < SCHEMA_VERSION:
            _run_script(conn, "schema.sql")
            _run_script(conn, "seed.sql")
            conn.commit()
            return True
        return False
    finally:
        conn.close()
