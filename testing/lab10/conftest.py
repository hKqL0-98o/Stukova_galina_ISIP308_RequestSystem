"""Общая подготовка для автоматических тестов (ЛР №10).

Каждый тест получает СВОЮ временную копию базы, созданную из db/schema.sql и db/seed.sql.
Рабочая база requests.db и реальные пароли тестами не затрагиваются: у всех пользователей
во временной базе выставляется тестовый пароль TEST_PASSWORD.
"""
import base64
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import create_app          # noqa: E402
from src.db import init_db          # noqa: E402

TEST_PASSWORD = "test-pass-123"

# Идентификаторы из db/seed.sql
ADMIN, OPERATOR, PETROV, MOROZOV, IVANOV, SOKOLOVA = 1, 2, 3, 4, 5, 6
BIG_ID = 10 ** 25   # больше, чем помещается в INTEGER SQLite (2**63 - 1)


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    """Эталонная база: схема + тестовые данные + известный тестовый пароль."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    init_db(str(path), reset=True)
    conn = sqlite3.connect(path)
    password_hash = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256:1000")
    conn.execute("UPDATE Users SET password_hash = ?", (password_hash,))
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def app(template_db, tmp_path):
    db_path = tmp_path / "test.db"
    shutil.copy(template_db, db_path)
    application = create_app({
        "TESTING": True,
        "PROPAGATE_EXCEPTIONS": False,   # непредвиденная ошибка должна превращаться в HTTP 500, как на сервере
        "DATABASE": str(db_path),
        "SECRET_KEY": "test-secret",
    })
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth():
    """auth('operator') -> заголовок HTTP Basic для запросов к API."""
    def make(login, password=TEST_PASSWORD):
        token = base64.b64encode(f"{login}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return make


@pytest.fixture
def db(app):
    """Прямое подключение к тестовой базе: проверяем, что данные действительно сохранились."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def ctx(app):
    """Контекст приложения для прямых вызовов сервисного слоя."""
    with app.app_context():
        yield


@pytest.fixture
def user(ctx):
    """user(PETROV) -> словарь пользователя, как его видит сервисный слой."""
    from src import repositories as repo

    def get(user_id):
        return repo.get_user(user_id)
    return get


@pytest.fixture
def web_login(client):
    """web_login('admin') -> клиент, вошедший через форму входа."""
    def do(login, password=TEST_PASSWORD):
        response = client.post("/login", data={"login": login, "password": password})
        assert response.status_code == 302, "вход не удался"
        return client
    return do
