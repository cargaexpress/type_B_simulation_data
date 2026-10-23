# CargaExpress Type B Carrier Simulators

## Overview

This project provides four independent REST APIs that simulate Type B shipping carriers for the CargaExpress Supply Chain project.

Type B carriers expose APIs that the Control Tower can query by tracking number. The simulators generate synthetic shipment and tracking-event data to support integration, testing, and development.

Each carrier has its own API service, database technology, data format, and tracking-state conventions.

## Project Objectives

- Simulate four independent Type B carrier APIs.
- Provide shipment and tracking-event endpoints.
- Generate synthetic shipment and event data.
- Simulate different carrier status catalogs and date formats.
- Support rate limiting and error scenarios.
- Run the services and data generator using Docker Compose.
- Provide a reproducible local environment for integration testing.

## Architecture

| Service | Database | Local API port |
|---|---|---:|
| Carrier A | PostgreSQL | 8001 |
| Carrier B | MySQL | 8002 |
| Carrier C | MongoDB | 8003 |
| Carrier D | SQLite | 8004 |

The project also includes:

- **Seed process:** creates the initial synthetic dataset.
- **Data generator:** periodically creates additional tracking events.
- **Docker Compose:** coordinates the containers and their dependencies.

The seed process and the periodic generator have different responsibilities. The seed initializes the dataset, while the generator adds new events during execution.

## Technology Stack

- Python
- FastAPI
- PostgreSQL
- MySQL
- MongoDB
- SQLite
- Docker
- Docker Compose
- SQLAlchemy and database-specific drivers, where applicable

## Project Structure

```text
simulador_type_b/
├── services/
│   ├── carrier_a/
│   │   └── app/
│   │       └── main.py
│   ├── carrier_b/
│   │   └── app/
│   │       └── main.py
│   ├── carrier_c/
│   │   └── app/
│   │       └── main.py
│   └── carrier_d/
│       └── app/
│           └── main.py
├── tools/
│   ├── generator.py
│   ├── data_engine.py
│   └── seed_all.py
├── compose.yaml
├── README.md
└── ...
```

This structure highlights the main components. Additional configuration files, Dockerfiles, tests, and database initialization scripts may exist in the repository.

## Requirements

Install the following tools before starting the project:

- Docker Desktop
- Docker Compose v2
- Git

Make sure Docker Desktop is running.

## Running the Project

Open a terminal in the project root directory:

```powershell
cd "$HOME\Desktop\cargaExpress\simulador_type_b"
```

Build the images and start the services:

```bash
docker compose up --build -d
```

Check the container status:

```bash
docker compose ps
```

Inspect the generator logs:

```bash
docker compose logs -f generator
```

Inspect the seed process logs:

```bash
docker compose logs seed
```

The seed process is expected to finish after initializing the dataset. The generator is expected to remain running and produce additional events according to its configured schedule.

Container names and service names must match those defined in `compose.yaml`.

## API Documentation

FastAPI provides interactive API documentation through Swagger UI.

| Carrier | Swagger UI |
|---|---|
| Carrier A | http://localhost:8001/docs |
| Carrier B | http://localhost:8002/docs |
| Carrier C | http://localhost:8003/docs |
| Carrier D | http://localhost:8004/docs |

Open the corresponding URL in a browser to inspect the endpoints and execute requests.

## Available Endpoints

The carrier APIs provide the following operations.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Check service health. |
| `GET /shipments` | List shipments. |
| `GET /shipments/{tracking_number}` | Retrieve a shipment by tracking number. |
| `GET /events` | Retrieve tracking events using pagination. |
| `GET /metrics` | Retrieve available service metrics. |

The exact response fields and response-envelope names may differ between carriers. Use each service's OpenAPI documentation as the authoritative reference.

### Query Parameters

The event endpoint supports pagination through:

- `limit`: maximum number of records to return.
- `offset`: number of records to skip.

The default limit is 100, and the maximum limit is 1,000.

Example:

```http
GET /events?limit=100&offset=0
```

Example shipment lookup:

```http
GET /shipments/RX-83921
```

Replace the tracking number with one that exists in the selected carrier's database.

## Automatic Event Generation

The generator is configured to produce **10,000 events per carrier per cycle**, with a default interval of **1,800 seconds (30 minutes)**.

The generator processes the four carriers and then waits for the configured interval before starting another cycle.

Because the waiting period occurs after generation, the elapsed time between cycle starts can exceed 30 minutes.

To monitor generation:

```bash
docker compose logs -f generator
```

To check the running containers:

```bash
docker compose ps
```

The actual event counts and timing should be verified through the generator logs and the carrier APIs.

## Stopping the Project

To stop and remove the containers without intentionally deleting their persistent volumes:

```bash
docker compose down
```

Start the project again with:

```bash
docker compose up -d
```

Persistent database data may remain available after stopping the containers.

## Resetting the Data

**Warning: a full reset may permanently delete locally persisted shipment and event data.**

Docker Compose volumes may contain the databases used by the simulators. Removing those volumes is different from simply restarting the services.

