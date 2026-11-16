"""Настройки приложения. Всё, что меняется между компьютером и сервером, берётся из переменных окружения."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Значения, которые лежат в общедоступном репозитории (в коде и в .env.example), на сервере их использовать нельзя
INSECURE_SECRET_KEYS = ("dev-only-change-me", "замените-на-длинную-случайную-строку")


class Config:
    # Ключ для подписи сессий. На сервере обязательно задать свой через SECRET_KEY.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "requests.db"))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5000"))

    # Защита от подбора пароля: после LOGIN_MAX_ATTEMPTS неудачных попыток подряд вход для этой пары
    # «адрес + логин» закрывается на LOGIN_WINDOW_SECONDS секунд. 0 отключает ограничение.
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
