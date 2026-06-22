from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from itertools import product
from typing import Literal

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    queued = "queued"
    mapping = "mapping"        # LLM generating the mapping
    extracting = "extracting"  # extraction + serialization + upload
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class GraphDBTargetConfig(BaseModel):
    """GraphDB target override; unset fields fall back to GRAPHDB_* in .env."""
    url: str | None = None
    repository: str | None = None
    username: str | None = None
    password: str | None = None


class RunConfig(BaseModel):
    """Configuration for a single pipeline run."""
    experiment_name: str = "unnamed"
    source_name: str
    use_sample_data: bool = True  # True = use schema's sample_records; False = connect to DB
    data_limit: int | None = None

    # Mapping: either reuse an existing mapping or generate via LLM
    mapping_id: str | None = None  # if set, skip LLM generation

    # LLM (ignored when mapping_id is set)
    provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    strategy: str = "zero_shot"
    ontology_format: str = "turtle"
    include_descriptions: bool = False

    graphdb: GraphDBTargetConfig = Field(default_factory=GraphDBTargetConfig)


class RunStats(BaseModel):
    records_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    triples_written: int = 0
    triples_in_db: int = 0
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Run(BaseModel):
    id: str = Field(default_factory=lambda: (
        datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    ))
    config: RunConfig
    status: RunStatus = RunStatus.queued
    mapping_id: str | None = None  # resolved after mapping step
    named_graph: str | None = None  # set when run starts
    stats: RunStats = Field(default_factory=RunStats)
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


# ── YAML experiment config ────────────────────────────────────────────────────

class MatrixConfig(BaseModel):
    """Defines the combinatorial space for an experiment."""
    provider_models: list[list[str]]  # [[provider, model], ...]
    strategies: list[str] = ["zero_shot"]
    ontology_formats: list[str] = ["turtle"]
    include_descriptions: list[bool] = [False]


class DataConfig(BaseModel):
    source_name: str
    limit: int | None = None
    use_sample_data: bool = True


class MappingStrategyConfig(BaseModel):
    mode: Literal["generate", "use_existing"] = "generate"
    mapping_id: str | None = None  # only if mode=use_existing


class ExperimentConfig(BaseModel):
    """Loaded from experiment YAML. Expands into individual RunConfigs."""
    name: str
    description: str = ""
    data: DataConfig
    graphdb: GraphDBTargetConfig = Field(default_factory=GraphDBTargetConfig)
    mapping: MappingStrategyConfig = Field(default_factory=MappingStrategyConfig)
    matrix: MatrixConfig

    def expand(self) -> list[RunConfig]:
        """Cross-product of all matrix dimensions → list of RunConfig."""
        configs = []
        for (provider, model), strategy, fmt, include_desc in product(
            self.matrix.provider_models,
            self.matrix.strategies,
            self.matrix.ontology_formats,
            self.matrix.include_descriptions,
        ):
            existing_id = (
                self.mapping.mapping_id
                if self.mapping.mode == "use_existing"
                else None
            )
            configs.append(RunConfig(
                experiment_name=self.name,
                source_name=self.data.source_name,
                use_sample_data=self.data.use_sample_data,
                data_limit=self.data.limit,
                mapping_id=existing_id,
                provider=provider,
                llm_model=model,
                strategy=strategy,
                ontology_format=fmt,
                include_descriptions=include_desc,
                graphdb=self.graphdb,
            ))
        return configs
