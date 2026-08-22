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

    metadata = sa.MetaData()
    source = sa.Table("clinic_subscriptions", metadata, autoload_with=bind)
    target = sa.Table("clinic_subscriptions_new", metadata, autoload_with=bind)

    def column_or_none(name: str):
        return source.c[name] if name in columns else sa.null()

    source_user = (
        sa.func.coalesce(source.c.user_id, source.c.doctor_id)
        if "user_id" in columns and "doctor_id" in columns
        else source.c.user_id
        if "user_id" in columns
        else source.c.doctor_id
    )
    source_plan = (
        sa.func.coalesce(column_or_none("plan_id"), column_or_none("plan"), sa.literal("free"))
        if "plan_id" in columns or "plan" in columns
        else sa.literal("free")
    )
    source_period_end = (
        sa.func.coalesce(column_or_none("current_period_end"), column_or_none("expires_at"))
        if "current_period_end" in columns or "expires_at" in columns
        else sa.null()
    )

    select_rows = (
        sa.select(
            sa.func.min(source.c.id),
            source_user,
            sa.func.min(sa.func.coalesce(source_plan, sa.literal("free"))),
            sa.func.min(sa.func.coalesce(column_or_none("status"), sa.literal("trial"))),
            sa.func.min(sa.func.coalesce(column_or_none("started_at"), sa.func.current_timestamp())),
            sa.func.min(column_or_none("trial_end_date")),
            sa.func.min(column_or_none("razorpay_subscription_id")),
            sa.func.min(source_period_end),
            sa.func.min(sa.func.coalesce(column_or_none("created_at"), sa.func.current_timestamp())),
        )
        .where(source_user.is_not(None))
        .group_by(source_user)
    )
    bind.execute(
        target.insert().from_select(
            [
                "id",
                "user_id",
                "plan_id",
                "status",
                "started_at",
                "trial_end_date",
                "razorpay_subscription_id",
                "current_period_end",
                "created_at",
            ],
            select_rows,
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
