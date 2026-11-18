"""Слой доступа к данным (repository): только SQL, без бизнес-правил."""
from .db import get_db

_REQUEST_SELECT = """
    SELECT r.id, r.title, r.description, r.priority,
           r.status_id,    s.name AS status,
           r.category_id,  c.name AS category,
           r.applicant_id, a.fio  AS applicant,
           r.executor_id,  e.fio  AS executor,
           datetime(r.created_at, 'localtime') AS created_at,
           datetime(r.updated_at, 'localtime') AS updated_at
    FROM Requests r
    JOIN Statuses   s ON s.id = r.status_id
    JOIN Categories c ON c.id = r.category_id
    JOIN Users      a ON a.id = r.applicant_id
    LEFT JOIN Users e ON e.id = r.executor_id
"""

_USER_COLUMNS = "id, fio, login, role, is_active, created_at"

_UPDATABLE_REQUEST_COLUMNS = {"title", "description", "category_id", "priority", "status_id", "executor_id"}


def _all(sql, params=()):
    return [dict(row) for row in get_db().execute(sql, params).fetchall()]


def _one(sql, params=()):
    row = get_db().execute(sql, params).fetchone()
    return dict(row) if row else None


def _escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------- Заявки ----------

def _request_conditions(search, status_id, category_id, priority, executor_id, applicant_id):
    """Общая часть WHERE для списка и для подсчёта: итог и страница не могут разойтись."""
    sql = " WHERE 1 = 1"
    params = []
    if search:
        pattern = f"%{_escape_like(search.lower())}%"
        conditions = ["PYLOWER(r.title) LIKE ? ESCAPE '\\'", "PYLOWER(r.description) LIKE ? ESCAPE '\\'"]
        params += [pattern, pattern]
        number = search.lstrip("#")
        # более 18 цифр — это уже не номер заявки, а подставление такого числа в SQL вызывает OverflowError
        if number.isascii() and number.isdigit() and len(number) <= 18:
            conditions.append("r.id = ?")
            params.append(int(number))
        sql += " AND (" + " OR ".join(conditions) + ")"
    for column, value in (("r.status_id", status_id), ("r.category_id", category_id),
                          ("r.priority", priority), ("r.executor_id", executor_id),
                          ("r.applicant_id", applicant_id)):
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(value)
    return sql, params


def find_requests(search=None, status_id=None, category_id=None, priority=None,
                  executor_id=None, applicant_id=None, limit=None, offset=0):
    where, params = _request_conditions(search, status_id, category_id, priority, executor_id, applicant_id)
    sql = _REQUEST_SELECT + where + " ORDER BY r.id DESC"      # порядок фиксирован: новые сверху
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return _all(sql, params)


def count_requests(search=None, status_id=None, category_id=None, priority=None,
                   executor_id=None, applicant_id=None):
    where, params = _request_conditions(search, status_id, category_id, priority, executor_id, applicant_id)
    return get_db().execute("SELECT COUNT(*) FROM Requests r" + where, params).fetchone()[0]


def get_request(request_id):
    return _one(_REQUEST_SELECT + " WHERE r.id = ?", (request_id,))


def insert_request(title, description, category_id, priority, status_id, applicant_id):
    cur = get_db().execute(
        """INSERT INTO Requests (title, description, category_id, priority, status_id, applicant_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, category_id, priority, status_id, applicant_id),
    )
    return cur.lastrowid


def update_request(request_id, fields):
    unknown = set(fields) - _UPDATABLE_REQUEST_COLUMNS
    if unknown:
        raise ValueError(f"Нельзя обновлять столбцы: {unknown}")
    assignments = ", ".join(f"{column} = ?" for column in fields)
    get_db().execute(
        f"UPDATE Requests SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (*fields.values(), request_id),
    )


def delete_request(request_id):
    return get_db().execute("DELETE FROM Requests WHERE id = ?", (request_id,)).rowcount


# ---------- Справочники ----------

def list_statuses():
    return _all("SELECT id, name FROM Statuses ORDER BY id")


def get_status(status_id):
    return _one("SELECT id, name FROM Statuses WHERE id = ?", (status_id,))


def get_status_by_name(name):
    return _one("SELECT id, name FROM Statuses WHERE name = ?", (name,))


def list_categories():
    return _all("SELECT id, name, description FROM Categories ORDER BY id")


def get_category(category_id):
    return _one("SELECT id, name, description FROM Categories WHERE id = ?", (category_id,))


# ---------- Пользователи ----------

def list_users(role=None, active_only=False):
    sql = f"SELECT {_USER_COLUMNS} FROM Users WHERE 1 = 1"
    params = []
    if role:
        sql += " AND role = ?"
        params.append(role)
    if active_only:
        sql += " AND is_active = 1"
    return _all(sql + " ORDER BY id", params)


def get_user(user_id):
    return _one(f"SELECT {_USER_COLUMNS} FROM Users WHERE id = ?", (user_id,))


def get_user_with_password(login):
    return _one(f"SELECT {_USER_COLUMNS}, password_hash FROM Users WHERE login = ?", (login,))


# ---------- Комментарии ----------

_COMMENT_SELECT = """
    SELECT cm.id, cm.request_id, cm.author_id, u.fio AS author, u.role AS author_role,
           cm.content, datetime(cm.created_at, 'localtime') AS created_at
    FROM Comments cm JOIN Users u ON u.id = cm.author_id
"""


def list_comments(request_id):
    return _all(_COMMENT_SELECT + " WHERE cm.request_id = ? ORDER BY cm.id", (request_id,))


def get_comment(comment_id):
    return _one(_COMMENT_SELECT + " WHERE cm.id = ?", (comment_id,))


def insert_comment(request_id, author_id, content):
    cur = get_db().execute(
        "INSERT INTO Comments (request_id, author_id, content) VALUES (?, ?, ?)",
        (request_id, author_id, content),
    )
    return cur.lastrowid


# ---------- История ----------

def list_history(request_id):
    return _all(
        """SELECT h.id, h.action, h.old_value, h.new_value, datetime(h.created_at, 'localtime') AS created_at,
                  h.user_id, u.fio AS user, u.role AS user_role
           FROM RequestHistory h JOIN Users u ON u.id = h.user_id
           WHERE h.request_id = ? ORDER BY h.id""",
        (request_id,),
    )


def insert_history(request_id, user_id, action, old_value, new_value):
    get_db().execute(
        """INSERT INTO RequestHistory (request_id, user_id, action, old_value, new_value)
           VALUES (?, ?, ?, ?, ?)""",
        (request_id, user_id, action, old_value, new_value),
    )


def ping():
    return get_db().execute("SELECT 1").fetchone()[0] == 1
