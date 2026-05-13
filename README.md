# ThreadSense

> **Transform messy WhatsApp real estate chats into a structured, searchable property database — powered by AI.**

ThreadSense is purpose-built for real estate brokers. It ingests raw WhatsApp chat exports and turns unstructured messages into pristine, filterable property listings. Whether you need to quickly narrow inventory by floor band and intent, or chat directly with an AI assistant for comparative client analyses, ThreadSense serves as a robust CRM and retrieval engine.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2-092E20.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)
![Celery](https://img.shields.io/badge/Celery-Redis-37814A.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991.svg)

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚡ **Lightning-Fast Parsing** | Ingests massive WhatsApp chat exports instantly via a low-level Rust engine. |
| 🤖 **AI-Powered Extraction** | Automatically structures raw text into beds, baths, price, location, and intent using state-of-the-art LLMs. |
| 🔍 **Hybrid Search Engine** | Filter properties by hard parameters (budget, configuration) combined with semantic AI search. |
| 💬 **Conversational Assistant** | Ask questions like *"Show me ready-to-move 3BHKs in Sector 20 under 2Cr"* and get precise, verified listings. |
| 🔗 **Source Verification** | Every listing links back to the original WhatsApp message — zero hallucinations, full traceability. |
| 📁 **Collections & Workspaces** | Curate and save matching listings into custom folders for specific clients. |

---

## 🏗️ Technical Architecture

ThreadSense utilizes a highly asynchronous, high-throughput stack designed for minimal operational complexity.

### Core Components

| Layer | Technology |
|---|---|
| **Frontend** | React SPA — Vite + Tailwind CSS |
| **Backend** | FastAPI — pure `asyncio` for endpoints and background jobs |
| **AI & Orchestration** | LangGraph integrated with OpenRouter |
| **Ingestion Engine** | High-performance Rust parser via PyO3 |
| **Database & Vector Store** | PostgreSQL + `pgvector` — unified single source of truth |
| **Infrastructure** | Docker Compose orchestration + Caddy (reverse proxy, automatic TLS) |

### Directory Structure

```
ThreadSense/
├── rust_parser/          # High-performance WhatsApp parser (Rust/PyO3)
├── backend/              # Async FastAPI application
│   ├── src/
│   │   ├── api/          # REST endpoints for listings, chat, collections
│   │   ├── core/         # Configuration, JWT auth, and security
│   │   ├── db/           # SQLAlchemy 2.0 + async sessions
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic validation schemas
│   │   ├── preprocessing/# Async LLM extraction pipeline
│   │   ├── embeddings/   # Vector embedding inference and storage
│   │   ├── rag/          # LangGraph agentic workflows
│   │   └── tasks/        # Async background workers
│   ├── alembic/          # Database migrations
│   └── tests/            # Pytest test suite
├── frontend/             # React SPA (Vite build)
├── docker-compose.yml    # Multi-service orchestration
└── Caddyfile             # Reverse proxy and HTTPS configuration
```

---

## 🚀 Deployment Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/parv-sr/ThreadSense.git
cd ThreadSense
```

### 2. Configure environment

Create a `.env` file at the project root based on the provided example:

```bash
cp backend/.env.example .env
```

#### Key Environment Variables

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | API key for LLM extraction and embeddings |
| `OPENROUTER_CHAT_MODEL` | Recommended: `google/gemini-1.5-flash` |
| `OPENROUTER_EMBEDDING_MODEL` | Recommended: `openai/text-embedding-3-small` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `THREADSENSE_DOMAIN` | Domain for Caddy (use `localhost` for local testing) |

### 3. Start the stack

```bash
docker compose up --build
```

The application will be available at `http://localhost` (or your configured domain).

---

## 🛠️ Developer Guide

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Backend Development

ThreadSense uses [uv](https://github.com/astral-sh/uv) for lightning-fast Python dependency management.

```bash
cd backend
uv sync
uvicorn src.main:app --reload
```

### Testing

Run the backend test suite:

```bash
python -m pytest backend/tests/
```

---

## 🤝 Contributing

1. **Fork** the repository.
2. Create a **focused feature branch**.
3. Make **atomic commits**.
4. Ensure all **Pytest and TypeScript checks** pass.
5. Submit a **pull request** with a clear description.

---

License: This project is for personal and internal use. Contact the maintainer for licensing questions.
