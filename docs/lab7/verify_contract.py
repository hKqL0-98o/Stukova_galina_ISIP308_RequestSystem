"""Сверка критики API-контракта (ЛР7) с реальным API. Временная БД, рабочая база не затрагивается.\nЗапуск из корня репозитория: python docs/lab7/verify_contract.py\nПосле добавления защиты от подбора пароля блок «#1» показывает 429 после 5 ошибок.\n"""
import base64, json, shutil, sqlite3, sys, tempfile
from pathlib import Path
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from app import create_app
from src.db import init_db

PW = "test-pass-123"
tmp = Path(tempfile.mkdtemp())
dbp = tmp / "t.db"
init_db(str(dbp), reset=True)
c = sqlite3.connect(dbp)
c.execute("UPDATE Users SET password_hash=?", (generate_password_hash(PW, method="pbkdf2:sha256:1000"),))
c.commit(); c.close()
app = create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False, "DATABASE": str(dbp), "SECRET_KEY": "x"})
cl = app.test_client()

def H(login, pw=PW):
    return {"Authorization": "Basic " + base64.b64encode(f"{login}:{pw}".encode()).decode()}

def show(label, r):
    body = r.get_data(as_text=True)
    print(f"{label:<62} -> {r.status_code}  {body[:90].replace(chr(10),' ')}")

print("== #2 утечка существования заявки")
show("sokolova GET чужая заявка #1", cl.get("/api/requests/1", headers=H("sokolova")))
show("sokolova GET несуществующая #9999", cl.get("/api/requests/9999", headers=H("sokolova")))
show("sokolova DELETE чужая #1", cl.delete("/api/requests/1", headers=H("sokolova")))
show("sokolova DELETE несуществующая #9999", cl.delete("/api/requests/9999", headers=H("sokolova")))

print("== #3 подмена заявителя")
show("sokolova POST applicant_id=5 (чужой)", cl.post("/api/requests", headers=H("sokolova"),
     json={"title": "Подмена", "category_id": 1, "applicant_id": 5}))
show("sokolova POST без applicant_id", cl.post("/api/requests", headers=H("sokolova"),
     json={"title": "Нормальная", "category_id": 1}))

print("== #8/#9 границы и спецсимволы")
show("operator GET /api/requests/10**25", cl.get(f"/api/requests/{10**25}", headers=H("operator")))
show("operator POST category_id=10**25", cl.post("/api/requests", headers=H("operator"),
     json={"title": "Тема", "category_id": 10**25, "applicant_id": 5}))
show("operator POST title с NUL", cl.post("/api/requests", headers=H("operator"),
     json={"title": "Тема\u0000x", "category_id": 1, "applicant_id": 5}))

print("== #5/#7 переходы статусов и параллельные правки")
rid = cl.post("/api/requests", headers=H("operator"), json={"title": "Для статусов", "category_id": 1, "applicant_id": 5}).get_json()["id"]
show("operator назначает исполнителя 3", cl.patch(f"/api/requests/{rid}", headers=H("operator"), json={"executor_id": 3}))
show("petrov: Новая -> Выполнена (пропуск «В работе»)", cl.patch(f"/api/requests/{rid}", headers=H("petrov"), json={"status_id": 3}))
show("operator: Выполнена -> Новая (откат назад)", cl.patch(f"/api/requests/{rid}", headers=H("operator"), json={"status_id": 1}))
print("   (после отката статус 'Новая' при назначенном исполнителе; конфликта версий нет, сравнение статуса перед записью не делается)")

print("== #1 перебор пароля")
codes = [cl.get("/api/me", headers=H("admin", f"wrong{i}")).status_code for i in range(30)]
print("30 неверных паролей подряд -> коды:", sorted(set(codes)))

print("== #11 формат списка")
r = cl.get("/api/requests?limit=1&page=2", headers=H("operator")).get_json()
print("тип ответа списка:", type(r).__name__, "; элементов при limit=1:", len(r))

print("== #10 крайние случаи PATCH")
show("PATCH пустое тело {}", cl.patch(f"/api/requests/{rid}", headers=H("operator"), json={}))
show("PATCH title=null", cl.patch(f"/api/requests/{rid}", headers=H("operator"), json={"title": None}))
