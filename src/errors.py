"""Ошибки приложения. Каждая знает свой HTTP-код, чтобы API и интерфейс отвечали единообразно."""


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError(AppError):
    status = 422
    code = "validation_error"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class UnsupportedMediaType(AppError):
    status = 415
    code = "unsupported_media_type"
