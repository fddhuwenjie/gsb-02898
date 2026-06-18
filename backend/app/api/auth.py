from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.exceptions import AuthenticationError, ValidationError
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token

router = APIRouter(prefix="/auth", tags=["认证"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise ValidationError(message="用户名已存在", detail="请更换其他用户名")
    
    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # 生成token
    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"User registered: {user.username}")
    
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise AuthenticationError(message="用户名或密码错误", detail="请检查输入后重试")
    
    if not user.is_active:
        raise AuthenticationError(message="用户已被禁用", detail="请联系管理员")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"User logged in: {user.username}")
    
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )
