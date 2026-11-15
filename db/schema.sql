-- Схема БД «Система учёта заявок» (версия 2).
-- Скрипт можно выполнять повторно: он удаляет и создаёт таблицы заново.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS RequestHistory;
DROP TABLE IF EXISTS Comments;
DROP TABLE IF EXISTS Requests;
DROP TABLE IF EXISTS Users;
DROP TABLE IF EXISTS Statuses;
DROP TABLE IF EXISTS Categories;

PRAGMA foreign_keys = ON;

-- Пользователи. Пароль хранится только в виде хеша (PBKDF2-SHA256).
CREATE TABLE Users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fio           TEXT    NOT NULL CHECK (length(trim(fio)) > 0),
    login         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('Администратор', 'Оператор', 'Исполнитель', 'Заявитель')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Справочник статусов.
CREATE TABLE Statuses (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Справочник категорий.
CREATE TABLE Categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

-- Заявки.
CREATE TABLE Requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL CHECK (length(title) BETWEEN 3 AND 100),
    description  TEXT    CHECK (description IS NULL OR length(description) <= 2000),
    priority     TEXT    NOT NULL DEFAULT 'Средний' CHECK (priority IN ('Низкий', 'Средний', 'Высокий')),
    category_id  INTEGER NOT NULL,
    status_id    INTEGER NOT NULL,
    applicant_id INTEGER NOT NULL,
    executor_id  INTEGER,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id)  REFERENCES Categories(id),
    FOREIGN KEY (status_id)    REFERENCES Statuses(id),
    FOREIGN KEY (applicant_id) REFERENCES Users(id),
    FOREIGN KEY (executor_id)  REFERENCES Users(id)
);

-- Комментарии. При удалении заявки удаляются вместе с ней.
CREATE TABLE Comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    author_id  INTEGER NOT NULL,
    content    TEXT    NOT NULL CHECK (length(trim(content)) BETWEEN 1 AND 1000),
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES Requests(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id)  REFERENCES Users(id)
);

-- История изменений заявки (создание, статус, исполнитель, правки).
CREATE TABLE RequestHistory (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    action     TEXT    NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES Requests(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES Users(id)
);

CREATE INDEX idx_requests_status    ON Requests(status_id);
CREATE INDEX idx_requests_category  ON Requests(category_id);
CREATE INDEX idx_requests_executor  ON Requests(executor_id);
CREATE INDEX idx_requests_applicant ON Requests(applicant_id);
CREATE INDEX idx_comments_request   ON Comments(request_id);
CREATE INDEX idx_history_request    ON RequestHistory(request_id);

-- Версия схемы: приложение по ней понимает, что базу нужно пересоздать.
PRAGMA user_version = 2;
