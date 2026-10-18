"""Initial schema for shipment history and idempotent generation runs."""
from alembic import op
import sqlalchemy as sa
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
 op.create_table("shipments",sa.Column("tracking_number",sa.String(120),primary_key=True),sa.Column("current_status",sa.String(120),nullable=True),sa.Column("updated_at",sa.String(120),nullable=True),sa.Column("raw_data",sa.Text(),nullable=True))
 op.create_table("shipment_events",sa.Column("event_key",sa.String(180),primary_key=True),sa.Column("cycle_id",sa.String(100),nullable=False),sa.Column("tracking_number",sa.String(120),nullable=True),sa.Column("event_status",sa.String(120),nullable=True),sa.Column("event_time",sa.String(120),nullable=True),sa.Column("raw_data",sa.Text(),nullable=True),sa.Column("is_dirty",sa.Boolean(),nullable=False,server_default=sa.false()))
 op.create_index("ix_shipment_events_cycle_id","shipment_events",["cycle_id"])
 op.create_index("ix_shipment_events_tracking_number","shipment_events",["tracking_number"])
 op.create_table("generation_runs",sa.Column("cycle_id",sa.String(100),primary_key=True),sa.Column("started_at",sa.String(50),nullable=True),sa.Column("finished_at",sa.String(50),nullable=True),sa.Column("events_requested",sa.Integer(),nullable=False,server_default="0"),sa.Column("events_inserted",sa.Integer(),nullable=False,server_default="0"),sa.Column("status",sa.String(30),nullable=False,server_default="started"))
def downgrade():
 op.drop_table("generation_runs")
 op.drop_index("ix_shipment_events_tracking_number",table_name="shipment_events")
 op.drop_index("ix_shipment_events_cycle_id",table_name="shipment_events")
 op.drop_table("shipment_events")
 op.drop_table("shipments")
