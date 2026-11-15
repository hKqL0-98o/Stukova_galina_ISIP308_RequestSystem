# ЛР5. Результаты выполнения запросов

База создана с нуля: `schema.sql` → `seed.sql` → `queries.sql`, SQLite 3.50.4.

## I1. Добавить новую категорию

```sql
INSERT INTO Categories (name, description)
VALUES ('Доступ к ресурсам', 'Права на общие папки, сайты и внутренние системы');
```

Результат: затронуто строк — **1**

## I2. Добавить нового исполнителя (пароль хранится только в виде хеша)

```sql
INSERT INTO Users (fio, login, password_hash, role)
VALUES ('Ольга Волкова', 'volkova',
        'pbkdf2:sha256:600000$jvgNK6WNv1SQpjJo$0c229f8e826b00379fb7e926d8ef6a91cd1f8bacb3ce78e307636f9fafe68ac4',
        'Исполнитель');
```

Результат: затронуто строк — **1**

## I3. Иван Иванов создаёт заявку в новой категории

```sql
INSERT INTO Requests (title, description, priority, category_id, status_id, applicant_id)
VALUES ('Нет доступа к общей папке', 'Папка «Бухгалтерия» пишет «Отказано в доступе»', 'Высокий',
        (SELECT id FROM Categories WHERE name = 'Доступ к ресурсам'),
        (SELECT id FROM Statuses   WHERE name = 'Новая'),
        (SELECT id FROM Users      WHERE login = 'ivanov'));
```

Результат: затронуто строк — **1**

## I4. Запись в историю о создании этой заявки

```sql
INSERT INTO RequestHistory (request_id, user_id, action, old_value, new_value)
VALUES ((SELECT id FROM Requests WHERE title = 'Нет доступа к общей папке'),
        (SELECT id FROM Users WHERE login = 'ivanov'),
        'Создана', NULL, 'Новая');
```

Результат: затронуто строк — **1**

## I5. Елена Соколова создаёт заявку

```sql
INSERT INTO Requests (title, description, priority, category_id, status_id, applicant_id)
VALUES ('Не печатает принтер на 3 этаже', 'Задания висят в очереди и не печатаются', 'Средний',
        (SELECT id FROM Categories WHERE name = 'Оборудование'),
        (SELECT id FROM Statuses   WHERE name = 'Новая'),
        (SELECT id FROM Users      WHERE login = 'sokolova'));
```

Результат: затронуто строк — **1**

## I6. Оператор оставляет комментарий к заявке Иванова

```sql
INSERT INTO Comments (request_id, author_id, content)
VALUES ((SELECT id FROM Requests WHERE title = 'Нет доступа к общей папке'),
        (SELECT id FROM Users WHERE login = 'operator'),
        'Уточните, пожалуйста, точный путь к папке');
```

Результат: затронуто строк — **1**

## S1. [JOIN] Все заявки с названиями статуса, категории, заявителя и исполнителя

```sql
SELECT r.id, r.title, s.name AS status, c.name AS category, r.priority,
       a.fio AS applicant, COALESCE(e.fio, 'Не назначен') AS executor
FROM Requests r
JOIN Statuses   s ON s.id = r.status_id
JOIN Categories c ON c.id = r.category_id
JOIN Users      a ON a.id = r.applicant_id
LEFT JOIN Users e ON e.id = r.executor_id
ORDER BY r.id;
```

Результат: 12 строк(и)

