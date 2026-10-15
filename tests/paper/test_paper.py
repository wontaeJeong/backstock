from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# JSON fixture dictionaries deliberately exercise untrusted wire input.
# ruff: noqa: ANN401
import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.paper import PaperService
from packages.broker.paper_store import FilePaperStore
from packages.domain.paper import PaperRuleError, approve, reconcile
from packages.shared.settings import Settings


def client(root: Path, **flags: Any) -> TestClient:
    return TestClient(create_app(Settings(data_storage_path=root, **flags)))


def account(api: TestClient, cash: str = "1000") -> str:
    response = api.post("/paper/accounts", json={"name": "연습", "initial_cash": cash})
    assert response.status_code == 201, response.text
    return str(response.json()["account_id"])


def proposal(api: TestClient, identity: str, key: str = "proposal-1", **changes: Any) -> str:
    body = {
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 2,
        "reference_price": "100",
        "quote_at": "2024-01-02T15:00:00Z",
        "idempotency_key": key,
        **changes,
    }
    response = api.post(f"/paper/accounts/{identity}/proposals", json=body)
    assert response.status_code == 200, response.text
    return str(response.json()["orders"][-1]["order_id"])


def action(api: TestClient, identity: str, order: str, verb: str, key: str) -> Any:
    return api.post(
        f"/paper/accounts/{identity}/orders/{order}/{verb}", json={"idempotency_key": key}
    )


def test_explicit_approval_only_and_costs_once(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    before = api.get(f"/paper/accounts/{identity}").json()
    assert before["cash"] == "1000"
    assert before["positions"] == []
    assert before["fills"] == []
    assert before["audit"][-1]["order_id"] == order
    filled = action(api, identity, order, "approve", "approve-1")
    assert filled.status_code == 200
    state = filled.json()
    assert state["mode"] == "paper"
    assert state["cash"] == "799.87999"
    assert state["positions"][0]["quantity"] == 2
    assert state["fills"][0]["execution_price"] == "100.05"
    assert state["fills"][0]["commission"] == "0.02001"
    assert state["fills"][0]["source"] == "manual_historical_paper"
    assert action(api, identity, order, "approve", "another").status_code == 409
    assert api.get("/paper/accounts").json()["items"][0]["account_id"] == identity


def test_restart_replay_payload_and_target_conflict(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    filled = action(api, identity, order, "approve", "private-key")
    restarted = client(tmp_path)
    assert action(restarted, identity, order, "approve", "private-key").json() == filled.json()
    assert action(restarted, identity, order, "cancel", "private-key").status_code == 409
    other = proposal(api, identity, "second")
    assert action(api, identity, other, "approve", "private-key").status_code == 409
    conflict = api.post(
        f"/paper/accounts/{identity}/proposals",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 3,
            "reference_price": "100",
            "quote_at": "2024-01-02T15:00:00Z",
            "idempotency_key": "proposal-1",
        },
    )
    assert conflict.status_code == 409
    state = restarted.get(f"/paper/accounts/{identity}").json()
    assert len(state["fills"]) == 1
    assert "private-key" not in str(state)
    assert "private-key" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


@pytest.mark.parametrize(
    ("cash", "side", "code"),
    [("100", "buy", "INSUFFICIENT_CASH"), ("1000", "sell", "INSUFFICIENT_POSITION")],
)
def test_risk_cannot_be_bypassed(tmp_path: Path, cash: str, side: str, code: str) -> None:
    api = client(tmp_path)
    identity = account(api, cash)
    order = proposal(api, identity, side=side)
    rejected = action(api, identity, order, "approve", "risk")
    assert rejected.status_code == 409
    assert rejected.json()["code"] == code
    state = api.get(f"/paper/accounts/{identity}").json()
    assert state["cash"] == cash
    assert state["fills"] == []
    assert state["orders"][0]["state"] == "risk_rejected"
    retry = action(api, identity, order, "approve", "risk")
    assert retry.status_code == 409
    assert retry.json()["code"] == code
    assert api.get(f"/paper/accounts/{identity}").json() == state


def test_marks_reconcile_and_kill_safe_actions(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    action(api, identity, order, "approve", "fill")
    pending = proposal(api, identity, "pending")
    mark = {
        "symbol": "AAPL",
        "price": "120",
        "quote_at": "2024-01-03T15:00:00Z",
        "idempotency_key": "mark",
    }
    state = api.post(f"/paper/accounts/{identity}/quotes", json=mark).json()
    assert state["cash"] == "799.87999"
    assert state["positions"][0]["market_value"] == "240"
    assert state["equity"] == "1039.87999"
    assert len(state["fills"]) == 1
    assert (
        api.post(f"/paper/accounts/{identity}/quotes", json={**mark, "price": "121"}).status_code
        == 409
    )
    assert (
        api.post(f"/paper/accounts/{identity}/kill-switch", json={"enabled": True}).status_code
        == 200
    )
    assert action(api, identity, pending, "approve", "blocked").json()["code"] == "KILL_SWITCH"
    blocked = api.post(
        f"/paper/accounts/{identity}/proposals",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 1,
            "reference_price": "100",
            "quote_at": "2024-01-02T15:00:00Z",
            "idempotency_key": "blocked-proposal",
        },
    )
    assert blocked.status_code == 409
    assert action(api, identity, pending, "cancel", "safe-cancel").status_code == 200
    reconciliation = api.get(f"/paper/accounts/{identity}/reconciliation").json()
    assert reconciliation["consistent"] is True
    assert reconciliation["scope"] == "internal_paper_ledger"
    assert reconciliation["expected_cash"] == "799.87999"


def test_concurrent_approvals_serialized(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api, "250")
    first = proposal(api, identity)
    second = proposal(api, identity, "second")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda pair: action(api, identity, pair[0], "approve", pair[1]),
                [(first, "one"), (second, "two")],
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    state = api.get(f"/paper/accounts/{identity}").json()
    assert state["cash"] == "49.87999"
    assert len(state["fills"]) == 1


def test_reject_cancel_and_feature_flags(tmp_path: Path) -> None:
    api = client(tmp_path, broker_mode="production", broker_production_enabled=True)
    identity = account(api)
    order = proposal(api, identity)
    filled = action(api, identity, order, "approve", "paper-only").json()
    assert filled["mode"] == "paper"
    assert filled["fills"][0]["source"] == "manual_historical_paper"
    order = proposal(api, identity, "reject-candidate")
    assert (
        action(api, identity, order, "reject", "reject").json()["orders"][-1]["state"] == "rejected"
    )
    assert action(api, identity, order, "approve", "no").status_code == 409
    off = client(tmp_path, paper_trading_enabled=False)
    assert off.get("/paper/accounts").status_code == 503
    assert off.post("/paper/accounts", json={"name": "x", "initial_cash": "100"}).status_code == 503


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": 0},
        {"quantity": 1000001},
        {"reference_price": "NaN"},
        {"reference_price": "1000001"},
        {"quote_at": "2024-01-01T00:00:00"},
        {"side": "short"},
        {"reference_price": "0.0000001"},
    ],
)
def test_bounded_requests(tmp_path: Path, change: dict[str, Any]) -> None:
    api = client(tmp_path)
    identity = account(api)
    response = api.post(
        f"/paper/accounts/{identity}/proposals",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 2,
            "reference_price": "100",
            "quote_at": "2024-01-02T15:00:00Z",
            "idempotency_key": "key",
            **change,
        },
    )
    assert response.status_code == 422


