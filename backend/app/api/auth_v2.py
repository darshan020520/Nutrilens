"""
Auth API Endpoints V2 - Clean Architecture

Provides authentication endpoints using repository pattern.

MIGRATED FROM: auth.py
USES: Clean architecture with AuthRepository + auth service functions
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel
from typing import Optional
import logging

from app.models.database import get_db, User
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import (
    authenticate_user,
    create_user,
    create_access_token,
    get_current_user,
    _calculate_onboarding_status,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.repositories.auth_repository import AuthRepository
from app.dependencies import get_auth_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/v2", tags=["auth-v2"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/v2/login")


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
    auth_repo: AuthRepository = Depends(get_auth_repository),
    db: Session = Depends(get_db)
):
    """
    Register a new user.

    MIGRATED FROM: auth.py:20-33

    Uses:
    - AuthRepository for checking existing user
    - auth service create_user() for user creation (which uses repo internally)
    """
    # Check if user exists - using repository
    existing_user = auth_repo.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user - using auth service (which uses repo internally)
    user = create_user(db, user_create)
    return user


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    db: Session = Depends(get_db)
):
    """
    Login and receive access token.

    MIGRATED FROM: auth.py:35-61

    Uses:
    - auth service authenticate_user() for authentication (which uses repo internally)
    - AuthRepository for updating last login
    - auth service create_access_token() for JWT generation
    """
    # Authenticate user - using auth service (which uses repo internally)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login - using repository (returns fresh user object)
    user = auth_repo.update_last_login(user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update login timestamp"
        )

    # Create access token - using auth service (pure utility, no DB)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)  # Fresh user with updated last_login
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current user information with onboarding status.

    MIGRATED FROM: auth.py:63-86

    Uses:
    - auth service get_current_user() for token validation (which uses repo internally)
    - auth service _calculate_onboarding_status() for onboarding info
    """
    # Get current user - using auth service (which uses repo internally)
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Calculate onboarding status - using auth service (pure calculation, no DB)
    onboarding_status = _calculate_onboarding_status(user)

    return MeResponse(
        success=True,
        data={
            "user": UserResponse.from_orm(user),
            "onboarding": onboarding_status
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Refresh access token.

    MIGRATED FROM: auth.py:90-110

    Uses:
    - auth service get_current_user() for token validation (which uses repo internally)
    - auth service create_access_token() for new JWT generation
    """
    # Validate current token - using auth service (which uses repo internally)
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    # Create new token - using auth service (pure utility, no DB)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )
