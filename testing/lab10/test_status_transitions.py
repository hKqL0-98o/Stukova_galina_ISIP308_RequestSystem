"""Порядок смены статусов (ЛР №9, кейсы SC-26 и SC-27 упали; регрессия — ЛР №10, BUG-05).

ТЗ, критерий приёмки 3: исполнитель «последовательно изменяет статус заявки».
Правило после исправления: оператор и исполнитель переводят заявку только вперёд на один шаг
(Новая → В работе → Выполнена); закрывает заявитель после выполнения (ФТ-6). Администратор может любой переход.
Нарушение порядка: HTTP 422, details.status_id = invalid_transition.
"""
import pytest

from conftest import ADMIN, IVANOV, OPERATOR, PETROV, SOKOLOVA
from src import repositories as repo
from src import services

NEW, WORK, DONE, CLOSED = 1, 2, 3, 4          # id статусов из db/seed.sql


def patch(client, auth, login, request_id, **body):
    return client.patch(f"/api/requests/{request_id}", json=body, headers=auth(login))


def assign_petrov(client, auth, request_id=1):
    assert patch(client, auth, "operator", request_id, executor_id=3).status_code == 200


def status_of(db, request_id):
    return db.execute("SELECT status_id FROM Requests WHERE id = ?", (request_id,)).fetchone()[0]


def test_executor_cannot_skip_in_progress(client, auth, db):
    """ST-01 (SC-26). Исполнитель не может перевести «Новая» сразу в «Выполнена»."""
    assign_petrov(client, auth)
    response = patch(client, auth, "petrov", 1, status_id=DONE)
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "validation_error" and error["details"] == {"status_id": "invalid_transition"}
    assert "последовательно" in error["message"]
    assert status_of(db, 1) == NEW


def test_operator_cannot_skip_in_progress(client, auth, db):
    """ST-02. Оператору нельзя пропустить «В работе» так же, как исполнителю."""
    assign_petrov(client, auth)
    assert patch(client, auth, "operator", 1, status_id=DONE).status_code == 422
    assert status_of(db, 1) == NEW


def test_executor_cannot_roll_back(client, auth, db):
    """ST-03 (SC-27). Исполнитель не может вернуть «Выполнена» в «В работе»."""
    response = patch(client, auth, "petrov", 3, status_id=WORK)
    assert response.status_code == 422
    assert response.get_json()["error"]["details"] == {"status_id": "invalid_transition"}
    assert status_of(db, 3) == DONE


def test_operator_cannot_roll_back_to_new(client, auth, db):
    """ST-04. Оператору нельзя вернуть «В работе» в «Новая»."""
    assert patch(client, auth, "operator", 2, status_id=NEW).status_code == 422
    assert status_of(db, 2) == WORK


def test_sequence_forward_works_for_all_roles(client, auth, db):
    """ST-05. Последовательный путь Новая → В работе → Выполнена → Закрыта проходит (закрывает заявитель)."""
    assign_petrov(client, auth)
    assert patch(client, auth, "petrov", 1, status_id=WORK).status_code == 200
    assert patch(client, auth, "operator", 1, status_id=DONE).status_code == 200
    assert patch(client, auth, "ivanov", 1, status_id=CLOSED).status_code == 200
    assert status_of(db, 1) == CLOSED


@pytest.mark.parametrize("request_id, target", [(1, DONE), (3, NEW), (4, WORK), (2, NEW)])
def test_admin_may_make_any_transition(client, auth, db, request_id, target):
    """ST-06. Администратор может любой переход: пропуск, откат, переоткрытие закрытой заявки."""
    if request_id == 1:
        assign_petrov(client, auth)
    assert patch(client, auth, "admin", request_id, status_id=target).status_code == 200
    assert status_of(db, request_id) == target


def test_same_status_is_not_an_error(client, auth, db):
    """ST-07. Повторная установка текущего статуса не ошибка и не пишется в историю (SC-28)."""
    before = db.execute("SELECT COUNT(*) FROM RequestHistory WHERE request_id = 2").fetchone()[0]
    assert patch(client, auth, "petrov", 2, status_id=WORK).status_code == 200
    assert db.execute("SELECT COUNT(*) FROM RequestHistory WHERE request_id = 2").fetchone()[0] == before


def test_rejected_transition_changes_nothing(client, auth, db):
    """ST-08. Запрещённый переход вместе с другими полями отменяет весь запрос (SC-22)."""
    assign_petrov(client, auth)
    before = db.execute("SELECT COUNT(*) FROM RequestHistory WHERE request_id = 1").fetchone()[0]
    response = patch(client, auth, "operator", 1, status_id=DONE, priority="Высокий")
    assert response.status_code == 422
    row = db.execute("SELECT priority FROM Requests WHERE id = 1").fetchone()
    assert row[0] == "Низкий"      # в seed.sql у заявки №1 приоритет «Низкий»: «Высокий» из отклонённого запроса не применился
    assert db.execute("SELECT COUNT(*) FROM RequestHistory WHERE request_id = 1").fetchone()[0] == before


def test_ui_offers_only_the_next_status(ctx, user):
    """ST-09. Список «Сменить статус» в интерфейсе предлагает только допустимые переходы."""
    def names(login_id, request_id):
        req = repo.get_request(request_id)
        return [s["name"] for s in services.permissions(user(login_id), req)["allowed_statuses"]]

    assert names(PETROV, 2) == ["Выполнена"]               # В работе → только вперёд
    assert names(OPERATOR, 3) == []                        # Выполнена: оператор закрывать не может, откат запрещён
    assert names(SOKOLOVA, 3) == ["Закрыта"]               # заявитель закрывает выполненную
    assert names(ADMIN, 2) == ["Новая", "Выполнена", "Закрыта"]
