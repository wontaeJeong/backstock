import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from packages.market_data.errors import MarketDataError

INVALID_ATTEMPTS: Final = "max_attempts must be at least one"
INVALID_DELAY: Final = "retry delays must be non-negative"
EXHAUSTED_RETRY: Final = "retry loop exhausted without returning or raising"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    jitter_seconds: float = 0.1

    def __post_init__(self) -> None:
        """Reject retry policies that cannot produce bounded delays."""
        if self.max_attempts < 1:
            raise ValueError(INVALID_ATTEMPTS)
        if min(self.initial_delay_seconds, self.max_delay_seconds, self.jitter_seconds) < 0:
            raise ValueError(INVALID_DELAY)


def retry_call[ResultT](
    operation: Callable[[], ResultT],
    *,
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> ResultT:
    for attempt in range(policy.max_attempts):
        try:
            return operation()
        except MarketDataError as error:
            if not error.retryable or attempt + 1 >= policy.max_attempts:
                raise
            exponential_delay: float = policy.initial_delay_seconds * (2.0**attempt)
            backoff: float = min(exponential_delay, policy.max_delay_seconds)
            delay: float = min(
                backoff + (jitter() * policy.jitter_seconds), policy.max_delay_seconds
            )
            if error.retry_after_seconds is not None:
                delay = min(max(delay, error.retry_after_seconds), policy.max_delay_seconds)
            sleep(delay)
    raise RuntimeError(EXHAUSTED_RETRY)
