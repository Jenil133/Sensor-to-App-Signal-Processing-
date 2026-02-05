"""analytics tables: clean_samples, daily_metrics, baselines, anomaly_events

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clean_samples",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "metric", "ts", name="uq_clean_dedupe"),
    )
    op.create_index("ix_clean_user_metric_ts", "clean_samples",
                    ["user_id", "metric", "ts"])
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("n_samples", sa.Integer(), nullable=False),
        sa.Column("vmin", sa.Float(), nullable=False),
        sa.Column("vmax", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=True),
        sa.UniqueConstraint("user_id", "day", "metric", name="uq_daily"),
    )
    op.create_index("ix_daily_user_metric_day", "daily_metrics",
                    ["user_id", "metric", "day"])
    op.create_table(
        "baselines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("as_of_day", sa.Date(), nullable=False),
        sa.Column("center", sa.Float(), nullable=False),
        sa.Column("spread", sa.Float(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "metric", "as_of_day", name="uq_baseline"),
    )
    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric", sa.String(32), nullable=True),
        sa.Column("detector", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_anomaly_user_status", "anomaly_events",
                    ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_anomaly_user_status", table_name="anomaly_events")
    op.drop_table("anomaly_events")
    op.drop_table("baselines")
    op.drop_index("ix_daily_user_metric_day", table_name="daily_metrics")
    op.drop_table("daily_metrics")
    op.drop_index("ix_clean_user_metric_ts", table_name="clean_samples")
    op.drop_table("clean_samples")
