from fastapi import HTTPException, status
from typing import Optional


class AppException(HTTPException):
    """应用异常基类"""
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: Optional[str] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "detail": detail
            }
        )


class AuthenticationError(AppException):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", detail: Optional[str] = None):
        super().__init__(
            code="AUTH_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class AuthorizationError(AppException):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", detail: Optional[str] = None):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundError(AppException):
    """资源不存在"""
    
    def __init__(self, message: str = "资源不存在", detail: Optional[str] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ValidationError(AppException):
    """验证错误"""
    
    def __init__(self, message: str = "参数验证失败", detail: Optional[str] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class ServiceError(AppException):
    """服务错误"""
    
    def __init__(self, message: str = "服务暂时不可用", detail: Optional[str] = None):
        super().__init__(
            code="SERVICE_ERROR",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail
        )
