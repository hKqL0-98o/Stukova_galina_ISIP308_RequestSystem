"""Постраничный вывод списка заявок (ЛР №6, AI-журнал, запись 2): тесты по ответу модели."""
import pytest

PAGED = "/api/requests"


def ids(response):
    return [item["id"] for item in response.get_json()]


def test_without_params_array_is_unchanged_and_pages_cover_it_without_gaps(client, auth):
    """PG-01. Без параметров приходит весь список массивом; страницы по 4 дают те же заявки без пропусков и повторов."""
    full = client.get(PAGED, headers=auth("admin"))
    assert isinstance(full.get_json(), list) and "X-Total-Count" not in full.headers
    assert ids(full) == sorted(ids(full), reverse=True)              # порядок фиксирован: новые (большой номер) сверху
    collected = []
    for page, expected in ((1, 4), (2, 4), (3, 2)):
        response = client.get(f"{PAGED}?page={page}&per_page=4", headers=auth("admin"))
        assert response.status_code == 200 and len(response.get_json()) == expected
        assert response.headers["X-Total-Count"] == str(len(ids(full)))
        assert response.headers["X-Total-Pages"] == "3" and response.headers["X-Page"] == str(page)
        collected += ids(response)
    assert collected == ids(full)                                    # тот же порядок: новые сверху
    beyond = client.get(f"{PAGED}?page=4&per_page=4", headers=auth("admin"))
    assert beyond.status_code == 200 and beyond.get_json() == []     # за последней страницей: пусто, но не ошибка


def test_total_respects_user_role(client, auth):
    """PG-02. Итог считается по видимым заявкам: у заявителя меньше, чем у администратора, и равен его полному списку."""
    own = ids(client.get(PAGED, headers=auth("ivanov")))
    admin_total = len(ids(client.get(PAGED, headers=auth("admin"))))
    response = client.get(f"{PAGED}?page=1&per_page=2", headers=auth("ivanov"))
    assert int(response.headers["X-Total-Count"]) == len(own) < admin_total
    assert set(ids(response)) <= set(own)                             # чужих заявок на странице нет


def test_total_respects_filters(client, auth):
    """PG-03. Итог и страницы считаются с учётом фильтра и поиска."""
    for query in ("priority=Высокий", "status_id=1", "search=интернет"):
        expected = ids(client.get(f"{PAGED}?{query}", headers=auth("admin")))
        response = client.get(f"{PAGED}?{query}&per_page=1&page=1", headers=auth("admin"))
        assert int(response.headers["X-Total-Count"]) == len(expected) > 0, query
        assert ids(response) == expected[:1]


@pytest.mark.parametrize("query", [
    "page=0", "page=-1", "page=abc", "page=1.5", "page=10000000000000000000000000", "page=1000001",
    "per_page=0", "per_page=101", "per_page=abc", "per_page=-5",
])
def test_invalid_page_values_are_422(client, auth, query):
    """PG-04. Неверные page и per_page → 422 в едином формате (а не 500 и не отрицательное смещение)."""
    response = client.get(f"{PAGED}?{query}", headers=auth("admin"))
    assert response.status_code == 422, response.get_data(as_text=True)
    assert response.get_json()["error"]["code"] == "validation_error"


def test_web_list_has_pager_and_keeps_filters(client, web_login):
    """PG-05. Страница списка: «Страница 1 из N», ссылка «Вперёд» сохраняет фильтр и номер следующей страницы."""
    web_login("admin")
    html = client.get("/?per_page=3").get_data(as_text=True)
    assert "Страница 1 из 4" in html and "Найдено заявок: 10" in html
    assert "page=2" in html and "per_page=3" in html and "Назад" not in html
    html = client.get("/?per_page=2&priority=Средний").get_data(as_text=True)
    assert "priority=" in html.split("Вперёд")[0].rsplit("href=", 1)[-1]   # фильтр есть в ссылке «Вперёд»
