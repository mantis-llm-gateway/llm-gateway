from collections.abc import Mapping
from enum import Enum
from typing import Any

from botocore.exceptions import ClientError


class ErrorAction(Enum):
    RETRY = "retry"
    COOLDOWN = "cooldown"
    FAILOVER = "failover"
    ABORT = "abort"


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def bedrock_error_code(e: ClientError) -> str:
    error = _as_mapping(e.response.get("Error"))
    code = error.get("Code")
    return str(code) if code is not None else "Unknown"


def bedrock_error_message(e: ClientError) -> str:
    error = _as_mapping(e.response.get("Error"))
    message = error.get("Message")
    return str(message) if message is not None else ""


def bedrock_status_code(e: ClientError) -> int:
    metadata = _as_mapping(e.response.get("ResponseMetadata"))
    status = metadata.get("HTTPStatusCode")
    return status if isinstance(status, int) else 500


def classify_bedrock_error(e: ClientError) -> tuple[ErrorAction, int]:
    code = bedrock_error_code(e)
    status = bedrock_status_code(e)

    if code == "ThrottlingException":
        return ErrorAction.COOLDOWN, 429
    if code in {"ServiceUnavailable", "RequestTimeoutException"}:
        return ErrorAction.FAILOVER, 503
    if 400 <= status < 500:
        # Abort because client-side error
        return ErrorAction.ABORT, status
    if status >= 500:
        return ErrorAction.RETRY, status
    return ErrorAction.FAILOVER, status