| id | title | status | category | priority | applicant | executor |
|---|---|---|---|---|---|---|
| 1 | Не работает мышь | Новая | Оборудование | Низкий | Иван Иванов | Не назначен |
| 2 | Установить PyCharm | В работе | Программное обеспечение | Средний | Иван Иванов | Петр Техников |
| 3 | Нет интернета | Выполнена | Техническая поддержка | Высокий | Елена Соколова | Петр Техников |
| 4 | Не открывается корпоративная почта | Закрыта | Прочие вопросы | Средний | Иван Иванов | Алексей Морозов |
| 5 | Замена картриджа | Новая | Оборудование | Низкий | Елена Соколова | Не назначен |
| 6 | Не включается монитор | Новая | Оборудование | Высокий | Иван Иванов | Не назначен |
| 7 | Обновить Windows | В работе | Программное обеспечение | Средний | Елена Соколова | Алексей Морозов |
| 8 | Медленный интернет | Новая | Техническая поддержка | Средний | Елена Соколова | Не назначен |
| 9 | Не работает антивирус | Выполнена | Программное обеспечение | Высокий | Иван Иванов | Алексей Морозов |
| 10 | Залипает клавиатура | В работе | Оборудование | Низкий | Елена Соколова | Петр Техников |
| 11 | Нет доступа к общей папке | Новая | Доступ к ресурсам | Высокий | Иван Иванов | Не назначен |
| 12 | Не печатает принтер на 3 этаже | Новая | Оборудование | Средний | Елена Соколова | Не назначен |

## S2. [WHERE + JOIN] Новые заявки, которым ещё не назначен исполнитель (очередь оператора)

```sql
SELECT r.id, r.title, r.priority, a.fio AS applicant
FROM Requests r
JOIN Statuses s ON s.id = r.status_id
JOIN Users    a ON a.id = r.applicant_id
WHERE s.name = 'Новая' AND r.executor_id IS NULL
ORDER BY CASE r.priority WHEN 'Высокий' THEN 1 WHEN 'Средний' THEN 2 ELSE 3 END, r.id;
```

Результат: 6 строк(и)

| id | title | priority | applicant |
|---|---|---|---|
| 6 | Не включается монитор | Высокий | Иван Иванов |
| 11 | Нет доступа к общей папке | Высокий | Иван Иванов |
| 8 | Медленный интернет | Средний | Елена Соколова |
| 12 | Не печатает принтер на 3 этаже | Средний | Елена Соколова |
| 1 | Не работает мышь | Низкий | Иван Иванов |
| 5 | Замена картриджа | Низкий | Елена Соколова |

## S3. [WHERE] Незакрытые заявки с высоким приоритетом

```sql
SELECT id, title, status_id
FROM Requests
WHERE priority = 'Высокий'
  AND status_id <> (SELECT id FROM Statuses WHERE name = 'Закрыта');
```

Результат: 4 строк(и)

| id | title | status_id |
|---|---|---|
| 3 | Нет интернета | 3 |
| 6 | Не включается монитор | 1 |
| 9 | Не работает антивирус | 3 |
| 11 | Нет доступа к общей папке | 1 |

## S4. [WHERE] Поиск заявок по слову «интернет» в теме или описании

```sql
SELECT id, title, description
FROM Requests
WHERE title LIKE '%интернет%' OR description LIKE '%интернет%';
```

Результат: 2 строк(и)

| id | title | description |
|---|---|---|
| 3 | Нет интернета | Отвалился Wi-Fi |
| 8 | Медленный интернет | Страницы загружаются по пять минут |

## S5. [JOIN + GROUP BY] Количество заявок в каждом статусе (включая пустые)

```sql
SELECT s.name AS status, COUNT(r.id) AS requests_count
FROM Statuses s
LEFT JOIN Requests r ON r.status_id = s.id
GROUP BY s.id, s.name
ORDER BY s.id;
```

Результат: 4 строк(и)

| status | requests_count |
|---|---|
| Новая | 6 |
| В работе | 3 |
| Выполнена | 2 |
| Закрыта | 1 |

## S6. [WHERE + JOIN + GROUP BY] Нагрузка исполнителей: сколько незакрытых заявок у каждого

```sql
SELECT u.fio AS executor, COUNT(r.id) AS active_requests
FROM Users u
LEFT JOIN Requests r
       ON r.executor_id = u.id
      AND r.status_id IN (SELECT id FROM Statuses WHERE name IN ('В работе', 'Выполнена'))
WHERE u.role = 'Исполнитель'
GROUP BY u.id, u.fio
ORDER BY active_requests DESC, u.fio;
```

