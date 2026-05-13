# Overview

ThreadSense transforms messy, raw WhatsApp real estate chat exports into beautifully structured, searchable, and conversational property listings.

Designed specifically to streamline broker workflows, it processes unstructured messages and turns them into a pristine database. Whether you need to quickly filter inventory by floor band and intent, or chat directly with an AI assistant to run comparative analyses for a client, ThreadSense serves as a robust real estate CRM and retrieval engine.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2-092E20.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)
![Celery](https://img.shields.io/badge/Celery-Redis-37814A.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991.svg)

# User Features
Lightning-Fast Parsing: Ingests massive WhatsApp chat exports instantly via a low-level engine.

AI-Powered Extraction: Automatically structures raw text into beds, baths, price, location, and intent using state-of-the-art LLMs.

Hybrid Search Engine: Instantly filter properties by hard parameters (like budget or configuration) combined with semantic AI search.

Conversational Assistant: Ask questions like "Show me ready-to-move 3BHKs in Sector 20 under 2Cr" and get precise, verified listings back.

Source Verification: Every listing links directly back to the original WhatsApp message, ensuring zero hallucinations and full traceability.

Collections & Workspaces: Easily curate and save matching listings into custom folders for specific clients.

# Technical Architecture
ThreadSense utilizes a highly asynchronous, high-throughput stack designed for minimal operational complexity.

# Core Components
Frontend: React SPA built with Vite and styled with Tailwind CSS.

Backend: FastAPI leveraging pure asyncio for endpoints and background jobs.

AI & Orchestration: LangGraph integrated with OpenRouter.

Ingestion Engine: High-performance Rust parser integrated into Python via PyO3.

Database & Vector Store: PostgreSQL with the pgvector extension acting as the unified single source of truth.

Infrastructure: Docker Compose orchestration paired with Caddy for reverse proxying and automatic TLS termination.

Directory Structure
Plaintext
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
Deployment Quick Start
1. Clone the repository:

Bash
git clone https://github.com/parv-sr/ThreadSense.git
cd ThreadSense
2. Configure environment:
Create a .env file at the root based on the provided examples.

Bash
cp backend/.env.example .env
Key Environment Variables:

OPENROUTER_API_KEY: API key for LLM extraction and embeddings.

OPENROUTER_CHAT_MODEL: Recommended google/gemini-1.5-flash

OPENROUTER_EMBEDDING_MODEL: Recommended openai/text-embedding-3-small

POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD: Database credentials.

THREADSENSE_DOMAIN: Domain for Caddy (use localhost for local testing).

3. Start the stack:

Bash
docker compose up --build
The application will be available at http://localhost (or your configured domain).

Developer Guide
Frontend Development
Bash
cd frontend
npm install
npm run dev
Backend Development
ThreadSense uses uv for lightning-fast Python dependency management.

Bash
cd backend
uv sync
uvicorn src.main:app --reload
Testing
To run the backend test suite:

Bash
python -m pytest backend/tests/
Contributing
Fork the repository.

Create a focused feature branch.

Make atomic commits.

Ensure all Pytest and TypeScript checks pass.

Submit a pull request with a clear description.

License: This project is for personal and internal use. Contact the maintainer for licensing questions.
