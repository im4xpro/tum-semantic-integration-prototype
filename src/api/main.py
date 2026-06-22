import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

from .routes import experiments, mappings, ontology, schemas

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Semantic Mapping Editor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ontology.router, prefix="/api/ontology", tags=["Ontology"])
app.include_router(schemas.router, prefix="/api/schemas", tags=["Schemas"])
app.include_router(mappings.router, prefix="/api/mappings", tags=["Mappings"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["Experiments"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/experiments", include_in_schema=False)
def experiments_ui():
    return FileResponse(_STATIC_DIR / "experiments.html")
