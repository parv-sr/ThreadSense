# ==================== BUILD STAGE ====================
FROM python:3.13-slim AS builder

# Install system dependencies + Rust toolchain for rust_parser builds
RUN apt-get update && apt-get install -y \
    curl build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
COPY rust_parser ./rust_parser

RUN pip install --no-cache-dir uv maturin

RUN uv venv /app/.venv
RUN uv sync --frozen

WORKDIR /app/rust_parser
RUN maturin develop --release

# ==================== RUNTIME STAGE ====================
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
RUN pip install --no-cache-dir uv
ENV PATH="/app/.venv/bin:$PATH"

COPY backend ./backend
COPY rust_parser ./rust_parser

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
