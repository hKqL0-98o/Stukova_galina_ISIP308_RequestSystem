"""ЛР №10, взаимодействие 1 (AI-журнал). Тесты по черновику модели, проверенные и исправленные на проекте.

Покрывает то, чего не было в testing/lab10/ на момент запроса:
  A) services.create_request: приоритет по умолчанию, обрезка пробелов, границы после обрезки, неверный приоритет;
  B) services.status_transition_error: чистая функция, проверяется напрямую, без БД и HTTP;
  C) POST /api/requests: нет входа, роль «Исполнитель», лишнее поле, неверные типы, кириллица и эмодзи.
"""
import pytest

from src import services
from src.errors import Forbidden, ValidationError
from src.services import CLOSED, DONE, IN_PROGRESS, NEW

ADMIN_ROLE, OPERATOR_ROLE, EXECUTOR_ROLE, APPLICANT_ROLE = "Администратор", "Оператор", "Исполнитель", "Заявитель"
ADMIN_ID, OPERATOR_ID, PETROV_ID, IVANOV_ID = 1, 2, 3, 5


def count_requests(db):
    return db.execute("SELECT COUNT(*) FROM Requests").fetchone()[0]


# ---------- A. services.create_request ----------

def test_create_without_priority_gets_default_medium(ctx, user):
    """AI-01. Приоритет не передан → «Средний», статус «Новая»."""
    created = services.create_request(user(OPERATOR_ID),
                                      {"title": "Сломалась мышь", "category_id": 1, "applicant_id": IVANOV_ID})
    assert created["priority"] == "Средний"
    assert created["status"] == NEW


def test_create_trims_spaces_around_title(ctx, user):
    """AI-02. Пробелы по краям темы обрезаются перед сохранением."""
    created = services.create_request(user(OPERATOR_ID),
                                      {"title": "   Сломался монитор   ", "category_id": 1, "applicant_id": IVANOV_ID})
    assert created["title"] == "Сломался монитор"


@pytest.mark.parametrize("title, ok", [("  abc  ", True), ("  ab  ", False)])
def test_title_minimum_is_checked_after_trimming(ctx, user, title, ok):
    """AI-03. Граница 3 символа считается после обрезки пробелов: «  ab  » нельзя, «  abc  » можно."""
    data = {"title": title, "category_id": 1, "applicant_id": IVANOV_ID}
    if ok:
        assert services.create_request(user(OPERATOR_ID), data)["title"] == "abc"
    else:
        with pytest.raises(ValidationError):
            services.create_request(user(OPERATOR_ID), data)


def test_create_with_invalid_priority_is_rejected_and_not_saved(ctx, user, db):
    """AI-04. Приоритет вне списка («Срочно») → ValidationError, в базе новых заявок нет."""
    before = count_requests(db)
    with pytest.raises(ValidationError):
        services.create_request(user(OPERATOR_ID), {"title": "Тема заявки", "category_id": 1,
                                                    "priority": "Срочно", "applicant_id": IVANOV_ID})
    assert count_requests(db) == before


# ---------- B. services.status_transition_error (чистая функция) ----------

def req(status):
    return {"status": status}


def usr(role):
    return {"role": role}


@pytest.mark.parametrize("role", [OPERATOR_ROLE, EXECUTOR_ROLE])
@pytest.mark.parametrize("current, target", [(NEW, IN_PROGRESS), (IN_PROGRESS, DONE), (DONE, CLOSED)])
def test_one_step_forward_is_allowed(role, current, target):
    """AI-05. Шаг вперёд на один статус разрешён: функция возвращает None (нет нарушения)."""
    assert services.status_transition_error(usr(role), req(current), target) is None


@pytest.mark.parametrize("current, target", [(NEW, DONE), (NEW, CLOSED), (IN_PROGRESS, CLOSED)])
def test_skipping_a_status_is_an_error(current, target):
    """AI-06. Пропуск статуса оператором даёт сообщение про последовательность."""
    message = services.status_transition_error(usr(OPERATOR_ROLE), req(current), target)
    assert message is not None and "последовательно" in message


