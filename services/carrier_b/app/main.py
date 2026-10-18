import json
import os
import time
from collections import defaultdict

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    GenerationRun,
    SessionLocal,
    Shipment,
    ShipmentEvent,
    engine,
)

CARRIER = "B"
RATE_LIMIT = max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))
METRICS_REGISTRY = CollectorRegistry()
SHIPMENTS_GAUGE = Gauge(
    "carrier_shipments",
    "Current number of shipments stored by the carrier.",
    ("carrier",),
    registry=METRICS_REGISTRY,
)
SHIPMENT_EVENTS_GAUGE = Gauge(
    "carrier_shipment_events",
    "Current number of shipment events stored by the carrier.",
    ("carrier",),
    registry=METRICS_REGISTRY,
)
DIRTY_EVENTS_GAUGE = Gauge(
    "carrier_dirty_shipment_events",
    "Current number of dirty shipment events stored by the carrier.",
    ("carrier",),
    registry=METRICS_REGISTRY,
)
GENERATION_RUNS_GAUGE = Gauge(
    "carrier_generation_runs",
    "Number of generation runs, grouped by status.",
    ("carrier", "status"),
    registry=METRICS_REGISTRY,
)
GENERATED_EVENTS_GAUGE = Gauge(
    "carrier_generation_events_inserted",
    "Total events reported as inserted by completed and incomplete runs.",
    ("carrier",),
    registry=METRICS_REGISTRY,
)

app = FastAPI(title="Carrier B API", version="1.0.0")
requests_by_ip = defaultdict(list)


def get_db():
    # Give each request its own database session.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/metrics", "/docs", "/openapi.json"):
        return await call_next(request)

    now = time.time()
    ip = request.client.host if request.client else "unknown"
    requests_by_ip[ip] = [
        timestamp for timestamp in requests_by_ip[ip] if now - timestamp < 60
    ]
    if len(requests_by_ip[ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"carrier": CARRIER, "error": "Rate limit exceeded"},
        )

    requests_by_ip[ip].append(now)
    return await call_next(request)


def apply_scenario(scenario):
    # Simulate integration errors without changing persisted data.
    scenarios = {
        "not_found": (404, "Simulated shipment not found"),
        "rate_limited": (429, "Simulated rate limit"),
        "server_error": (500, "Simulated internal server error"),
        "unavailable": (503, "Simulated service unavailable"),
    }
    if scenario in scenarios:
        code, message = scenarios[scenario]
        raise HTTPException(status_code=code, detail=message)


def raw_value(value):
    try:
        return json.loads(value) if value else None
    except (TypeError, json.JSONDecodeError):
        return value


def shipment_value(row):
    return {
        "tracking_number": row.tracking_number,
        "status": row.current_status,
        "updated_at": row.updated_at,
        "raw_data": raw_value(row.raw_data),
    }


def event_value(row):
    return {
        "event_key": row.event_key,
        "cycle_id": row.cycle_id,
        "tracking_number": row.tracking_number,
        "status": row.event_status,
        "event_time": row.event_time,
        "raw_data": raw_value(row.raw_data),
        "is_dirty": row.is_dirty,
    }


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    return {"carrier": CARRIER, "status": "ok", "database": "connected"}


@app.get("/metrics", include_in_schema=False)
def metrics(db: Session = Depends(get_db)):
    SHIPMENTS_GAUGE.labels(CARRIER).set(
        db.scalar(select(func.count()).select_from(Shipment))
    )
    SHIPMENT_EVENTS_GAUGE.labels(CARRIER).set(
        db.scalar(select(func.count()).select_from(ShipmentEvent))
    )
    DIRTY_EVENTS_GAUGE.labels(CARRIER).set(
        db.scalar(
            select(func.count())
            .select_from(ShipmentEvent)
            .where(ShipmentEvent.is_dirty.is_(True))
        )
    )
    run_counts = db.execute(
        select(GenerationRun.status, func.count()).group_by(GenerationRun.status)
    )
    for status in ("started", "completed", "failed"):
        GENERATION_RUNS_GAUGE.labels(CARRIER, status).set(0)
    for status, count in run_counts:
        GENERATION_RUNS_GAUGE.labels(CARRIER, status).set(count)
    GENERATED_EVENTS_GAUGE.labels(CARRIER).set(
        db.scalar(
            select(func.coalesce(func.sum(GenerationRun.events_inserted), 0))
        )
    )

    return Response(
        content=generate_latest(METRICS_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/shipments")
def list_shipments(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Shipment)
        .order_by(Shipment.tracking_number)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [shipment_value(row) for row in rows]
    return {
        "carrier_code": CARRIER,
        "results": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(items),
        },
    }


@app.get("/shipments/{tracking_number}")
def get_shipment(
    tracking_number: str,
    scenario: str | None = None,
    db: Session = Depends(get_db),
):
    apply_scenario(scenario)
    row = db.get(Shipment, tracking_number)
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {"carrier": CARRIER, "shipment": shipment_value(row)}


@app.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(ShipmentEvent)
        .order_by(ShipmentEvent.event_key)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [event_value(row) for row in rows]
    return {
        "carrier": CARRIER,
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(items),
        },
    }
