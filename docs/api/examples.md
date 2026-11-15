# Примеры запросов к REST API HelpDesk

Получены реальным прогоном `15.11.2026` на временной базе из `db/seed.sql` (скрипт `docs/api/gen_examples.py`). Тестовый пароль учётных записей во временной базе подставляется переменной `PASS`; рабочая база и настоящие пароли не использовались.

Всего запросов: **20**, успешных: 12, с ожидаемой ошибкой: 8.

## 1. Текущий пользователь

GET /api/me  (пользователь `admin`)

Ответ: **HTTP 200**

```json
{
  "id": 1,
  "fio": "Анна Смирнова",
  "login": "admin",
  "role": "Администратор",
  "is_active": 1,
  "created_at": "2026-11-15 09:09:14"
}
```

## 2. Справочник статусов

GET /api/statuses  (пользователь `operator`)

Ответ: **HTTP 200**

```json
[
  {
    "id": 1,
    "name": "Новая"
  },
  {
    "id": 2,
    "name": "В работе"
  },
  {
    "id": 3,
    "name": "Выполнена"
  },
  {
    "id": 4,
    "name": "Закрыта"
  }
]
```

## 3. Справочник категорий

GET /api/categories  (пользователь `operator`)

Ответ: **HTTP 200**

```json
[
  {
    "id": 1,
    "name": "Техническая поддержка",
    "description": "Сеть, доступы, учётные записи"
  },
  {
    "id": 2,
    "name": "Программное обеспечение",
    "description": "Установка, обновление и ошибки программ"
  },
  {
    "id": 3,
    "name": "Оборудование",
    "description": "Неисправности компьютеров и периферии"
  },
  {
    "id": 4,
    "name": "Прочие вопросы",
    "description": "Всё, что не подходит под другие категории"
  }
]
```

## 4. Список пользователей (оператор)

GET /api/users  (пользователь `operator`)

Ответ: **HTTP 200** (показаны первые 2 из 6 элементов)

```json
[
  {
    "id": 1,
    "fio": "Анна Смирнова",
    "login": "admin",
    "role": "Администратор",
    "is_active": 1,
    "created_at": "2026-11-15 09:09:14"
  },
  {
    "id": 2,
    "fio": "Мария Кузнецова",
    "login": "operator",
    "role": "Оператор",
    "is_active": 1,
    "created_at": "2026-11-15 09:09:14"
  }
]
```

## 5. Список заявок

GET /api/requests  (пользователь `operator`)

Ответ: **HTTP 200** (показаны первые 2 из 10 элементов)

```json
[
  {
    "id": 10,
    "title": "Залипает клавиатура",
    "description": "Пролили сладкий чай на пробел",
    "priority": "Низкий",
    "status_id": 2,
    "status": "В работе",
    "category_id": 3,
    "category": "Оборудование",
    "applicant_id": 6,
    "applicant": "Елена Соколова",
    "executor_id": 3,
    "executor": "Петр Техников",
    "created_at": "2026-11-15 14:09:14",
    "updated_at": "2026-11-15 14:09:14"
  },
  {
    "id": 9,
    "title": "Не работает антивирус",
    "description": "Программа не запускается после обновления",
    "priority": "Высокий",
    "status_id": 3,
    "status": "Выполнена",
    "category_id": 2,
    "category": "Программное обеспечение",
    "applicant_id": 5,
    "applicant": "Иван Иванов",
    "executor_id": 4,
    "executor": "Алексей Морозов",
    "created_at": "2026-11-15 14:09:14",
    "updated_at": "2026-11-15 14:09:14"
  }
]
```

## 6. Поиск и фильтр по статусу

GET /api/requests?search=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80&status_id=1  (пользователь `operator`)

Ответ: **HTTP 200**

```json
[
  {
    "id": 5,
    "title": "Замена картриджа",
    "description": "Принтер полосит",
    "priority": "Низкий",
    "status_id": 1,
    "status": "Новая",
    "category_id": 3,
    "category": "Оборудование",
    "applicant_id": 6,
    "applicant": "Елена Соколова",
    "executor_id": null,
    "executor": null,
    "created_at": "2026-11-15 14:09:14",
    "updated_at": "2026-11-15 14:09:14"
  }
]
```

## 7. Одна заявка с комментариями и историей

GET /api/requests/1  (пользователь `operator`)

Ответ: **HTTP 200**

```json
{
  "id": 1,
  "title": "Не работает мышь",
  "description": "Сломалась левая кнопка",
  "priority": "Низкий",
  "status_id": 1,
  "status": "Новая",
  "category_id": 3,
  "category": "Оборудование",
  "applicant_id": 5,
  "applicant": "Иван Иванов",
  "executor_id": null,
  "executor": null,
  "created_at": "2026-11-15 14:09:14",
  "updated_at": "2026-11-15 14:09:14",
  "comments": [],
  "history": [
    {
      "id": 1,
      "action": "Создана",
      "old_value": null,
      "new_value": "Новая",
      "created_at": "2026-11-15 14:09:14",
      "user_id": 5,
      "user": "Иван Иванов",
      "user_role": "Заявитель"
    }
  ]
}
```

## 8. Создание заявки

POST /api/requests  (пользователь `operator`)

Тело запроса:

