# Running in Docker

## First-time setup

1. Make sure `.env` exists at the repo root (it's gitignored — copy your existing one, or
   fill in `experiment.example.yaml`'s referenced provider keys plus `GRAPHDB_*`).
2. Bring up the app and GraphDB:

   ```
   docker compose up -d
   ```

   `graphdb-init` runs once and creates the `bsm` repository the app expects
   (`GRAPHDB_REPOSITORY` in `.env`). Check its log if the app fails to reach GraphDB:

   ```
   docker compose logs graphdb-init
   ```

   If auto-creation failed (GraphDB REST API shape can differ by version), create the
   repository by hand — it's a one-time, ~1 minute step: open http://localhost:7200 →
   Setup → Repositories → Create new repository → GraphDB Free → Repository ID `bsm` → Create.

3. Open http://localhost:8000/experiments to run experiments, or http://localhost:8000/evaluation
   and http://localhost:8000/diff to inspect results.

## Editing prompts / mapping logic without rebuilding

`docker-compose.yml` bind-mounts `./src` and `./data` into the container, and the app
runs with `--reload`. Editing anything under `src/pipeline/mapping/prompt_strategies/`
(or any other source file) takes effect within a couple seconds — no rebuild needed.
Rebuild (`docker compose build app`) only when you change `pyproject.toml` dependencies.

## Live database sources (optional)

The thesis experiment config (`experiment_thesis.yaml`) uses `use_sample_data: true`,
which reads records embedded in `data/schemas/*.json` — no live DB required. Postgres/
MongoDB/TimescaleDB are only needed if you set `use_sample_data: false` to pull fresh
data from a real source. They're behind a compose profile so they don't start by default:

```
docker compose --profile live-data up -d
```

These start with empty databases — you'd need to load data into them yourself before
extraction would find anything.

## Running the CLI scripts inside the container

```
docker compose exec app python scripts/evaluate-experiment.py thesis_eval_acled
```

## Known caveat

The GraphDB image tag pinned in `docker-compose.yml` (`ontotext/graphdb:10.7.0`) was
picked without network access to verify it's current — if `docker compose pull` fails,
check https://hub.docker.com/r/ontotext/graphdb/tags and update the tag.
