import importlib
import os
from dataclasses import dataclass
from typing import Protocol

import duckdb
from op_coreutils.logger import structlog

from .types import NamedRelations

log = structlog.get_logger()

_LOADED = False


class ModelFunction(Protocol):
    def __call__(
        self,
        duckdb_client: duckdb.DuckDBPyConnection,
        input_tables: NamedRelations,
    ) -> NamedRelations: ...


@dataclass
class IntermediateModel:
    name: str
    input_datasets: list[str]
    func: ModelFunction
    expected_output_datasets: list[str]


REGISTERED_INTERMEDIATE_MODELS: dict[str, IntermediateModel] = {}


def register_model(input_datasets: list[str], expected_outputs: list[str]):
    def decorator(func):
        REGISTERED_INTERMEDIATE_MODELS[func.__name__] = IntermediateModel(
            name=func.__name__,
            input_datasets=input_datasets,
            func=func,
            expected_output_datasets=expected_outputs,
        )
        return func

    return decorator


def load_model_definitions():
    """Import python modules under the models directory so the model registry is populated."""
    global _LOADED

    if _LOADED:
        return

    # Python modules under the "models" directory are imported to populate the model registry.
    MODELS_PATH = os.path.join(os.path.dirname(__file__), "models")

    count = 0
    for fname in os.listdir(MODELS_PATH):
        name = os.path.join(MODELS_PATH, fname)
        if os.path.isfile(name) and fname not in ("__init__.py", "registry.py"):
            importlib.import_module(
                f"op_datasets.etl.intermediate.models.{fname.removesuffix(".py")}"
            )
            count += 1

    log.info(f"Loaded {count} python modules with intermediate model definitions.")
    _LOADED = True
