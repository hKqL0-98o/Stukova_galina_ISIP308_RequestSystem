"""Регрессионные тесты для дефектов, найденных в ЛР №9 (см. testing/lab9/bug_reports.md)."""
import re

import pytest

from conftest import BIG_ID

BODY = {"title": "Регрессия", "category_id": 1, "applicant_id": 5}


# BUG-01: идентификатор больше 2**63-1 вызывал OverflowError в SQLite и ответ HTTP 500
@pytest.mark.parametrize("method, path, payload", [
    ("get",    f"/api/requests/{BIG_ID}", None),
    ("delete", f"/api/requests/{BIG_ID}", None),
    ("get",    f"/api/requests/{BIG_ID}/comments", None),
    ("get",    f"/api/requests?status_id={BIG_ID}", None),
    ("get",    f"/api/requests?category_id={BIG_ID}", None),
    ("get",    f"/api/requests?executor_id={BIG_ID}", None),
    ("post",   "/api/requests", {**BODY, "category_id": BIG_ID}),
    ("post",   "/api/requests", {**BODY, "applicant_id": BIG_ID}),
    ("post",   "/api/requests", {**BODY, "category_id": "9" * 5000}),      # строка из 5000 цифр
    ("patch",  "/api/requests/1", {"status_id": BIG_ID}),
    ("patch",  "/api/requests/1", {"executor_id": BIG_ID}),
    ("patch",  "/api/requests/1", {"category_id": BIG_ID}),
])
def test_bug01_huge_identifier_does_not_cause_500(client, auth, method, path, payload):
    """REG-01 (BUG-01). Огромный идентификатор → 404 или 422, но никогда 500."""
    kwargs = {"json": payload} if payload is not None else {}
    response = getattr(client, method)(path, headers=auth("admin"), **kwargs)
    assert response.status_code in (404, 422), response.get_data(as_text=True)


# BUG-02: поиск по длинному числу (19 цифр и больше) вызывал ошибку и HTTP 500
@pytest.mark.parametrize("query", ["9" * 19, "9" * 20, "#" + "9" * 30, "9" * 5000])
def test_bug02_search_by_long_number_returns_empty_list(client, auth, query):
    """REG-02 (BUG-02). Поиск по очень длинному числу → 200 и пустой список."""
    response = client.get("/api/requests", query_string={"search": query}, headers=auth("admin"))
    assert response.status_code == 200 and response.get_json() == []


def test_bug02_search_by_normal_number_still_works(client, auth):
    """REG-03. Исправление не сломало поиск по обычному номеру заявки."""
    found = client.get("/api/requests?search=%237", headers=auth("admin")).get_json()
    assert 7 in [r["id"] for r in found]


# BUG-03: управляющие символы в тексте: в теме давали 500, в описании и комментарии сохранялись в БД
@pytest.mark.parametrize("field", ["title", "description"])
@pytest.mark.parametrize("char", ["\x00", "\x07"])
def test_bug03_control_characters_are_rejected(client, auth, field, char):
    """REG-04 (BUG-03). NUL и другие управляющие символы в теме/описании → 422."""
    response = client.post("/api/requests", json={**BODY, field: f"до{char}после"}, headers=auth("operator"))
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_bug03_control_character_in_comment_is_rejected(client, auth):
    """REG-05 (BUG-03). То же для комментария."""
    response = client.post("/api/requests/1/comments", json={"content": "a\x00b"}, headers=auth("admin"))
    assert response.status_code == 422


def test_bug03_failed_request_leaves_db_unchanged(client, auth, db):
    """REG-06. После отклонённого запроса в БД не появилось новых записей."""
    client.post("/api/requests", json={**BODY, "title": "до\x00после"}, headers=auth("operator"))
    client.post("/api/requests/1/comments", json={"content": "a\x00b"}, headers=auth("admin"))
    assert db.execute("SELECT COUNT(*) FROM Requests").fetchone()[0] == 10
    assert db.execute("SELECT COUNT(*) FROM Comments").fetchone()[0] == 3


def test_normal_multiline_text_is_still_allowed(client, auth):
    """REG-07. Обычные переносы строк и табуляция в описании по-прежнему допустимы."""
    response = client.post("/api/requests", json={**BODY, "description": "строка 1\nстрока 2\r\n\tс отступом"},
                           headers=auth("operator"))
    assert response.status_code == 201


# BUG-04: список «Сменить статус» предлагал по умолчанию «Новая» и позволял случайно вернуть заявку в начальный статус
def test_bug04_status_form_has_no_default_transition(client, web_login):
    """REG-08 (BUG-04). В форме смены статуса по умолчанию выбран пустой недоступный пункт, а не конкретный статус."""
    web_login("operator")
    html = client.get("/requests/2").get_data(as_text=True)       # заявка №2 в seed.sql: статус «В работе»
    select = re.search(r'<select id="status_id"[^>]*>.*?</select>', html, re.S).group(0)
    assert re.search(r'<option value=""\s+selected\s+disabled>', select), select
    assert "required" in select.split(">")[0]
    assert select.count("selected") == 1          # другого выбранного пункта нет
