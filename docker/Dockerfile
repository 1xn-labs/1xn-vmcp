 # vMCP OSS - Dockerfile
# Builds backend and uses pre-built frontend from backend/public/frontend
# Frontend should be built first using: make build-frontend

# Stage 1: Build Python dependencies
FROM python:3.11-slim as python-base

WORKDIR /app

# Copy OSS backend files
COPY README.md /app/README.md
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/src /app/backend/src

# Create public/frontend directory (required by pyproject.toml force-include)
RUN mkdir -p /app/backend/public/frontend

# Install Python dependencies
WORKDIR /app/backend
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.11-slim

# Install curl (for health check)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python environment from build stage
COPY --from=python-base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-base /usr/local/bin /usr/local/bin
COPY --from=python-base /app/backend/src /app/src

# Copy pre-built frontend (built by make build-frontend)
COPY backend/public/frontend /app/src/vmcp/public/frontend

# Create data directory and user
RUN mkdir -p /app/data && \
    useradd -m -u 1000 vmcp && \
    chown -R vmcp:vmcp /app

# No entrypoint script needed - using 'vmcp run' which handles all initialization

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATABASE_URL=sqlite:///app/data/vmcp.db
ENV LOG_LEVEL=INFO
ENV ENV=production

EXPOSE 8000

USER vmcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["vmcp", "run", "--host", "0.0.0.0", "--port", "8000", "--no-open", "--skip-db-check"]
