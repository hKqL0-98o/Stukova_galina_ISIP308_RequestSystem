"""Сервисный слой: бизнес-правила системы учёта заявок.

Здесь проверяются данные и права ролей. SQL здесь нет, он в repositories.py.
HTML и JSON здесь тоже нет, они в web.py и api.py.
"""
import re

from . import repositories as repo
from .db import transaction
from .errors import Forbidden, NotFound, ValidationError

# Роли
ADMIN, OPERATOR, EXECUTOR, APPLICANT = "Администратор", "Оператор", "Исполнитель", "Заявитель"
ROLES = (ADMIN, OPERATOR, EXECUTOR, APPLICANT)

# Статусы
NEW, IN_PROGRESS, DONE, CLOSED = "Новая", "В работе", "Выполнена", "Закрыта"
STATUSES_NEED_EXECUTOR = (IN_PROGRESS, DONE, CLOSED)

PRIORITIES = ("Низкий", "Средний", "Высокий")
DEFAULT_PRIORITY = "Средний"

# Наибольшее число, которое помещается в INTEGER SQLite. Идентификаторы больше этого значения не существуют.
SQLITE_INT_MAX = 2 ** 63 - 1
# Управляющие символы (включая NUL), кроме табуляции и переводов строки
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

TITLE_MIN, TITLE_MAX = 3, 100
DESCRIPTION_MAX = 2000
COMMENT_MAX = 1000
SEARCH_MAX = 100

CREATE_FIELDS = {"title", "description", "category_id", "priority", "applicant_id"}
UPDATE_FIELDS = {"title", "description", "category_id", "priority", "status_id", "executor_id"}
CONTENT_FIELDS = ("title", "description", "category_id", "priority")

FIELD_LABELS = {
    "title": "Тема", "description": "Описание", "category_id": "Категория",
    "priority": "Приоритет", "status_id": "Статус", "executor_id": "Исполнитель",
    "applicant_id": "Заявитель", "content": "Текст комментария",
}


# ---------- Проверка входных данных ----------

def _label(field):
    return f"«{FIELD_LABELS.get(field, field)}»"


def _required(field):
    return ValidationError(f"Поле {_label(field)} обязательно", {field: "required"})


def _ensure_object(data):
    if not isinstance(data, dict):
        raise ValidationError("Тело запроса должно быть JSON-объектом")
    return data


def _reject_unknown(data, allowed):
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValidationError(f"Неизвестные поля: {', '.join(unknown)}",
                              {name: "unknown_field" for name in unknown})


def _parse_id(value, field, required=True):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise _required(field)
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= SQLITE_INT_MAX:
        return value
    if isinstance(value, str):
        text = value.strip()
        # длина проверяется до int(): число из тысяч цифр иначе вызывает ValueError
        if text.isascii() and text.isdigit() and len(text) <= 19 and 0 < int(text) <= SQLITE_INT_MAX:
            return int(text)
    raise ValidationError(f"Поле {_label(field)} должно быть положительным целым числом", {field: "integer"})


def _parse_text(value, field, min_len=0, max_len=None, required=True):
    if value is None:
        if required:
            raise _required(field)
        return None
    if not isinstance(value, str):
        raise ValidationError(f"Поле {_label(field)} должно быть строкой", {field: "string"})
    if CONTROL_CHARS.search(value):
        raise ValidationError(f"Поле {_label(field)} содержит недопустимые управляющие символы",
                              {field: "invalid_characters"})
    text = value.strip()
    if required and not text:
        raise _required(field)
    if len(text) < min_len:
        raise ValidationError(f"Поле {_label(field)}: минимум {min_len} символа, сейчас {len(text)}",
                              {field: f"min_length:{min_len}"})
    if max_len is not None and len(text) > max_len:
        raise ValidationError(f"Поле {_label(field)}: максимум {max_len} символов, сейчас {len(text)}",
                              {field: f"max_length:{max_len}"})
    return text


def _parse_priority(value):
    if value not in PRIORITIES:
        raise ValidationError(f"Приоритет должен быть одним из: {', '.join(PRIORITIES)}",
                              {"priority": "invalid_choice"})
    return value


def _get_category(value):
    category_id = _parse_id(value, "category_id")
    category = repo.get_category(category_id)
    if category is None:
        raise ValidationError(f"Категории с id={category_id} не существует", {"category_id": "not_found"})
    return category


def _get_active_user_with_role(value, field, role):
    user_id = _parse_id(value, field)
    user = repo.get_user(user_id)
    if user is None or user["role"] != role or not user["is_active"]:
        raise ValidationError(f"{FIELD_LABELS[field]}: нужен активный пользователь с ролью «{role}»",
                              {field: "invalid"})
    return user


