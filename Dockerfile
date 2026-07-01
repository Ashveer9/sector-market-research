FROM python:3.11-slim

LABEL maintainer="data-engineering"
LABEL description="Sector Market Research Data Pipeline"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        pandas==2.2.2 \
        pyarrow==16.1.0 \
        duckdb==0.10.3 \
        numpy==1.26.4 \
        dbt-core==1.8.4 \
        dbt-duckdb==1.8.1 \
        pyyaml==6.0.1 \
        python-dotenv==1.0.1 \
        click==8.1.7 \
        rich==13.7.1 \
        tenacity==8.3.0 \
        plotly==5.22.0 \
        pytest==8.2.2 \
        pytest-cov==5.0.0 \
        faker==25.2.0

# Copy project
COPY . .

# Create data directories
RUN mkdir -p data/{raw,processed,analytics,sample} logs

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default: run the pipeline
CMD ["python", "scripts/run_pipeline.py", "--skip-dbt"]
