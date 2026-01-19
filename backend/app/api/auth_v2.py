"""
Auth API Endpoints V2 - Clean Architecture

Provides authentication endpoints using clean architecture pattern.

MIGRATED FROM: auth.py
ARCHITECTURE: API → Service → Repository → Database
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel
from typing import Optional
import logging

from app.models.database import User
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import (
    AuthService,
    create_access_token,
    calculate_onboarding_status,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.dependencies import get_auth_service, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/v2", tags=["auth-v2"])


# ===== RESPONSE SCHEMAS (IDENTICAL TO V1) =====

class LoginResponse(BaseModel):
    """Login response with token and user"""
    access_token: str
    token_type: str
    user: UserResponse

    class Config:
        orm_mode = True


class MeResponse(BaseModel):
    """Current user with onboarding status"""
    success: bool
    data: dict

    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    """Token refresh response"""
    access_token: str
    token_type: str


# ===== ENDPOINTS =====

@router.post("/register", response_model=UserResponse)
async def register(
    user_create: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user.

    MIGRATED FROM: auth.py:20-33

    Architecture: API → AuthService → AuthRepository → Database
    """
    try:
        user = auth_service.register_user(user_create)
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Login and receive access token.

    MIGRATED FROM: auth.py:35-61

    Architecture: API → AuthService → AuthRepository → Database
    """
    # Authenticate user
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user = auth_service.update_last_login(user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update login timestamp"
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information with onboarding status.

    MIGRATED FROM: auth.py:63-86

    Architecture: API → get_current_user (DI) → AuthService → AuthRepository → Database
    """
    # Calculate onboarding status
    onboarding_status = calculate_onboarding_status(current_user)

    return MeResponse(
        success=True,
        data={
            "user": UserResponse.from_orm(current_user),
            "onboarding": onboarding_status
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user)
):
    """
    Refresh access token.

    MIGRATED FROM: auth.py:90-110

    Architecture: API → get_current_user (DI) → AuthService → AuthRepository → Database
    """
    # Create new token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.id)},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )
