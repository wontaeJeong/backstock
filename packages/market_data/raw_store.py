import hashlib
import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, ValidationError

UNAWARE_CLOCK: Final = "raw capture clock must return a timezone-aware datetime"
UNSAFE_PROVIDER: Final = "provider name must contain a safe path character"
ARTIFACT_COLLISION: Final = "immutable raw artifact collision"
CACHE_BINDING_MISMATCH: Final = "cache key and raw artifact binding must match"

RequestValue = str | bool | int | float
RequestOptions = tuple[tuple[str, RequestValue], ...]
RequestInput = Mapping[str, RequestValue]


class RawArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    artifact_id: str
    provider: str
    provider_version: str
    acquired_at: datetime
    request: RequestOptions
    checksum: str
    media_type: str
    payload_path: Path
    metadata_path: Path


class _RawMetadata(BaseModel):
    artifact_id: str
    provider: str
    provider_version: str
    acquired_at: datetime
    request: RequestOptions
    checksum: str
    media_type: str


class _ArtifactIdentity(BaseModel):
    provider: str
    provider_version: str
    acquired_at: datetime
    request: RequestOptions
    checksum: str
    media_type: str


class _CacheEntry(BaseModel):
    provider: str
    artifact_id: str
    expires_at: datetime


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class FileRawStore:
    _root: Path
    _clock: Callable[[], datetime]

    def __init__(self, root: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        """Create an immutable artifact store rooted at the supplied directory."""
        self._root = root
        self._clock = clock or (lambda: datetime.now(UTC))
        self._root.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        *,
        provider: str,
        provider_version: str,
        request: RequestInput,
        payload: bytes,
        media_type: str,
    ) -> RawArtifact:
        acquired_at = self._clock()
        if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
            raise ValueError(UNAWARE_CLOCK)
        frozen_request = freeze_request(request)
        checksum = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        identity = _ArtifactIdentity(
            provider=provider,
            provider_version=provider_version,
            acquired_at=acquired_at,
            request=frozen_request,
            checksum=checksum,
            media_type=media_type,
        )
        artifact_id = _artifact_id(identity)
        provider_dir = self._root / _safe_provider(provider)
        provider_dir.mkdir(parents=True, exist_ok=True)
        payload_path = provider_dir / f"{artifact_id}.payload"
        metadata_path = provider_dir / f"{artifact_id}.json"
        metadata = _RawMetadata(
            artifact_id=artifact_id,
            provider=provider,
            provider_version=provider_version,
            acquired_at=acquired_at,
            request=frozen_request,
            checksum=checksum,
            media_type=media_type,
        )
        _write_once(payload_path, payload)
        _write_once(metadata_path, metadata.model_dump_json(indent=2).encode())
        return _to_artifact(metadata, payload_path, metadata_path)

    def load(self, provider: str, artifact_id: str) -> RawArtifact | None:
        provider_dir = self._root / _safe_provider(provider)
        metadata_path = provider_dir / f"{artifact_id}.json"
        payload_path = provider_dir / f"{artifact_id}.payload"
        if not metadata_path.is_file() or not payload_path.is_file():
            return None
        try:
            metadata = _RawMetadata.model_validate_json(metadata_path.read_bytes())
            payload = payload_path.read_bytes()
        except (OSError, ValidationError):
            return None
        identity = _ArtifactIdentity(
            provider=metadata.provider,
            provider_version=metadata.provider_version,
            acquired_at=metadata.acquired_at,
            request=metadata.request,
            checksum=metadata.checksum,
            media_type=metadata.media_type,
        )
        expected_id = _artifact_id(identity)
        if metadata.provider != provider or metadata.artifact_id != artifact_id:
            return None
        if expected_id != artifact_id:
            return None
        if f"sha256:{hashlib.sha256(payload).hexdigest()}" != metadata.checksum:
            return None
        return _to_artifact(metadata, payload_path, metadata_path)


class FileRequestCache:
    _root: Path
    _store: FileRawStore
    _clock: Callable[[], datetime]

    def __init__(
        self,
        root: Path,
        *,
        store: FileRawStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Create a TTL index that references validated raw artifacts."""
        self._root = root
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._root.mkdir(parents=True, exist_ok=True)

    def get(self, provider: str, request: RequestInput) -> RawArtifact | None:
        path = self._entry_path(provider, request)
        if not path.is_file():
            return None
        try:
            entry = _CacheEntry.model_validate_json(path.read_bytes())
        except (OSError, ValidationError):
            entry = None
        if entry is None or entry.provider != provider:
            return None
        if entry.expires_at <= self._clock():
            return None
        artifact = self._store.load(entry.provider, entry.artifact_id)
        expected_request = freeze_request(request)
        if (
            artifact is not None
            and artifact.provider == provider
            and artifact.request == expected_request
        ):
            return artifact
        return None

    def put(
        self,
        provider: str,
        request: RequestInput,
        artifact: RawArtifact,
        *,
        ttl: timedelta,
    ) -> None:
        if artifact.provider != provider or artifact.request != freeze_request(request):
            raise ValueError(CACHE_BINDING_MISMATCH)
        entry = _CacheEntry(
            provider=provider, artifact_id=artifact.artifact_id, expires_at=self._clock() + ttl
        )
        destination = self._entry_path(provider, request)
        with NamedTemporaryFile(dir=self._root, delete=False) as stream:
            temporary = Path(stream.name)
            _ = stream.write(entry.model_dump_json(indent=2).encode())
            stream.flush()
            os.fsync(stream.fileno())
        _ = temporary.replace(destination)

    def _entry_path(self, provider: str, request: RequestInput) -> Path:
        content = _canonical_json({"provider": provider, "request": freeze_request(request)})
        key = hashlib.sha256(content).hexdigest()
        return self._root / f"{key}.json"


def _safe_provider(provider: str) -> str:
    safe = "".join(character for character in provider if character.isalnum() or character in "-_")
    if not safe:
        raise ValueError(UNSAFE_PROVIDER)
    return safe


def _write_once(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as stream:
            _ = stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise RuntimeError(ARTIFACT_COLLISION) from None


def freeze_request(request: RequestInput) -> RequestOptions:
    return tuple(sorted(request.items()))


def _artifact_id(identity: _ArtifactIdentity) -> str:
    content = _canonical_json(
        {
            "provider": identity.provider,
            "version": identity.provider_version,
            "acquired_at": identity.acquired_at.isoformat(),
            "request": identity.request,
            "checksum": identity.checksum,
            "media_type": identity.media_type,
        }
    )
    return hashlib.sha256(content).hexdigest()


def _to_artifact(metadata: _RawMetadata, payload_path: Path, metadata_path: Path) -> RawArtifact:
    return RawArtifact(
        artifact_id=metadata.artifact_id,
        provider=metadata.provider,
        provider_version=metadata.provider_version,
        acquired_at=metadata.acquired_at,
        request=metadata.request,
        checksum=metadata.checksum,
        media_type=metadata.media_type,
        payload_path=payload_path,
        metadata_path=metadata_path,
    )
