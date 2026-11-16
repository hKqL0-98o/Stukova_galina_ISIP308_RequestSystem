"""Защита от подбора пароля (ЛР №7, замечание модели №1 к API-контракту; регрессия — ЛР №10).

Правило: после LOGIN_MAX_ATTEMPTS неудачных попыток входа подряд пара «адрес + логин» блокируется
на LOGIN_WINDOW_SECONDS секунд, сервер отвечает 429 и заголовком Retry-After.
"""
import shutil

from conftest import TEST_PASSWORD
from app import create_app
from src.ratelimit import LoginLimiter

MAX = 5   # значение по умолчанию из config.py


def bad_api_login(client, auth, login="admin", times=1):
    return [client.get("/api/me", headers=auth(login, "wrong-password")) for _ in range(times)]


def test_api_blocks_after_max_failed_attempts(client, auth):
    """RL-01. 5 неверных паролей → 401, 6-й запрос → 429 с Retry-After и единым форматом ошибки."""
    responses = bad_api_login(client, auth, times=MAX)
    assert [r.status_code for r in responses] == [401] * MAX
    blocked = client.get("/api/me", headers=auth("admin", "wrong-password"))
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "too_many_requests"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 300


def test_correct_password_is_also_blocked_during_lock(client, auth):
    """RL-02. Во время блокировки даже верный пароль не пускает: иначе перебор можно продолжать."""
    bad_api_login(client, auth, times=MAX)
    assert client.get("/api/me", headers=auth("admin")).status_code == 429


def test_other_login_is_not_affected(client, auth):
    """RL-03. Блокировка относится к паре «адрес + логин»: другой логин входит без помех."""
    bad_api_login(client, auth, "admin", times=MAX + 1)
    assert client.get("/api/me", headers=auth("operator")).status_code == 200


def test_successful_login_resets_counter(client, auth):
    """RL-04. Верный пароль обнуляет счётчик: 4 ошибки, вход, ещё 4 ошибки — блокировки нет."""
    assert [r.status_code for r in bad_api_login(client, auth, times=MAX - 1)] == [401] * (MAX - 1)
    assert client.get("/api/me", headers=auth("admin")).status_code == 200
    assert [r.status_code for r in bad_api_login(client, auth, times=MAX - 1)] == [401] * (MAX - 1)
    assert client.get("/api/me", headers=auth("admin")).status_code == 200


def test_web_form_blocks_and_shows_message(client):
    """RL-05. Форма входа: после 5 ошибок страница входа отвечает 429 с понятным сообщением."""
    for _ in range(MAX):
        assert client.post("/login", data={"login": "admin", "password": "wrong"}).status_code == 401
    response = client.post("/login", data={"login": "admin", "password": TEST_PASSWORD})
    assert response.status_code == 429
    assert "Слишком много неудачных попыток" in response.get_data(as_text=True)
    assert "Retry-After" in response.headers


def test_login_is_case_insensitive_for_limit(client, auth):
    """RL-06. «Admin» и «admin» считаются одним логином, иначе лимит обходится заменой регистра."""
    for login in ("admin", "ADMIN", "Admin", "aDMIN", "admin"):
        assert client.get("/api/me", headers=auth(login, "wrong-password")).status_code == 401
    assert client.get("/api/me", headers=auth("admin", "wrong-password")).status_code == 429


def test_limit_can_be_disabled(template_db, tmp_path, auth):
    """RL-07. LOGIN_MAX_ATTEMPTS=0 отключает ограничение (например, для локальной отладки)."""
    db_path = tmp_path / "off.db"
    shutil.copy(template_db, db_path)
    app = create_app({"TESTING": True, "DATABASE": str(db_path), "SECRET_KEY": "x", "LOGIN_MAX_ATTEMPTS": 0})
    client = app.test_client()
    codes = {client.get("/api/me", headers=auth("admin", "wrong")).status_code for _ in range(20)}
    assert codes == {401}


def test_limiter_unblocks_after_window():
    """RL-08. Блокировка снимается по истечении окна (время подменено, ожидание не нужно)."""
    now = [1000.0]
    limiter = LoginLimiter(max_attempts=3, window_seconds=60, clock=lambda: now[0])
    key = ("127.0.0.1", "admin")
    for _ in range(3):
        limiter.fail(key)
    assert 0 < limiter.retry_after(key) <= 60
    now[0] += 61
    assert limiter.retry_after(key) == 0
