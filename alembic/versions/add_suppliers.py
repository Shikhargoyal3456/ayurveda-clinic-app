"""add suppliers

Revision ID: add_suppliers
Revises:
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "add_suppliers"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DEPLOY-FULL-1 / SUPPLIER-FULL-1: Create supplier registry without touching existing patient/order data.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppliers" not in inspector.get_table_names():
        op.create_table(
            "suppliers",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("location", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("categories", sa.JSON(), nullable=False),
            sa.Column("api_url", sa.String(length=255), nullable=True),
            sa.Column("whatsapp", sa.String(length=40), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_suppliers_name", "suppliers", ["name"])
        op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])

    suppliers = sa.table(
        "suppliers",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("phone", sa.String),
        sa.column("location", sa.String),
        sa.column("categories", sa.JSON),
        sa.column("api_url", sa.String),
        sa.column("whatsapp", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    existing = set(bind.execute(sa.text("SELECT id FROM suppliers WHERE id IN ('sup_1', 'sup_2')")).scalars().all())
    rows = []
    if "sup_1" not in existing:
        rows.append(
            {
                "id": "sup_1",
                "name": "Pharma Distributor A",
                "phone": "",
                "location": "Delhi",
                "categories": ["general", "tablets", "modern_medicine"],
                "api_url": None,
                "whatsapp": None,
                "is_active": True,
            }
        )
    if "sup_2" not in existing:
        rows.append(
            {
                "id": "sup_2",
                "name": "Ayurveda Supplier B",
                "phone": "",
                "location": "Gurgaon",
                "categories": ["general", "ayurveda", "rare"],
                "api_url": None,
                "whatsapp": None,
                "is_active": True,
            }
        )
    if rows:
        op.bulk_insert(suppliers, rows)


def downgrade() -> None:
    # DEPLOY-FULL-1 / SUPPLIER-FULL-1: Supplier table is isolated; downgrade removes only supplier registry data.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppliers" in inspector.get_table_names():
        op.drop_index("ix_suppliers_is_active", table_name="suppliers")
        op.drop_index("ix_suppliers_name", table_name="suppliers")
        op.drop_table("suppliers")