Результат: 3 строк(и)

| executor | active_requests |
|---|---|
| Петр Техников | 3 |
| Алексей Морозов | 2 |
| Ольга Волкова | 0 |

## S7. [WHERE + JOIN] История изменений заявки #4 с авторами действий

```sql
SELECT h.created_at, h.action, h.old_value, h.new_value, u.fio AS who, u.role
FROM RequestHistory h
JOIN Users u ON u.id = h.user_id
WHERE h.request_id = 4
ORDER BY h.id;
```

Результат: 5 строк(и)

| created_at | action | old_value | new_value | who | role |
|---|---|---|---|---|---|
| 2026-11-09 16:32:44 | Создана | NULL | Новая | Иван Иванов | Заявитель |
| 2026-11-09 16:32:44 | Исполнитель | Не назначен | Алексей Морозов | Мария Кузнецова | Оператор |
| 2026-11-09 16:32:44 | Статус | Новая | В работе | Алексей Морозов | Исполнитель |
| 2026-11-09 16:32:44 | Статус | В работе | Выполнена | Алексей Морозов | Исполнитель |
| 2026-11-09 16:32:44 | Статус | Выполнена | Закрыта | Иван Иванов | Заявитель |

## S8. [JOIN] Все комментарии с темой заявки и автором

```sql
SELECT cm.id, r.id AS request_id, r.title, u.fio AS author, cm.content
FROM Comments cm
JOIN Requests r ON r.id = cm.request_id
JOIN Users    u ON u.id = cm.author_id
ORDER BY cm.id;
```

Результат: 4 строк(и)

| id | request_id | title | author | content |
|---|---|---|---|---|
| 1 | 2 | Установить PyCharm | Петр Техников | Взял в работу, скоро поставлю |
| 2 | 3 | Нет интернета | Елена Соколова | Уже починилось само |
| 3 | 4 | Не открывается корпоративная почта | Мария Кузнецова | Зайдите в отдел кадров |
| 4 | 11 | Нет доступа к общей папке | Мария Кузнецова | Уточните, пожалуйста, точный путь к папке |

## U1. Оператор назначает Ольгу Волкову на заявку про общую папку и переводит её в работу

```sql
UPDATE Requests
SET executor_id = (SELECT id FROM Users WHERE login = 'volkova'),
    status_id   = (SELECT id FROM Statuses WHERE name = 'В работе'),
    updated_at  = CURRENT_TIMESTAMP
WHERE title = 'Нет доступа к общей папке';
```

Результат: затронуто строк — **1**

## U2. Заявитель подтвердил решение: все выполненные заявки Ивана Иванова закрываются

```sql
UPDATE Requests
SET status_id  = (SELECT id FROM Statuses WHERE name = 'Закрыта'),
    updated_at = CURRENT_TIMESTAMP
WHERE applicant_id = (SELECT id FROM Users WHERE login = 'ivanov')
  AND status_id    = (SELECT id FROM Statuses WHERE name = 'Выполнена');
```

Результат: затронуто строк — **1**

## U3. Уточнить описание категории

```sql
UPDATE Categories
SET description = 'Сеть, Wi-Fi, учётные записи и пароли'
WHERE name = 'Техническая поддержка';
```

Результат: затронуто строк — **1**

## S9. [WHERE + JOIN] Проверка UPDATE: заявки Волковой и закрытые заявки Иванова

```sql
SELECT r.id, r.title, s.name AS status, e.fio AS executor
FROM Requests r
JOIN Statuses s ON s.id = r.status_id
LEFT JOIN Users e ON e.id = r.executor_id
WHERE r.executor_id = (SELECT id FROM Users WHERE login = 'volkova')
   OR (r.applicant_id = (SELECT id FROM Users WHERE login = 'ivanov') AND s.name = 'Закрыта')
ORDER BY r.id;
```

Результат: 3 строк(и)

