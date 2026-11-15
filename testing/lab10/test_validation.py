"""Валидация и негативные сценарии: границы длины, неверные типы, несуществующие справочники."""
import pytest

from conftest import ADMIN, IVANOV, OPERATOR
from src import services
from src.errors import ValidationError

BASE = {"title": "Заявка для проверки", "category_id": 1, "applicant_id": IVANOV}


def create(user, **overrides):
    data = {**BASE, **overrides}
    return services.create_request(user(OPERATOR), data)


@pytest.mark.parametrize("title", ["", "   ", "ab", None])
def test_title_too_short_or_empty_is_rejected(ctx, user, title):
    """AT-18. Пустая, из пробелов или слишком короткая тема отклоняется."""
    with pytest.raises(ValidationError) as error:
        create(user, title=title)
    assert "title" in error.value.details


@pytest.mark.parametrize("length, ok", [(3, True), (100, True), (101, False)])
def test_title_length_boundaries(ctx, user, length, ok):
    """AT-19. Граница длины темы: 3 и 100 символов можно, 101 нельзя."""
    if ok:
        assert len(create(user, title="я" * length)["title"]) == length
    else:
        with pytest.raises(ValidationError):
            create(user, title="я" * length)


@pytest.mark.parametrize("length, ok", [(0, True), (2000, True), (2001, False)])
def test_description_length_boundaries(ctx, user, length, ok):
    """AT-20. Описание необязательно; 2000 символов можно, 2001 нельзя."""
    if ok:
        create(user, description="б" * length)
    else:
        with pytest.raises(ValidationError):
            create(user, description="б" * length)


def test_special_characters_are_stored_as_text(ctx, user):
    """AT-21. Кавычки, SQL и HTML сохраняются как обычный текст, а не исполняются."""
    nasty = "Robert'); DROP TABLE Requests;-- <script>alert(1)</script> \"кавычки\" 😀"
    created = create(user, title=nasty, description=nasty)
    assert created["title"] == nasty
    assert len(services.list_requests(user(ADMIN), {})) == 11          # таблица на месте


@pytest.mark.parametrize("field, value", [
    ("priority", "Срочно"),
    ("priority", "высокий"),         # регистр важен: допустимо только «Высокий»
    ("category_id", 999),
    ("category_id", "abc"),
    ("category_id", True),
    ("category_id", -1),
    ("category_id", 1.5),
    ("applicant_id", 2),          # оператор — не заявитель
    ("applicant_id", 999),
])
def test_invalid_reference_values_are_rejected(ctx, user, field, value):
    """AT-22. Недопустимый приоритет, несуществующая категория/заявитель и неверный тип отклоняются."""
    with pytest.raises(ValidationError):
        create(user, **{field: value})


def test_unknown_field_is_rejected(ctx, user):
    """AT-23. Лишнее поле в запросе не игнорируется молча."""
    with pytest.raises(ValidationError) as error:
        create(user, is_admin=True)
    assert error.value.details == {"is_admin": "unknown_field"}


def test_body_must_be_object(ctx, user):
    """AT-24. Тело запроса — не объект (например, список) отклоняется."""
    with pytest.raises(ValidationError):
        services.create_request(user(OPERATOR), ["title"])


@pytest.mark.parametrize("content, ok", [("", False), ("   ", False), ("а", True), ("а" * 1000, True), ("а" * 1001, False)])
def test_comment_length_boundaries(ctx, user, content, ok):
    """AT-25. Комментарий: пустой нельзя, от 1 до 1000 символов можно, 1001 нельзя."""
    if ok:
        assert services.add_comment(user(ADMIN), 1, {"content": content})["content"] == content
    else:
        with pytest.raises(ValidationError):
            services.add_comment(user(ADMIN), 1, {"content": content})


def test_failed_validation_does_not_change_data(ctx, user):
    """AT-26. После отклонённого запроса заявка и история остались прежними."""
    from src import repositories as repo
    before = (repo.get_request(1), repo.list_history(1))
    with pytest.raises(ValidationError):
        services.update_request(user(ADMIN), 1, {"title": "ok-тема", "priority": "Срочно"})
    assert (repo.get_request(1), repo.list_history(1)) == before
