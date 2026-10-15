from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from apps.api.schemas import DatasetUploadRequest
from packages.application.datasets import DatasetSnapshotService
from packages.market_data.local_file import (
    LocalFileProvider,
    LocalFileSelection,
    LocalFileSource,
)
from packages.market_data.raw_store import FileRawStore
from packages.market_data.snapshots import SnapshotManifest
from packages.shared.settings import Settings

MEDIA_TYPES: Final = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/vnd.apache.parquet": ".parquet",
}


def _publish_upload(
    service: DatasetSnapshotService,
    settings: Settings,
    upload: DatasetUploadRequest,
    safe_path: Path,
    filename: str,
) -> SnapshotManifest:
    provider = LocalFileProvider(
        LocalFileSource(
            path=safe_path,
            source_name=filename,
            instrument=upload.to_bar_request().instrument,
            price_adjustment=upload.price_adjustment,
            volume_adjustment=upload.volume_adjustment,
            max_rows=settings.dataset_upload_max_rows,
            max_columns=settings.dataset_upload_max_columns,
            selection=LocalFileSelection.FULL_SOURCE,
        ),
        raw_store=FileRawStore(settings.data_storage_path.resolve() / "raw"),
    )
    return service.create_from_provider(provider, upload.to_bar_request())


def build_dataset_router(service: DatasetSnapshotService, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/datasets",
        status_code=status.HTTP_201_CREATED,
        tags=["datasets"],
    )
    async def upload_dataset(
        upload: Annotated[DatasetUploadRequest, Depends()],
        request: Request,
        filename: Annotated[str, Header(alias="X-Filename", min_length=1, max_length=255)],
        content_type: Annotated[str, Header(alias="Content-Type")],
    ) -> SnapshotManifest:
        suffix = MEDIA_TYPES.get(content_type.casefold())
        if suffix is None:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if Path(filename).suffix.casefold() != suffix:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > settings.dataset_upload_max_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE)
        upload_root = settings.data_storage_path.resolve() / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=upload_root) as directory:
            safe_path = Path(directory) / f"upload{suffix}"
            size = 0
            with safe_path.open("wb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings.dataset_upload_max_bytes:
                        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE)
                    _ = await run_in_threadpool(stream.write, chunk)
            return await run_in_threadpool(
                _publish_upload, service, settings, upload, safe_path, filename
            )

    @router.get(
        "/dataset-snapshots/{snapshot_id}",
        tags=["datasets"],
    )
    def get_dataset_snapshot(snapshot_id: str) -> SnapshotManifest:
        return service.get(snapshot_id)

    _ = upload_dataset, get_dataset_snapshot
    return router
