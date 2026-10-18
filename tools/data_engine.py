import hashlib
import json
import os
import random
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, UpdateOne
from sqlalchemy import MetaData, Table, Column, String, Text, Boolean, Integer, create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

CARRIERS = {
    "A": {"url": os.getenv("CARRIER_A_DATABASE_URL"), "statuses": ["REGISTERED", "COLLECTED", "IN_ROUTE", "AT_HUB", "DELIVERED", "RETURNED"]},
    "B": {"url": os.getenv("CARRIER_B_DATABASE_URL"), "statuses": ["CREATED", "PICKED_UP", "MOVING", "ARRIVED", "COMPLETED", "REJECTED"]},
    "C": {"url": os.getenv("MONGODB_URL"), "statuses": ["NEW", "ACCEPTED", "TRANSIT", "LOCAL_DEPOT", "DONE", "INCIDENT"]},
    "D": {"url": os.getenv("CARRIER_D_DATABASE_URL"), "statuses": ["OPEN", "RECEIVED", "ON_ROUTE", "BRANCH", "FINISHED", "RETURN"]},
}
DB_NAME = os.getenv("MONGODB_DATABASE", "carrier_c_db")
SEED = int(os.getenv("SEED", "42"))
DIRTY_RATE = float(os.getenv("DIRTY_RATE", "0.10"))

metadata = MetaData()
shipments = Table("shipments", metadata,
    Column("tracking_number", String(120), primary_key=True),
    Column("current_status", String(120)), Column("updated_at", String(120)), Column("raw_data", Text))
events = Table("shipment_events", metadata,
    Column("event_key", String(180), primary_key=True), Column("cycle_id", String(100), nullable=False),
    Column("tracking_number", String(120)), Column("event_status", String(120)),
    Column("event_time", String(120)), Column("raw_data", Text), Column("is_dirty", Boolean, nullable=False))
runs = Table("generation_runs", metadata,
    Column("cycle_id", String(100), primary_key=True), Column("started_at", String(50)),
    Column("finished_at", String(50)), Column("events_requested", Integer, nullable=False),
    Column("events_inserted", Integer, nullable=False), Column("status", String(30), nullable=False))

def get_engine(carrier):
    url = CARRIERS[carrier]["url"]
    if not url:
        raise RuntimeError(f"Database URL for carrier {carrier} is missing")
    return create_engine(url, pool_pre_ping=True)

def rng_for(key):
    digest = hashlib.sha256(key.encode()).hexdigest()[:8]
    return random.Random(int(digest, 16) ^ SEED)

def insert_idempotent(engine, table, rows, key):
    if not rows:
        return
    dialect = engine.dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(table).values(rows).on_conflict_do_nothing(index_elements=[key])
    elif dialect == "mysql":
        ins = mysql_insert(table).values(rows)
        stmt = ins.on_duplicate_key_update(**{key: ins.inserted[key]})
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(rows).on_conflict_do_nothing(index_elements=[key])
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    with engine.begin() as conn:
        conn.execute(stmt)

def defect_names(carrier):
    return {
        "A": ["date_format", "out_of_order", "missing_field"],
        "B": ["date_format", "unknown_status", "invalid_tracking", "missing_field", "orphan_event"],
        "C": ["out_of_order", "unknown_status", "duplicate_event", "missing_field", "wrong_type"],
        "D": ["out_of_order", "unknown_status", "invalid_tracking", "wrong_type"],
    }[carrier]

