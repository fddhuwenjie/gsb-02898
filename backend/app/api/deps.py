from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户"""
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise AuthenticationError(message="无效的认证凭据", detail="Token无效或已过期")
    
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError(message="无效的认证凭据", detail="Token中缺少用户信息")
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise AuthenticationError(message="用户不存在", detail="Token对应的用户已被删除")
    
    if not user.is_active:
        raise AuthorizationError(message="用户已被禁用", detail="请联系管理员")
    
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """获取当前管理员用户"""
    if not current_user.is_admin:
        raise AuthorizationError(message="需要管理员权限", detail="当前用户不是管理员")
    return current_user
