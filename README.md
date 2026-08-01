# LLM-Assisted Semantic Data Integration

A framework for evaluating the quality of LLM-assisted mapping creation for ontology population.

---

## Problem statement

Integrating data from different sources into one unified schema is a commong problem in data science, which is currently solved by manual effort. Domain experts must inspect the source data, understand the target schema and write mapping logic to transform the source data. This is a time-consuming and error-prone process, especially when the source data is large and complex. The goal of this project is to explore how Large Language Models (LLMs) can assist in this process by automatically generating mapping logic from source data to a target ontology.

## Solution
This project implements a End-to-End pipeline that takes a data source and a target ontology (schema) as input, generates a mapping file using various LLM prompting strategies, applies the mapping to the source data to produce a knowledge graph, and evaluates the quality of the generated mapping against a gold standard. The system also provides a visual editor for reviewing and correcting the generated mappings.
The goal is to reduce the manual effort by allowing the LLM to generate the initial mapping logic, which can then be reviewed and corrected by a human expert. This approach aims to improve the efficiency and accuracy of the data integration process.

**Tech Stack** Python 3.12 · FastAPI · rdflib · GraphDB ·
React 18 · TypeScript · Vite · React Flow · Docker.

---

## Quick start (Docker)

Requires Docker. This brings up the backend, the mapping editor, and GraphDB.

```bash
cp .env.example .env                 # backend env
cp editor-frontend/.env.example editor-frontend/.env   # frontend env
docker compose up -d
```

Frontends are exposed on the following ports:

| Frontend | URL | Purpose |
|----------|-----|---------|
| **Experiment runner** | <http://localhost:8420/experiments> | run the LLM benchmark matrix; also `/evaluation`, `/diff` |
| **Mapping editor** | <http://localhost:8421> | visually author / review / deploy mappings |
| API docs (OpenAPI) | <http://localhost:8420/docs> | interactive REST reference |
| GraphDB workbench | <http://localhost:7210> | inspect the knowledge graph |

The benchmark uses sample records embedded in `data/schemas/*.json`, so **no live database
is required** to run experiments or evaluations. Live Postgres/MongoDB/TimescaleDB are
only needed to *populate* a full source from the editor (see `DOCKER.md`).

See **[DOCKER.md](DOCKER.md)** for ports, rebuilding, and live-database configuration.

---

## Repository Overview

```
src/pipeline/      the engine: connectors, ontology, mapping generation (LLM),
                   extraction, RDF serialisation, evaluation, run/provenance stores
src/api/           FastAPI REST API + the static experiment-runner UI
editor-frontend/   React/Vite mapping editor (its own container)
data/              ontology, source schemas, the gold standard, and runtime output
scripts/           the evaluation CLI + manual check scripts
tests/             pytest suite
```

---

## Local development (without Docker)

### Backend

Requires Python ≥ 3.12 and a reachable GraphDB (configure via `.env`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src uvicorn api.main:app --reload      # run the API
pytest                                            # run the test suite
ruff check . && ruff format --check .             # lint + format
```

Score an experiment's runs against the gold standard from the CLI:

```bash
PYTHONPATH=src python scripts/evaluate-experiment.py <experiment_name>
```

### Editor frontend

Requires Node.js. The Vite dev server proxies `/api` to the backend (`VITE_API_URL`).

```bash
cd editor-frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # production build
```

---

## Running a benchmark

An experiment is a small YAML file describing a matrix of configurations to sweep
(see `experiment_thesis.yaml` / `experiment.example.yaml`):

```yaml
name: thesis_eval_acled
data: { source_name: acled_data, use_sample_data: true }
matrix:
  provider_models: [[openrouter, anthropic/claude-sonnet-5]]
  strategies: [zero_shot, few_shot, chain_of_thought]
  ontology_formats: [class_list, turtle, compact, json_ld]
  include_descriptions: [true, false]
```

Submit it via the experiment-runner UI (or `POST /api/experiments/submit-yaml`); the
matrix expands into one run per combination, each generating a mapping, materialising RDF
into GraphDB, and being scored against the gold standard. Results are written to
`data/output/`.

---

## Configuration

- **Backend** — copy `.env.example` → `.env`. Sets LLM provider keys
  (`OPENROUTER_API_KEY`, …), GraphDB (`GRAPHDB_*`), and data-source credentials
  (`POSTGRES_*` / `MONGODB_*` / `TIMESCALE_*`).
- **Editor** — copy `editor-frontend/.env.example` → `editor-frontend/.env`. Sets the
  `VITE_*` defaults baked into the SPA at build time.

---

## Acknowledgements

This project was developed as part of the Master's thesis **"Semantic Data Integration in Defense Information Systems: An LLM-Based Approach for Automated Ontology Mapping and Knowledge Graph Population"** at the Technical University of Munich (TUM) in cooperation with fortiss GmbH, examined by Prof. Dr. Alexander Pretschner and supervised by Tomas Bueno Momcilovic.

