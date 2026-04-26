"""normalize subscription columns

Revision ID: subscription_new_schema
Revises: add_suppliers
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "subscription_new_schema"
down_revision = "add_suppliers"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "clinic_subscriptions"):
        return

    columns = {column["name"] for column in inspector.get_columns("clinic_subscriptions")}
    if "doctor_id" not in columns and "plan" not in columns:
        return

    op.create_table(
        "clinic_subscriptions_new",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("plan_id", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="trial"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("trial_end_date", sa.Date(), nullable=True),
        sa.Column("razorpay_subscription_id", sa.String(length=100), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clinic_subscriptions_user_id", "clinic_subscriptions_new", ["user_id"], unique=True)
    op.create_index("ix_clinic_subscriptions_plan_id", "clinic_subscriptions_new", ["plan_id"])
    op.create_index("ix_clinic_subscriptions_status", "clinic_subscriptions_new", ["status"])

    source_user = "COALESCE(user_id, doctor_id)" if "user_id" in columns and "doctor_id" in columns else ("user_id" if "user_id" in columns else "doctor_id")
    source_plan = "COALESCE(plan_id, plan, 'free')" if "plan_id" in columns and "plan" in columns else ("plan_id" if "plan_id" in columns else "plan")
    source_trial_end = "trial_end_date" if "trial_end_date" in columns else "NULL"
    source_razorpay = "razorpay_subscription_id" if "razorpay_subscription_id" in columns else "NULL"
    source_period_end = "COALESCE(current_period_end, expires_at)" if "current_period_end" in columns and "expires_at" in columns else ("current_period_end" if "current_period_end" in columns else ("expires_at" if "expires_at" in columns else "NULL"))

    bind.execute(
        sa.text(
            f"""
            INSERT INTO clinic_subscriptions_new (
                id,
                user_id,
                plan_id,
                status,
                started_at,
                trial_end_date,
                razorpay_subscription_id,
                current_period_end,
                created_at
            )
            SELECT
                MIN(id) AS id,
                {source_user} AS user_id,
                MIN(COALESCE({source_plan}, 'free')) AS plan_id,
                MIN(COALESCE(status, 'trial')) AS status,
                MIN(COALESCE(started_at, CURRENT_TIMESTAMP)) AS started_at,
                MIN({source_trial_end}) AS trial_end_date,
                MIN({source_razorpay}) AS razorpay_subscription_id,
                MIN({source_period_end}) AS current_period_end,
                MIN(COALESCE(created_at, CURRENT_TIMESTAMP)) AS created_at
            FROM clinic_subscriptions
            WHERE {source_user} IS NOT NULL
            GROUP BY {source_user}
            """
        )
    )

    op.drop_table("clinic_subscriptions")
    op.rename_table("clinic_subscriptions_new", "clinic_subscriptions")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "clinic_subscriptions"):
        return

    columns = {column["name"] for column in inspector.get_columns("clinic_subscriptions")}
    if "doctor_id" in columns and "plan" in columns:
        return

    op.create_table(
        "clinic_subscriptions_old",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO clinic_subscriptions_old (
                id, doctor_id, plan, status, started_at, expires_at, created_at
            )
            SELECT
                id, user_id, plan_id, status, started_at, current_period_end, created_at
            FROM clinic_subscriptions
            """
        )
    )

    op.drop_table("clinic_subscriptions")
    op.rename_table("clinic_subscriptions_old", "clinic_subscriptions")
