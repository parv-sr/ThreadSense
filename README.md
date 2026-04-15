# 🧵 ThreadSense v2

> **ThreadSense** is an end-to-end WhatsApp real-estate intelligence pipeline.
> It ingests chat exports, extracts structured property listings, embeds them, indexes them in Qdrant, and serves RAG-powered search/chat.

---

## ✨ What this project does

ThreadSense converts noisy WhatsApp messages into searchable listing intelligence:

1. 📥 **Ingestion** — upload `.txt` / `.zip` / `.rar` WhatsApp exports.
2. 🧹 **Preprocessing** — parser + dedupe + junk/system filtering.
3. 🧠 **Extraction** — LLM-based structured listing extraction (batched + retried).
4. 🔎 **Embedding + Vector Indexing** — OpenAI embeddings upserted to Qdrant.
5. 💬 **RAG Chat** — query listings through an API + frontend.

---

## 🏗️ Monorepo layout

```text
ThreadSense/
├── backend/                 # FastAPI app + async workers + SQLAlchemy models
│   ├── src/
│   │   ├── api/             # REST endpoints (/ingest, /chat)
│   │   ├── tasks/           # TaskIQ tasks (ingestion, extraction, embeddings)
│   │   ├── preprocessing/   # LLM extraction pipeline
│   │   ├── embeddings/      # Qdrant + embedding service
│   │   ├── rag/             # Retrieval and agent orchestration
│   │   ├── models/          # SQLAlchemy models
│   │   ├── db/              # async engine/session/config
│   │   └── startup.py       # migration + Qdrant bootstrap
├── frontend/                # Vite + React UI
├── rust_parser/             # Rust-accelerated WhatsApp parser
├── docker-compose.yml       # API + worker runtime
├── Dockerfile               # unified image for API/worker
└── Makefile                 # convenience commands
```

---

## 🧰 Tech stack

- ⚡ **FastAPI** (backend API)
- 🧵 **TaskIQ + Redis** (background jobs)
- 🐘 **PostgreSQL / Supabase** (relational store)
- 🧠 **OpenAI** (extraction + embeddings)
- 📌 **Qdrant** (vector store)
- 🦀 **Rust parser (maturin)** for WhatsApp parsing
- 🎨 **React + Vite** frontend

---

## 🔄 Data flow (high level)

```mermaid
flowchart LR
A[Upload WhatsApp export] --> B[Raw files + chunks]
B --> C[Preprocess + dedupe]
C --> D[LLM extraction to structured listings]
D --> E[Create listing_chunks]
E --> F[Embedding generation]
F --> G[Qdrant upsert]
G --> H[RAG retrieval + chat response]
```

---

## 🚀 Quick start

### 1) Prerequisites

- Docker + Docker Compose
- OpenAI API key
- Redis URL/token
- Postgres/Supabase connection URL
- Qdrant endpoint + API key

### 2) Configure environment

Create a `.env` at repo root:

```bash
# App
APP_ENV=production
DEBUG=false

# OpenAI
OPENAI_API_KEY=your_openai_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800

# Redis / TaskIQ
REDIS_URL=redis://host:6379/0
REDIS_TOKEN=
TASKIQ_RESULT_TTL_SECONDS=3600

# Qdrant
QDRANT_URL=
QDRANT_CLUSTER_ENDPOINT=https://<cluster>.<region>.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_key

# Ingestion limits
INGEST_MAX_BYTES=52428800
INGEST_MAX_RETRIES=3

# Extractor packet tuning
MESSAGES_PER_PACKET=15
MAX_CONCURRENT_PACKETS=6
```

### 3) Run with Docker

```bash
docker compose up --build
```

Services started:

- 🌐 API: `http://localhost:8000`
- 👷 Worker: TaskIQ worker (background processing)

### 4) Frontend (optional local)

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Development commands

### Backend quality checks

```bash
uv run ruff check backend/src
uv run python -m compileall backend/src
```

### Run tests

```bash
OPENAI_API_KEY=dummy PYTHONPATH=. uv run pytest
```

> ℹ️ Some tests/integration paths require reachable Postgres/Redis/Qdrant.

---

## 📡 Core API endpoints

### `POST /ingest/`
Upload WhatsApp export for pipeline processing.

- accepted: `.txt`, `.zip`, `.rar`
- response includes `task_id` and `rawfile_id`

### `POST /chat/`
Ask natural-language queries over indexed listings.

### `GET /chat/source/{chunk_id}`
Fetch original source chunk for traceability.

### `GET /health`
Basic service liveness.

---

## ⚙️ Background tasks

- `ingest_raw_file_task` → parses + dedupes incoming file.
- `preprocess_rawfile_task` → batch LLM extraction into `property_listings` / `listing_chunks`.
- `embed_property_listing_task` → embeddings + Qdrant upsert.

---

## 🧠 Extraction subsystem notes

The extractor is designed for **accuracy + throughput**:

- ✅ batched packet processing (`MESSAGES_PER_PACKET`)
- ✅ bounded concurrency (`MAX_CONCURRENT_PACKETS` + semaphore)
- ✅ strict structured output (Pydantic schema)
- ✅ robust value normalization (price, phone, furnishing, area)
- ✅ retry with exponential backoff (tenacity)
- ✅ irrelevance gating and confidence scoring

---

## 📦 Qdrant schema conventions

ThreadSense uses named dense vectors:

- Collection: `threadsense_listings`
- Vector name: `dense`

Ensure the existing collection matches this schema before upserts/retrieval.

---

## 🗃️ Database probe parity checks

Use this Alembic preflight command to print the migration-path DB probe **without** applying migrations:

```bash
alembic -c backend/alembic.ini -x preflight=true upgrade head
```

The command prints:

- masked `database_url`
- `current_database()`
- `current_schema()`
- `inet_server_addr()`
- `inet_server_port()`

At runtime, API startup logs print the same fields to compare migration-path and runtime-path targets.

---

## 🛠️ Troubleshooting

### 1) Too many DB clients (`MaxClientsInSessionMode`)

- reduce worker concurrency (`--workers`, `--max-async-tasks`)
- lower DB pool settings and align with Supabase limits

### 2) Qdrant bad request (`Not existing vector name`)

- verify collection vector schema uses named vector `dense`
- ensure upserts use `{ "dense": vector }`

### 3) Too many null extractions

- validate `OPENAI_API_KEY`
- inspect worker logs for parsing failures
- tune `MESSAGES_PER_PACKET` / `MAX_CONCURRENT_PACKETS`

---

## 🔐 Security & ops recommendations

- Keep secrets in environment variables or secret manager.
- Do not commit `.env`.
- Rotate API keys periodically.
- Add per-environment observability (structured logs, error alerts).

---

## 🗺️ Roadmap ideas

- Hybrid retrieval (dense + sparse) for harder matching
- Better multilingual extraction
- Listing change detection / dedupe across historical uploads
- Fine-grained confidence calibration + QA dashboards

---

## 🤝 Contributing

1. Create feature branch.
2. Make small, focused commits.
3. Run lint/tests.
4. Open PR with clear validation steps.

---

## 📄 License

Internal / project-specific (add official license file if open-sourcing).
