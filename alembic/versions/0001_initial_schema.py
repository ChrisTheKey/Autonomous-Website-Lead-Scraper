"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "searches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("industry", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("radius_km", sa.Integer, nullable=False, server_default="10"),
        sa.Column("keywords", JSONB),
        sa.Column("target", sa.String(50), server_default="no_website"),
        sa.Column("max_results", sa.Integer, server_default="100"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Enums
    leadtype = sa.Enum(
        "no_website_candidate", "weak_website_candidate",
        "website_exists_not_target", "invalid_or_risky",
        name="leadtype",
    )
    leadsourcetype = sa.Enum(
        "google_places", "company_website", "manual_entry",
        "licensed_provider", "public_register",
        name="leadsourcetype",
    )
    enrichmentstatus = sa.Enum(
        "discovered", "place_only", "no_website", "website_found",
        "website_analyzed", "manual_review_required", "verified", "rejected",
        name="enrichmentstatus",
    )
    companystatus = sa.Enum(
        "discovered", "needs_review", "verified", "rejected",
        "contacted", "suppressed",
        name="companystatus",
    )
    leadpriority = sa.Enum(
        "high_priority", "medium_priority", "low_priority", "blocked",
        name="leadpriority",
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("searches.id")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500)),
        sa.Column("industry", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(100)),
        sa.Column("website", sa.String(2000)),
        sa.Column("normalized_domain", sa.String(500)),
        sa.Column("google_place_id", sa.String(255), unique=True),
        sa.Column("website_available", sa.Boolean, server_default="false"),
        sa.Column("lead_type", leadtype, server_default="invalid_or_risky"),
        sa.Column("lead_source_type", leadsourcetype, server_default="google_places"),
        sa.Column("enrichment_status", enrichmentstatus, server_default="discovered"),
        sa.Column("status", companystatus, server_default="discovered"),
        sa.Column("lead_priority", leadpriority),
        sa.Column("website_opportunity_score", sa.Integer, server_default="0"),
        sa.Column("confidence_score", sa.Float, server_default="0.0"),
        sa.Column("can_export", sa.Boolean, server_default="false"),
        sa.Column("export_block_reason", sa.String(500)),
        sa.Column("data_origin", sa.String(255)),
        sa.Column("data_retention_until", sa.DateTime(timezone=True)),
        sa.Column("has_https", sa.Boolean),
        sa.Column("has_mobile_viewport", sa.Boolean),
        sa.Column("has_contact_page", sa.Boolean),
        sa.Column("website_reachable", sa.Boolean),
        sa.Column("weak_website_reason", sa.String(500)),
        sa.Column("google_data_expires_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("contacted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_companies_lead_type", "companies", ["lead_type"])
    op.create_index("ix_companies_status", "companies", ["status"])
    op.create_index("ix_companies_lead_priority", "companies", ["lead_priority"])
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])
    op.create_index("ix_companies_normalized_domain", "companies", ["normalized_domain"])

    reviewstatus = sa.Enum("pending", "accepted", "rejected", name="reviewstatus")
    op.create_table(
        "place_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("searches.id"), nullable=False),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id")),
        sa.Column("google_place_id", sa.String(255), nullable=False),
        sa.Column("has_website", sa.Boolean, server_default="false"),
        sa.Column("website_uri", sa.String(2000)),
        sa.Column("phone_available", sa.Boolean, server_default="false"),
        sa.Column("address_available", sa.Boolean, server_default="false"),
        sa.Column("business_status", sa.String(100)),
        sa.Column("types", JSONB),
        sa.Column("rating", sa.Float),
        sa.Column("user_rating_count", sa.Integer),
        sa.Column("raw_payload_hash", sa.String(64)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("review_status", reviewstatus, server_default="pending"),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "crawled_pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status_code", sa.Integer),
        sa.Column("title", sa.String(1000)),
        sa.Column("text_excerpt", sa.Text),
        sa.Column("robots_allowed", sa.Boolean, server_default="true"),
        sa.Column("crawled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    contactreviewstatus = sa.Enum(
        "needs_review", "verified", "rejected", name="contactreviewstatus"
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("full_name", sa.String(500)),
        sa.Column("role", sa.String(255)),
        sa.Column("email", sa.String(500)),
        sa.Column("phone", sa.String(100)),
        sa.Column("source_url", sa.Text),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float, server_default="0.0"),
        sa.Column("is_personal_data", sa.Boolean, server_default="false"),
        sa.Column("review_status", contactreviewstatus, server_default="needs_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), server_default="system"),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "suppression_list",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id")),
        sa.Column("domain", sa.String(500)),
        sa.Column("phone", sa.String(100)),
        sa.Column("email", sa.String(500)),
        sa.Column("google_place_id", sa.String(255)),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("suppression_list")
    op.drop_table("audit_logs")
    op.drop_table("contacts")
    op.drop_table("crawled_pages")
    op.drop_table("place_candidates")
    op.drop_table("companies")
    op.drop_table("searches")
    for name in ["contactreviewstatus", "reviewstatus", "leadpriority",
                 "companystatus", "enrichmentstatus", "leadsourcetype", "leadtype"]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
