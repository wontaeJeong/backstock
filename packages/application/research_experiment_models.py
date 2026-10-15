from datetime import datetime
from decimal import Decimal
from math import prod
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.application.simulation_models import SimulationRequest

MAX_GRID_RUNS = 16
MAX_WALK_RUNS = 32


class ResearchModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class Axis(ResearchModel):
    path: str = Field(max_length=200)
    values: tuple[Decimal, ...] = Field(min_length=1, max_length=16)


class GridRequest(ResearchModel):
    base: SimulationRequest
    axes: tuple[Axis, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def bounded(self) -> "GridRequest":
        if prod(len(a.values) for a in self.axes) > MAX_GRID_RUNS:
            msg = "최대 16개 조합입니다."
            raise ValueError(msg)
        if len({a.path for a in self.axes}) != len(self.axes):
            msg = "중복 axis path입니다."
            raise ValueError(msg)
        if any(not v.is_finite() for a in self.axes for v in a.values):
            msg = "유한 숫자만 허용합니다."
            raise ValueError(msg)
        return self


class WalkForwardRequest(ResearchModel):
    base: SimulationRequest
    train_bars: int = Field(ge=2, le=3000)
    test_bars: int = Field(ge=2, le=3000)
    folds: int = Field(ge=1, le=4)
    axes: tuple[Axis, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def bounded(self) -> "WalkForwardRequest":
        if (prod(len(a.values) for a in self.axes) + 1) * self.folds > MAX_WALK_RUNS:
            msg = "학습과 테스트 합계는 최대 32회 실행입니다."
            raise ValueError(msg)
        if self.axes:
            GridRequest(base=self.base, axes=self.axes)
        return self


class Component(ResearchModel):
    weight: Decimal = Field(gt=0, le=1, allow_inf_nan=False)
    request: SimulationRequest


class PortfolioRequest(ResearchModel):
    initial_cash: Decimal = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    components: tuple[Component, ...] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def bounded(self) -> "PortfolioRequest":
        if sum(c.weight for c in self.components) > 1:
            msg = "비중 합은 1 이하여야 합니다."
            raise ValueError(msg)
        return self


class ExperimentRow(ResearchModel):
    parameters: dict[str, Decimal]
    run_id: str | None = None
    status: Literal["succeeded", "failed", "cancelled", "not_run"]
    total_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    net_profit: Decimal | None = None
    error: str | None = None


class GridExperiment(ResearchModel):
    experiment_id: str = ""
    kind: Literal["grid"] = "grid"
    request: GridRequest
    rows: list[ExperimentRow]
    warnings: list[str]
    baseline_snapshot_id: str


class WalkFold(ResearchModel):
    fold: int
    train_start: datetime | None = None
    train_end: datetime | None = None
    test_start: datetime | None = None
    test_end: datetime | None = None
    train_run_ids: list[str] = Field(default_factory=list)
    training: list[ExperimentRow] = Field(default_factory=list)
    selected_parameters: dict[str, Decimal] = Field(default_factory=dict)
    test_run_id: str | None = None
    test: ExperimentRow | None = None
    status: Literal["succeeded", "failed", "cancelled", "not_run"]
    error: str | None = None


class WalkForwardExperiment(ResearchModel):
    experiment_id: str = ""
    kind: Literal["walk_forward"] = "walk_forward"
    request: WalkForwardRequest
    baseline_snapshot_id: str
    folds: list[WalkFold]
    warnings: list[str]
    selection_metric: Literal["training_total_return"] = "training_total_return"


class PortfolioComponentResult(ResearchModel):
    index: int
    weight: Decimal
    budget: Decimal
    run_id: str | None
    status: str
    error: str | None


class PortfolioPoint(ResearchModel):
    timestamp: datetime
    equity: Decimal


class Correlation(ResearchModel):
    left: int
    right: int
    value: Decimal | None
    reason: str | None
    observations: int


class PortfolioExperiment(ResearchModel):
    experiment_id: str = ""
    kind: Literal["portfolio"] = "portfolio"
    request: PortfolioRequest
    components: list[PortfolioComponentResult]
    reserve_cash: Decimal
    curve: list[PortfolioPoint]
    correlations: list[Correlation]
    excluded_timestamps: dict[str, int]
    warnings: list[str]


Experiment = GridExperiment | WalkForwardExperiment | PortfolioExperiment