```json
{
  "title": "Не работает сканер в приёмной",
  "description": "Сканер не определяется компьютером после обновления.",
  "category_id": 3,
  "priority": "Высокий",
  "applicant_id": 5
}
```

Ответ: **HTTP 201**

```json
{
  "id": 11,
  "title": "Не работает сканер в приёмной",
  "description": "Сканер не определяется компьютером после обновления.",
  "priority": "Высокий",
  "status_id": 1,
  "status": "Новая",
  "category_id": 3,
  "category": "Оборудование",
  "applicant_id": 5,
  "applicant": "Иван Иванов",
  "executor_id": null,
  "executor": null,
  "created_at": "2026-11-15 14:09:15",
  "updated_at": "2026-11-15 14:09:15"
}
```

## 9. Назначение исполнителя

PATCH /api/requests/11  (пользователь `operator`)

Тело запроса:

```json
{
  "executor_id": 3
}
```

Ответ: **HTTP 200**

```json
{
  "id": 11,
  "title": "Не работает сканер в приёмной",
  "description": "Сканер не определяется компьютером после обновления.",
  "priority": "Высокий",
  "status_id": 1,
  "status": "Новая",
  "category_id": 3,
  "category": "Оборудование",
  "applicant_id": 5,
  "applicant": "Иван Иванов",
  "executor_id": 3,
  "executor": "Петр Техников",
  "created_at": "2026-11-15 14:09:15",
  "updated_at": "2026-11-15 14:09:15"
}
```

## 10. Смена статуса исполнителем

PATCH /api/requests/11  (пользователь `petrov`)

Тело запроса:

```json
{
  "status_id": 2
}
```

Ответ: **HTTP 200**

```json
{
  "id": 11,
  "title": "Не работает сканер в приёмной",
  "description": "Сканер не определяется компьютером после обновления.",
  "priority": "Высокий",
  "status_id": 2,
  "status": "В работе",
  "category_id": 3,
  "category": "Оборудование",
  "applicant_id": 5,
  "applicant": "Иван Иванов",
  "executor_id": 3,
  "executor": "Петр Техников",
  "created_at": "2026-11-15 14:09:15",
  "updated_at": "2026-11-15 14:09:15"
}
```

## 11. Добавление комментария

POST /api/requests/11/comments  (пользователь `petrov`)

Тело запроса:

```json
{
  "content": "Драйвер переустановлен, проверяю."
}
```

Ответ: **HTTP 201**

```json
{
  "id": 4,
  "request_id": 11,
  "author_id": 3,
  "author": "Петр Техников",
  "author_role": "Исполнитель",
  "content": "Драйвер переустановлен, проверяю.",
  "created_at": "2026-11-15 14:09:15"
}
```

## 12. Ошибка: слишком короткая тема (422)

POST /api/requests  (пользователь `operator`)

Тело запроса:

```json
{
  "title": "Hi",
  "category_id": 3,
  "applicant_id": 5
}
```

Ответ: **HTTP 422**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Поле «Тема»: минимум 3 символа, сейчас 2",
    "details": {
      "title": "min_length:3"
    }
  }
}
```

## 13. Ошибка: недопустимый приоритет (422)

POST /api/requests  (пользователь `operator`)

Тело запроса:

```json
{
  "title": "Проверка приоритета",
  "category_id": 3,
  "priority": "Срочный",
  "applicant_id": 5
}
```

Ответ: **HTTP 422**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Приоритет должен быть одним из: Низкий, Средний, Высокий",
    "details": {
      "priority": "invalid_choice"
    }
  }
}
```

## 14. Ошибка: тело не JSON (415)

POST /api/requests  (пользователь `operator`)

Тело запроса (`Content-Type: text/plain`): `title=abc`

Ответ: **HTTP 415**

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "Ожидается тело запроса с Content-Type: application/json",
    "details": {}
  }
}
```

## 15. Ошибка: заявка не найдена (404)

GET /api/requests/9999  (пользователь `operator`)

Ответ: **HTTP 404**

```json
{
  "error": {
    "code": "not_found",
    "message": "Заявка #9999 не найдена",
    "details": {}
  }
}
```

## 16. Ошибка: нет авторизации (401)

GET /api/requests  (без авторизации)

Ответ: **HTTP 401**

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Требуется авторизация: HTTP Basic (логин и пароль) или вход через веб-интерфейс",
    "details": {}
  }
}
```

## 17. Ошибка: нет прав (403)

GET /api/users  (пользователь `ivanov`)

Ответ: **HTTP 403**

```json
{
  "error": {
    "code": "forbidden",
    "message": "Список пользователей доступен только оператору и администратору",
    "details": {}
  }
}
```

## 18. Ошибка: оператор не может удалять (403)

DELETE /api/requests/11  (пользователь `operator`)

Ответ: **HTTP 403**

```json
{
  "error": {
    "code": "forbidden",
    "message": "Удалять заявки может только администратор",
    "details": {}
  }
}
```

## 19. Удаление заявки администратором

DELETE /api/requests/11  (пользователь `admin`)

Ответ: **HTTP 204**

## 20. Проверка: удалённая заявка (404)

GET /api/requests/11  (пользователь `admin`)

Ответ: **HTTP 404**

```json
{
  "error": {
    "code": "not_found",
    "message": "Заявка #11 не найдена",
    "details": {}
  }
}
```
