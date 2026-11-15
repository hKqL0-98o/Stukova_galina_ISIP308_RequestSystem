"""Веб-интерфейс + база данных: действия через формы действительно сохраняются в БД."""
from urllib.parse import urlparse

from conftest import BIG_ID


def test_login_and_logout(client, web_login):
    """AT-45. Вход по правильному паролю открывает список; выход возвращает на страницу входа."""
    web_login("operator")
    assert client.get("/").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302          # снова требуется вход


def test_wrong_password_is_rejected(client):
    """AT-46. Неверный пароль → 401 и сообщение, сессия не создаётся."""
    response = client.post("/login", data={"login": "admin", "password": "wrong"})
    assert response.status_code == 401
    assert "Неверный логин или пароль" in response.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_pages_require_login(client):
    """AT-47. Без входа все страницы перенаправляют на /login."""
    for path in ("/", "/requests/1", "/requests/new"):
        response = client.get(path)
        assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_create_request_via_form_is_saved_in_db(client, web_login, db):
    """AT-48. Заявка, созданная через форму заявителем, сохранена в БД с нужными полями."""
    web_login("ivanov")
    response = client.post("/requests/new", data={
        "title": "Не работает Wi-Fi в кабинете", "description": "Пропадает сигнал",
        "category_id": "1", "priority": "Высокий"})
    assert response.status_code == 302
    row = db.execute("SELECT * FROM Requests WHERE title = 'Не работает Wi-Fi в кабинете'").fetchone()
    assert row is not None and row["applicant_id"] == 5 and row["status_id"] == 1 and row["priority"] == "Высокий"


def test_invalid_form_shows_error_and_saves_nothing(client, web_login, db):
    """AT-49. Пустая тема: форма возвращается с ошибкой (422), в БД новых заявок нет."""
    web_login("ivanov")
    response = client.post("/requests/new", data={"title": "", "category_id": "1", "priority": "Средний"})
    assert response.status_code == 422
    assert "обязательно" in response.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM Requests").fetchone()[0] == 10


def test_status_change_via_form_is_saved(client, web_login, db):
    """AT-50. Смена статуса оператором через форму сохраняется в БД и истории."""
    web_login("operator")
    assert client.post("/requests/2/status", data={"status_id": "3"}).status_code == 302
    assert db.execute("SELECT status_id FROM Requests WHERE id = 2").fetchone()[0] == 3
    assert db.execute("SELECT new_value FROM RequestHistory WHERE request_id = 2 ORDER BY id DESC").fetchone()[0] == "Выполнена"


def test_forbidden_status_change_is_not_saved(client, web_login, db):
    """AT-51. Запрещённая смена статуса (оператор → «Закрыта») не меняет данные."""
    web_login("operator")
    client.post("/requests/3/status", data={"status_id": "4"})
    assert db.execute("SELECT status_id FROM Requests WHERE id = 3").fetchone()[0] == 3


def test_admin_deletes_request_via_form(client, web_login, db):
    """AT-52. Администратор удаляет заявку через форму; запись исчезает из БД."""
    web_login("admin")
    assert client.post("/requests/1/delete").status_code == 302
    assert db.execute("SELECT COUNT(*) FROM Requests WHERE id = 1").fetchone()[0] == 0


def test_login_redirect_cannot_leave_the_site(client):
    """AT-53. Параметр next не позволяет увести пользователя на чужой сайт."""
    for target in ("//evil.example", "/\\evil.example", "https://evil.example"):
        response = client.post("/login", data={"login": "admin", "password": "test-pass-123", "next": target})
        location = response.headers["Location"]
        parsed = urlparse(location)
        assert not parsed.scheme and not parsed.netloc            # переход только внутри сайта
        assert not location.startswith(("//", "/\\"))             # браузер не воспримет адрес как внешний
        client.post("/logout")


def test_user_cannot_open_foreign_request_page(client, web_login):
    """AT-54. Заявитель не открывает карточку чужой заявки."""
    web_login("sokolova")
    assert client.get("/requests/1").status_code == 403


def test_web_page_for_huge_identifier_is_404(client, web_login):
    """AT-55. Огромный номер в адресе страницы → 404, а не 500."""
    web_login("admin")
    assert client.get(f"/requests/{BIG_ID}").status_code == 404
