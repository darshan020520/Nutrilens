"""
Auth Service - Business Logic Layer

Handles authentication, user creation, token management.
Uses AuthRepository for database operations via dependency injection.
"""

from loguru import logger
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.database import User
from app.schemas.user import UserCreate
from app.core.config import settings
from app.repositories.interfaces.auth_repository import IAuthRepository

from fastapi import Depends, HTTPException, status


# ===== CONFIGURATION =====

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# ===== UTILITY FUNCTIONS (Pure functions, no dependencies) =====

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def calculate_onboarding_status(user: User) -> dict:
    if user.onboarding_completed:
        return {
            "completed": True,
            "current_step": 4,
            "completed_steps": [1, 2, 3, 4],
            "redirect_to": "/dashboard",
            "next_step_name": None
        }

    completed_steps = []
    if user.basic_info_completed:
        completed_steps.append(1)
    if user.goal_selection_completed:
        completed_steps.append(2)
    if user.path_selection_completed:
        completed_steps.append(3)
    if user.preferences_completed:
        completed_steps.append(4)

    # Determine next step
    current_step = user.onboarding_current_step
    step_names = {
        1: "basic-info",
        2: "goal-selection",
        3: "path-selection",
        4: "preferences"
    }

    next_step_name = step_names.get(current_step, "basic-info")
    redirect_to = f"/onboarding/{next_step_name}"

    return {
        "completed": False,
        "current_step": current_step,
        "completed_steps": completed_steps,
        "redirect_to": redirect_to,
        "next_step_name": next_step_name
    }


class AuthService:

    def __init__(self, auth_repo: IAuthRepository):
        self.auth_repo = auth_repo

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.auth_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    def register_user(self, user_create: UserCreate) -> User:

        existing_user = self.auth_repo.get_by_email(user_create.email)
        if existing_user:
            raise ValueError("Email already registered")

        hashed_password = get_password_hash(user_create.password)

        # Create user
        user = self.auth_repo.create(user_create.email, hashed_password)

        # Create default notification preferences
        self.auth_repo.create_notification_preferences(user.id)

        return user

    def get_user_from_token(self, token: str) -> Optional[User]:
        payload = verify_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = self.auth_repo.get_by_id(int(user_id))
        return user

    def update_last_login(self, user_id: int) -> Optional[User]:
        """
        Update user's last login timestamp.

        Args:
            user_id: User ID

        Returns:
            Updated user object, None if user not found
        """
        return self.auth_repo.update_last_login(user_id)