def make_event(carrier, cycle_id, i, tracking, rng, dirty):
    statuses = CARRIERS[carrier]["statuses"]
    status = statuses[i % len(statuses)]
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=7*i)
    event_time = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = {"source": f"carrier_{carrier.lower()}", "sequence": i, "status": status, "event_time": event_time}
    defect = None
    if dirty:
        defect = rng.choice(defect_names(carrier))
        if defect == "date_format":
            event_time = stamp.strftime("%d/%m/%Y %H:%M:%S")
        elif defect == "out_of_order":
            event_time = (stamp - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif defect == "unknown_status":
            status = "STATUS_NOT_MAPPED"
        elif defect == "missing_field":
            if i % 2:
                tracking = None
            else:
                status = None
        elif defect in ("invalid_tracking", "orphan_event"):
            tracking = f"INVALID-{carrier}-{i:07d}"
        elif defect == "wrong_type":
            raw["sequence"] = str(i)
            raw["event_time"] = i
            if carrier == "D":
                event_time = str(i)
        elif defect == "duplicate_event":
            # Repite el contenido lógico de otro evento, pero conserva una clave técnica única.
            duplicate_index = i % 100
            status = statuses[duplicate_index % len(statuses)]
            event_time = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=7 * duplicate_index)).strftime("%Y-%m-%dT%H:%M:%SZ")
            raw["duplicate_signature"] = f"{carrier}-{duplicate_index}"
        raw["intentional_defect"] = defect
    return {
        "event_key": f"{cycle_id}-{carrier}-{i:07d}", "cycle_id": cycle_id,
        "tracking_number": tracking, "event_status": status, "event_time": event_time,
        "raw_data": json.dumps(raw, separators=(",", ":")), "is_dirty": dirty,
    }

