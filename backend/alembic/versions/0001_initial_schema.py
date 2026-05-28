"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False, index=True),
        sa.Column("website", sa.String(512), nullable=False, unique=True),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(100)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "status",
            sa.Enum("new", "enriched", "qualified", "synced", "rejected", name="leadstatus"),
            nullable=False,
            default="new",
            index=True,
        ),
        sa.Column("source_url", sa.Text()),
        sa.Column("raw_html", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("crm_id", sa.String(255)),
        sa.Column("crm_source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id")),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("scrape_jobs")
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS leadstatus")
