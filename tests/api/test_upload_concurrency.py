import asyncio
from pathlib import Path
from threading import Event
from typing import override

import anyio
from httpx2 import ASGITransport, AsyncClient

from apps.api.app import create_app
from packages.application.datasets import DatasetSnapshotService
from packages.domain.market_data import BarRequest
from packages.market_data.contracts import MarketDataProvider
from packages.market_data.snapshots import FileSnapshotStore, SnapshotManifest
from packages.shared.settings import Settings
from tests.api.test_datasets import FIXTURES, _params


def test_health_responds_while_upload_processing_is_active(tmp_path: Path) -> None:
    started = Event()
    release = Event()
    finished = Event()

    class DelayedDatasetService(DatasetSnapshotService):
        @override
        def create_from_provider(
            self, provider: MarketDataProvider, request: BarRequest
        ) -> SnapshotManifest:
            started.set()
            _ = release.wait(timeout=3)
            try:
                return super().create_from_provider(provider, request)
            finally:
                finished.set()

    app = create_app(
        Settings(data_storage_path=tmp_path),
        dataset_service=DelayedDatasetService(FileSnapshotStore(tmp_path / "published")),
    )

    async def check() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload = asyncio.create_task(
                client.post(
                    "/datasets",
                    params=_params(),
                    content=(FIXTURES / "local_bars.csv").read_bytes(),
                    headers={"Content-Type": "text/csv", "X-Filename": "bars.csv"},
                )
            )
            try:
                assert await anyio.to_thread.run_sync(lambda: started.wait(timeout=5))
                assert not finished.is_set(), (
                    "event loop could not handle requests during processing"
                )
                assert not upload.done(), "upload work blocked the event loop until it finished"
                assert (
                    await asyncio.wait_for(client.get("/health/live"), timeout=1)
                ).status_code == 200
            finally:
                release.set()
            response = await upload
            assert response.status_code == 201
            assert not list((tmp_path / "uploads").glob("*"))

    anyio.run(check)