@pytest.mark.parametrize("current, target", [(IN_PROGRESS, NEW), (DONE, IN_PROGRESS), (DONE, NEW)])
def test_rolling_back_is_an_error(current, target):
    """AI-07. Откат назад для оператора и исполнителя запрещён."""
    for role in (OPERATOR_ROLE, EXECUTOR_ROLE):
        assert services.status_transition_error(usr(role), req(current), target) is not None


def test_same_status_is_never_an_error():
    """AI-08. «Сменить» статус на тот же, что и сейчас, не ошибка для любой роли и любого статуса."""
    for role in (ADMIN_ROLE, OPERATOR_ROLE, EXECUTOR_ROLE, APPLICANT_ROLE):
        for status in (NEW, IN_PROGRESS, DONE, CLOSED):
            assert services.status_transition_error(usr(role), req(status), status) is None


def test_admin_may_make_any_transition():
    """AI-09. Администратору разрешены все 16 пар (включая откат и переоткрытие закрытой)."""
    for current in (NEW, IN_PROGRESS, DONE, CLOSED):
        for target in (NEW, IN_PROGRESS, DONE, CLOSED):
            assert services.status_transition_error(usr(ADMIN_ROLE), req(current), target) is None


def test_closed_request_is_protected_by_permission_check_not_by_order_check():
    """AI-10. У «Закрыта» нет следующего статуса, поэтому проверка порядка её не блокирует (None);
    закрытую заявку защищает status_denied_reason (права). Тест фиксирует это разделение обязанностей."""
    operator, closed = usr(OPERATOR_ROLE), req(CLOSED)
    assert services.status_transition_error(operator, closed, NEW) is None
    assert "только администратор" in services.status_denied_reason(operator, closed, NEW)


def test_operator_cannot_reopen_closed_request_via_api(client, auth, db):
    """AI-10б. Итог для пользователя: оператор не может вернуть закрытую заявку №4 в «Новая» → 403, статус прежний."""
    response = client.patch("/api/requests/4", json={"status_id": 1}, headers=auth("operator"))
    assert response.status_code == 403
    assert db.execute("SELECT status_id FROM Requests WHERE id = 4").fetchone()[0] == 4

# ---------- C. POST /api/requests ----------

BODY = {"title": "Не работает сканер", "category_id": 3, "priority": "Высокий", "applicant_id": IVANOV_ID}


def test_post_without_login_is_401_and_saves_nothing(client, db):
    """AI-11. Без входа → 401 в едином формате, заявка не создаётся."""
    before = count_requests(db)
    response = client.post("/api/requests", json=BODY)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"
    assert count_requests(db) == before


def test_post_by_executor_is_403(client, auth, db):
    """AI-12. Исполнитель не может создавать заявки → 403 forbidden, в базе без изменений."""
    before = count_requests(db)
    response = client.post("/api/requests", json=BODY, headers=auth("petrov"))
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"
    assert count_requests(db) == before


def test_post_unknown_field_is_422_and_saves_nothing(client, auth, db):
    """AI-13. Лишнее поле в JSON (например, status_id) отвергается, а не игнорируется молча."""
    before = count_requests(db)
    response = client.post("/api/requests", json={**BODY, "status_id": 4}, headers=auth("operator"))
    assert response.status_code == 422
    assert count_requests(db) == before


@pytest.mark.parametrize("field, value", [
    ("title", 12345), ("title", ["a", "b"]), ("category_id", "abc"), ("category_id", True),
    ("category_id", 1.5), ("priority", 5),
])
def test_post_wrong_types_are_422(client, auth, field, value):
    """AI-14. Неверные типы полей (число вместо строки, строка вместо числа, булево, дробь) → 422."""
    response = client.post("/api/requests", json={**BODY, field: value}, headers=auth("operator"))
    assert response.status_code == 422, response.get_data(as_text=True)


def test_post_cyrillic_and_emoji_survive_roundtrip(client, auth):
    """AI-15. Кириллица и эмодзи в теме сохраняются без искажений (UTF-8 до базы и обратно)."""
    title = "Не печатает принтер 🖨 в кабинете 12"
    created = client.post("/api/requests", json={**BODY, "title": title}, headers=auth("operator")).get_json()
    again = client.get(f"/api/requests/{created['id']}", headers=auth("admin")).get_json()
    assert again["title"] == title
