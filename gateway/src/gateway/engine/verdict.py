from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class CompleteSuccess:
    response: str


@dataclass(frozen=True)
class StreamingSuccess:
    chunks: AsyncIterator[str]


@dataclass(frozen=True)
class Abort:
    """Client-side error (non-429 4xx). Do not try any more targets."""

    status_code: int
    message: str = "bad request"


@dataclass(frozen=True)
class Failover:
    """Provider-side problem (5xx, 429, retries exhausted). Try the next target."""

    status_code: int
    message: str = "service unavailable"


Verdict = CompleteSuccess | StreamingSuccess | Abort | Failover
