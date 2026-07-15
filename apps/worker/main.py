import json
import logging

import anyio

from packages.shared.logging import configure_logging
from packages.shared.settings import get_settings


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger("backstock.worker").info(
        json.dumps({"event": "worker.started", "environment": settings.app_env})
    )
    await anyio.sleep_forever()


def main() -> None:
    anyio.run(run_worker)


if __name__ == "__main__":
    main()