def test_ambiguous_commit_failure_retry_cannot_double_fill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    original = Path.replace

    def replace_then_fail(path: Path, target: Any) -> Path:
        original(path, target)
        raise OSError

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", replace_then_fail)
        failed = action(api, identity, order, "approve", "retry-commit")
    assert failed.status_code == 503
    retry = action(client(tmp_path), identity, order, "approve", "retry-commit")
    assert retry.status_code == 200
    assert retry.json()["cash"] == "799.87999"
    assert len(retry.json()["fills"]) == 1


def test_configured_costs_round_trip_and_normalized_replay(tmp_path: Path) -> None:
    api = client(tmp_path)
    response = api.post(
        "/paper/accounts",
        json={
            "name": "수수료",
            "initial_cash": "1000",
            "costs": {"commission_bps": "10", "sell_tax_bps": "20", "slippage_bps": "0"},
        },
    )
    assert response.status_code == 201
    identity = response.json()["account_id"]
    buy = proposal(api, identity)
    normalized = api.post(
        f"/paper/accounts/{identity}/proposals",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 2,
            "reference_price": "100.000",
            "quote_at": "2024-01-02T10:00:00-05:00",
            "idempotency_key": "proposal-1",
        },
    )
    assert normalized.status_code == 200
    assert len(normalized.json()["orders"]) == 1
    action(api, identity, buy, "approve", "buy")
    sell = proposal(api, identity, "sell-proposal", side="sell", reference_price="120")
    result = action(api, identity, sell, "approve", "sell").json()
    assert result["cash"] == "1039.08"
    assert result["realized_pnl"] == "39.08"
    assert result["positions"] == []
    assert result["commission"] == "0.44"
    assert result["tax"] == "0.48"
    assert api.get(f"/paper/accounts/{identity}/reconciliation").json()["consistent"] is True


def test_request_logs_redact_auth_key_and_body(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    api = client(tmp_path)
    identity = account(api)
    response = api.post(
        f"/paper/accounts/{identity}/proposals",
        headers={"Authorization": "Bearer sensitive-auth"},
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 2,
            "reference_price": "100",
            "quote_at": "2024-01-02T15:00:00Z",
            "idempotency_key": "sensitive-request-key",
            "credential": "sensitive-body",
        },
    )
    assert response.status_code == 422
    assert "sensitive" not in response.text
    assert "sensitive" not in caplog.text


