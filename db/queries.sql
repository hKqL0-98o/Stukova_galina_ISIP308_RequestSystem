-- ЛР5. Запросы к базе «Система учёта заявок».
-- Порядок выполнения на чистой базе: db/schema.sql -> db/seed.sql -> db/queries.sql
-- Итого: INSERT 6, SELECT 10 (WHERE 7, JOIN 7), UPDATE 3, DELETE 3.

PRAGMA foreign_keys = ON;

-- ==================== INSERT ====================

-- I1. Добавить новую категорию
INSERT INTO Categories (name, description)
VALUES ('Доступ к ресурсам', 'Права на общие папки, сайты и внутренние системы');

-- I2. Добавить нового исполнителя (пароль хранится только в виде хеша)
INSERT INTO Users (fio, login, password_hash, role)
VALUES ('Ольга Волкова', 'volkova',
        'pbkdf2:sha256:600000$jvgNK6WNv1SQpjJo$0c229f8e826b00379fb7e926d8ef6a91cd1f8bacb3ce78e307636f9fafe68ac4',
        'Исполнитель');

-- I3. Иван Иванов создаёт заявку в новой категории
INSERT INTO Requests (title, description, priority, category_id, status_id, applicant_id)
VALUES ('Нет доступа к общей папке', 'Папка «Бухгалтерия» пишет «Отказано в доступе»', 'Высокий',
        (SELECT id FROM Categories WHERE name = 'Доступ к ресурсам'),
        (SELECT id FROM Statuses   WHERE name = 'Новая'),
        (SELECT id FROM Users      WHERE login = 'ivanov'));

-- I4. Запись в историю о создании этой заявки
INSERT INTO RequestHistory (request_id, user_id, action, old_value, new_value)
VALUES ((SELECT id FROM Requests WHERE title = 'Нет доступа к общей папке'),
        (SELECT id FROM Users WHERE login = 'ivanov'),
        'Создана', NULL, 'Новая');

-- I5. Елена Соколова создаёт заявку
INSERT INTO Requests (title, description, priority, category_id, status_id, applicant_id)
VALUES ('Не печатает принтер на 3 этаже', 'Задания висят в очереди и не печатаются', 'Средний',
        (SELECT id FROM Categories WHERE name = 'Оборудование'),
        (SELECT id FROM Statuses   WHERE name = 'Новая'),
        (SELECT id FROM Users      WHERE login = 'sokolova'));

-- I6. Оператор оставляет комментарий к заявке Иванова
INSERT INTO Comments (request_id, author_id, content)
VALUES ((SELECT id FROM Requests WHERE title = 'Нет доступа к общей папке'),
        (SELECT id FROM Users WHERE login = 'operator'),
        'Уточните, пожалуйста, точный путь к папке');

-- ==================== SELECT ====================

-- S1. [JOIN] Все заявки с названиями статуса, категории, заявителя и исполнителя
SELECT r.id, r.title, s.name AS status, c.name AS category, r.priority,
       a.fio AS applicant, COALESCE(e.fio, 'Не назначен') AS executor
FROM Requests r
JOIN Statuses   s ON s.id = r.status_id
JOIN Categories c ON c.id = r.category_id
JOIN Users      a ON a.id = r.applicant_id
LEFT JOIN Users e ON e.id = r.executor_id
ORDER BY r.id;

-- S2. [WHERE + JOIN] Новые заявки, которым ещё не назначен исполнитель (очередь оператора)
SELECT r.id, r.title, r.priority, a.fio AS applicant
FROM Requests r
JOIN Statuses s ON s.id = r.status_id
JOIN Users    a ON a.id = r.applicant_id
WHERE s.name = 'Новая' AND r.executor_id IS NULL
ORDER BY CASE r.priority WHEN 'Высокий' THEN 1 WHEN 'Средний' THEN 2 ELSE 3 END, r.id;

-- S3. [WHERE] Незакрытые заявки с высоким приоритетом
SELECT id, title, status_id
FROM Requests
WHERE priority = 'Высокий'
  AND status_id <> (SELECT id FROM Statuses WHERE name = 'Закрыта');

-- S4. [WHERE] Поиск заявок по слову «интернет» в теме или описании
SELECT id, title, description
FROM Requests
WHERE title LIKE '%интернет%' OR description LIKE '%интернет%';

