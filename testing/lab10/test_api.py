"""REST API: успешные и ошибочные запросы, HTTP-коды, единый формат ошибок."""
import pytest

from conftest import BIG_ID

NEW = {"title": "Не работает сканер", "category_id": 3, "priority": "Высокий", "applicant_id": 5}


def assert_error(response, status, code):
    """Все ошибки API имеют единый формат {"error": {"code", "message", "details"}}."""
    assert response.status_code == status
    body = response.get_json()
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


# ---------- чтение ----------

def test_list_requests_returns_json_array(client, auth):
    """AT-27. GET /api/requests → 200 и JSON-массив из 10 заявок."""
    response = client.get("/api/requests", headers=auth("admin"))
    assert response.status_code == 200
    assert response.is_json and len(response.get_json()) == 10


def test_get_request_contains_comments_and_history(client, auth):
    """AT-28. GET /api/requests/{id} → 200, внутри комментарии и история."""
    body = client.get("/api/requests/3", headers=auth("admin")).get_json()
    assert body["id"] == 3 and body["status"] == "Выполнена"
    assert "comments" in body and "history" in body


def test_get_missing_request_is_404(client, auth):
    """AT-29. Несуществующая заявка → 404 в едином формате."""
    assert_error(client.get("/api/requests/9999", headers=auth("admin")), 404, "not_found")


def test_reference_lists(client, auth):
    """AT-30. Справочники статусов и категорий содержат по 4 записи, пользователи доступны оператору."""
    assert len(client.get("/api/statuses", headers=auth("ivanov")).get_json()) == 4
    assert len(client.get("/api/categories", headers=auth("ivanov")).get_json()) == 4
    users = client.get("/api/users", headers=auth("operator")).get_json()
    assert len(users) == 6 and all("password_hash" not in u for u in users)   # хеши паролей наружу не отдаются


def test_filters_via_query_parameters(client, auth):
    """AT-31. Поиск и фильтры передаются через query-параметры."""
    found = client.get("/api/requests?search=pycharm", headers=auth("admin")).get_json()
    assert [r["id"] for r in found] == [2]
    assert len(client.get("/api/requests?priority=Высокий", headers=auth("admin")).get_json()) == 3
    assert_error(client.get("/api/requests?priority=Срочно", headers=auth("admin")), 422, "validation_error")


# ---------- создание, изменение, удаление ----------

def test_create_request_returns_201_and_is_readable(client, auth):
    """AT-32. POST → 201, заголовок Location, повторное чтение возвращает те же данные."""
    response = client.post("/api/requests", json=NEW, headers=auth("operator"))
    assert response.status_code == 201
    created = response.get_json()
    assert response.headers["Location"].endswith(f"/api/requests/{created['id']}")
    again = client.get(f"/api/requests/{created['id']}", headers=auth("admin")).get_json()
    assert again["title"] == NEW["title"] and again["status"] == "Новая"


@pytest.mark.parametrize("payload", [{}, {"title": "x"}, {"title": "Нормальная тема"}, {**NEW, "category_id": 99}])
def test_create_with_invalid_data_is_422(client, auth, payload):
    """AT-33. Пустой JSON, короткая тема, нет категории, несуществующая категория → 422."""
    assert_error(client.post("/api/requests", json=payload, headers=auth("operator")), 422, "validation_error")


def test_create_without_json_is_415_and_broken_json_is_400(client, auth):
    """AT-34. Не JSON → 415, битый JSON → 400."""
    assert_error(client.post("/api/requests", data="title=abc", headers=auth("operator")), 415, "unsupported_media_type")
    broken = client.post("/api/requests", data="{не json", content_type="application/json", headers=auth("operator"))
    assert_error(broken, 400, "bad_request")


@pytest.mark.parametrize("method", ["patch", "put"])
def test_update_request(client, auth, method):
    """AT-35. PATCH и PUT меняют переданные поля → 200; изменения видны при повторном чтении."""
    response = getattr(client, method)("/api/requests/1", json={"description": "Новое описание"}, headers=auth("admin"))
    assert response.status_code == 200 and response.get_json()["description"] == "Новое описание"
    assert client.get("/api/requests/1", headers=auth("admin")).get_json()["description"] == "Новое описание"