# ---------- Права доступа ----------

def can_view(user, req):
    role = user["role"]
    if role in (ADMIN, OPERATOR):
        return True
    if role == EXECUTOR:
        return req["executor_id"] == user["id"]
    if role == APPLICANT:
        return req["applicant_id"] == user["id"]
    return False


def edit_denied_reason(user, req):
    """None, если пользователь может менять тему/описание/категорию/приоритет, иначе причина отказа."""
    role = user["role"]
    if role == ADMIN:
        return None
    if req["status"] == CLOSED:
        return "Закрытую заявку может изменять только администратор"
    if role == OPERATOR:
        return None
    if role == APPLICANT:
        if req["applicant_id"] == user["id"] and req["status"] == NEW:
            return None
        return "Заявитель может редактировать только свои заявки в статусе «Новая»"
    return "Исполнитель не может редактировать содержание заявки"


def assign_denied_reason(user, req):
    if user["role"] not in (ADMIN, OPERATOR):
        return "Назначать исполнителя могут только оператор и администратор"
    if req["status"] == CLOSED and user["role"] != ADMIN:
        return "Закрытую заявку может изменять только администратор"
    return None


def status_denied_reason(user, req, new_status):
    """Правила смены статуса из ТЗ (ФТ-6)."""
    role, current = user["role"], req["status"]
    if new_status == current or role == ADMIN:
        return None
    if current == CLOSED:
        return "Закрытую заявку может изменять только администратор"
    if role == APPLICANT:
        if current == DONE and new_status == CLOSED:
            return None
        return "Заявитель может только закрыть заявку после её выполнения"
    if new_status == CLOSED:
        return "Закрыть заявку может только заявитель (после выполнения) или администратор"
    return None  # оператор и назначенный исполнитель


def permissions(user, req):
    """Что пользователь может делать с заявкой. Используется интерфейсом, чтобы скрывать лишние кнопки."""
    allowed_statuses = [s for s in repo.list_statuses()
                        if s["name"] != req["status"] and status_denied_reason(user, req, s["name"]) is None]
    return {
        "can_edit": edit_denied_reason(user, req) is None,
        "can_assign": assign_denied_reason(user, req) is None,
        "allowed_statuses": allowed_statuses,
        "can_delete": user["role"] == ADMIN,
        "can_comment": True,
    }


def can_create(user):
    return user["role"] in (ADMIN, OPERATOR, APPLICANT)


# ---------- Заявки ----------

def list_requests(user, filters):
    search = filters.get("search")
    search = search.strip()[:SEARCH_MAX] if isinstance(search, str) else ""
    criteria = {
        "search": search or None,
        "status_id": _parse_id(filters.get("status_id"), "status_id", required=False),
        "category_id": _parse_id(filters.get("category_id"), "category_id", required=False),
        "executor_id": _parse_id(filters.get("executor_id"), "executor_id", required=False),
        "priority": _parse_priority(filters["priority"]) if filters.get("priority") else None,
    }
    if user["role"] == APPLICANT:
        criteria["applicant_id"] = user["id"]        # заявитель видит только свои заявки
    elif user["role"] == EXECUTOR:
        criteria["executor_id"] = user["id"]         # исполнитель видит только назначенные ему
    return repo.find_requests(**criteria)


def _find_request(request_id):
    """Заявка по номеру или None. Номер больше допустимого для базы — это просто несуществующая заявка."""
    if request_id > SQLITE_INT_MAX:
        return None
    return repo.get_request(request_id)


def get_request(user, request_id):
    req = _find_request(request_id)
    if req is None:
        raise NotFound(f"Заявка #{request_id} не найдена")
    if not can_view(user, req):
        raise Forbidden(f"Нет доступа к заявке #{request_id}")
    return req


def get_request_details(user, request_id):
    req = get_request(user, request_id)
    return {**req, "comments": repo.list_comments(request_id), "history": repo.list_history(request_id)}


def create_request(user, data):
    if not can_create(user):
        raise Forbidden("Исполнитель не может создавать заявки")
    data = _ensure_object(data)
    _reject_unknown(data, CREATE_FIELDS)

    title = _parse_text(data.get("title"), "title", TITLE_MIN, TITLE_MAX)
    description = _parse_text(data.get("description"), "description", 0, DESCRIPTION_MAX, required=False) or None
    category = _get_category(data.get("category_id"))
    priority = _parse_priority(data.get("priority") or DEFAULT_PRIORITY)

    if user["role"] == APPLICANT:
        requested = _parse_id(data.get("applicant_id"), "applicant_id", required=False)
        if requested not in (None, user["id"]):
            raise Forbidden("Заявитель может создавать заявки только от своего имени")
        applicant_id = user["id"]
    else:
        applicant_id = _get_active_user_with_role(data.get("applicant_id"), "applicant_id", APPLICANT)["id"]

    with transaction():
        new_id = repo.insert_request(title, description, category["id"], priority,
                                     repo.get_status_by_name(NEW)["id"], applicant_id)
        repo.insert_history(new_id, user["id"], "Создана", None, NEW)
    return repo.get_request(new_id)


