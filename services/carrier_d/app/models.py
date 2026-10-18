import os
from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

class Shipment(Base):
    __tablename__ = "shipments"
    tracking_number = Column(String(120), primary_key=True)
    current_status = Column(String(120), nullable=True)
    updated_at = Column(String(120), nullable=True)
    raw_data = Column(Text, nullable=True)

class ShipmentEvent(Base):
    __tablename__ = "shipment_events"
    event_key = Column(String(180), primary_key=True)
    cycle_id = Column(String(100), nullable=False, index=True)
    tracking_number = Column(String(120), nullable=True, index=True)
    event_status = Column(String(120), nullable=True)
    event_time = Column(String(120), nullable=True)
    raw_data = Column(Text, nullable=True)
    is_dirty = Column(Boolean, nullable=False, default=False)

class GenerationRun(Base):
    __tablename__ = "generation_runs"
    cycle_id = Column(String(100), primary_key=True)
    started_at = Column(String(50), nullable=True)
    finished_at = Column(String(50), nullable=True)
    events_requested = Column(Integer, nullable=False, default=0)
    events_inserted = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="started")
