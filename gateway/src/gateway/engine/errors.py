from enum import Enum

from botocore.exceptions import ClientError


class ErrorAction(Enum):
    RETRY = "retry"
    COOLDOWN = "cooldown"
    FAILOVER = "failover"
    ABORT = "abort"


def classify_bedrock_error(e: ClientError) -> tuple[ErrorAction, int]:
    code = e.response["Error"]["Code"]
    status = e.response["ResponseMetadata"]["HTTPStatusCode"]

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
