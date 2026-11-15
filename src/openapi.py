"""Описание API в формате OpenAPI 3: по нему Swagger UI на /docs строит документацию с кнопкой «Try it out»."""

_ERR = {"$ref": "#/components/schemas/Error"}


def _json(schema):
    return {"application/json": {"schema": schema}}


def _resp(description, schema=None):
    body = {"description": description}
    if schema is not None:
        body["content"] = _json(schema)
    return body


def _errors(*codes):
    text = {
        400: "Некорректный JSON", 401: "Не выполнен вход", 403: "Недостаточно прав для роли",
        404: "Заявка не найдена", 415: "Тело запроса не JSON", 422: "Ошибка валидации",
    }
    return {str(c): _resp(text[c], _ERR) for c in codes}


_ID_PATH = {"name": "request_id", "in": "path", "required": True,
            "schema": {"type": "integer", "minimum": 1}, "description": "Номер заявки"}

_PRIORITY = {"type": "string", "enum": ["Низкий", "Средний", "Высокий"]}


def build_spec():
    ref = lambda name: {"$ref": f"#/components/schemas/{name}"}
    array = lambda name: {"type": "array", "items": ref(name)}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "HelpDesk REST API",
            "version": "2.0.0",
            "description": (
                "API системы учёта заявок.\n\n"
                "**Авторизация:** HTTP Basic (логин и пароль пользователя). "
                "Нажмите «Authorize» и введите логин/пароль тестовой учётной записи.\n\n"
                "Права зависят от роли: заявитель видит только свои заявки, исполнитель — только назначенные ему.\n\n"
                "Все ошибки возвращаются в едином формате `{\"error\": {\"code\", \"message\", \"details\"}}`."
            ),
        },
        "servers": [{"url": "/"}],
        "security": [{"basicAuth": []}],
        "tags": [{"name": "Заявки"}, {"name": "Комментарии"}, {"name": "Справочники"}, {"name": "Служебное"}],
        "paths": {
            "/api/requests": {
                "get": {
                    "tags": ["Заявки"], "summary": "Список заявок с поиском и фильтрами",
                    "parameters": [
                        {"name": "search", "in": "query", "schema": {"type": "string", "maxLength": 100},
                         "description": "Поиск по номеру (можно «#4»), теме и описанию, без учёта регистра"},
                        {"name": "status_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "category_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "executor_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "priority", "in": "query", "schema": _PRIORITY},
                    ],
                    "responses": {"200": _resp("Массив заявок", array("Request")), **_errors(401, 422)},
                },
                "post": {
                    "tags": ["Заявки"], "summary": "Создать заявку",
                    "description": "Заявитель создаёт заявку от своего имени (applicant_id не нужен). "
                                   "Оператор и администратор обязаны указать applicant_id. Исполнитель создавать не может.",
                    "requestBody": {"required": True, "content": _json(ref("RequestCreate"))},
                    "responses": {"201": _resp("Созданная заявка", ref("Request")), **_errors(401, 403, 415, 422)},
                },
            },
            "/api/requests/{request_id}": {
                "parameters": [_ID_PATH],
                "get": {
                    "tags": ["Заявки"], "summary": "Заявка с комментариями и историей",
                    "responses": {"200": _resp("Заявка", ref("RequestDetails")), **_errors(401, 403, 404)},
                },
                "patch": {
                    "tags": ["Заявки"], "summary": "Изменить заявку (только переданные поля)",
                    "description": "Правила: закрыть заявку может только заявитель (после выполнения) или администратор; "
                                   "назначать исполнителя — оператор и администратор; "
                                   "статусы «В работе», «Выполнена», «Закрыта» требуют исполнителя.",
                    "requestBody": {"required": True, "content": _json(ref("RequestUpdate"))},
                    "responses": {"200": _resp("Обновлённая заявка", ref("Request")),
                                  **_errors(400, 401, 403, 404, 415, 422)},
                },
                "put": {
                    "tags": ["Заявки"], "summary": "То же, что PATCH",
                    "requestBody": {"required": True, "content": _json(ref("RequestUpdate"))},
                    "responses": {"200": _resp("Обновлённая заявка", ref("Request")),
                                  **_errors(400, 401, 403, 404, 415, 422)},
                },
                "delete": {
                    "tags": ["Заявки"], "summary": "Удалить заявку (только администратор)",
                    "description": "Комментарии и история удаляются вместе с заявкой.",
                    "responses": {"204": _resp("Удалено"), **_errors(401, 403, 404)},
                },
            },
            "/api/requests/{request_id}/comments": {
                "parameters": [_ID_PATH],
                "get": {"tags": ["Комментарии"], "summary": "Комментарии к заявке",
                        "responses": {"200": _resp("Массив комментариев", array("Comment")), **_errors(401, 403, 404)}},
                "post": {"tags": ["Комментарии"], "summary": "Добавить комментарий",
                         "requestBody": {"required": True, "content": _json(ref("CommentCreate"))},
                         "responses": {"201": _resp("Комментарий", ref("Comment")),
                                       **_errors(400, 401, 403, 404, 415, 422)}},
            },
            "/api/users": {"get": {"tags": ["Справочники"], "summary": "Пользователи (оператор, администратор)",
                                   "responses": {"200": _resp("Массив пользователей", array("User")),
                                                 **_errors(401, 403)}}},
            "/api/statuses": {"get": {"tags": ["Справочники"], "summary": "Справочник статусов",
                                      "responses": {"200": _resp("Массив статусов", array("Status")),
                                                    **_errors(401)}}},
            "/api/categories": {"get": {"tags": ["Справочники"], "summary": "Справочник категорий",
                                        "responses": {"200": _resp("Массив категорий", array("Category")),
                                                      **_errors(401)}}},
            "/api/me": {"get": {"tags": ["Служебное"], "summary": "Текущий пользователь",
                                "responses": {"200": _resp("Пользователь", ref("User")), **_errors(401)}}},
            "/health": {"get": {"tags": ["Служебное"], "summary": "Проверка работоспособности", "security": [],
                                "responses": {"200": _resp("Приложение и БД работают"),
                                              "503": _resp("База данных недоступна")}}},
        },
        "components": {
            "securitySchemes": {"basicAuth": {"type": "http", "scheme": "basic"}},
            "schemas": {
                "Request": {"type": "object", "properties": {
                    "id": {"type": "integer", "example": 1},
                    "title": {"type": "string", "example": "Не работает мышь"},
                    "description": {"type": "string", "nullable": True},
                    "priority": _PRIORITY,
                    "status_id": {"type": "integer"}, "status": {"type": "string", "example": "Новая"},
                    "category_id": {"type": "integer"}, "category": {"type": "string"},
                    "applicant_id": {"type": "integer"}, "applicant": {"type": "string"},
                    "executor_id": {"type": "integer", "nullable": True},
                    "executor": {"type": "string", "nullable": True},
                    "created_at": {"type": "string"}, "updated_at": {"type": "string"},
                }},
                "RequestDetails": {"allOf": [ref("Request"), {"type": "object", "properties": {
                    "comments": array("Comment"), "history": array("HistoryItem")}}]},
                "RequestCreate": {"type": "object", "required": ["title", "category_id"],
                                  "additionalProperties": False, "properties": {
                    "title": {"type": "string", "minLength": 3, "maxLength": 100, "example": "Не работает сканер"},
                    "description": {"type": "string", "maxLength": 2000, "example": "Не включается после обновления"},
                    "category_id": {"type": "integer", "example": 3},
                    "priority": {**_PRIORITY, "default": "Средний"},
                    "applicant_id": {"type": "integer", "example": 5,
                                     "description": "Обязателен для оператора и администратора"},
                }},
                "RequestUpdate": {"type": "object", "additionalProperties": False, "minProperties": 1, "properties": {
                    "title": {"type": "string", "minLength": 3, "maxLength": 100},
                    "description": {"type": "string", "maxLength": 2000, "nullable": True},
                    "category_id": {"type": "integer"},
                    "priority": _PRIORITY,
                    "status_id": {"type": "integer", "example": 2},
                    "executor_id": {"type": "integer", "nullable": True, "example": 3},
                }},
                "Comment": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "request_id": {"type": "integer"},
                    "author_id": {"type": "integer"}, "author": {"type": "string"},
                    "author_role": {"type": "string"}, "content": {"type": "string"},
                    "created_at": {"type": "string"}}},
                "CommentCreate": {"type": "object", "required": ["content"], "additionalProperties": False,
                                  "properties": {"content": {"type": "string", "minLength": 1, "maxLength": 1000,
                                                             "example": "Проверил, всё работает"}}},
                "HistoryItem": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "action": {"type": "string", "example": "Статус"},
                    "old_value": {"type": "string", "nullable": True}, "new_value": {"type": "string", "nullable": True},
                    "user_id": {"type": "integer"}, "user": {"type": "string"}, "user_role": {"type": "string"},
                    "created_at": {"type": "string"}}},
                "User": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "fio": {"type": "string"}, "login": {"type": "string"},
                    "role": {"type": "string"}, "is_active": {"type": "integer"}, "created_at": {"type": "string"}}},
                "Status": {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}},
                "Category": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "name": {"type": "string"}, "description": {"type": "string"}}},
                "Error": {"type": "object", "properties": {"error": {"type": "object", "properties": {
                    "code": {"type": "string", "example": "validation_error"},
                    "message": {"type": "string", "example": "Поле «Тема»: минимум 3 символа, сейчас 1"},
                    "details": {"type": "object", "example": {"title": "min_length:3"}}}}}},
            },
        },
    }


SWAGGER_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>HelpDesk API — документация</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
<script>
    window.onload = () => { window.ui = SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" }); };
</script>
</body>
</html>"""
