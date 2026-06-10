import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import ontology, schemas, mappings

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


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
