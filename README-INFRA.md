# Type B Simulator Infrastructure

This bundle prepares the container infrastructure and Python dependencies for four independent carrier simulators.

## Database allocation

- Carrier A: PostgreSQL
- Carrier B: MySQL
- Carrier C: MongoDB
- Carrier D: SQLite stored in a Docker volume

The APIs use ports 8001, 8002, 8003, and 8004 on the host.

## Metrics

Each carrier exposes Prometheus text-format metrics at `/metrics`:

- Carrier A: `http://localhost:8001/metrics`
- Carrier B: `http://localhost:8002/metrics`
- Carrier C: `http://localhost:8003/metrics`
- Carrier D: `http://localhost:8004/metrics`

The endpoint reports the current shipment and event counts, dirty event count,
generation runs grouped by status, and total events reported as inserted.

## Setup

1. Copy `.env.example` to `.env`.
2. Keep `.env` local. Never commit it.
3. Ensure the existing `services/carrier_a/app/main.py` through `carrier_d/app/main.py` files are present.
4. Validate the Compose configuration:
   `docker compose --env-file .env config`
5. Build and start:
   `docker compose --env-file .env up --build -d`
6. Inspect status and logs:
   `docker compose ps`
   `docker compose logs -f carrier_a carrier_b carrier_c carrier_d`

## Important

This bundle configures containers, volumes, environment variables, and dependencies. The existing Python application code must still read the relevant environment variables and implement database connection/session logic before data is actually persisted.

- Carrier A and B use `DATABASE_URL` with SQLAlchemy.
- Carrier C uses `MONGODB_URL` and `MONGODB_DATABASE` with PyMongo.
- Carrier D can use `DATABASE_URL` or `DATABASE_PATH` with SQLite.

Database ports are intentionally not published to the host. The APIs reach their own databases through isolated Docker networks.
Relational migrations and MongoDB index initialization run automatically before
each carrier API starts.

For local development only, `.env.example` contains placeholder credentials. Replace them for any shared or deployed environment. Use URL-safe passwords for the initial connection URLs; otherwise percent-encode reserved characters.

To stop containers without deleting database data:
`docker compose down`

Do not run `docker compose down -v` unless you intentionally want to delete all named database volumes.
