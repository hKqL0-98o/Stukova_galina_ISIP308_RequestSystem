"""ЛР №9. Прогон набора ручных кейсов «Смена статуса заявки» (SC-01…SC-31) по HTTP против запущенного приложения.

Каждый кейс выполняется на СВЕЖЕЙ копии тестовой базы (как требует предусловие набора). Ожидаемые результаты взяты
из таблицы docs/lab9/status_change_qa_cases.md; здесь они не подгоняются под поведение приложения.
Кейсы SC-07 (веб-форма), SC-10 (перезапуск) и SC-30 (одновременная правка) выполняются вручную и здесь не запускаются.

Запуск из корня проекта:  python testing/lab9/run_status_cases.py
Рабочая база requests.db и реальные пароли не затрагиваются.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_cases as rc          # noqa: E402  (повторное использование HTTP-клиента и запуска сервера)
from run_cases import call      # noqa: E402

NEW, WORK, DONE, CLOSED = 1, 2, 3, 4          # id статусов из db/seed.sql
CASES = []


def case(tc, title, expected, priority):
    def deco(fn):
        CASES.append(dict(id=tc, title=title, expected=expected, priority=priority, fn=fn))
        return fn
    return deco


def get(rid):
    r = call("GET", f"/api/requests/{rid}", user="admin")
    return r.json


def status_changes(rid):
    return [h for h in get(rid)["history"] if h["action"] == "Статус"]


def patch(user, rid, body):
    return call("PATCH", f"/api/requests/{rid}", data=body, user=user)


def msg(resp):
    return ((resp.json or {}).get("error") or {}).get("message", "")


def code(resp):
    return ((resp.json or {}).get("error") or {}).get("code", "")


def result(ok, text):
    return ok, text


# ------------------------------------------------------------ позитивные
@case("SC-01", "Исполнитель берёт заявку в работу", "200, «В работе», запись в истории от petrov", "Critical")
def _():
    call("PATCH", "/api/requests/1", data={"executor_id": 3}, user="operator")
    before = len(status_changes(1))
    r = patch("petrov", 1, {"status_id": WORK})
    j, h = get(1), status_changes(1)
    ok = (r.status == 200 and j["status"] == "В работе" and len(h) == before + 1
          and h[-1]["old_value"] == "Новая" and h[-1]["new_value"] == "В работе" and h[-1]["user"] == "Петр Техников")
    return result(ok, f"HTTP {r.status}, статус «{j['status']}», последняя запись истории: {h[-1]['old_value']}→{h[-1]['new_value']}, автор {h[-1]['user']}")


@case("SC-02", "Исполнитель переводит в «Выполнена»", "200, запись «В работе → Выполнена»", "Critical")
def _():
    r = patch("petrov", 2, {"status_id": DONE})
    j, h = get(2), status_changes(2)
    ok = r.status == 200 and j["status"] == "Выполнена" and (h[-1]["old_value"], h[-1]["new_value"]) == ("В работе", "Выполнена")
    return result(ok, f"HTTP {r.status}, статус «{j['status']}», запись {h[-1]['old_value']}→{h[-1]['new_value']}")


@case("SC-03", "Заявитель закрывает выполненную заявку", "200, «Закрыта», автор sokolova", "Critical")
def _():
    r = patch("sokolova", 3, {"status_id": CLOSED})
    j, h = get(3), status_changes(3)
    ok = r.status == 200 and j["status"] == "Закрыта" and h[-1]["user_role"] == "Заявитель"
    return result(ok, f"HTTP {r.status}, статус «{j['status']}», автор записи: {h[-1]['user']} ({h[-1]['user_role']})")


@case("SC-04", "Полный жизненный цикл", "все шаги 200, +4 записи (исполнитель и 3 статуса), итог «Закрыта»", "High")
def _():
    n0 = len(get(5)["history"])
    steps = [patch("operator", 5, {"executor_id": 3}), patch("petrov", 5, {"status_id": WORK}),
             patch("petrov", 5, {"status_id": DONE}), patch("sokolova", 5, {"status_id": CLOSED})]
    j = get(5)
    ok = [s.status for s in steps] == [200] * 4 and j["status"] == "Закрыта" and len(j["history"]) == n0 + 4
    return result(ok, f"коды {[s.status for s in steps]}, итог «{j['status']}», новых записей истории {len(j['history']) - n0}")


@case("SC-05", "Администратор закрывает заявку", "200, «Закрыта», автор admin", "High")
def _():
    r = patch("admin", 9, {"status_id": CLOSED})
    j, h = get(9), status_changes(9)
    return result(r.status == 200 and j["status"] == "Закрыта" and h[-1]["user"] == "Анна Смирнова",
                  f"HTTP {r.status}, статус «{j['status']}», автор {h[-1]['user']}")


@case("SC-06", "Назначение исполнителя и статус одним запросом", "200, исполнитель Морозов, «В работе», 2 записи истории", "High")
def _():
    n0 = len(get(6)["history"])
    r = patch("operator", 6, {"executor_id": 4, "status_id": WORK})
    j = get(6)
    ok = r.status == 200 and j["executor"] == "Алексей Морозов" and j["status"] == "В работе" and len(j["history"]) == n0 + 2
    return result(ok, f"HTTP {r.status}, исполнитель {j['executor']}, статус «{j['status']}», новых записей {len(j['history']) - n0}")


@case("SC-08", "Заявитель видит статус и историю", "200, статус и история со всеми полями", "Medium")
def _():
    patch("petrov", 2, {"status_id": DONE})
    r = call("GET", "/api/requests/2", user="ivanov")
    h = [x for x in r.json["history"] if x["action"] == "Статус"][-1]
    ok = r.status == 200 and r.json["status"] == "Выполнена" and all(h.get(k) for k in ("user", "created_at", "old_value", "new_value"))
    return result(ok, f"HTTP {r.status}, статус «{r.json['status']}», запись: {h['old_value']}→{h['new_value']}, {h['user']}, {h['created_at']}")


@case("SC-09", "Фильтр по статусу после смены", "200, в списке №2, только «Выполнена»", "Medium")
def _():
    patch("petrov", 2, {"status_id": DONE})
    r = call("GET", f"/api/requests?status_id={DONE}", user="admin")
    ok = r.status == 200 and 2 in rc.ids(r) and all(x["status_id"] == DONE for x in r.json)
    return result(ok, f"HTTP {r.status}, заявки: {rc.ids(r)}")


# ------------------------------------------------------------ права
def denied(tc, title, user, rid, body, expect_msg, priority, expect_status):
    @case(tc, title, f"403 forbidden, «{expect_msg}», статус в БД не изменился" if expect_status == 403 else "401", priority)
    def _():
        before = get(rid)
        r = patch(user, rid, body) if user else call("PATCH", f"/api/requests/{rid}", data=body)
        after = get(rid)
        ok = (r.status == expect_status and expect_msg in msg(r) and after["status"] == before["status"]
              and len(after["history"]) == len(before["history"]))
        return result(ok, f"HTTP {r.status}, {code(r)}: «{msg(r)}», статус в БД «{after['status']}», записей истории {len(after['history'])}")


@case("SC-11", "Смена статуса без авторизации", "401 unauthorized, статус и история без изменений", "Critical")
def _():
    before = get(2)
    r = call("PATCH", "/api/requests/2", data={"status_id": DONE})
    after = get(2)
    ok = r.status == 401 and code(r) == "unauthorized" and after["status"] == before["status"] and len(after["history"]) == len(before["history"])
    return result(ok, f"HTTP {r.status}, {code(r)}, статус в БД «{after['status']}»")


denied("SC-12", "Оператор не может закрыть заявку", "operator", 3, {"status_id": CLOSED},
       "Закрыть заявку может только заявитель (после выполнения) или администратор", "Critical", 403)
denied("SC-13", "Исполнитель не может закрыть заявку", "petrov", 3, {"status_id": CLOSED},
       "Закрыть заявку может только заявитель (после выполнения) или администратор", "Critical", 403)
denied("SC-14", "Заявитель закрывает ещё не выполненную", "ivanov", 2, {"status_id": CLOSED},
       "Заявитель может только закрыть заявку после её выполнения", "Critical", 403)
denied("SC-15", "Заявитель ставит статус, кроме «Закрыта»", "sokolova", 3, {"status_id": WORK},
       "Заявитель может только закрыть заявку после её выполнения", "High", 403)
denied("SC-16", "Заявитель меняет статус чужой заявки", "ivanov", 3, {"status_id": CLOSED}, "", "High", 403)
denied("SC-17", "Исполнитель меняет статус не своей заявки", "petrov", 7, {"status_id": DONE}, "", "High", 403)
denied("SC-18", "Не-администратор меняет статус закрытой заявки", "operator", 4, {"status_id": WORK},
       "Закрытую заявку может изменять только администратор", "High", 403)
denied("SC-19", "Исполнитель смешивает статус и правку содержания", "petrov", 2, {"status_id": DONE, "title": "Другая тема"},
       "Исполнитель не может редактировать содержание заявки", "Medium", 403)


# ------------------------------------------------------------ данные и переходы
def rejected(tc, title, user, rid, body, expect_status, expect_msg, priority, expected_text):
    @case(tc, title, expected_text, priority)
    def _():
        before = get(rid)
        r = patch(user, rid, body)
        after = get(rid)
        ok = (r.status == expect_status and expect_msg in msg(r) and after["status"] == before["status"]
              and after["title"] == before["title"] and after["executor_id"] == before["executor_id"]
              and len(after["history"]) == len(before["history"]))
        return result(ok, f"HTTP {r.status}, {code(r)}: «{msg(r)}», статус в БД «{after['status']}», исполнитель {after['executor']}, записей истории {len(after['history'])}")


rejected("SC-20", "«В работе» без исполнителя", "operator", 8, {"status_id": WORK}, 422,
         "нельзя оставить без исполнителя", "High", "422 validation_error, «Заявку в статусе «В работе» нельзя оставить без исполнителя»")
rejected("SC-21", "Снять исполнителя у заявки в работе", "operator", 2, {"executor_id": None}, 422,
         "нельзя оставить без исполнителя", "High", "422, то же сообщение, исполнитель petrov остался")
rejected("SC-22", "Атомарность: ошибка отменяет все поля", "operator", 8, {"status_id": WORK, "title": "Новая тема заявки"}, 422,
         "нельзя оставить без исполнителя", "Medium", "422, тема и статус прежние, история без записей")
rejected("SC-23", "Несуществующий статус", "admin", 2, {"status_id": 77}, 422,
         "Статуса с id=77 не существует", "Medium", "422, «Статуса с id=77 не существует»")


@case("SC-24", "Некорректный тип status_id", "для каждого значения 422 «…положительным целым числом», ни одного 500", "Medium")
def _():
    out, ok = [], True
    for value in ("abc", -1, 0, True, 3.5):
        r = patch("admin", 2, {"status_id": value})
        good = r.status == 422 and "положительным целым числом" in msg(r)
        ok &= good
        out.append(f"{value!r}→{r.status}")
    ok &= get(2)["status"] == "В работе"
    return result(ok, "; ".join(out))


@case("SC-25", "Смена статуса несуществующей заявки", "404 not_found в едином формате", "Medium")
def _():
    r = patch("admin", 9999, {"status_id": WORK})
    return result(r.status == 404 and code(r) == "not_found", f"HTTP {r.status}, {code(r)}: «{msg(r)}»")


@case("SC-26", "Пропуск статуса «В работе» (ТЗ: «последовательно»)",
      "по ТЗ отказ: 422, «Новая → Выполнена» недопустим, статус остаётся «Новая»", "High")
def _():
    call("PATCH", "/api/requests/1", data={"executor_id": 3}, user="operator")
    r = patch("petrov", 1, {"status_id": DONE})
    j = get(1)
    ok = r.status == 422 and j["status"] == "Новая"
    return result(ok, f"HTTP {r.status}, статус в БД «{j['status']}»" + (f", {code(r)}: «{msg(r)}»" if r.status >= 400 else ""))


@case("SC-27", "Откат статуса «Выполнена» → «В работе»",
      "по ТЗ не определено; ожидается отказ 422, статус «Выполнена» (требует уточнения)", "Medium")
def _():
    r = patch("petrov", 3, {"status_id": WORK})
    j = get(3)
    return result(r.status == 422 and j["status"] == "Выполнена", f"HTTP {r.status}, статус в БД «{j['status']}»")


# ------------------------------------------------------------ граничные
@case("SC-28", "Установка текущего статуса", "200, новой записи в истории нет", "Medium")
def _():
    n0 = len(status_changes(2))
    r = patch("petrov", 2, {"status_id": WORK})
    n1 = len(status_changes(2))
    return result(r.status == 200 and n1 == n0, f"HTTP {r.status}, записей смены статуса было {n0}, стало {n1}")


@case("SC-29", "Администратор переоткрывает закрытую заявку", "200, «В работе», запись «Закрыта → В работе»", "High")
def _():
    r = patch("admin", 4, {"status_id": WORK})
    j, h = get(4), status_changes(4)
    ok = r.status == 200 and j["status"] == "В работе" and (h[-1]["old_value"], h[-1]["new_value"]) == ("Закрыта", "В работе")
    return result(ok, f"HTTP {r.status}, статус «{j['status']}», запись {h[-1]['old_value']}→{h[-1]['new_value']}")


@case("SC-31", "Время отклика смены статуса", "каждый из 10 запросов быстрее 3 с", "Low")
def _():
    times = []
    for i in range(10):
        t = time.perf_counter()
        patch("admin", 2, {"status_id": WORK if i % 2 else DONE})
        times.append(time.perf_counter() - t)
    return result(max(times) < 3, f"максимум {max(times) * 1000:.0f} мс, среднее {sum(times) / len(times) * 1000:.0f} мс")


# ------------------------------------------------------------ исследовательские (не из таблицы)
EXPLORATORY = []


def explore(xid, title, question):
    def deco(fn):
        EXPLORATORY.append(dict(id=xid, title=title, question=question, fn=fn))
        return fn
    return deco


@explore("X-01", "status_id строкой «3»", "ТЗ не определяет; принимается ли строка вместо числа?")
def _():
    r = patch("admin", 2, {"status_id": "3"})
    return f"HTTP {r.status}, статус в БД «{get(2)['status']}»"


@explore("X-02", "Оператор меняет статус «Новая» → «В работе»", "по ТЗ статусы меняет только исполнитель; оператор — регистрирует и назначает")
def _():
    call("PATCH", "/api/requests/1", data={"executor_id": 3}, user="operator")
    r = patch("operator", 1, {"status_id": WORK})
    return f"HTTP {r.status}, статус в БД «{get(1)['status']}»"


@explore("X-03", "Пустое тело PATCH {}", "что отвечает сервер, если менять нечего?")
def _():
    r = patch("admin", 2, {})
    return f"HTTP {r.status}, {code(r)}: «{msg(r)}»"


@explore("X-04", "status_id = 10^25", "не должно быть 500")
def _():
    r = patch("admin", 2, {"status_id": 10 ** 25})
    return f"HTTP {r.status}, {code(r)}: «{msg(r)}»"


@explore("X-05", "Заявитель закрывает заявку «Новая»", "ТЗ: закрывает «после подтверждения решения»")
def _():
    r = patch("ivanov", 1, {"status_id": CLOSED})
    return f"HTTP {r.status}, статус в БД «{get(1)['status']}»"


@explore("X-06", "Исполнитель из «Новая» сразу в «Закрыта»", "запрещено ТЗ (ФТ-6)")
def _():
    call("PATCH", "/api/requests/1", data={"executor_id": 3}, user="operator")
    r = patch("petrov", 1, {"status_id": CLOSED})
    return f"HTTP {r.status}, статус в БД «{get(1)['status']}»"


def main():
    tmp = tempfile.mkdtemp()
    template, live = os.path.join(tmp, "template.db"), os.path.join(tmp, "live.db")
    rc.prepare_db(template)
    shutil.copy(template, live)
    server = rc.start_server(live)
    results, extra = [], []
    try:
        for c in CASES:
            shutil.copy(template, live)          # свежая база на каждый кейс
            rc.LOG.clear()
            try:
                ok, actual = c["fn"]()
                status = "PASS" if ok else "FAIL"
            except Exception as exc:
                status, actual = "FAIL", f"сценарий завершился ошибкой: {exc!r}"
            results.append(dict(id=c["id"], title=c["title"], priority=c["priority"], expected=c["expected"], actual=actual, status=status))
            print(f"{c['id']}  {status:5} {c['title']}\n         ожидалось: {c['expected']}\n         фактически: {actual}")
        for e in EXPLORATORY:
            shutil.copy(template, live)
            rc.LOG.clear()
            try:
                actual = e["fn"]()
            except Exception as exc:
                actual = f"ошибка сценария: {exc!r}"
            extra.append(dict(id=e["id"], title=e["title"], question=e["question"], actual=actual))
            print(f"{e['id']}  INFO  {e['title']}  ->  {actual}")
    finally:
        server.kill()
    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\nИтого: {len(results)} кейсов, PASS {passed}, FAIL {len(results) - passed}; исследовательских: {len(extra)}")
    out = HERE / "results_status_cases.json"
    out.write_text(json.dumps(dict(date=time.strftime("%Y-%m-%d %H:%M"), results=results, exploratory=extra),
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