def update_request(user, request_id, data):
    data = _ensure_object(data)
    _reject_unknown(data, UPDATE_FIELDS)
    if not data:
        raise ValidationError("Не передано ни одного поля для изменения")
    req = get_request(user, request_id)

    changes, history = {}, []

    # Содержание заявки
    if any(field in data for field in CONTENT_FIELDS):
        reason = edit_denied_reason(user, req)
        if reason:
            raise Forbidden(reason)
        if "title" in data:
            changes["title"] = _parse_text(data["title"], "title", TITLE_MIN, TITLE_MAX)
        if "description" in data:
            changes["description"] = _parse_text(data["description"], "description", 0, DESCRIPTION_MAX,
                                                 required=False) or None
        if "category_id" in data:
            changes["category_id"] = _get_category(data["category_id"])["id"]
        if "priority" in data:
            changes["priority"] = _parse_priority(data["priority"])
        changes = {k: v for k, v in changes.items() if v != req[k]}
        if changes:
            history.append(("Изменена", None, ", ".join(FIELD_LABELS[k] for k in CONTENT_FIELDS if k in changes)))

    # Исполнитель
    executor_id = req["executor_id"]
    if "executor_id" in data:
        reason = assign_denied_reason(user, req)
        if reason:
            raise Forbidden(reason)
        executor_name = "Не назначен"
        executor_id = None
        if data["executor_id"] not in (None, ""):
            executor = _get_active_user_with_role(data["executor_id"], "executor_id", EXECUTOR)
            executor_id, executor_name = executor["id"], executor["fio"]
        if executor_id != req["executor_id"]:
            changes["executor_id"] = executor_id
            history.append(("Исполнитель", req["executor"] or "Не назначен", executor_name))

    # Статус
    status_name = req["status"]
    if "status_id" in data:
        status_id = _parse_id(data["status_id"], "status_id")
        status = repo.get_status(status_id)
        if status is None:
            raise ValidationError(f"Статуса с id={status_id} не существует", {"status_id": "not_found"})
        reason = status_denied_reason(user, req, status["name"])
        if reason:
            raise Forbidden(reason)
        if status["id"] != req["status_id"]:
            changes["status_id"] = status["id"]
            history.append(("Статус", req["status"], status["name"]))
        status_name = status["name"]

    if status_name in STATUSES_NEED_EXECUTOR and executor_id is None:
        raise ValidationError(f"Заявку в статусе «{status_name}» нельзя оставить без исполнителя",
                              {"executor_id": "required"})

    if changes:
        with transaction():
            repo.update_request(req["id"], changes)
            for action, old_value, new_value in history:
                repo.insert_history(req["id"], user["id"], action, old_value, new_value)
    return repo.get_request(req["id"])


def delete_request(user, request_id):
    if _find_request(request_id) is None:
        raise NotFound(f"Заявка #{request_id} не найдена")
    if user["role"] != ADMIN:
        raise Forbidden("Удалять заявки может только администратор")
    with transaction():
        repo.delete_request(request_id)  # комментарии и история удаляются каскадно


# ---------- Комментарии ----------

def list_comments(user, request_id):
    get_request(user, request_id)
    return repo.list_comments(request_id)


def add_comment(user, request_id, data):
    data = _ensure_object(data)
    _reject_unknown(data, {"content"})
    req = get_request(user, request_id)
    content = _parse_text(data.get("content"), "content", 1, COMMENT_MAX)
    with transaction():
        comment_id = repo.insert_comment(req["id"], user["id"], content)
    return repo.get_comment(comment_id)


# ---------- Справочники ----------

def list_statuses():
    return repo.list_statuses()


def list_categories():
    return repo.list_categories()


def list_executors():
    return repo.list_users(role=EXECUTOR, active_only=True)


def list_applicants():
    return repo.list_users(role=APPLICANT, active_only=True)


def list_users(user):
    if user["role"] not in (ADMIN, OPERATOR):
        raise Forbidden("Список пользователей доступен только оператору и администратору")
    return repo.list_users()
