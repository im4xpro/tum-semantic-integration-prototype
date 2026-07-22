FROM python:3.12-slim

WORKDIR /app

# build-essential covers packages without prebuilt wheels for this platform
# (chromadb's native deps in particular); psycopg2-binary ships its own libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Only the versioned scientific inputs ship in the image; data/runs, data/output,
# and LLM-generated mappings are runtime state — mount ./data as a volume instead.
COPY data/ontology ./data/ontology
COPY data/gold_standard ./data/gold_standard
COPY data/schemas ./data/schemas
COPY data/descriptions ./data/descriptions
COPY data/mappings ./data/mappings

ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
