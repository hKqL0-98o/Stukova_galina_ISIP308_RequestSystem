"""Секретный ключ сессий (ЛР №8, ревью Dockerfile, замечание №1 уровня Critical; регрессия — ЛР №10).

Проблема: образец SECRET_KEY лежит в открытом репозитории (config.py, .env.example). Если на сервере
забыли задать свой ключ, приложение раньше молча запускалось с известным всем ключом, и любой желающий
мог подделать cookie сессии и войти администратором.

Правило после исправления:
  * ключ из репозитория вне режима отладки и тестов: приложение НЕ запускается (RuntimeError);
  * ключ не задан: приложение запускается со случайным ключом (его не знает никто) и пишет предупреждение;
  * свой ключ используется как есть.
"""
import pytest

from app import create_app
from config import INSECURE_SECRET_KEYS


def make_app(tmp_path, **settings):
    config = {"DATABASE": str(tmp_path / "sk.db"), "TESTING": False, "DEBUG": False}
    config.update(settings)
    return create_app(config)


def forged_admin_cookie(app, known_key):
    """Cookie сессии администратора, подписанная ключом, известным атакующему."""
    victim = create_app({"DATABASE": app.config["DATABASE"], "SECRET_KEY": known_key, "TESTING": True})
    return victim.session_interface.get_signing_serializer(victim).dumps({"user_id": 1})


@pytest.mark.parametrize("known_key", INSECURE_SECRET_KEYS)
def test_app_refuses_to_start_with_key_from_repository(tmp_path, known_key):
    """SK-01. Ключ из репозитория вне режима отладки и тестов: запуск запрещён."""
    with pytest.raises(RuntimeError):
        make_app(tmp_path, SECRET_KEY=known_key)


def test_error_message_names_the_setting(tmp_path):
    """SK-02. Сообщение называет переменную и подсказывает, как сгенерировать ключ."""
    with pytest.raises(RuntimeError) as err:
        make_app(tmp_path, SECRET_KEY=INSECURE_SECRET_KEYS[0])
    assert "SECRET_KEY" in str(err.value)
    assert "openssl rand -hex 32" in str(err.value)


@pytest.mark.parametrize("mode", ["DEBUG", "TESTING"])
def test_known_key_is_allowed_in_debug_and_tests(tmp_path, mode):
    """SK-03. Для локальной отладки и автотестов образец ключа остаётся допустимым."""
    app = make_app(tmp_path, SECRET_KEY=INSECURE_SECRET_KEYS[0], **{mode: True})
    assert app.config["SECRET_KEY"] == INSECURE_SECRET_KEYS[0]


@pytest.mark.parametrize("empty", [None, ""])
def test_missing_key_gets_random_value(tmp_path, empty):
    """SK-04. Ключ не задан: запуск возможен, ключ случайный, длинный и не совпадает с образцом."""
    app = make_app(tmp_path, SECRET_KEY=empty)
    key = app.config["SECRET_KEY"]
    assert len(key) >= 32
    assert key not in INSECURE_SECRET_KEYS


def test_random_keys_differ_and_forged_cookie_is_rejected(tmp_path):
    """SK-05. Два запуска получают разные ключи; cookie, подписанная ключом из репозитория, не принимается."""
    first = make_app(tmp_path, SECRET_KEY=None)
    second = make_app(tmp_path, SECRET_KEY=None)
    assert first.config["SECRET_KEY"] != second.config["SECRET_KEY"]

    client = first.test_client()
    client.set_cookie("session", forged_admin_cookie(first, INSECURE_SECRET_KEYS[0]))
    assert client.get("/api/me").status_code == 401


def test_own_key_is_kept_as_is(tmp_path):
    """SK-06. Заданный пользователем ключ используется без изменений и без предупреждений."""
    app = make_app(tmp_path, SECRET_KEY="my-very-long-private-key-0123456789abcdef")
    assert app.config["SECRET_KEY"] == "my-very-long-private-key-0123456789abcdef"
