from typing import Final

from fastapi import APIRouter
from pydantic import JsonValue

from apps.api.schemas import (
    IndicatorMetadataResponse,
    OperatorMetadataResponse,
    StrategyMetadataResponse,
)
from packages.strategy.metadata import INDICATORS, OPERATORS
from packages.strategy.schema import StrategyDefinition
from packages.strategy.templates import TEMPLATES
from packages.strategy.validation import (
    StrategyVersion,
    create_strategy_version,
    validate_definition,
)

_TEMPLATE_UNIVERSE: Final = ("EXAMPLE:000000",)


def build_strategy_router() -> APIRouter:
    router = APIRouter()

    @router.post("/strategies/validate", tags=["strategies"])
    def validate_strategy(payload: dict[str, JsonValue]) -> StrategyVersion:
        definition = validate_definition(payload)
        return create_strategy_version(definition)

    @router.get("/strategies/metadata", tags=["strategies"])
    def get_strategy_metadata() -> StrategyMetadataResponse:
        templates: dict[str, JsonValue] = {
            name: create_strategy_version(factory(_TEMPLATE_UNIVERSE)).definition.model_dump(
                mode="json"
            )
            for name, factory in TEMPLATES.items()
        }
        return StrategyMetadataResponse(
            json_schema=StrategyDefinition.model_json_schema(),
            operators=tuple(
                OperatorMetadataResponse(
                    name=item.name,
                    category=item.category,
                    arity=item.arity,
                    description=item.description,
                )
                for item in OPERATORS
            ),
            indicators=tuple(
                IndicatorMetadataResponse(
                    name=item.name,
                    parameters=item.parameters,
                    minimum_lookback=item.minimum_lookback,
                    output_type=item.output_type,
                    availability=item.availability,
                    description=item.description,
                )
                for item in INDICATORS
            ),
            templates=templates,
        )

    _ = validate_strategy, get_strategy_metadata
    return router
