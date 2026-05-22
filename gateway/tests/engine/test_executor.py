import pytest
from botocore.exceptions import ClientError

from gateway.engine.executor import execute_attempt
from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess
from gateway.routing import ResolvedTarget


def make_bedrock_error(code: str, http: int) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {
                "RequestId": "test-request-id",
                "HostId": "test-host-id",
                "HTTPStatusCode": http,
                "HTTPHeaders": {},
                "RetryAttempts": 0,
            },
        },
        operation_name="Converse",
    )


@pytest.fixture
def target() -> ResolvedTarget:
    return ResolvedTarget(provider="bedrock", model="claude-opus-4-7")


@pytest.mark.asyncio
class TestExecuteAttempt:
    async def test_non_stream_success_returns_complete_success(
        self, fake_adaptor, fake_redis, target
    ):
        fake_adaptor.response = [{"token": "hello"}]

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, CompleteSuccess)
        assert verdict.response == "hello"

    async def test_stream_success_returns_streaming_success(self, fake_adaptor, fake_redis, target):
        fake_adaptor.response = [{"token": "he"}, {"token": "llo"}]

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=True,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, StreamingSuccess)
        assert [chunk async for chunk in verdict.chunks] == ["he", "llo"]

    async def test_passes_model_id_messages_and_stream_to_adaptor(
        self, fake_adaptor, fake_redis, target
    ):
        fake_adaptor.response = [{"token": "hello"}]

        await execute_attempt(
            target,
            prompt="say hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        model_id, messages, stream = fake_adaptor.send_request_calls[0]

        assert model_id == "claude-opus-4-7"
        assert messages == [{"role": "user", "content": [{"text": "say hi"}]}]
        assert stream is False

    async def test_throttling_sets_cooldown_and_failovers(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("ThrottlingException", 429)

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert "cooldown:bedrock:claude-opus-4-7" in fake_redis._cooldowns

    async def test_service_unavailable_failovers_without_cooldown(
        self, fake_adaptor, fake_redis, target
    ):
        fake_adaptor.error = make_bedrock_error("ServiceUnavailable", 503)

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert not fake_redis._cooldowns

    async def test_4xx_returns_abort(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("ValidationException", 400)

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Abort)
        assert verdict.status_code == 400

    async def test_5xx_retries_then_failovers(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("InternalServerError", 500)

        verdict = await execute_attempt(
            target,
            prompt="hi",
            stream=False,
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=2,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert verdict.status_code == 500
        assert len(fake_adaptor.send_request_calls) == 3
