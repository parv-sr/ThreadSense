# ThreadSense Ultimate

ThreadSense ingests raw WhatsApp real-estate chats, preserves the high-speed Rust parser, extracts strict listing fields through OpenRouter, and stores raw text, relational inventory, and embeddings in PostgreSQL with pgvector.

## Architecture

- `rust_parser/`: preserved ingestion parser.
- `backend/`: FastAPI, SQLAlchemy, Alembic, LangGraph, Celery tasks.
- `frontend/`: React/Vite app with separate `/search` and `/chat` workflows.
- `db`: PostgreSQL with pgvector as the single source of truth.
- `redis`: Celery broker and LangGraph checkpoint backing store.
- `caddy`: self-hosted TLS reverse proxy.

## Environment

Create `.env` from the checked-in examples and set:

```env
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=google/gemini-1.5-flash
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
POSTGRES_DB=threadsense
POSTGRES_USER=threadsense
POSTGRES_PASSWORD=threadsense
THREADSENSE_DOMAIN=localhost
```

## Self-Hosted Run

```bash
docker compose up --build
```

Caddy routes `/api/*` to FastAPI and all other traffic to the static frontend.

## Backend Highlights

- `GET /api/listings/facets`: live SQL aggregates.
- `GET /api/listings`: hard SQL filters first, optional pgvector semantic ordering second.
- `POST /api/listings/delete`: bulk listing deletion.
- `GET /api/chat/source/{listing_id}`: raw WhatsApp source verification.
- `POST /api/chat`: LangGraph assistant with deterministic listing tables.

## Frontend Highlights

- `/search`: fast database explorer with hard filters, pagination, semantic overlay, bulk delete, and source modal.
- `/chat`: conversational assistant for comparative and exploratory questions.
- Listing IDs are clickable in both workflows and open the raw WhatsApp source.

## Validation

```bash
npm run typecheck --prefix frontend
npm run build --prefix frontend
python -m pytest backend/tests/test_retriever_rerank.py
docker compose config
```
