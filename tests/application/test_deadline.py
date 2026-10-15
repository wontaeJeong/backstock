from packages.application.simulations import RunDeadline


def test_run_deadline_requests_cancellation_without_wall_clock_sleep() -> None:
    times = iter((0.0, 1.0, 16.0))
    deadline = RunDeadline(clock=lambda: next(times))
    assert not deadline.should_cancel(1)
    assert deadline.should_cancel(2)