-- S5. [JOIN + GROUP BY] Количество заявок в каждом статусе (включая пустые)
SELECT s.name AS status, COUNT(r.id) AS requests_count
FROM Statuses s
LEFT JOIN Requests r ON r.status_id = s.id
GROUP BY s.id, s.name
ORDER BY s.id;

-- S6. [WHERE + JOIN + GROUP BY] Нагрузка исполнителей: сколько незакрытых заявок у каждого
SELECT u.fio AS executor, COUNT(r.id) AS active_requests
FROM Users u
LEFT JOIN Requests r
       ON r.executor_id = u.id
      AND r.status_id IN (SELECT id FROM Statuses WHERE name IN ('В работе', 'Выполнена'))
WHERE u.role = 'Исполнитель'
GROUP BY u.id, u.fio
ORDER BY active_requests DESC, u.fio;

-- S7. [WHERE + JOIN] История изменений заявки #4 с авторами действий
SELECT h.created_at, h.action, h.old_value, h.new_value, u.fio AS who, u.role
FROM RequestHistory h
JOIN Users u ON u.id = h.user_id
WHERE h.request_id = 4
ORDER BY h.id;

-- S8. [JOIN] Все комментарии с темой заявки и автором
SELECT cm.id, r.id AS request_id, r.title, u.fio AS author, cm.content
FROM Comments cm
JOIN Requests r ON r.id = cm.request_id
JOIN Users    u ON u.id = cm.author_id
ORDER BY cm.id;

-- ==================== UPDATE ====================

-- U1. Оператор назначает Ольгу Волкову на заявку про общую папку и переводит её в работу
UPDATE Requests
SET executor_id = (SELECT id FROM Users WHERE login = 'volkova'),
    status_id   = (SELECT id FROM Statuses WHERE name = 'В работе'),
    updated_at  = CURRENT_TIMESTAMP
WHERE title = 'Нет доступа к общей папке';

-- U2. Заявитель подтвердил решение: все выполненные заявки Ивана Иванова закрываются
UPDATE Requests
SET status_id  = (SELECT id FROM Statuses WHERE name = 'Закрыта'),
    updated_at = CURRENT_TIMESTAMP
WHERE applicant_id = (SELECT id FROM Users WHERE login = 'ivanov')
  AND status_id    = (SELECT id FROM Statuses WHERE name = 'Выполнена');

-- U3. Уточнить описание категории
UPDATE Categories
SET description = 'Сеть, Wi-Fi, учётные записи и пароли'
WHERE name = 'Техническая поддержка';

-- S9. [WHERE + JOIN] Проверка UPDATE: заявки Волковой и закрытые заявки Иванова
SELECT r.id, r.title, s.name AS status, e.fio AS executor
FROM Requests r
JOIN Statuses s ON s.id = r.status_id
LEFT JOIN Users e ON e.id = r.executor_id
WHERE r.executor_id = (SELECT id FROM Users WHERE login = 'volkova')
   OR (r.applicant_id = (SELECT id FROM Users WHERE login = 'ivanov') AND s.name = 'Закрыта')
ORDER BY r.id;

-- ==================== DELETE ====================

-- D1. Удалить комментарий оператора (вопрос снят)
DELETE FROM Comments
WHERE content = 'Уточните, пожалуйста, точный путь к папке';

-- D2. Удалить заявку «Замена картриджа». Её история удаляется каскадно (ON DELETE CASCADE)
DELETE FROM Requests
WHERE title = 'Замена картриджа';

-- D3. Удалить категорию, только если в ней нет заявок. Здесь удалится 0 строк: категория используется
DELETE FROM Categories
WHERE name = 'Доступ к ресурсам'
  AND NOT EXISTS (SELECT 1 FROM Requests WHERE Requests.category_id = Categories.id);

-- S10. [WHERE] Проверка DELETE: от удалённой заявки не осталось ни истории, ни комментариев
SELECT
    (SELECT COUNT(*) FROM Requests       WHERE title = 'Замена картриджа') AS request_left,
    (SELECT COUNT(*) FROM RequestHistory WHERE request_id = 5)            AS history_left,
    (SELECT COUNT(*) FROM Comments       WHERE request_id = 5)            AS comments_left,
    (SELECT COUNT(*) FROM Categories     WHERE name = 'Доступ к ресурсам') AS category_kept;
