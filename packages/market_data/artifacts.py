import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def publish_immutable(path: Path, content: bytes) -> bool:
    """Atomically publish complete bytes without replacing an existing artifact.

    Return false only when an existing artifact has different bytes. The temporary
    file is on the same filesystem so hard-link creation is an atomic no-replace.
    """
    with NamedTemporaryFile(dir=path.parent, prefix=".artifact-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            _ = stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            return path.read_bytes() == content
        return True
    finally:
        temporary.unlink(missing_ok=True)
