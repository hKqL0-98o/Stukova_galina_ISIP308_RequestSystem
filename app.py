"""Точка входа приложения «Система учёта заявок» (HelpDesk).

Запуск: python app.py
Пересоздать базу с тестовыми данными: flask --app app init-db
"""
import logging
import secrets
import sqlite3

import click
from flask import Flask, jsonify, make_response, render_template, request
from werkzeug.exceptions import HTTPException

from config import INSECURE_SECRET_KEYS, Config
from src import api, web
from src import repositories as repo
from src.auth import load_current_user
from src.db import close_db, init_db
from src.openapi import SWAGGER_HTML, build_spec
from src.ratelimit import LoginLimiter

HTTP_MESSAGES = {
    400: "Некорректный запрос", 401: "Требуется авторизация", 403: "Доступ запрещён",
    404: "Ресурс не найден", 405: "Метод не поддерживается для этого адреса",
    415: "Неподдерживаемый формат тела запроса",
    429: "Слишком много неудачных попыток входа. Повторите через несколько минут.",
}


def _is_api():
    return request.path.startswith("/api/")


def _check_secret_key(app):
    """Не даёт запустить приложение с ключом сессий, который известен всем (ЛР №8, ревью Dockerfile).

    Образцы ключей лежат в открытом репозитории: с ними cookie сессии администратора подделывается за минуту.
    Поэтому вне режима отладки и тестов такой ключ — ошибка запуска, а не предупреждение в журнале.
    """
    key = app.config.get("SECRET_KEY")
    relaxed = app.config["DEBUG"] or app.config["TESTING"]
    if key in INSECURE_SECRET_KEYS:
        if not relaxed:
            raise RuntimeError("SECRET_KEY равен образцу из репозитория, этот ключ известен всем. Задайте свой "
                               "(например, openssl rand -hex 32) в .env или переменной окружения SECRET_KEY.")
        return
    if not key:
        # Ключ не задан: берём случайный, его не знает никто. Минус: после перезапуска сессии входа сбросятся.
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY не задан: использован случайный ключ, после перезапуска все сессии "
                           "входа сбросятся. На сервере задайте постоянный ключ (openssl rand -hex 32).")


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.json.ensure_ascii = False   # кириллица в JSON читается как есть, а не \u0418...
    app.json.sort_keys = False

    if init_db(app.config["DATABASE"]):
        app.logger.warning("База данных создана заново из db/schema.sql и db/seed.sql: %s", app.config["DATABASE"])
    _check_secret_key(app)

    app.extensions["login_limiter"] = LoginLimiter(app.config["LOGIN_MAX_ATTEMPTS"],
                                                   app.config["LOGIN_WINDOW_SECONDS"])
    app.before_request(load_current_user)
    app.teardown_appcontext(close_db)
    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)

    @app.get("/health")
    def health():
        try:
            repo.ping()
        except sqlite3.Error:
            return jsonify({"status": "error", "database": "unavailable"}), 503
        return jsonify({"status": "ok", "database": "ok", "service": "HelpDesk RequestSystem", "version": "2.0.0"})

    @app.get("/docs")
    def docs():
        return SWAGGER_HTML

    @app.get("/openapi.json")
    def openapi():
        return jsonify(build_spec())

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = HTTP_MESSAGES.get(error.code, error.description)
        if _is_api():
            code = error.name.lower().replace(" ", "_")
            response = make_response(jsonify({"error": {"code": code, "message": message, "details": {}}}), error.code)
        else:
            response = make_response(render_template("error.html", status=error.code, message=message), error.code)
        retry_after = getattr(error, "retry_after", None)
        if retry_after:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("Ошибка базы данных")
        message = "Ошибка базы данных. Попробуйте повторить действие позже."
        if _is_api():
            return jsonify({"error": {"code": "database_error", "message": message, "details": {}}}), 500
        return render_template("error.html", status=500, message=message), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Непредвиденная ошибка")
        message = "Внутренняя ошибка сервера"
        if _is_api():
            return jsonify({"error": {"code": "internal_error", "message": message, "details": {}}}), 500
        return render_template("error.html", status=500, message=message), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Пересоздать базу и заполнить тестовыми данными (все текущие данные будут удалены)."""
        init_db(app.config["DATABASE"], reset=True)
        click.echo(f"База пересоздана: {app.config['DATABASE']}")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    application = create_app()
    application.run(host=application.config["HOST"], port=application.config["PORT"],
                    debug=application.config["DEBUG"])
