"""Schema validation, canonicalization, and immutable versioning for strategies."""

import hashlib
import json
from typing import Any, ClassVar, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from packages.strategy.schema import StrategyDefinition

HASH_ALGORITHM: Final = "sha256"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class StrategyValidationIssue(_FrozenModel):
    path: str
    message: str


class StrategyValidationError(Exception):
    issues: tuple[StrategyValidationIssue, ...]

    def __init__(self, issues: tuple[StrategyValidationIssue, ...]) -> None:
        """Preserve field-level issues for API and MCP error surfaces."""
        self.issues = issues
        super().__init__("strategy definition failed validation")


def validate_definition(payload: dict[str, Any]) -> StrategyDefinition:
    try:
        return StrategyDefinition.model_validate(payload)
    except ValidationError as error:
        issues = tuple(
            StrategyValidationIssue(
                path=".".join(str(part) for part in item["loc"]) or "$",
                message=item["msg"],
            )
            for item in error.errors()
        )
        raise StrategyValidationError(issues) from error


def canonical_json(definition: StrategyDefinition) -> str:
    payload = definition.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class StrategyVersion(_FrozenModel):
    version_id: str
    schema_version: str
    canonical_json: str
    definition: StrategyDefinition


def create_strategy_version(definition: StrategyDefinition) -> StrategyVersion:
    serialized = canonical_json(definition)
    digest = hashlib.new(HASH_ALGORITHM, serialized.encode("utf-8")).hexdigest()
    return StrategyVersion(
        version_id=f"{HASH_ALGORITHM}:{digest}",
        schema_version=definition.schema_version,
        canonical_json=serialized,
        definition=definition,
    )
