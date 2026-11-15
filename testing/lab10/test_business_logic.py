"""Бизнес-логика: сервисный слой (src/services.py) без HTTP.

Проверяются правила ролей из ТЗ, статусы, исполнитель, поиск и фильтры.
"""
import pytest

from conftest import ADMIN, IVANOV, MOROZOV, OPERATOR, PETROV, SOKOLOVA
from src import repositories as repo
from src import services
from src.errors import Forbidden, NotFound, ValidationError

NEW_REQUEST = {"title": "Не работает принтер", "category_id": 3, "priority": "Высокий", "applicant_id": IVANOV}


def status_id(name):
    return repo.get_status_by_name(name)["id"]


# ---------- создание ----------

def test_create_request_gets_status_new_and_history(ctx, user):
    """AT-01. Новая заявка получает статус «Новая» и запись «Создана» в истории."""
    created = services.create_request(user(OPERATOR), NEW_REQUEST)
    assert created["status"] == "Новая"
    assert created["executor_id"] is None
    history = repo.list_history(created["id"])
    assert [h["action"] for h in history] == ["Создана"]


def test_applicant_creates_request_only_for_himself(ctx, user):
    """AT-02. Заявитель не может создать заявку от имени другого заявителя."""
    data = {**NEW_REQUEST, "applicant_id": SOKOLOVA}
    with pytest.raises(Forbidden):
        services.create_request(user(IVANOV), data)
    own = services.create_request(user(IVANOV), {k: v for k, v in NEW_REQUEST.items() if k != "applicant_id"})
    assert own["applicant_id"] == IVANOV


def test_executor_cannot_create_request(ctx, user):
    """AT-03. Исполнитель заявки не создаёт."""
    with pytest.raises(Forbidden):
        services.create_request(user(PETROV), NEW_REQUEST)


# ---------- статусы ----------

def test_status_in_progress_requires_executor(ctx, user):
    """AT-04. Заявку без исполнителя нельзя перевести в «В работе» (заявка №1 без исполнителя)."""
    with pytest.raises(ValidationError) as error:
        services.update_request(user(ADMIN), 1, {"status_id": status_id("В работе")})
    assert error.value.details == {"executor_id": "required"}
    assert repo.get_request(1)["status"] == "Новая"          # состояние не изменилось


def test_operator_cannot_close_request(ctx, user):
    """AT-05. ФТ-6: «Закрыта» разрешено только заявителю или администратору (заявка №3 «Выполнена»)."""
    with pytest.raises(Forbidden):
        services.update_request(user(OPERATOR), 3, {"status_id": status_id("Закрыта")})
    assert repo.get_request(3)["status"] == "Выполнена"


def test_applicant_can_close_done_request(ctx, user):
    """AT-06. Заявитель закрывает свою выполненную заявку, в истории остаётся запись о смене статуса."""
    updated = services.update_request(user(SOKOLOVA), 3, {"status_id": status_id("Закрыта")})
    assert updated["status"] == "Закрыта"
    last = repo.list_history(3)[-1]
    assert (last["action"], last["old_value"], last["new_value"]) == ("Статус", "Выполнена", "Закрыта")


def test_applicant_cannot_close_unfinished_request(ctx, user):
    """AT-07. Заявитель не может закрыть заявку, которая ещё не «Выполнена»."""
    with pytest.raises(Forbidden):
        services.update_request(user(IVANOV), 2, {"status_id": status_id("Закрыта")})


def test_executor_changes_status_of_own_request(ctx, user):
    """AT-08. Назначенный исполнитель переводит свою заявку «В работе» → «Выполнена»."""
    updated = services.update_request(user(PETROV), 2, {"status_id": status_id("Выполнена")})
    assert updated["status"] == "Выполнена"


def test_executor_cannot_touch_foreign_request(ctx, user):
    """AT-09. Исполнитель не видит и не меняет заявки, назначенные другому (заявка №7 у Морозова)."""
    with pytest.raises(Forbidden):
        services.update_request(user(PETROV), 7, {"status_id": status_id("Выполнена")})


