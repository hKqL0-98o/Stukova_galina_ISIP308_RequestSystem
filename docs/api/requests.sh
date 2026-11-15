#!/usr/bin/env bash
# Коллекция curl-запросов к API HelpDesk (ЛР №7). Запускать в bash / Git Bash.
# Перед запуском: export PASS='пароль_тестовой_учётки'; приложение должно работать на BASE (по умолчанию 127.0.0.1:5000).
BASE="${BASE:-http://127.0.0.1:5000}"

# 1. Текущий пользователь (ожидается HTTP 200)
curl -s -i -X GET -u admin:"$PASS" "$BASE/api/me"

# 2. Справочник статусов (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/statuses"

# 3. Справочник категорий (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/categories"

# 4. Список пользователей (оператор) (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/users"

# 5. Список заявок (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/requests"

# 6. Поиск и фильтр по статусу (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/requests?search=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80&status_id=1"

# 7. Одна заявка с комментариями и историей (ожидается HTTP 200)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/requests/1"

# 8. Создание заявки (ожидается HTTP 201)
curl -s -i -X POST -u operator:"$PASS" -H 'Content-Type: application/json' -d '{"title": "Не работает сканер в приёмной", "description": "Сканер не определяется компьютером после обновления.", "category_id": 3, "priority": "Высокий", "applicant_id": 5}' "$BASE/api/requests"

# 9. Назначение исполнителя (ожидается HTTP 200)
curl -s -i -X PATCH -u operator:"$PASS" -H 'Content-Type: application/json' -d '{"executor_id": 3}' "$BASE/api/requests/11"

# 10. Смена статуса исполнителем (ожидается HTTP 200)
curl -s -i -X PATCH -u petrov:"$PASS" -H 'Content-Type: application/json' -d '{"status_id": 2}' "$BASE/api/requests/11"

# 11. Добавление комментария (ожидается HTTP 201)
curl -s -i -X POST -u petrov:"$PASS" -H 'Content-Type: application/json' -d '{"content": "Драйвер переустановлен, проверяю."}' "$BASE/api/requests/11/comments"

# 12. Ошибка: слишком короткая тема (422) (ожидается HTTP 422)
curl -s -i -X POST -u operator:"$PASS" -H 'Content-Type: application/json' -d '{"title": "Hi", "category_id": 3, "applicant_id": 5}' "$BASE/api/requests"

# 13. Ошибка: недопустимый приоритет (422) (ожидается HTTP 422)
curl -s -i -X POST -u operator:"$PASS" -H 'Content-Type: application/json' -d '{"title": "Проверка приоритета", "category_id": 3, "priority": "Срочный", "applicant_id": 5}' "$BASE/api/requests"

# 14. Ошибка: тело не JSON (415) (ожидается HTTP 415)
curl -s -i -X POST -u operator:"$PASS" -H 'Content-Type: text/plain' -d 'title=abc' "$BASE/api/requests"

# 15. Ошибка: заявка не найдена (404) (ожидается HTTP 404)
curl -s -i -X GET -u operator:"$PASS" "$BASE/api/requests/9999"

# 16. Ошибка: нет авторизации (401) (ожидается HTTP 401)
curl -s -i -X GET "$BASE/api/requests"

# 17. Ошибка: нет прав (403) (ожидается HTTP 403)
curl -s -i -X GET -u ivanov:"$PASS" "$BASE/api/users"

# 18. Ошибка: оператор не может удалять (403) (ожидается HTTP 403)
curl -s -i -X DELETE -u operator:"$PASS" "$BASE/api/requests/11"

# 19. Удаление заявки администратором (ожидается HTTP 204)
curl -s -i -X DELETE -u admin:"$PASS" "$BASE/api/requests/11"

# 20. Проверка: удалённая заявка (404) (ожидается HTTP 404)
curl -s -i -X GET -u admin:"$PASS" "$BASE/api/requests/11"

# Примечание: в запросах, где в пути стоит /api/requests/11, используется заявка, созданная запросом 8.
# На чистой базе из db/seed.sql она получает id=11; если у вас другой id, подставьте его.
