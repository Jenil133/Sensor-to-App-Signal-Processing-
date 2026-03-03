"""model_artifacts registry for per-user detector checkpoints

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("detector", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "detector", "version", name="uq_model_version"),
    )


def downgrade() -> None:
    op.drop_table("model_artifacts")
