import hashlib
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from packages.application.simulation_models import SYMBOLS, SimulationReport, SimulationRequest
from packages.application.simulations import SimulationService
from packages.market_data.errors import MarketDataError
from packages.market_data.snapshots import SnapshotIntegrityError

MAX_REQUEST_BYTES = 65536


def _run_simulation(service: SimulationService, body: bytearray) -> SimulationReport | JSONResponse:
    try:
        return service.run(SimulationRequest.model_validate_json(body))
    except (ValidationError, ValueError) as error:
        message = "입력값을 확인하세요. 종목·기간·주기·전략 조건이 유효해야 합니다."
        if not isinstance(error, ValidationError):
            message = str(error)
        return JSONResponse({"code": "SIMULATION_INVALID", "message": message}, status_code=422)
    except MarketDataError:
        return JSONResponse(
            {
                "code": "PROVIDER_UNAVAILABLE",
                "message": "시세 공급자 조회에 실패했습니다. "
                "기간을 확인하거나 파일을 업로드하세요. "
                "데모로 자동 대체하지 않습니다.",
            },
            status_code=502,
        )
    except SnapshotIntegrityError:
        return JSONResponse(
            {
                "code": "SNAPSHOT_CORRUPT",
                "message": "데이터 무결성 검사에 실패했습니다. 다시 업로드하세요.",
            },
            status_code=409,
        )


def source_revision() -> str:
    """Bind results to source contents even in an installed image without .git."""
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for directory in (root / "apps" / "api", root / "packages"):
        for path in sorted(directory.rglob("*.py")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return f"source-sha256:{digest.hexdigest()}"


def build_simulation_router(service: SimulationService) -> APIRouter:
    router = APIRouter()

    @router.get("/research/catalog", tags=["research"])
    def catalog() -> dict[str, object]:
        return {
            "symbols": list(SYMBOLS),
            "intervals": ["1d", "1m", "5m"],
            "max_bars": 3000,
            "currency": "USD",
            "remote_intervals": ["1d"],
            "intraday_timestamp_label": "close",
            "exchange_timezone": "America/New_York",
        }

    @router.post(
        "/simulations", tags=["research"], response_model=SimulationReport, status_code=201
    )
    async def simulate(request: Request) -> SimulationReport | JSONResponse:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    {"code": "BODY_TOO_LARGE", "message": "전략 요청은 64 KiB 이하여야 합니다."},
                    status_code=413,
                )
        return await run_in_threadpool(_run_simulation, service, body)

    @router.get("/simulations/{run_id}", tags=["research"], response_model=SimulationReport)
    def get_simulation(run_id: str) -> SimulationReport | JSONResponse:
        try:
            report = service.get(run_id)
        except ValueError:
            return JSONResponse(
                {"code": "RESULT_CORRUPT", "message": "실행 결과 무결성 검사에 실패했습니다."},
                status_code=409,
            )
        if report is None:
            return JSONResponse(
                {"code": "NOT_FOUND", "message": "실행 결과를 찾을 수 없습니다."}, status_code=404
            )
        return report

    return router
