from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.application.research_store import ResearchStore
from packages.application.simulation_models import SimulationReport
from packages.application.simulations import SimulationService
from packages.market_data.snapshots import FileSnapshotStore, SnapshotManifest
from packages.strategy.schema import StrategyDefinition
from packages.strategy.validation import create_strategy_version

LibraryKind = Literal["strategies", "datasets", "runs"]


class SaveStrategy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)
    definition: StrategyDefinition
    description: str = Field(default="", max_length=2000)
    tags: tuple[str, ...] = Field(default=(), max_length=20)


class StrategyRecord(SaveStrategy):
    strategy_id: str
    version_id: str
    name: str
    created_at: datetime


class LibraryPage(BaseModel):
    items: list[StrategyRecord | SnapshotManifest | SimulationReport]
    total: int
    page: int
    page_size: int


class ArchiveRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    archived: bool


class ArchiveState(ArchiveRequest):
    kind: LibraryKind
    id: str


class ResearchLibrary:
    def __init__(self, root: Path, simulations: SimulationService) -> None:
        """Bind existing verified stores rather than duplicating market/run artifacts."""
        self._store = ResearchStore(root)
        self._snapshots = FileSnapshotStore(root / "published")
        self._simulations = simulations

    def save_strategy(self, body: SaveStrategy) -> StrategyRecord:
        version = create_strategy_version(body.definition)
        draft = StrategyRecord(
            **body.model_dump(),
            strategy_id="",
            version_id=version.version_id,
            name=body.definition.name,
            created_at=datetime.now(UTC),
        )
        return StrategyRecord.model_validate(self._store.save("strategies", draft, "strategy_id"))

    def get(
        self, kind: LibraryKind, identity: str
    ) -> StrategyRecord | SnapshotManifest | SimulationReport:
        record: StrategyRecord | SnapshotManifest | SimulationReport | None
        if kind == "strategies":
            payload = self._store.get(kind, identity, "strategy_id")
            record = StrategyRecord.model_validate(payload) if payload is not None else None
        elif kind == "datasets":
            record = self._snapshots.load(identity)
        else:
            record = self._simulations.get(identity)
        if record is None:
            raise LookupError(identity)
        return record

    def list(
        self,
        kind: LibraryKind,
        *,
        q: str,
        page: int,
        page_size: int,
        archived: bool,
    ) -> LibraryPage:
        directory = "published/snapshots" if kind == "datasets" else kind
        records = [
            self.get(kind, identity)
            for identity in self._store.ids(directory)
            if self._store.archived(kind, identity) == archived
        ]
        query = q.casefold()
        records = [r for r in records if query in r.model_dump_json().casefold()]
        records.sort(key=lambda r: r.model_dump_json(), reverse=True)
        offset = (page - 1) * page_size
        return LibraryPage(
            items=records[offset : offset + page_size],
            total=len(records),
            page=page,
            page_size=page_size,
        )

    def archive(self, kind: LibraryKind, identity: str, body: ArchiveRequest) -> ArchiveState:
        self.get(kind, identity)
        self._store.archive(kind, identity, archived=body.archived)
        return ArchiveState(kind=kind, id=identity, archived=body.archived)
