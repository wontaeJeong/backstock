"""Local POSIX filesystem paper adapter with same-account flock and atomic commit."""

# Error literals are allowlisted codes, not free-form exception messages.
# ruff: noqa: EM101

import fcntl
import hashlib
import os
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from packages.application.paper import PaperDocument, SavedResponse
from packages.domain.paper import PaperRuleError


class FilePaperStore:
    def __init__(self, root: Path) -> None:
        """Keep all simulation artifacts in their own storage namespace."""
        self.root = root / "paper"

    def path(self, identity: str) -> Path:
        if not re.fullmatch(r"paper_[0-9a-f]{32}", identity):
            raise PaperRuleError("NOT_FOUND")
        return self.root / f"{identity}.json"

    @contextmanager
    def lock(self, identity: str) -> Iterator[Path]:
        path = self.path(identity)
        self.root.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield path
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def create(self, document: PaperDocument) -> None:
        with self.lock(document.account.account_id) as path:
            if path.exists():
                raise PaperRuleError("IDEMPOTENCY_CONFLICT")
            self.commit(path, document)

    def get(self, account_id: str) -> PaperDocument:
        path = self.path(account_id)
        try:
            content = path.read_bytes()
        except FileNotFoundError as exc:
            raise PaperRuleError("NOT_FOUND") from exc
        try:
            document = PaperDocument.model_validate_json(content)
            if document.account.account_id != account_id:
                raise PaperRuleError("PAPER_INTEGRITY_ERROR")
            digest = hashlib.sha256(content).hexdigest()
            immutable = self.root / "commits" / account_id / f"{digest}.json"
            if immutable.read_bytes() != content:
                raise PaperRuleError("PAPER_INTEGRITY_ERROR")
        except (ValidationError, FileNotFoundError) as exc:
            raise PaperRuleError("PAPER_INTEGRITY_ERROR") from exc
        return document

    def identities(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("paper_*.json"))

    def save_response(self, response: SavedResponse) -> str:
        content = response.model_dump_json(exclude_computed_fields=True).encode()
        digest = hashlib.sha256(content).hexdigest()
        directory = self.root / "responses"
        directory.mkdir(parents=True, exist_ok=True)
        self.write_immutable(directory / f"{digest}.json", content)
        self.sync_directory(directory)
        return digest

    def get_response(self, response_id: str) -> SavedResponse:
        if not re.fullmatch(r"[0-9a-f]{64}", response_id):
            raise PaperRuleError("PAPER_INTEGRITY_ERROR")
        try:
            content = (self.root / "responses" / f"{response_id}.json").read_bytes()
            if hashlib.sha256(content).hexdigest() != response_id:
                raise PaperRuleError("PAPER_INTEGRITY_ERROR")
            return SavedResponse.model_validate_json(content)
        except (ValidationError, FileNotFoundError) as exc:
            raise PaperRuleError("PAPER_INTEGRITY_ERROR") from exc

    def transact(
        self, account_id: str, operation: Callable[[PaperDocument], PaperDocument]
    ) -> PaperDocument:
        with self.lock(account_id) as path:
            before = self.get(account_id)
            after = operation(before)
            if after is not before:
                self.commit(path, after)
            return after

    def commit(self, path: Path, document: PaperDocument) -> None:
        # Computed presentation fields are never re-ingested as persistence input.
        content = document.model_dump_json(exclude_computed_fields=True).encode()
        digest = hashlib.sha256(content).hexdigest()
        directory = self.root / "commits" / document.account.account_id
        directory.mkdir(parents=True, exist_ok=True)
        self.sync_directory(directory.parent)
        immutable = directory / f"{digest}.json"
        self.write_immutable(immutable, content)
        self.sync_directory(directory)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=self.root, prefix=".paper-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            self.sync_directory(self.root)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def write_immutable(path: Path, content: bytes) -> None:
        try:
            with path.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != content:
                raise PaperRuleError("PAPER_INTEGRITY_ERROR") from None

    @staticmethod
    def sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