def test_same_key_concurrent_approval_and_read_only_reconciliation(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    callers = [client(tmp_path) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda caller: action(caller, identity, order, "approve", "same"), callers)
        )
    assert all(r.status_code == 200 for r in results)
    assert all(r.json() == results[0].json() for r in results)
    state = api.get(f"/paper/accounts/{identity}").json()
    assert len(state["fills"]) == 1
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert api.get(f"/paper/accounts/{identity}/reconciliation").json()["consistent"] is True
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


def test_notional_risk_and_order_approval_body_cannot_bypass(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    response = api.post(
        f"/paper/accounts/{identity}/proposals",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10001,
            "reference_price": "100",
            "quote_at": "2024-01-02T15:00:00Z",
            "idempotency_key": "limit",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "NOTIONAL_LIMIT"
    order = proposal(api, identity)
    response = api.post(
        f"/paper/accounts/{identity}/orders/{order}/approve",
        json={"idempotency_key": "bypass", "quantity": 1, "state": "filled"},
    )
    assert response.status_code == 422
    assert api.get(f"/paper/accounts/{identity}").json()["fills"] == []


def test_approval_failure_before_atomic_replace_preserves_pending_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)

    def fail_replace(path: Path, target: Any) -> Path:
        del path, target
        raise OSError

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_replace)
        assert action(api, identity, order, "approve", "retry").status_code == 503
    state = api.get(f"/paper/accounts/{identity}").json()
    assert state["cash"] == "1000"
    assert state["fills"] == []
    assert state["orders"][0]["state"] == "pending_approval"
    assert (
        action(client(tmp_path), identity, order, "approve", "retry").json()["cash"] == "799.87999"
    )


def test_tampered_state_fails_closed_and_prior_audit_copies_unchanged(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    commits = {p: p.read_bytes() for p in (tmp_path / "paper" / "commits").rglob("*.json")}
    order = proposal(api, identity)
    action(api, identity, order, "approve", "fill")
    assert all(p.read_bytes() == data for p, data in commits.items())
    mutable = tmp_path / "paper" / f"{identity}.json"
    mutable.write_text(mutable.read_text().replace('"cash":"799.87999"', '"cash":"999"'))
    failed = api.get(f"/paper/accounts/{identity}")
    assert failed.status_code == 409
    assert failed.json()["code"] == "PAPER_INTEGRITY_ERROR"


def test_reconciliation_detects_internal_cash_position_and_fill_corruption(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    action(api, identity, order, "approve", "fill")
    service = PaperService(FilePaperStore(tmp_path))
    state = service.get(identity)
    corrupted = state.model_copy(update={"cash": state.cash + 1, "positions": (), "audit": ()})
    report = reconcile(corrupted)
    assert report.consistent is False
    assert set(report.issues) == {
        "cash_mismatch",
        "position_mismatch",
        "cost_basis_or_realized_mismatch",
        "approval_audit_mismatch",
    }


def test_approval_notional_limit_includes_adverse_execution_price(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api, "10000000")
    order = proposal(api, identity, quantity=1, reference_price="1000000")
    rejected = action(api, identity, order, "approve", "over-execution-limit")
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "NOTIONAL_LIMIT"
    state = api.get(f"/paper/accounts/{identity}").json()
    assert state["cash"] == "10000000"
    assert state["fills"] == []


def test_domain_refuses_stale_or_never_proposed_approval(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order_id = proposal(api, identity)
    service = PaperService(FilePaperStore(tmp_path))
    pending = service.get(identity)
    original_order = pending.orders[0]
    action(api, identity, order_id, "approve", "fill")
    filled = service.get(identity)
    with pytest.raises(PaperRuleError):
        approve(filled, original_order, datetime.now(UTC))
    absent = original_order.model_copy(update={"order_id": "paper_order_" + "a" * 32})
    with pytest.raises(PaperRuleError):
        approve(pending, absent, datetime.now(UTC))


def test_historical_replay_does_not_undo_current_kill_and_quote_state(tmp_path: Path) -> None:
    api = client(tmp_path)
    identity = account(api)
    order = proposal(api, identity)
    original = action(api, identity, order, "approve", "saved")
    api.post(f"/paper/accounts/{identity}/kill-switch", json={"enabled": True})
    api.post(
        f"/paper/accounts/{identity}/quotes",
        json={
            "symbol": "AAPL",
            "price": "120",
            "quote_at": "2024-01-03T15:00:00Z",
            "idempotency_key": "later-mark",
        },
    )
    replay = action(client(tmp_path), identity, order, "approve", "saved")
    assert replay.json() == original.json()
    current = api.get(f"/paper/accounts/{identity}").json()
    assert current["kill_switch"] is True
    assert current["equity"] == "1039.87999"
    assert len(current["fills"]) == 1


def test_body_limit_and_missing_identity_fail_without_echo(tmp_path: Path) -> None:
    api = client(tmp_path)
    assert api.get("/paper/accounts/not-a-generated-id").status_code == 404
    assert (
        api.post(
            "/paper/accounts", content=b" " * 65537, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )
