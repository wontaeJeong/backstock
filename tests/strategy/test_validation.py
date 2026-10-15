import re
from decimal import Decimal

from packages.strategy.schema import (
    CompareCondition,
    ConstantValue,
    EntryRule,
    FixedQuantitySizing,
    StrategyDefinition,
)
from packages.strategy.validation import canonical_json, create_strategy_version

_VERSION_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _definition(name: str = "hash-me") -> StrategyDefinition:
    return StrategyDefinition(
        name=name,
        universe=("AAA",),
        entry=EntryRule(
            condition=CompareCondition(
                op="gt", left=ConstantValue(value=Decimal(1)), right=ConstantValue(value=Decimal(0))
            )
        ),
        position_sizing=FixedQuantitySizing(quantity=1),
    )


def test_version_id_is_a_sha256_digest() -> None:
    version = create_strategy_version(_definition())

    assert _VERSION_ID_PATTERN.match(version.version_id)


def test_identical_definitions_produce_the_same_version() -> None:
    first = create_strategy_version(_definition())
    second = create_strategy_version(_definition())

    assert first.version_id == second.version_id
    assert first.canonical_json == second.canonical_json


def test_changing_a_field_changes_the_version() -> None:
    first = create_strategy_version(_definition("a"))
    second = create_strategy_version(_definition("b"))

    assert first.version_id != second.version_id


def test_canonical_json_has_sorted_and_compact_keys() -> None:
    serialized = canonical_json(_definition())

    assert ", " not in serialized
    assert ": " not in serialized
    assert '"universe"' in serialized