Before performing a full reset, verify the following in `compose.yaml` and the seed implementation:

1. Which volumes store the persistent data for each carrier.
2. Whether the seed service runs automatically when the stack starts.
3. Whether the seed recreates the initial dataset after the databases are empty.
4. Whether the seed operation is idempotent and whether it removes or preserves existing records.

The following command removes the Compose-managed containers and volumes:

```bash
docker compose down -v
```

**Do not run this command if you need to preserve existing data.** Also verify that the volumes are not shared with other projects.

After confirming the seed configuration, rebuild and start the environment:

```bash
docker compose up --build -d
```

Check that the seed finishes successfully and that the generator starts. A successful container startup alone does not prove that the initial dataset was restored correctly.

If you only want to restart the generator without resetting the databases, use:

```bash
docker compose restart generator
```

Restarting the generator does not necessarily create a new initial dataset or clear existing events.

## Troubleshooting

### A container exits unexpectedly

Inspect its logs:

```bash
docker compose logs --tail=100 <service_name>
```

Replace `<service_name>` with the relevant service name.

### An API does not respond

Check the container status:

```bash
docker compose ps
```

Inspect the relevant carrier logs and confirm that the expected port is available.

### The generator does not appear to create events

Inspect the generator logs:

```bash
docker compose logs --tail=200 generator
```

Check for database connection errors, failed writes, and the configured generation interval.

### The seed service has exited

A completed seed process is expected to exit after initialization. Verify that it exited successfully and that the databases contain the expected records.

## Data and Integration Notes

- All shipment and tracking data is synthetic.
- Each carrier can use its own status catalog and date representation.
- Tracking events may intentionally arrive out of chronological order.
- Pagination does not, by itself, guarantee incremental event ingestion.
- The Control Tower integration contract must determine how events are consumed, deduplicated, and processed.

## Scope and Limitations

This repository implements the Type B carrier simulation layer. It does not, by itself, implement the complete CargaExpress Supply Chain solution.

The broader project also requires event ingestion, canonical status mapping, SLA calculations, responsibility attribution, penalties, data pipelines, analytics, and deployment in AWS.

## Development Guidelines

- Keep carrier services independently testable.
- Document API contracts using OpenAPI.
- Keep database configuration outside source code where appropriate.
- Avoid committing credentials or secrets.
- Validate seed reproducibility and idempotency through automated tests.
- Verify data generation and reset behavior before destructive operations.

## Docker Multi-Stage Builds & Optimization (RIWI-168)

All services (carrier_a, carrier_b, carrier_c, carrier_d, 	ools) use multi-stage Docker builds based on python:3.12-slim:

1. **Builder Stage**: Resolves dependencies using uv into a dedicated virtual environment (/app/.venv) with bytecode pre-compilation (UV_COMPILE_BYTECODE=1).
2. **Runtime Stage**: Copies solely the pre-compiled virtual environment and application code into a clean python:3.12-slim base, running as unprivileged user ppuser (uid=1000, gid=1000). Build tools (uv, compiler artifacts) are eliminated from the final image.
3. **Storage Isolation**: Services interacting with local storage (such as Carrier D and Tools using SQLite at /data/carrier_d.sqlite3) create /data owned by ppuser.

### Build Commands

`ash
# Build all services via Compose
docker compose build

# Build individual carriers
docker build -t cargaexpress-carrier-a:latest ./services/carrier_a
docker build -t cargaexpress-carrier-b:latest ./services/carrier_b
docker build -t cargaexpress-carrier-c:latest ./services/carrier_c
docker build -t cargaexpress-carrier-d:latest ./services/carrier_d

# Build seed & generator tools
docker build -f tools/Dockerfile -t cargaexpress-type-b-tools:latest .
`

### Security & Verification Commands

`ash
# Verify non-root user
docker run --rm cargaexpress-carrier-a:latest whoami
# appuser

# Verify UID/GID
docker run --rm cargaexpress-carrier-a:latest id
# uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)

# Verify absence of build tools
docker run --rm cargaexpress-carrier-a:latest which uv
# (exits with 1, not found)
`

### Benchmarking & Size Optimization

| Component | Single-Stage Baseline | Multi-Stage Optimized | Content Size (Compressed) | Reduction | User |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Carrier A (PostgreSQL)** | 485 MB | **305 MB** | 71.0 MB | **-37.1%** | ppuser (1000) |
| **Carrier B (MySQL)** | 460 MB | **278 MB** | 65.2 MB | **-39.5%** | ppuser (1000) |
| **Carrier C (MongoDB)** | 435 MB | **249 MB** | 58.8 MB | **-42.7%** | ppuser (1000) |
| **Carrier D (SQLite)** | 455 MB | **277 MB** | 65.1 MB | **-39.1%** | ppuser (1000) |
| **Tools (Seed / Generator)** | 425 MB | **258 MB** | 60.4 MB | **-39.3%** | ppuser (1000) |

## License

This project is developed for the CargaExpress Supply Chain educational project.