# ---------- права на редактирование ----------

def test_closed_request_editable_only_by_admin(ctx, user):
    """AT-10. Закрытую заявку (№4) может править только администратор."""
    with pytest.raises(Forbidden):
        services.update_request(user(OPERATOR), 4, {"title": "Новое название"})
    assert services.update_request(user(ADMIN), 4, {"title": "Новое название"})["title"] == "Новое название"


def test_applicant_edits_only_own_new_requests(ctx, user):
    """AT-11. Заявитель редактирует только свои заявки в статусе «Новая» (№1 можно, №2 «В работе» нельзя)."""
    assert services.update_request(user(IVANOV), 1, {"description": "Уточнение"})["description"] == "Уточнение"
    with pytest.raises(Forbidden):
        services.update_request(user(IVANOV), 2, {"description": "Уточнение"})


def test_assign_executor_checks_role_and_permission(ctx, user):
    """AT-12. Исполнителя назначает оператор; назначить можно только пользователя с ролью «Исполнитель»."""
    assigned = services.update_request(user(OPERATOR), 1, {"executor_id": MOROZOV})
    assert assigned["executor_id"] == MOROZOV
    with pytest.raises(ValidationError):
        services.update_request(user(OPERATOR), 1, {"executor_id": IVANOV})     # заявитель — не исполнитель
    with pytest.raises(Forbidden):
        services.update_request(user(IVANOV), 1, {"executor_id": PETROV})       # заявитель не назначает


# ---------- видимость ----------

@pytest.mark.parametrize("who, expected", [
    (ADMIN, {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
    (OPERATOR, {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
    (PETROV, {2, 3, 10}),
    (IVANOV, {1, 2, 4, 6, 9}),
])
def test_each_role_sees_only_allowed_requests(ctx, user, who, expected):
    """AT-13. Видимость списка зависит от роли."""
    visible = {r["id"] for r in services.list_requests(user(who), {})}
    assert visible == expected


# ---------- удаление ----------

def test_only_admin_deletes_and_children_are_removed(ctx, user, db):
    """AT-14. Удаляет только администратор; комментарии и история удаляются вместе с заявкой."""
    with pytest.raises(Forbidden):
        services.delete_request(user(OPERATOR), 2)
    assert repo.get_request(2) is not None
    services.delete_request(user(ADMIN), 2)
    assert repo.get_request(2) is None
    assert repo.list_comments(2) == [] and repo.list_history(2) == []
    with pytest.raises(NotFound):
        services.delete_request(user(ADMIN), 2)


# ---------- поиск и фильтры ----------

@pytest.mark.parametrize("query, expected_ids", [
    ("pycharm", {2}),            # регистр не важен
    ("УСТАНОВИТЬ", {2}),         # кириллица в верхнем регистре
    ("#5", {5}),                 # поиск по номеру
    ("интернет", {3, 8}),
    ("%", set()),                # символ % ищется буквально, а не как шаблон «любой текст»
])
def test_search(ctx, user, query, expected_ids):
    """AT-15. Поиск по теме, описанию и номеру, без учёта регистра."""
    found = {r["id"] for r in services.list_requests(user(ADMIN), {"search": query})}
    assert expected_ids <= found
    if query == "%":
        assert found == set()


def test_filters_by_status_and_priority(ctx, user):
    """AT-16. Фильтр по статусу и по приоритету работает и комбинируется."""
    in_progress = services.list_requests(user(ADMIN), {"status_id": status_id("В работе")})
    assert {r["id"] for r in in_progress} == {2, 7, 10}
    combined = services.list_requests(user(ADMIN), {"status_id": status_id("В работе"), "priority": "Низкий"})
    assert {r["id"] for r in combined} == {10}


def test_empty_search_result_is_empty_list(ctx, user):
    """AT-17. Ничего не найдено → пустой список, а не ошибка."""
    assert services.list_requests(user(ADMIN), {"search": "такого-текста-нет-нигде"}) == []
