# ==================== BUILD STAGE ====================
FROM python:3.13-slim AS builder

# Install system dependencies + Rust
RUN apt-get update && apt-get install -y \
    curl build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./
COPY rust_parser ./rust_parser

# Install uv + maturin (this is the fix)
RUN pip install --no-cache-dir uv maturin

# Create venv and sync project dependencies
RUN uv venv /app/.venv
RUN uv sync --frozen

# Build the Rust parser in release mode (now maturin exists)
WORKDIR /app/rust_parser
RUN maturin develop --release

# ==================== RUNTIME STAGE ====================
FROM python:3.13-slim

WORKDIR /app

# Copy the virtual environment from builder (much smaller final image)
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code
COPY backend ./backend
COPY rust_parser ./rust_parser

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8000

CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]