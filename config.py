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

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
