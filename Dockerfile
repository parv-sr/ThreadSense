FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml ./
COPY rust_parser ./rust_parser

RUN pip install --no-cache-dir uv maturin
RUN uv venv /app/.venv
RUN uv sync --no-dev

WORKDIR /app/rust_parser
RUN maturin develop --release

FROM python:3.13-slim AS runtime

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY --from=builder /app/.venv /app/.venv
COPY backend ./backend
COPY rust_parser ./rust_parser

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app:/app/backend"
ENV APP_ENV="production"

RUN mkdir -p /app/uploads

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
