from botocore.exceptions import ClientError

from gateway.engine.errors import ErrorAction, classify_bedrock_error


def _err(code: str, http: int) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": http},
        },
        operation_name="InvokeModel",
    )


class TestClassifyBedrockError:
    def test_throttling_is_cooldown(self):
        action, code = classify_bedrock_error(_err("ThrottlingException", 429))
        assert action == ErrorAction.COOLDOWN
        assert code == 429

    def test_service_unavailable_is_failover(self):
        action, _ = classify_bedrock_error(_err("ServiceUnavailable", 503))
        assert action == ErrorAction.FAILOVER

    def test_client_4xx_is_abort(self):
        action, code = classify_bedrock_error(_err("ValidationException", 400))
        assert action == ErrorAction.ABORT
        assert code == 400

    def test_server_5xx_is_retry(self):
        action, _ = classify_bedrock_error(_err("InternalServerError", 500))
        assert action == ErrorAction.RETRY
