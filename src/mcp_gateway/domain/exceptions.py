from mcp_gateway.domain.external.error_response import AppError

class InvalidAccessTokenError(AppError):
    pass

class AuthorizationDeniedError(AppError):
    pass

class MissingTokenError(AppError):
    pass

class ForbiddenError(AppError):
    pass

class AlreadyExistsError(AppError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error="ALREADY_EXISTS",
            error_type="AlreadyExistsError",
            status_code=409,
        )

class NotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error="NOT_FOUND",
            error_type="NotFoundError",
            status_code=404,
        )

class ServiceError(AppError):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error="INTERNAL_ERROR",
            error_type="ServiceError",
            status_code=500,
        )

class RepositoryError(Exception):
    pass