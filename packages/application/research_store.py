"""Local immutable research artifacts and independent archive state."""

import hashlib
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, JsonValue

from packages.market_data.snapshots import _write_once


class ResearchIntegrityError(ValueError):
    pass


def valid_id(identity: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", identity) is not None


def content_hash(payload: dict[str, JsonValue]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def verified_payload(path: Path, identity: str, key: str) -> dict[str, JsonValue]:
    """Hash stored JSON BEFORE schema defaults can change the historical payload."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        msg = "저장된 연구 결과의 무결성 검증에 실패했습니다."
        raise ResearchIntegrityError(msg) from error
    if not isinstance(payload, dict) or payload.get(key) != identity:
        msg = "저장된 연구 결과의 무결성 검증에 실패했습니다."
        raise ResearchIntegrityError(msg)
    body = {name: value for name, value in payload.items() if name != key}
    if content_hash(body) != identity:
        msg = "저장된 연구 결과의 무결성 검증에 실패했습니다."
        raise ResearchIntegrityError(msg)
    return payload


class ResearchStore:
    def __init__(self, root: Path) -> None:
        """Keep artifacts separate from mutable archive visibility sidecars."""
        self.root = root

    def save(self, kind: str, model: BaseModel, key: str) -> dict[str, JsonValue]:
        payload = model.model_dump(mode="json", exclude={key})
        identity = content_hash(payload)
        payload[key] = identity
        directory = self.root / kind
        directory.mkdir(parents=True, exist_ok=True)
        _write_once(directory / f"{identity}.json", json.dumps(payload).encode())
        return payload

    def get(self, kind: str, identity: str, key: str) -> dict[str, JsonValue] | None:
        if not valid_id(identity):
            return None
        path = self.root / kind / f"{identity}.json"
        return verified_payload(path, identity, key) if path.is_file() else None

    def ids(self, kind: str) -> list[str]:
        return sorted(p.stem for p in (self.root / kind).glob("*.json") if valid_id(p.stem))

    def archived(self, kind: str, identity: str) -> bool:
        path = self.root / "archives" / kind / f"{identity}.json"
        return path.is_file() and path.read_bytes() == b"true"

    def archive(self, kind: str, identity: str, *, archived: bool) -> None:
        if not valid_id(identity):
            raise LookupError(identity)
        directory = self.root / "archives" / kind
        directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=directory, delete=False) as temporary:
            temporary.write(b"true" if archived else b"false")
            path = Path(temporary.name)
        path.replace(directory / f"{identity}.json")
