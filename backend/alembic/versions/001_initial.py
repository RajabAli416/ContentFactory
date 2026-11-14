"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are also created via SQLAlchemy metadata.create_all on startup.
    # This migration documents the baseline schema for Alembic users.
    op.create_table(
        "projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(64)),
        sa.Column("language", sa.String(64)),
        sa.Column("tone", sa.String(128)),
        sa.Column("visual_aesthetic", sa.String(128)),
        sa.Column("narration_voice", sa.String(128)),
        sa.Column("target_duration_seconds", sa.Integer()),
        sa.Column("aspect_ratio", sa.String(16)),
        sa.Column("extra_instructions", sa.Text()),
        sa.Column("manifest_path", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_type", sa.String(64)),
        sa.Column("status", sa.String(32)),
        sa.Column("current_stage", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "job_stages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32)),
        sa.Column("retry_count", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("output_ref", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("logs", sa.Text()),
    )
    op.create_table(
        "scenes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("narration_text", sa.Text()),
        sa.Column("visual_description", sa.Text()),
        sa.Column("video_prompt", sa.Text()),
        sa.Column("negative_prompt", sa.Text()),
        sa.Column("estimated_duration_seconds", sa.Float()),
        sa.Column("actual_duration_seconds", sa.Float()),
        sa.Column("visual_style", sa.String(128)),
        sa.Column("camera_movement", sa.String(128)),
        sa.Column("composition", sa.String(64)),
        sa.Column("generation_status", sa.String(32)),
        sa.Column("raw_asset_path", sa.String(1024)),
        sa.Column("processed_asset_path", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scene_id", sa.String(64)),
        sa.Column("asset_type", sa.String(64)),
        sa.Column("source", sa.String(64)),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("fps", sa.Float()),
        sa.Column("codec", sa.String(64)),
        sa.Column("checksum", sa.String(128)),
        sa.Column("provider", sa.String(64)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("assets")
    op.drop_table("scenes")
    op.drop_table("job_stages")
    op.drop_table("jobs")
    op.drop_table("projects")
