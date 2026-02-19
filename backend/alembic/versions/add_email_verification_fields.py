"""add email verification fields to users

Revision ID: add_email_verification
Revises: add_meal_plan_link
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_email_verification"
down_revision = "add_meal_plan_link"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("email_verification_token", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    op.create_index(
        "ix_users_email_verification_token",
        "users",
        ["email_verification_token"],
        unique=True,
    )

    # Existing users should remain able to log in after rollout.
    op.execute("UPDATE users SET email_verified = TRUE")


def downgrade():
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")