def test_update_errors(client, auth):
    """AT-36. Несуществующая заявка → 404; пустое тело → 422; недопустимый статус → 422."""
    assert_error(client.patch("/api/requests/9999", json={"title": "Тема"}, headers=auth("admin")), 404, "not_found")
    assert_error(client.patch("/api/requests/1", json={}, headers=auth("admin")), 422, "validation_error")
    assert_error(client.patch("/api/requests/1", json={"status_id": 77}, headers=auth("admin")), 422, "validation_error")


def test_status_change_via_api_is_persisted(client, auth):
    """AT-37. Смена статуса через API сохраняется и попадает в историю."""
    response = client.patch("/api/requests/2", json={"status_id": 3}, headers=auth("petrov"))
    assert response.status_code == 200
    body = client.get("/api/requests/2", headers=auth("admin")).get_json()
    assert body["status"] == "Выполнена"
    assert body["history"][-1]["new_value"] == "Выполнена"


def test_delete_request(client, auth):
    """AT-38. DELETE → 204 (оператору 403), после удаления GET → 404 и повторный DELETE → 404."""
    assert_error(client.delete("/api/requests/1", headers=auth("operator")), 403, "forbidden")
    assert client.delete("/api/requests/1", headers=auth("admin")).status_code == 204
    assert_error(client.get("/api/requests/1", headers=auth("admin")), 404, "not_found")
    assert_error(client.delete("/api/requests/1", headers=auth("admin")), 404, "not_found")


def test_comments_api(client, auth):
    """AT-39. POST комментария → 201, он появляется в списке; пустой комментарий → 422."""
    response = client.post("/api/requests/1/comments", json={"content": "Проверяю"}, headers=auth("ivanov"))
    assert response.status_code == 201
    listed = client.get("/api/requests/1/comments", headers=auth("admin")).get_json()
    assert listed[-1]["content"] == "Проверяю" and listed[-1]["author"] == "Иван Иванов"
    assert_error(client.post("/api/requests/1/comments", json={"content": " "}, headers=auth("ivanov")), 422, "validation_error")


# ---------- авторизация и доступ ----------

def test_api_requires_authentication(client, auth):
    """AT-40. Без авторизации и с неверным паролем → 401; /health доступен без входа."""
    assert_error(client.get("/api/requests"), 401, "unauthorized")
    assert_error(client.get("/api/requests", headers=auth("admin", "wrong-password")), 401, "unauthorized")
    assert client.get("/health").status_code == 200


def test_api_access_depends_on_role(client, auth):
    """AT-41. Чужая заявка → 403; список пользователей заявителю → 403; создание исполнителем → 403."""
    assert_error(client.get("/api/requests/1", headers=auth("sokolova")), 403, "forbidden")
    assert_error(client.get("/api/users", headers=auth("ivanov")), 403, "forbidden")
    assert_error(client.post("/api/requests", json=NEW, headers=auth("petrov")), 403, "forbidden")


def test_health(client):
    """AT-42. /health сообщает, что приложение и база работают."""
    body = client.get("/health").get_json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_unknown_path_and_method_return_json_errors(client, auth):
    """AT-43. Неизвестный адрес → 404, неподдерживаемый метод → 405, оба в формате API."""
    assert_error(client.get("/api/unknown", headers=auth("admin")), 404, "not_found")
    assert client.delete("/api/statuses", headers=auth("admin")).status_code == 405


@pytest.mark.parametrize("path", [f"/api/requests/{BIG_ID}", "/api/requests/abc", "/api/requests/-1", "/api/requests/0"])
def test_strange_identifiers_give_404(client, auth, path):
    """AT-44. Странные идентификаторы (огромный, текст, отрицательный, ноль) → 404, а не 500."""
    assert_error(client.get(path, headers=auth("admin")), 404, "not_found")
