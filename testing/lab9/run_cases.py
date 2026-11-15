"""ЛР №9. Прогон тест-кейсов по HTTP против РЕАЛЬНО запущенного сервера приложения.

Скрипт сам поднимает приложение (python app.py) на временной копии БД с тестовым паролем,
выполняет тест-кейсы, сохраняет запрос и ответ каждого кейса в evidence/ и пишет results.json.

Запуск из корня проекта:   python testing/lab9/run_cases.py [--label before|after]
Рабочая база requests.db и реальные пароли не затрагиваются.
"""
import argparse
import base64
import http.cookiejar
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PORT = 5077
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "test-pass-123"
BIG = 10 ** 25

sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------- HTTP-клиент
class Resp:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    @property
    def json(self):
        try:
            return json.loads(self.body)
        except ValueError:
            return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


LOG = []     # журнал запросов текущего кейса


def call(method, path, data=None, user=None, form=None, opener=None, raw=None, ctype=None):
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif raw is not None:
        body = raw.encode()
        headers["Content-Type"] = ctype or "application/json"
    if user:
        token = base64.b64encode(f"{user}:{PASSWORD}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    op = opener or urllib.request.build_opener(NoRedirect)
    try:
        r = op.open(req, timeout=10)
        resp = Resp(r.status, dict(r.headers), r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        resp = Resp(e.code, dict(e.headers), e.read().decode("utf-8", "replace"))
    shown = (data if data is not None else form if form is not None else raw)
    LOG.append(f"> {method} {path}" + (f"   [{user}]" if user else "") + (f"\n> тело: {shown!r}" if shown is not None else "")
               + f"\n< HTTP {resp.status}\n< {resp.body[:600].strip()}\n")
    return resp


def session(login):
    """Клиент с cookie: вход через веб-форму, как в браузере."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    r = call("POST", "/login", form={"login": login, "password": PASSWORD}, opener=opener)
    assert r.status == 302, f"вход {login} не удался: {r.status}"
    return opener


def ids(resp):
    return [x["id"] for x in resp.json]


# ---------------------------------------------------------------- тест-кейсы
CASES = []


def case(tc, group, title, expected):
    def deco(fn):
        CASES.append(dict(id=tc, group=group, title=title, expected=expected, fn=fn))
        return fn
    return deco


OK = {"title": "Не работает сканер", "category_id": 3, "priority": "Высокий", "applicant_id": 5}


@case("TC-01", "Позитивный, API", "Просмотр списка заявок администратором", "HTTP 200, JSON-массив из 10 заявок")
def _():
    r = call("GET", "/api/requests", user="admin")
    return r.status == 200 and len(r.json) == 10, f"HTTP {r.status}, заявок: {len(r.json)}"


@case("TC-02", "Позитивный, API", "Создание заявки оператором с корректными данными", "HTTP 201, заголовок Location, статус «Новая»")
def _():
    r = call("POST", "/api/requests", OK, "operator")
    return (r.status == 201 and "Location" in r.headers and r.json["status"] == "Новая",
            f"HTTP {r.status}, Location={r.headers.get('Location')}, статус={r.json and r.json.get('status')}")


@case("TC-03", "Позитивный, API", "Просмотр одной заявки (№3)", "HTTP 200, поля comments и history присутствуют")
def _():
    r = call("GET", "/api/requests/3", user="admin")
    return (r.status == 200 and "comments" in r.json and "history" in r.json,
            f"HTTP {r.status}, статус={r.json.get('status')}, комментариев={len(r.json['comments'])}, записей истории={len(r.json['history'])}")


@case("TC-04", "Позитивный, API", "Поиск по слову «pycharm» (регистр не важен)", "Найдена только заявка №2")
def _():
    r = call("GET", "/api/requests?search=pycharm", user="admin")
    return r.status == 200 and ids(r) == [2], f"HTTP {r.status}, найдено: {ids(r)}"


@case("TC-05", "Позитивный, API", "Изменение описания заявки №1 и повторное чтение", "PATCH → 200; GET возвращает новое описание")
def _():
    r = call("PATCH", "/api/requests/1", {"description": "Уточнённое описание"}, "admin")
    g = call("GET", "/api/requests/1", user="admin")
    return (r.status == 200 and g.json["description"] == "Уточнённое описание",
            f"PATCH → {r.status}; GET → описание «{g.json['description']}»")


@case("TC-06", "Позитивный, интеграционный", "Смена статуса исполнителем (заявка №2 → «Выполнена») и запись в истории", "HTTP 200; статус сохранён; в истории появилась запись")
def _():
    r = call("PATCH", "/api/requests/2", {"status_id": 3}, "petrov")
    g = call("GET", "/api/requests/2", user="admin")
    last = g.json["history"][-1]
    return (r.status == 200 and g.json["status"] == "Выполнена" and last["new_value"] == "Выполнена",
            f"PATCH → {r.status}; статус при повторном чтении: {g.json['status']}; история: {last['old_value']} → {last['new_value']}")


@case("TC-07", "Негативный", "Создание заявки с пустой темой", "HTTP 422, код validation_error, заявка не создана")
def _():
    before = len(call("GET", "/api/requests", user="admin").json)
    r = call("POST", "/api/requests", {**OK, "title": ""}, "operator")
    after = len(call("GET", "/api/requests", user="admin").json)
    return (r.status == 422 and r.json["error"]["code"] == "validation_error" and before == after,
            f"HTTP {r.status}, заявок до запроса: {before}, после: {after}")


@case("TC-08", "Негативный", "Недопустимый приоритет «Срочно»", "HTTP 422")
def _():
    r = call("POST", "/api/requests", {**OK, "priority": "Срочно"}, "operator")
    return r.status == 422, f"HTTP {r.status}: {r.json['error']['message']}"


@case("TC-09", "Негативный", "Несуществующий статус (status_id=77)", "HTTP 422")
def _():
    r = call("PATCH", "/api/requests/1", {"status_id": 77}, "admin")
    return r.status == 422, f"HTTP {r.status}: {r.json['error']['message']}"


@case("TC-10", "Негативный, API", "Запрос несуществующей заявки №9999", "HTTP 404 в едином формате ошибок")
def _():
    r = call("GET", "/api/requests/9999", user="admin")
    return r.status == 404 and r.json["error"]["code"] == "not_found", f"HTTP {r.status}: {r.json['error']['message']}"


@case("TC-11", "Негативный", "Управляющий символ NUL в теме заявки", "HTTP 422 (ввод отклонён, ошибка сервера недопустима)")
def _():
    r = call("POST", "/api/requests", {**OK, "title": "до\x00после"}, "operator")
    return r.status == 422, f"HTTP {r.status}: {(r.json or {}).get('error', {}).get('message')}"


@case("TC-12", "Граничный", "Длина темы: 2 символа — нельзя, 3 символа — можно", "2 символа → 422; 3 символа → 201")
def _():
    a = call("POST", "/api/requests", {**OK, "title": "аб"}, "operator")
    b = call("POST", "/api/requests", {**OK, "title": "абв"}, "operator")
    return a.status == 422 and b.status == 201, f"2 символа → {a.status}; 3 символа → {b.status}"


@case("TC-13", "Граничный", "Длина темы: 100 символов — можно, 101 — нельзя", "100 → 201; 101 → 422")
def _():
    a = call("POST", "/api/requests", {**OK, "title": "я" * 100}, "operator")
    b = call("POST", "/api/requests", {**OK, "title": "я" * 101}, "operator")
    return a.status == 201 and b.status == 422, f"100 символов → {a.status}; 101 символ → {b.status}"


@case("TC-14", "Граничный", "Длина описания: 2000 — можно, 2001 — нельзя", "2000 → 201; 2001 → 422")
def _():
    a = call("POST", "/api/requests", {**OK, "description": "б" * 2000}, "operator")
    b = call("POST", "/api/requests", {**OK, "description": "б" * 2001}, "operator")
    return a.status == 201 and b.status == 422, f"2000 символов → {a.status}; 2001 символ → {b.status}"


@case("TC-15", "Граничный", "Поиск, который ничего не находит", "HTTP 200 и пустой список")
def _():
    r = call("GET", "/api/requests?search=" + urllib.parse.quote("такого-текста-нет"), user="admin")
    return r.status == 200 and r.json == [], f"HTTP {r.status}, список: {r.json}"


@case("TC-16", "Граничный", "Специальные символы и SQL-инъекция в теме", "Текст сохранён как есть, таблицы целы")
def _():
    nasty = "x'); DROP TABLE Requests;-- <b>\"q\"</b>"
    r = call("POST", "/api/requests", {**OK, "title": nasty}, "operator")
    g = call("GET", "/api/requests", user="admin")
    return (r.status == 201 and r.json["title"] == nasty and g.status == 200,
            f"HTTP {r.status}; тема сохранена без изменений: {r.json['title'] == nasty}; список читается: HTTP {g.status}")


@case("TC-17", "Граничный, API", "Огромный номер заявки (10^25) в адресе", "HTTP 404, а не ошибка сервера")
def _():
    r = call("GET", f"/api/requests/{BIG}", user="admin")
    return r.status == 404, f"HTTP {r.status}"


@case("TC-18", "Граничный", "Поиск по очень длинному числу (20 цифр)", "HTTP 200 и пустой список")
def _():
    r = call("GET", "/api/requests?search=" + "9" * 20, user="admin")
    return r.status == 200 and r.json == [], f"HTTP {r.status}"


@case("TC-19", "Роли и доступ", "Запрос к API без авторизации", "HTTP 401")
def _():
    r = call("GET", "/api/requests")
    return r.status == 401 and r.json["error"]["code"] == "unauthorized", f"HTTP {r.status}"


@case("TC-20", "Роли и доступ", "Заявитель Соколова открывает чужую заявку №1", "HTTP 403")
def _():
    r = call("GET", "/api/requests/1", user="sokolova")
    return r.status == 403, f"HTTP {r.status}: {r.json['error']['message']}"


@case("TC-21", "Роли и доступ", "Оператор пытается закрыть заявку №3 (запрещено ТЗ, ФТ-6)", "HTTP 403, статус остался «Выполнена»")
def _():
    r = call("PATCH", "/api/requests/3", {"status_id": 4}, "operator")
    g = call("GET", "/api/requests/3", user="admin")
    return r.status == 403 and g.json["status"] == "Выполнена", f"HTTP {r.status}; статус после попытки: {g.json['status']}"


@case("TC-22", "Роли и доступ", "Заявитель запрашивает список пользователей", "HTTP 403")
def _():
    r = call("GET", "/api/users", user="ivanov")
    return r.status == 403, f"HTTP {r.status}"


@case("TC-23", "Позитивный + роли, API", "Удаление заявки №5: оператором нельзя, администратором можно", "Оператор → 403; админ → 204; затем GET → 404")
def _():
    a = call("DELETE", "/api/requests/5", user="operator")
    b = call("DELETE", "/api/requests/5", user="admin")
    c = call("GET", "/api/requests/5", user="admin")
    return a.status == 403 and b.status == 204 and c.status == 404, f"оператор → {a.status}; админ → {b.status}; повторный GET → {c.status}"


@case("TC-24", "Интеграционный (веб + БД)", "Создание заявки через веб-форму и проверка сохранения в БД", "Форма → 302 на карточку; заявка читается через API")
def _():
    op = session("ivanov")
    r = call("POST", "/requests/new", form={"title": "Не работает Wi-Fi в кабинете", "description": "Пропадает сигнал",
                                           "category_id": "1", "priority": "Высокий"}, opener=op)
    g = call("GET", "/api/requests?search=" + urllib.parse.quote("Wi-Fi в кабинете"), user="admin")
    ok = r.status == 302 and len(g.json) == 1 and g.json[0]["applicant_id"] == 5 and g.json[0]["status"] == "Новая"
    return ok, f"форма → HTTP {r.status}, Location={r.headers.get('Location')}; через API найдено заявок: {len(g.json)}"


@case("TC-25", "Интеграционный (веб + БД)", "Смена статуса через веб-форму (заявка №7 → «Выполнена») и проверка через API", "Форма → 302; API показывает новый статус")
def _():
    op = session("operator")
    r = call("POST", "/requests/7/status", form={"status_id": "3"}, opener=op)
    g = call("GET", "/api/requests/7", user="admin")
    return r.status == 302 and g.json["status"] == "Выполнена", f"форма → HTTP {r.status}; статус через API: {g.json['status']}"


@case("TC-26", "Интеграционный", "Заявка, созданная через API, видна на веб-странице списка", "Тема присутствует в HTML главной страницы")
def _():
    call("POST", "/api/requests", {**OK, "title": "Заявка из API для веба"}, "operator")
    page = call("GET", "/", opener=session("admin"))
    return page.status == 200 and "Заявка из API для веба" in page.body, f"HTTP {page.status}; тема на странице: {'Заявка из API для веба' in page.body}"


@case("TC-27", "API, негативный", "POST с телом не в формате JSON", "HTTP 415")
def _():
    r = call("POST", "/api/requests", raw="title=abc", ctype="application/x-www-form-urlencoded", user="operator")
    return r.status == 415, f"HTTP {r.status}"


@case("TC-28", "API, негативный", "POST с битым JSON", "HTTP 400")
def _():
    r = call("POST", "/api/requests", raw="{не json", user="operator")
    return r.status == 400, f"HTTP {r.status}"


@case("TC-29", "API", "Проверка /health и документации Swagger", "/health → 200 status=ok; /docs → 200; /openapi.json содержит пути API")
def _():
    h = call("GET", "/health")
    d = call("GET", "/docs")
    o = call("GET", "/openapi.json")
    paths = list((o.json or {}).get("paths", {}))
    return (h.status == 200 and h.json["status"] == "ok" and d.status == 200 and "/api/requests" in paths,
            f"/health → {h.status} ({h.json['status']}); /docs → {d.status}; путей в OpenAPI: {len(paths)}")


@case("TC-30", "UI, безопасность", "HTML в теме заявки не исполняется (экранирование)", "На странице тема выведена как текст: &lt;script&gt;")
def _():
    call("POST", "/api/requests", {**OK, "title": "<script>alert(1)</script>"}, "operator")
    page = call("GET", "/", opener=session("admin"))
    return ("&lt;script&gt;" in page.body and "<script>alert(1)</script>" not in page.body,
            f"экранировано: {'&lt;script&gt;' in page.body}; сырой тег на странице: {'<script>alert(1)</script>' in page.body}")


@case("TC-31", "Роли и доступ, UI", "Неверный пароль в форме входа; страницы без входа", "401 с сообщением; без входа — перенаправление на /login")
def _():
    a = call("POST", "/login", form={"login": "admin", "password": "wrong"})
    b = call("GET", "/")
    return (a.status == 401 and "Неверный логин или пароль" in a.body and b.status == 302 and "/login" in b.headers.get("Location", ""),
            f"неверный пароль → HTTP {a.status}; главная без входа → HTTP {b.status}, Location={b.headers.get('Location')}")


# ---------------------------------------------------------------- запуск сервера и выполнение
def prepare_db(path):
    from src.db import init_db
    from werkzeug.security import generate_password_hash
    init_db(path, reset=True)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE Users SET password_hash = ?", (generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000"),))
    conn.commit()
    conn.close()


def start_server(db_path):
    env = dict(os.environ, DATABASE_PATH=db_path, PORT=str(PORT), HOST="127.0.0.1", FLASK_DEBUG="0",
               SECRET_KEY="manual-run-secret", PYTHONUTF8="1")
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("сервер не запустился")


def commit_hash():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after")
    args = parser.parse_args()

    evidence = HERE / "evidence" / args.label
    evidence.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "manual.db")
    prepare_db(db_path)
    server = start_server(db_path)
    results = []
    try:
        for c in CASES:
            LOG.clear()
            try:
                passed, actual = c["fn"]()
                status = "PASS" if passed else "FAIL"
            except Exception as exc:                       # сбой самого сценария — фиксируем честно
                status, actual = "FAIL", f"сценарий завершился ошибкой: {exc!r}"
            (evidence / f"{c['id']}.txt").write_text(
                f"{c['id']} — {c['title']}\nОжидается: {c['expected']}\nФактически: {actual}\nСтатус: {status}\n\n" + "\n".join(LOG),
                encoding="utf-8")
            results.append({k: c[k] for k in ("id", "group", "title", "expected")} | {"actual": actual, "status": status})
            print(f"{c['id']}  {status:5} {c['title']}  ->  {actual}")
    finally:
        server.kill()
    (HERE / f"results_{args.label}.json").write_text(
        json.dumps({"label": args.label, "commit": commit_hash(), "date": time.strftime("%Y-%m-%d %H:%M"),
                    "python": sys.version.split()[0], "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = len(results)
    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\nИтого: {total} кейсов, PASS {passed}, FAIL {total - passed}")


if __name__ == "__main__":
    main()

