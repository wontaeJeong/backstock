import json
import logging
import sys


def configure_logging(level: str) -> None:
    normalized_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        level=normalized_level,
        stream=sys.stdout,
        force=True,
    )


def request_log_payload(*, request_id: str, method: str, path: str, status_code: int) -> str:
    return json.dumps(
        {
            "event": "http.request.complete",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
