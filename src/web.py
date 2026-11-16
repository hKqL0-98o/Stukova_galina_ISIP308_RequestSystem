"""Контроллеры веб-интерфейса: принимают запрос, вызывают сервис, показывают страницу."""
from urllib.parse import urlparse

from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.exceptions import TooManyRequests

from . import services
from .auth import authenticate, login_user, logout_user
from .errors import AppError

bp = Blueprint("web", __name__)


def _safe_next(target):
    """Разрешаем переход только внутри сайта, чтобы ссылкой нельзя было увести на чужой сайт."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("web.index")


def _back():
    ref = request.referrer
    if ref and urlparse(ref).netloc == request.host:
        return redirect(ref)
    return redirect(url_for("web.index"))


@bp.before_request
def require_login():
    if g.user is None and request.endpoint != "web.login":
        return redirect(url_for("web.login", next=request.full_path if request.args else request.path))


@bp.errorhandler(AppError)
def handle_app_error(error):
    if request.method == "POST":
        flash(error.message, "error")
        return _back()
    return render_template("error.html", status=error.status, message=error.message), error.status


# ---------- Вход ----------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("web.index"))
    next_url = request.values.get("next", "")
    if request.method == "POST":
        try:
            user = authenticate(request.form.get("login", ""), request.form.get("password", ""))
        except TooManyRequests as error:
            flash(error.description, "error")
            response = make_response(render_template("login.html", login=request.form.get("login", ""),
                                                     next=next_url), 429)
            response.headers["Retry-After"] = str(error.retry_after)
            return response
        if user is None:
            flash("Неверный логин или пароль", "error")
            return render_template("login.html", login=request.form.get("login", ""), next=next_url), 401
        login_user(user)
        return redirect(_safe_next(next_url))
    return render_template("login.html", login="", next=next_url)


@bp.post("/logout")
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for("web.login"))


# ---------- Список ----------

@bp.get("/")
def index():
    filters = request.args.to_dict()
    try:
        items = services.list_requests(g.user, filters)
    except AppError as error:
        flash(error.message, "error")
        filters, items = {}, services.list_requests(g.user, {})
    return render_template(
        "index.html",
        requests=items,
        filters=filters,
        statuses=services.list_statuses(),
        categories=services.list_categories(),
        executors=services.list_executors(),
        priorities=services.PRIORITIES,
        can_create=services.can_create(g.user),
    )


# ---------- Создание и редактирование ----------

def _form_data(fields):
    return {field: request.form.get(field, "") for field in fields}


def _render_form(form, mode, request_id=None, errors=None, status=200):
    is_staff = g.user["role"] in (services.ADMIN, services.OPERATOR)
    return render_template(
        "request_form.html",
        form=form,
        mode=mode,
        request_id=request_id,
        errors=errors or {},
        categories=services.list_categories(),
        priorities=services.PRIORITIES,
        applicants=services.list_applicants() if (mode == "create" and is_staff) else None,
        limits={"title_min": services.TITLE_MIN, "title_max": services.TITLE_MAX,
                "description_max": services.DESCRIPTION_MAX},
    ), status


@bp.route("/requests/new", methods=["GET", "POST"])
def new_request():
    if not services.can_create(g.user):
        flash("Исполнитель не может создавать заявки", "error")
        return redirect(url_for("web.index"))
    fields = ["title", "description", "category_id", "priority"]
    if g.user["role"] != services.APPLICANT:
        fields.append("applicant_id")
    if request.method == "GET":
        return _render_form({"priority": services.DEFAULT_PRIORITY}, "create")
    form = _form_data(fields)
    try:
        created = services.create_request(g.user, form)
    except AppError as error:
        flash(error.message, "error")
        return _render_form(form, "create", errors=error.details, status=error.status)
    flash(f"Заявка #{created['id']} создана", "success")
    return redirect(url_for("web.request_detail", request_id=created["id"]))


@bp.route("/requests/<int:request_id>/edit", methods=["GET", "POST"])
def edit_request(request_id):
    req = services.get_request(g.user, request_id)
    reason = services.edit_denied_reason(g.user, req)
    if reason:
        flash(reason, "error")
        return redirect(url_for("web.request_detail", request_id=request_id))
    if request.method == "GET":
        form = {k: req[k] or "" for k in ("title", "description", "category_id", "priority")}
        return _render_form(form, "edit", request_id=request_id)
    form = _form_data(["title", "description", "category_id", "priority"])
    try:
        services.update_request(g.user, request_id, form)
    except AppError as error:
        flash(error.message, "error")
        return _render_form(form, "edit", request_id=request_id, errors=error.details, status=error.status)
    flash("Изменения сохранены", "success")
    return redirect(url_for("web.request_detail", request_id=request_id))


# ---------- Карточка заявки и действия ----------

@bp.get("/requests/<int:request_id>")
def request_detail(request_id):
    details = services.get_request_details(g.user, request_id)
    return render_template(
        "request_detail.html",
        req=details,
        perms=services.permissions(g.user, details),
        executors=services.list_executors(),
    )


@bp.post("/requests/<int:request_id>/status")
def change_status(request_id):
    services.update_request(g.user, request_id, {"status_id": request.form.get("status_id")})
    flash("Статус изменён", "success")
    return redirect(url_for("web.request_detail", request_id=request_id))


@bp.post("/requests/<int:request_id>/executor")
def change_executor(request_id):
    services.update_request(g.user, request_id, {"executor_id": request.form.get("executor_id") or None})
    flash("Исполнитель обновлён", "success")
    return redirect(url_for("web.request_detail", request_id=request_id))


@bp.post("/requests/<int:request_id>/comments")
def add_comment(request_id):
    services.add_comment(g.user, request_id, {"content": request.form.get("content")})
    flash("Комментарий добавлен", "success")
    return redirect(url_for("web.request_detail", request_id=request_id) + "#comments")


@bp.post("/requests/<int:request_id>/delete")
def delete_request(request_id):
    services.delete_request(g.user, request_id)
    flash(f"Заявка #{request_id} удалена", "success")
    return redirect(url_for("web.index"))
