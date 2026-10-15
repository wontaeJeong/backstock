from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import BinaryIO, cast

import pytest

from packages.market_data.snapshots import _write_once


def test_reader_never_sees_partial_immutable_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "result.json"
    payload = b"a" * (10 * 1024 * 1024)
    opened = Event()
    release = Event()
    original = Path.open

    def slow_creation(file: Path, mode: str = "r") -> BinaryIO:
        stream = cast("BinaryIO", original(file, mode))
        if file == path and mode == "xb":
            opened.set()
            _ = release.wait(timeout=5)
        return stream

    monkeypatch.setattr(Path, "open", slow_creation)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_write_once, path, payload)
        try:
            if opened.wait(timeout=0.2):
                assert path.read_bytes() == payload
        finally:
            release.set()
        future.result(timeout=5)
    assert path.read_bytes() == payload