def seed_relational(carrier, count, cycle_id):
    engine = get_engine(carrier)
    rand = rng_for(f"seed-{carrier}-{SEED}")
    shipment_count = max(1000, count // 5)
    # Timestamp fijo para que la semilla produzca el mismo contenido en ejecuciones nuevas.
    now = "2026-01-01T00:00:00Z"
    shipment_rows = [{"tracking_number": f"{carrier}-SEED-{i+1:07d}",
        "current_status": CARRIERS[carrier]["statuses"][i % 6], "updated_at": now,
        "raw_data": json.dumps({"seed": SEED, "carrier": carrier})} for i in range(shipment_count)]
    for start in range(0, len(shipment_rows), 1000):
        insert_idempotent(engine, shipments, shipment_rows[start:start+1000], "tracking_number")
    batch = []
    dirty_count = int(count * DIRTY_RATE)
    for i in range(count):
        batch.append(make_event(carrier, cycle_id, i, f"{carrier}-SEED-{(i % shipment_count)+1:07d}", rand, i < dirty_count))
        if len(batch) == 1000:
            insert_idempotent(engine, events, batch, "event_key")
            batch = []
    insert_idempotent(engine, events, batch, "event_key")
    insert_idempotent(engine, runs, [{"cycle_id": cycle_id, "started_at": now,
        "finished_at": datetime.now(timezone.utc).isoformat(), "events_requested": count,
        "events_inserted": count, "status": "completed"}], "cycle_id")
    engine.dispose()

def seed_mongo(count, cycle_id):
    client = MongoClient(CARRIERS["C"]["url"], serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    db["shipments"].create_index("tracking_number", unique=True)
    db["events"].create_index("event_key", unique=True)
    db["generation_runs"].create_index("cycle_id", unique=True)
    shipment_count = max(1000, count // 5)
    # Timestamp fijo para mantener reproducible el conjunto inicial.
    now = "2026-01-01T00:00:00Z"
    db["shipments"].bulk_write([UpdateOne({"tracking_number": f"C-SEED-{i+1:07d}"},
        {"$setOnInsert": {"tracking_number": f"C-SEED-{i+1:07d}", "current_status": CARRIERS["C"]["statuses"][i % 6],
        "updated_at": now, "seed": SEED}}, upsert=True) for i in range(shipment_count)], ordered=False)
    rand = rng_for(f"seed-C-{SEED}")
    batch = []
    for i in range(count):
        event = make_event("C", cycle_id, i, f"C-SEED-{(i % shipment_count)+1:07d}", rand, i < int(count*DIRTY_RATE))
        raw = json.loads(event["raw_data"])
        if raw.get("intentional_defect") == "wrong_type":
            event["event_time"] = i
            event["event_status"] = i
        event["raw_data"] = raw
        batch.append(UpdateOne({"event_key": event["event_key"]}, {"$setOnInsert": event}, upsert=True))
        if len(batch) == 1000:
            db["events"].bulk_write(batch, ordered=False); batch=[]
    if batch:
        db["events"].bulk_write(batch, ordered=False)
    db["generation_runs"].update_one({"cycle_id": cycle_id}, {"$setOnInsert": {
        "cycle_id": cycle_id, "started_at": now, "finished_at": datetime.now(timezone.utc).isoformat(),
        "events_requested": count, "events_inserted": count, "status": "completed"}}, upsert=True)
    client.close()

def generate_cycle(carrier, count, cycle_id):
    # Los identificadores estables permiten reintentar un ciclo sin duplicar eventos.
    if carrier == "C":
        seed_mongo_cycle(count, cycle_id)
        return
    engine = get_engine(carrier)
    rand = rng_for(f"{cycle_id}-{carrier}")
    now = datetime.now(timezone.utc).isoformat()
    shipment_count = max(1000, int(os.getenv("SEED_EVENTS_PER_CARRIER", "50000")) // 5)
    batch = []
    for i in range(count):
        tracking = f"{carrier}-SEED-{(i % shipment_count)+1:07d}"
        if i % 100 == 0:
            tracking = f"{carrier}-{cycle_id[-12:]}-{i:07d}"
            insert_idempotent(engine, shipments, [{"tracking_number": tracking,
                "current_status": CARRIERS[carrier]["statuses"][i % 6], "updated_at": now,
                "raw_data": json.dumps({"created_by_cycle": cycle_id})}], "tracking_number")
        batch.append(make_event(carrier, cycle_id, i, tracking, rand, i < int(count*DIRTY_RATE)))
        if len(batch) == 1000:
            insert_idempotent(engine, events, batch, "event_key"); batch=[]
    insert_idempotent(engine, events, batch, "event_key")
    insert_idempotent(engine, runs, [{"cycle_id": cycle_id, "started_at": now,
        "finished_at": datetime.now(timezone.utc).isoformat(), "events_requested": count,
        "events_inserted": count, "status": "completed"}], "cycle_id")
    engine.dispose()

def seed_mongo_cycle(count, cycle_id):
    client = MongoClient(CARRIERS["C"]["url"], serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    db["events"].create_index("event_key", unique=True)
    rand = rng_for(f"{cycle_id}-C")
    shipment_count = max(1000, int(os.getenv("SEED_EVENTS_PER_CARRIER", "50000")) // 5)
    now = datetime.now(timezone.utc).isoformat()
    batch = []
    for i in range(count):
        tracking = f"C-SEED-{(i % shipment_count)+1:07d}"
        if i % 100 == 0:
            tracking = f"C-{cycle_id[-12:]}-{i:07d}"
            db["shipments"].update_one({"tracking_number": tracking}, {"$setOnInsert": {
                "tracking_number": tracking, "current_status": CARRIERS["C"]["statuses"][i % 6],
                "updated_at": now, "created_by_cycle": cycle_id}}, upsert=True)
        event = make_event("C", cycle_id, i, tracking, rand, i < int(count*DIRTY_RATE))
        event["raw_data"] = json.loads(event["raw_data"])
        if event["raw_data"].get("intentional_defect") == "wrong_type":
            event["event_time"] = i
            event["event_status"] = i
        batch.append(UpdateOne({"event_key": event["event_key"]}, {"$setOnInsert": event}, upsert=True))
        if len(batch) == 1000:
            db["events"].bulk_write(batch, ordered=False); batch=[]
    if batch:
        db["events"].bulk_write(batch, ordered=False)
    db["generation_runs"].update_one({"cycle_id": cycle_id}, {"$setOnInsert": {
        "cycle_id": cycle_id, "started_at": now, "finished_at": datetime.now(timezone.utc).isoformat(),
        "events_requested": count, "events_inserted": count, "status": "completed"}}, upsert=True)
    client.close()
