"""REST API. Контроллеры тонкие: разбирают JSON и вызывают тот же сервисный слой, что и интерфейс."""
from flask import Blueprint, g, jsonify, request, url_for

from . import services
from .errors import AppError, Unauthorized, UnsupportedMediaType

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.before_request
def require_auth():
    if g.user is None:
        raise Unauthorized("Требуется авторизация: HTTP Basic (логин и пароль) или вход через веб-интерфейс")


@bp.errorhandler(AppError)
def handle_app_error(error):
    return jsonify(error.to_dict()), error.status


def _json_body():
    if not request.is_json:
        raise UnsupportedMediaType("Ожидается тело запроса с Content-Type: application/json")
    data = request.get_json(silent=True)
    if data is None:
        raise AppError("Тело запроса не является корректным JSON")
    return data


# ---------- Заявки ----------

@bp.get("/requests")
def list_requests():
    args = request.args.to_dict()
    if "page" not in args and "per_page" not in args:
        return jsonify(services.list_requests(g.user, args))      # как раньше: весь список массивом
    result = services.list_requests_page(g.user, args)
    response = jsonify(result["items"])                           # тело по-прежнему массив
    response.headers["X-Total-Count"] = str(result["total"])
    response.headers["X-Page"] = str(result["page"])
    response.headers["X-Per-Page"] = str(result["per_page"])
    response.headers["X-Total-Pages"] = str(result["pages"])
    return response


@bp.get("/requests/<int:request_id>")
def get_request(request_id):
    return jsonify(services.get_request_details(g.user, request_id))


@bp.post("/requests")
def create_request():
    created = services.create_request(g.user, _json_body())
    response = jsonify(created)
    response.status_code = 201
    response.headers["Location"] = url_for("api.get_request", request_id=created["id"])
    return response


@bp.route("/requests/<int:request_id>", methods=["PATCH", "PUT"])
def update_request(request_id):
    return jsonify(services.update_request(g.user, request_id, _json_body()))


@bp.delete("/requests/<int:request_id>")
def delete_request(request_id):
    services.delete_request(g.user, request_id)
    return "", 204


# ---------- Комментарии ----------

@bp.get("/requests/<int:request_id>/comments")
def list_comments(request_id):
    return jsonify(services.list_comments(g.user, request_id))


@bp.post("/requests/<int:request_id>/comments")
def add_comment(request_id):
    return jsonify(services.add_comment(g.user, request_id, _json_body())), 201


# ---------- Справочники ----------

@bp.get("/me")
def me():
    return jsonify(g.user)


@bp.get("/users")
def list_users():
    return jsonify(services.list_users(g.user))


@bp.get("/statuses")
def list_statuses():
    return jsonify(services.list_statuses())


@bp.get("/categories")
def list_categories():
    return jsonify(services.list_categories())