| id | title | status | executor |
|---|---|---|---|
| 4 | Не открывается корпоративная почта | Закрыта | Алексей Морозов |
| 9 | Не работает антивирус | Закрыта | Алексей Морозов |
| 11 | Нет доступа к общей папке | В работе | Ольга Волкова |

## D1. Удалить комментарий оператора (вопрос снят)

```sql
DELETE FROM Comments
WHERE content = 'Уточните, пожалуйста, точный путь к папке';
```

Результат: затронуто строк — **1**

## D2. Удалить заявку «Замена картриджа». Её история удаляется каскадно (ON DELETE CASCADE)

```sql
DELETE FROM Requests
WHERE title = 'Замена картриджа';
```

Результат: затронуто строк — **1**

## D3. Удалить категорию, только если в ней нет заявок. Здесь удалится 0 строк: категория используется

```sql
DELETE FROM Categories
WHERE name = 'Доступ к ресурсам'
  AND NOT EXISTS (SELECT 1 FROM Requests WHERE Requests.category_id = Categories.id);
```

Результат: затронуто строк — **0**

## S10. [WHERE] Проверка DELETE: от удалённой заявки не осталось ни истории, ни комментариев

```sql
SELECT
    (SELECT COUNT(*) FROM Requests       WHERE title = 'Замена картриджа') AS request_left,
    (SELECT COUNT(*) FROM RequestHistory WHERE request_id = 5)            AS history_left,
    (SELECT COUNT(*) FROM Comments       WHERE request_id = 5)            AS comments_left,
    (SELECT COUNT(*) FROM Categories     WHERE name = 'Доступ к ресурсам') AS category_kept;
```

Результат: 1 строк(и)

| request_left | history_left | comments_left | category_kept |
|---|---|---|---|
| 0 | 0 | 0 | 1 |

## Итого

| Тип | Требуется | Выполнено |
|---|---|---|
| INSERT | 5 | 6 |
| SELECT | 5 | 10 |
| UPDATE | 2 | 3 |
| DELETE | 2 | 3 |
| SELECT с WHERE | 3 | 7 (S2, S3, S4, S6, S7, S9, S10) |
| Запросы с JOIN | 2 | 7 (S1, S2, S5, S6, S7, S8, S9) |

## Самопроверка

### Ограничения целостности

Каждая попытка ниже должна быть отклонена базой.

| Попытка | Результат |
|---|---|
| Заявка с несуществующей категорией (id=99) | отклонено: `FOREIGN KEY constraint failed` |
| Заявка с несуществующим заявителем (id=555) | отклонено: `FOREIGN KEY constraint failed` |
| Удаление категории, в которой есть заявки | отклонено: `FOREIGN KEY constraint failed` |
| Удаление пользователя, у которого есть заявки | отклонено: `FOREIGN KEY constraint failed` |
| Тема короче 3 символов | отклонено: `CHECK constraint failed: length(title) BETWEEN 3 AND 100` |
| Недопустимый приоритет | отклонено: `CHECK constraint failed: priority IN ('Низкий', 'Средний', 'Высокий')` |
| Недопустимая роль | отклонено: `CHECK constraint failed: role IN ('Администратор', 'Оператор', 'Исполнитель', 'Заявитель')` |
| Повторяющийся логин | отклонено: `UNIQUE constraint failed: Users.login` |
| Повторяющийся статус | отклонено: `UNIQUE constraint failed: Statuses.name` |
| Пустой комментарий | отклонено: `CHECK constraint failed: length(trim(content)) BETWEEN 1 AND 1000` |

- `PRAGMA foreign_key_check`: нарушений нет
- `PRAGMA integrity_check`: ok

### Повторный запуск скриптов

`schema.sql` и `seed.sql` выполнены повторно поверх уже заполненной базы. Ошибок нет, база вернулась к исходному состоянию:

| Таблица | Строк |
|---|---|
| Users | 6 |
| Statuses | 4 |
| Categories | 4 |
| Requests | 10 |
| Comments | 3 |
| RequestHistory | 26 |
