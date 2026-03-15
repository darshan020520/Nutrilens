"""
Auth Service - Business Logic Layer

Handles authentication, user creation, token management.
Uses AuthRepository for database operations via dependency injection.
"""

from loguru import logger
from datetime import datetime, timedelta
from typing import Optional
import secrets
import smtplib
import ssl
from urllib.parse import quote
from email.message import EmailMessage
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.models.database import User
from app.schemas.user import UserCreate
from app.core.config import settings
from app.repositories.interfaces.auth_repository import IAuthRepository



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


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
        if not user.email_verified and not settings.skip_email_verification:
            raise ValueError("Email not verified. Please verify your email before logging in.")
        return user

    def register_user(self, user_create: UserCreate) -> User:

        existing_user = self.auth_repo.get_by_email(user_create.email)
        if existing_user:
            raise ValueError("Email already registered")

        hashed_password = get_password_hash(user_create.password)

        user = self.auth_repo.create(user_create.email, hashed_password)

        self.auth_repo.create_notification_preferences(user.id)

        return user

    def _is_localhost_url(self, url: str) -> bool:
        lowered = url.strip().lower()
        return "localhost" in lowered or "127.0.0.1" in lowered

    def _build_verification_url(self, token: str, request_base_url: Optional[str] = None) -> str:
        encoded_token = quote(token, safe="")
        environment = settings.environment.lower().strip()

        frontend_url = settings.frontend_url.strip()
        if frontend_url:
            # In production, ignore localhost defaults to avoid sending unusable links.
            if not (environment == "production" and self._is_localhost_url(frontend_url)):
                return f"{frontend_url.rstrip('/')}/verify-email?token={encoded_token}"

        backend_url = settings.backend_public_url.strip()
        if not backend_url and request_base_url:
            backend_url = request_base_url.strip()
        if backend_url:
            return f"{backend_url.rstrip('/')}/auth/v2/verify-email?token={encoded_token}"

        if frontend_url:
            return f"{frontend_url.rstrip('/')}/verify-email?token={encoded_token}"

        raise ValueError("Set FRONTEND_URL or BACKEND_PUBLIC_URL to generate verification links")

    async def send_verification_email(self, user: User, request_base_url: Optional[str] = None) -> None:
        token = secrets.token_urlsafe(48)
        updated_user = self.auth_repo.set_email_verification_token(user.id, token)
        if not updated_user:
            raise ValueError("Unable to generate verification token")

        verification_url = self._build_verification_url(token, request_base_url=request_base_url)

        html_content = (
            "<div style='font-family: Arial, sans-serif; line-height: 1.6;'>"
            "<h2>Verify your NutriLens account</h2>"
            "<p>Click the button below to verify your email address.</p>"
            f"<p><a href='{verification_url}' "
            "style='display:inline-block;padding:10px 18px;background:#16a34a;color:white;"
            "text-decoration:none;border-radius:6px;'>Verify Email</a></p>"
            f"<p>If the button does not work, copy and paste this URL:<br>{verification_url}</p>"
            f"<p>This link expires in {settings.email_verification_expire_hours} hours.</p>"
            "</div>"
        )

        try:
            provider = settings.email_verification_provider.lower().strip()
            subject = "Verify your NutriLens email"

            if provider == "gmail":
                self._send_verification_email_via_gmail(
                    to_email=updated_user.email,
                    subject=subject,
                    html_content=html_content,
                )
            else:
                self._send_verification_email_via_sendgrid(
                    to_email=updated_user.email,
                    subject=subject,
                    html_content=html_content,
                )
        except Exception as e:
            logger.error(f"Verification email send failed for {updated_user.email}: {e}")
            raise ValueError("Failed to send verification email")

    def _send_verification_email_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> None:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content

        if not settings.sendgrid_api_key:
            raise ValueError("SendGrid API key is not configured")

        message = Mail(
            from_email=Email(settings.from_email, "NutriLens"),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content),
        )
        client = SendGridAPIClient(settings.sendgrid_api_key)
        response = client.send(message)
        if response.status_code not in [200, 201, 202]:
            raise ValueError("Failed to send verification email via SendGrid")

    def _send_verification_email_via_gmail(
        self,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> None:
        smtp_user = settings.gmail_smtp_user.strip()
        # Google shows app passwords grouped with spaces; SMTP login needs contiguous characters.
        smtp_password = settings.gmail_smtp_app_password.replace(" ", "").strip()
        from_email = settings.from_email.strip() if settings.from_email else smtp_user

        if not smtp_user or not smtp_password:
            raise ValueError("Gmail SMTP credentials are not configured")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content("Please open this message in an HTML-capable email client.")
        msg.add_alternative(html_content, subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.gmail_smtp_host, settings.gmail_smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

    def verify_email_token(self, token: str) -> User:
        user = self.auth_repo.get_by_email_verification_token(token)
        if not user:
            raise ValueError("Invalid verification link")

        if user.email_verified:
            return user

        if not user.email_verification_sent_at:
            raise ValueError("Invalid verification link")

        expires_at = user.email_verification_sent_at + timedelta(
            hours=settings.email_verification_expire_hours
        )
        if datetime.utcnow() > expires_at:
            raise ValueError("Verification link has expired")

        verified_user = self.auth_repo.mark_email_verified(user.id)
        if not verified_user:
            raise ValueError("Failed to verify email")

        return verified_user

    async def resend_verification_email(self, email: str, request_base_url: Optional[str] = None) -> None:
        user = self.auth_repo.get_by_email(email)
        if not user:
            return
        if user.email_verified:
            return
        await self.send_verification_email(user, request_base_url=request_base_url)

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
        return self.auth_repo.update_last_login(user_id)
