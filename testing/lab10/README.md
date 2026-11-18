# Автоматические тесты (ЛР №10)

## Зависимости

```bash
pip install -r requirements-dev.txt     # Flask, waitress и pytest
```

## Запуск всего набора одной командой

Из корня проекта:

```bash
python -m pytest
```

Настройки лежат в `pytest.ini` (`testpaths = testing/lab10`). Сохранить вывод в файл:

```bash
python -m pytest > testing/lab10/test_run.txt
```

## Как устроены тесты

- Каждый тест получает **свою временную копию БД**, созданную из `db/schema.sql` и `db/seed.sql`. Рабочий `requests.db` не затрагивается.
- У всех пользователей во временной базе выставляется тестовый пароль `test-pass-123` (см. `conftest.py`). Реальные пароли тестам не нужны.
- `conftest.py` содержит фикстуры: `client` (HTTP-клиент Flask), `auth('operator')` (заголовок Basic), `db` (прямое чтение БД для проверки, что данные сохранились), `user(id)` и `ctx` (прямые вызовы сервисного слоя), `web_login` (вход через форму).

| Файл | Что проверяет |
|---|---|
| `test_business_logic.py` | бизнес-правила и права ролей (сервисный слой) |
| `test_validation.py` | валидация, граничные значения, негативные сценарии |
| `test_api.py` | REST API: коды ответов и формат ошибок |
| `test_web_integration.py` | веб-формы и сохранение в БД |
| `test_regression.py` | регрессия по дефектам BUG-01…BUG-04 |
| `test_login_rate_limit.py` | защита от подбора пароля (429, Retry-After), 8 тестов RL-01…RL-08 |
| `test_secret_key.py` | обязательный `SECRET_KEY`: отказ запуска с ключом-образцом, 9 тестов SK-01…SK-06 |
| `test_status_transitions.py` | порядок статусов (BUG-05): только шаг вперёд для оператора и исполнителя, админ любой переход, 12 тестов ST |
| `test_ai_drafts.py` | тесты по черновику модели (AI-журнал ЛР10): `create_request`, `status_transition_error`, `POST /api/requests`, граница числа SQLite, 34 теста AI-01…AI-16 |

Идентификаторы `AT-xx` и `REG-xx` в описаниях тестов соответствуют `test_summary.md`.

## Файлы результатов

- `test_run.txt` — полный вывод после последних изменений (176 passed).
- `test_run_rate_limit_before_fix.txt` — тесты защиты от подбора пароля на коде без ограничения (4 failed): доказательство, что они находят отсутствие защиты.
- `test_run_bug04_before_fix.txt`, `test_run_bug05_before_fix.txt` — регрессионные тесты BUG-04 и BUG-05 на коде до исправления.
- `test_run_before_fix.txt` — вывод до исправления (24 failed): доказательство, что тесты находят ошибки.
- `test_summary.md` — итоговый отчёт о тестировании.
