"""The RunConfig.origin field must be inert for existing/benchmark runs."""

from pipeline.runner.models import Run, RunConfig


def test_origin_defaults_to_experiment():
    assert RunConfig(source_name="x").origin == "experiment"


def test_run_json_without_origin_loads_as_experiment():
    # A pre-existing benchmark run record predates the origin field; it must still
    # load and default to "experiment" rather than failing validation.
    run = Run.model_validate({"config": {"source_name": "acled_data"}})
    assert run.config.origin == "experiment"
