from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel, EmailStr, TypeAdapter, ValidationError
from typing import List, Optional
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
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/v2", tags=["auth-v2"])


class WhatsAppNumberRequest(BaseModel):
    whatsapp_number: str


class NotificationPreferencesResponse(BaseModel):
    enabled_providers: List[str]
    enabled_types: List[str]
    quiet_hours_start: int
    quiet_hours_end: int
    timezone: str
    whatsapp_number: Optional[str]
    phone_number: Optional[str]

    class Config:
        from_attributes = True


class NotificationPreferencesUpdateRequest(BaseModel):
    enabled_providers: Optional[List[str]] = None
    enabled_types: Optional[List[str]] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    timezone: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
    class Config:
        orm_mode = True


class MeResponse(BaseModel):
    success: bool
    data: dict
    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    message: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


@router.post("/register", response_model=UserResponse)
async def register(
    user_create: UserCreate,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):

    try:
        user = auth_service.register_user(user_create)
        if settings.skip_email_verification:
            auth_service.auth_repo.mark_email_verified(user.id)
        else:
            await auth_service.send_verification_email(user, request_base_url=str(request.base_url))
        return UserResponse.from_orm(user)
    except ValueError as e:
        status_code = (
            status.HTTP_409_CONFLICT
            if str(e) == "Email already registered"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        email = TypeAdapter(EmailStr).validate_python(form_data.username)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    try:
        user = auth_service.authenticate_user(str(email), form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    user = auth_service.update_last_login(user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update login timestamp"
        )

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
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.id)},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        auth_service.verify_email_token(payload.token)
        return VerifyEmailResponse(message="Email verified successfully. You can now log in.")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email_get(
    token: str = Query(..., min_length=1),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        auth_service.verify_email_token(token)
        return VerifyEmailResponse(message="Email verified successfully. You can now log in.")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        pref = auth_service.get_notification_preferences(current_user.id)
        return NotificationPreferencesResponse(
            enabled_providers=pref.enabled_providers or [],
            enabled_types=pref.enabled_types or [],
            quiet_hours_start=pref.quiet_hours_start,
            quiet_hours_end=pref.quiet_hours_end,
            timezone=pref.timezone or "UTC",
            whatsapp_number=pref.whatsapp_number,
            phone_number=pref.phone_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        pref = auth_service.update_notification_preferences(current_user.id, updates)
        return NotificationPreferencesResponse(
            enabled_providers=pref.enabled_providers or [],
            enabled_types=pref.enabled_types or [],
            quiet_hours_start=pref.quiet_hours_start,
            quiet_hours_end=pref.quiet_hours_end,
            timezone=pref.timezone or "UTC",
            whatsapp_number=pref.whatsapp_number,
            phone_number=pref.phone_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/whatsapp-number")
async def update_whatsapp_number(
    payload: WhatsAppNumberRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        auth_service.update_whatsapp_number(current_user.id, payload.whatsapp_number)
        return {"success": True, "message": "WhatsApp number updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    await auth_service.resend_verification_email(
        str(payload.email),
        request_base_url=str(request.base_url)
    )
    return MessageResponse(
        message="If an unverified account exists for this email, a verification link has been sent."
    )
