**ThreadSense** is a high-performance, self-hosted intelligence pipeline that transforms raw WhatsApp real-estate chat exports into structured, searchable property listings. 

It combines a fast Rust parser for ingestion, LLM-powered extraction via OpenRouter, relational storage in PostgreSQL, and vector search with pgvector. The system provides both a fast database explorer and a conversational LangGraph assistant.

### Key Features

- **High-speed ingestion** — Preserved Rust parser for efficient WhatsApp chat parsing.
- **Accurate structured extraction** — Strict Pydantic schemas with OpenRouter LLMs, batching, retries, and normalization.
- **Hybrid search** — Hard SQL filters combined with optional pgvector semantic ranking.
- **Dual interfaces**:
  - `/search`: Fast faceted explorer with pagination, bulk operations, and source verification.
  - `/chat`: LangGraph-powered conversational assistant for complex, comparative queries.
- **Production-ready deployment** — Docker Compose with Caddy reverse proxy for TLS termination.
- **Authentication** — JWT-based admin and user authentication.

### Architecture

```
ThreadSense/
├── rust_parser/          # High-performance WhatsApp parser (preserved from earlier versions)
├── backend/              # FastAPI application
│   ├── src/
│   │   ├── api/          # REST endpoints for listings, chat, auth
│   │   ├── core/         # Configuration and security
│   │   ├── db/           # SQLAlchemy + async sessions
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── preprocessing/# LLM extraction pipeline
│   │   ├── embeddings/   # Vector embedding and storage
│   │   ├── rag/          # LangGraph orchestration
│   │   └── tasks/        # Background workers (Celery)
│   ├── alembic/          # Database migrations
│   └── tests/
├── frontend/             # React + TypeScript + Vite + Tailwind
├── docker-compose.yml    # Multi-service orchestration
├── Caddyfile             # Reverse proxy and TLS
├── Dockerfile            # Unified build
└── pyproject.toml        # Python dependencies (uv)
```

**Core Services**:
- **PostgreSQL + pgvector**: Primary store for raw text, structured listings, and embeddings.
- **Redis**: Celery broker and LangGraph checkpoint store.
- **Caddy**: Self-hosted reverse proxy with automatic TLS.
- **FastAPI backend**: REST API + background task workers.
- **React frontend**: Static build served via Caddy.

### Quick Start

1. **Clone the repository** (inference branch):
   ```bash
   git clone https://github.com/parv-sr/ThreadSense.git
   cd ThreadSense
   git checkout inference
   ```

2. **Configure environment**:
   Copy and edit the example files:
   ```bash
   cp backend/.env.example .env
   # Update required variables (see Environment section)
   ```

3. **Start the stack**:
   ```bash
   docker compose up --build
   ```

   The application will be available at `http://localhost` (or the domain configured via `THREADSENSE_DOMAIN`).

4. **Default Admin Credentials**:
   - Use the admin password set in environment variables (default handling improved in recent commits).

### Environment Variables

Create a `.env` file at the project root based on checked-in examples. Key variables include:

- `OPENROUTER_API_KEY`: API key for LLM extraction and embeddings.
- `OPENROUTER_BASE_URL`: `https://openrouter.ai/api/v1`
- `OPENROUTER_CHAT_MODEL`: Recommended `google/gemini-1.5-flash`
- `OPENROUTER_EMBEDDING_MODEL`: Recommended `openai/text-embedding-3-small`
- PostgreSQL credentials (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)
- `THREADSENSE_DOMAIN`: Domain for Caddy (use `localhost` for local development)
- Authentication and other service-specific settings.

### API Highlights

- `GET /api/listings/facets` — Live SQL aggregates for filters.
- `GET /api/listings` — Filtered listings with optional semantic reranking.
- `POST /api/listings/delete` — Bulk deletion.
- `GET /api/chat/source/{listing_id}` — Raw WhatsApp source verification.
- `POST /api/chat` — LangGraph conversational interface.
- Authentication endpoints for login and admin access.

### Frontend Workflows

- **Search Page** (`/search`): Advanced filtering, pagination, semantic search toggle, bulk delete, and source modals.
- **Chat Page** (`/chat`): Natural language queries with deterministic listing references.
- Listing IDs link directly to original chat sources for full traceability.

### Development and Validation

**Frontend**:
```bash
cd frontend
npm run typecheck
npm run build
```

**Backend**:
```bash
python -m pytest backend/tests/
```

**Docker**:
```bash
docker compose config
docker compose up --build
```

### Technology Stack

- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, Celery, LangGraph, Pydantic
- **Database**: PostgreSQL with pgvector extension
- **Vector Search**: Native pgvector (single source of truth)
- **LLM Provider**: OpenRouter (configurable models)
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Parsing**: Rust (maturin/pyo3 integration)
- **Proxy**: Caddy
- **Containerization**: Docker Compose

### Project Status

The `inference` branch represents an evolved architecture focused on:
- PostgreSQL + pgvector as the unified backend (removing external vector stores).
- Enhanced authentication system.
- Simplified deployment and reduced operational complexity.
- Maintained high-fidelity Rust parsing and robust LLM extraction.

### Contributing

1. Fork the repository.
2. Create a feature branch from `inference`.
3. Make focused, atomic commits.
4. Ensure all tests pass and run validation commands.
5. Submit a pull request with clear description and testing steps.

---

**License**: This project is for personal and internal use. Contact the maintainer for licensing questions.
