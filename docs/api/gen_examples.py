"""Прогон API реальными запросами; результат пишется в docs/api/examples.md и docs/api/requests.sh.

Запускает приложение на временной базе (тестовый пароль), реальные пароли не затрагиваются.
"""
import base64
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
PORT = 5078
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "test-pass-123"

sys.path.insert(0, str(ROOT))
from src.db import init_db  # noqa: E402

tmp = tempfile.mkdtemp()
db_path = os.path.join(tmp, "api.db")
init_db(db_path, reset=True)
conn = sqlite3.connect(db_path)
conn.execute("UPDATE Users SET password_hash = ?", (generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000"),))
conn.commit()
conn.close()

env = dict(os.environ, DATABASE_PATH=db_path, PORT=str(PORT), SECRET_KEY="examples-only", PYTHONIOENCODING="utf-8")
proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        urllib.request.urlopen(BASE + "/api/statuses", timeout=1)
    except urllib.error.HTTPError:
        break
    except Exception:
        time.sleep(0.2)

results = []


def req(title, method, path, user=None, data=None, ctype="application/json", raw=None, expect=None, trim=2):
    headers = {}
    body = None
    if user:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{PASSWORD}".encode()).decode()
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
    if raw is not None:
        body = raw.encode()
    if body is not None:
        headers["Content-Type"] = ctype
    r = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(r, timeout=5)
        status, text = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8")
    parsed = None
    shown = text
    note = ""
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list) and len(parsed) > trim:
                note = f"показаны первые {trim} из {len(parsed)} элементов"
                parsed = parsed[:trim]
            shown = json.dumps(parsed, ensure_ascii=False, indent=2)
        except ValueError:
            pass
    ok = (expect is None) or (status == expect)
    results.append(dict(title=title, method=method, path=path, user=user, data=data, ctype=ctype, raw=raw,
                        status=status, body=shown, note=note, expect=expect, ok=ok))
    if not ok:
        print("НЕОЖИДАННЫЙ КОД:", title, status, "ждали", expect)
    return json.loads(text) if text and text.lstrip().startswith(("{", "[")) else None


try:
    req("Текущий пользователь", "GET", "/api/me", "admin", expect=200)
    req("Справочник статусов", "GET", "/api/statuses", "operator", expect=200, trim=4)
    req("Справочник категорий", "GET", "/api/categories", "operator", expect=200, trim=4)
    req("Список пользователей (оператор)", "GET", "/api/users", "operator", expect=200)
    req("Список заявок", "GET", "/api/requests", "operator", expect=200)
    req("Поиск и фильтр по статусу", "GET", "/api/requests?search=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80&status_id=1",
        "operator", expect=200)
    req("Одна заявка с комментариями и историей", "GET", "/api/requests/1", "operator", expect=200)
    created = req("Создание заявки", "POST", "/api/requests", "operator", expect=201, data={
        "title": "Не работает сканер в приёмной", "description": "Сканер не определяется компьютером после обновления.",
        "category_id": 3, "priority": "Высокий", "applicant_id": 5})
    new_id = created["id"]
    req("Назначение исполнителя", "PATCH", f"/api/requests/{new_id}", "operator", data={"executor_id": 3}, expect=200)
    req("Смена статуса исполнителем", "PATCH", f"/api/requests/{new_id}", "petrov", data={"status_id": 2}, expect=200)
    req("Добавление комментария", "POST", f"/api/requests/{new_id}/comments", "petrov",
        data={"content": "Драйвер переустановлен, проверяю."}, expect=201)
    req("Ошибка: слишком короткая тема (422)", "POST", "/api/requests", "operator", expect=422,
        data={"title": "Hi", "category_id": 3, "applicant_id": 5})
    req("Ошибка: недопустимый приоритет (422)", "POST", "/api/requests", "operator", expect=422,
        data={"title": "Проверка приоритета", "category_id": 3, "priority": "Срочный", "applicant_id": 5})
    req("Ошибка: тело не JSON (415)", "POST", "/api/requests", "operator", ctype="text/plain", raw="title=abc", expect=415)
    req("Ошибка: заявка не найдена (404)", "GET", "/api/requests/9999", "operator", expect=404)
    req("Ошибка: нет авторизации (401)", "GET", "/api/requests", None, expect=401)
    req("Ошибка: нет прав (403)", "GET", "/api/users", "ivanov", expect=403)
    req("Ошибка: оператор не может удалять (403)", "DELETE", f"/api/requests/{new_id}", "operator", expect=403)
    req("Удаление заявки администратором", "DELETE", f"/api/requests/{new_id}", "admin", expect=204)
    req("Проверка: удалённая заявка (404)", "GET", f"/api/requests/{new_id}", "admin", expect=404)
finally:
    proc.terminate()
    proc.wait(timeout=10)

# ---------- examples.md
today = date.today().strftime("%d.%m.%Y")
md = [f"# Примеры запросов к REST API HelpDesk\n",
      f"Получены реальным прогоном `{today}` на временной базе из `db/seed.sql` (скрипт `docs/api/gen_examples.py`). "
      "Тестовый пароль учётных записей во временной базе подставляется переменной `PASS`; рабочая база и настоящие пароли не использовались.\n",
      f"Всего запросов: **{len(results)}**, успешных: {sum(1 for r in results if 200 <= r['status'] < 300)}, "
      f"с ожидаемой ошибкой: {sum(1 for r in results if r['status'] >= 400)}.\n"]
for i, r in enumerate(results, 1):
    cmd_user = f"-u {r['user']}:$PASS " if r["user"] else ""
    md.append(f"## {i}. {r['title']}\n")
    line = f"{r['method']} {r['path']}" + (f"  (пользователь `{r['user']}`)" if r["user"] else "  (без авторизации)")
    md.append(line + "\n")
    if r["data"] is not None:
        md.append("Тело запроса:\n\n```json\n" + json.dumps(r["data"], ensure_ascii=False, indent=2) + "\n```\n")
    elif r["raw"] is not None:
        md.append(f"Тело запроса (`Content-Type: {r['ctype']}`): `{r['raw']}`\n")
    md.append(f"Ответ: **HTTP {r['status']}**" + (f" ({r['note']})" if r["note"] else "") + "\n")
    if r["body"]:
        md.append("```json\n" + r["body"] + "\n```\n")
(OUT / "examples.md").write_text("\n".join(md), encoding="utf-8", newline="\n")

# ---------- requests.sh
sh = ["#!/usr/bin/env bash",
      "# Коллекция curl-запросов к API HelpDesk (ЛР №7). Запускать в bash / Git Bash.",
      "# Перед запуском: export PASS='пароль_тестовой_учётки'; приложение должно работать на BASE (по умолчанию 127.0.0.1:5000).",
      'BASE="${BASE:-http://127.0.0.1:5000}"', ""]
for i, r in enumerate(results, 1):
    cmd = "curl -s -i -X " + r["method"] + " "
    if r["user"]:
        cmd += f"-u {r['user']}:\"$PASS\" "
    if r["data"] is not None:
        cmd += f"-H 'Content-Type: application/json' -d '{json.dumps(r['data'], ensure_ascii=False)}' "
    elif r["raw"] is not None:
        cmd += f"-H 'Content-Type: {r['ctype']}' -d '{r['raw']}' "
    sh.append(f"# {i}. {r['title']} (ожидается HTTP {r['status']})")
    sh.append(cmd + f"\"$BASE{r['path']}\"")
    sh.append("")
sh.append(f"# Примечание: в запросах, где в пути стоит /api/requests/{new_id}, используется заявка, созданная запросом 8.")
sh.append(f"# На чистой базе из db/seed.sql она получает id={new_id}; если у вас другой id, подставьте его.")
(OUT / "requests.sh").write_text("\n".join(sh) + "\n", encoding="utf-8", newline="\n")
print("запросов:", len(results), "| все ожидаемые коды:", all(r["ok"] for r in results))
print("id созданной заявки в прогоне:", new_id)
