import os
import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)
from pymongo import MongoClient

CARRIER = "C"
RATE_LIMIT = max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))
client = MongoClient(
    os.environ["MONGODB_URL"],
    serverSelectionTimeoutMS=5000,
)
db = client[os.getenv("MONGODB_DATABASE", "carrier_c_db")]
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

app = FastAPI(title="Carrier C API", version="1.0.0")
requests_by_ip = defaultdict(list)


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


def scenario_error(scenario):
    # Simulate integration errors without changing persisted documents.
    cases = {
        "not_found": (404, "Simulated shipment not found"),
        "rate_limited": (429, "Simulated rate limit"),
        "server_error": (500, "Simulated internal server error"),
        "unavailable": (503, "Simulated service unavailable"),
    }
    if scenario in cases:
        code, message = cases[scenario]
        raise HTTPException(status_code=code, detail=message)


def clean(document):
    if document is not None:
        document.pop("_id", None)
    return document


@app.get("/health")
def health():
    client.admin.command("ping")
    return {"carrier": CARRIER, "status": "ok", "database": "connected"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    SHIPMENTS_GAUGE.labels(CARRIER).set(db["shipments"].count_documents({}))
    SHIPMENT_EVENTS_GAUGE.labels(CARRIER).set(db["events"].count_documents({}))
    DIRTY_EVENTS_GAUGE.labels(CARRIER).set(
        db["events"].count_documents({"is_dirty": True})
    )
    run_counts = db["generation_runs"].aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    )
    for status in ("started", "completed", "failed"):
        GENERATION_RUNS_GAUGE.labels(CARRIER, status).set(0)
    for run in run_counts:
        GENERATION_RUNS_GAUGE.labels(CARRIER, run["_id"]).set(run["count"])
    inserted_events = db["generation_runs"].aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$events_inserted"}}}]
    )
    total = next(inserted_events, {"total": 0}).get("total", 0)
    GENERATED_EVENTS_GAUGE.labels(CARRIER).set(total)

    return Response(
        content=generate_latest(METRICS_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/shipments")
def list_shipments(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    items = [
        clean(document)
        for document in db["shipments"].find().skip(offset).limit(limit)
    ]
    return {
        "carrier": CARRIER,
        "shipment_documents": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(items),
        },
    }


@app.get("/shipments/{tracking_number}")
def get_shipment(tracking_number: str, scenario: str | None = None):
    scenario_error(scenario)
    document = db["shipments"].find_one({"tracking_number": tracking_number})
    if document is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {"carrier": CARRIER, "shipment_document": clean(document)}


@app.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    items = [
        clean(document)
        for document in db["events"].find().skip(offset).limit(limit)
    ]
    return {
        "carrier": CARRIER,
        "event_documents": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(items),
        },
    }
