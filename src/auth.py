"""Аутентификация: вход по логину и паролю, сессия для интерфейса и HTTP Basic для API."""
from flask import current_app, g, request, session
from werkzeug.exceptions import TooManyRequests
from werkzeug.security import check_password_hash

from . import repositories as repo


def authenticate(login, password):
    """Пользователь или None. После серии неудачных попыток бросает TooManyRequests (HTTP 429)."""
    if not login or not password:
        return None
    login = login.strip()
    limiter = current_app.extensions["login_limiter"]
    key = (request.remote_addr, login.lower())
    wait = limiter.retry_after(key)
    if wait:
        raise TooManyRequests("Слишком много неудачных попыток входа. Повторите через несколько минут.",
                              retry_after=wait)
    user = repo.get_user_with_password(login)
    if user is None or not user["is_active"] or not check_password_hash(user["password_hash"], password):
        limiter.fail(key)
        return None
    limiter.reset(key)
    user.pop("password_hash")
    return user


def load_current_user():
    """Вызывается перед каждым запросом и кладёт текущего пользователя в g.user."""
    g.user = None
    if request.endpoint == "static":
        return
    user_id = session.get("user_id")
    if user_id is not None:
        user = repo.get_user(user_id)
        if user and user["is_active"]:
            g.user = user
            return
        session.clear()
    auth = request.authorization
    if request.path.startswith("/api/") and auth is not None and auth.type == "basic":
        g.user = authenticate(auth.username, auth.password)


def login_user(user):
    session.clear()
    session["user_id"] = user["id"]


def logout_user():
    session.clear()
