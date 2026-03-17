FROM python:3.11-slim

# System dependencies for weasyprint (PDF generation) and general tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /workspace

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --no-dev

# Copy source
COPY src/ ./src/
COPY agent_docs/ ./agent_docs/
COPY reports/templates/ ./reports/templates/

# Install the package
RUN uv pip install -e . --no-deps

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /workspace
USER agent

CMD ["agentorg"]
