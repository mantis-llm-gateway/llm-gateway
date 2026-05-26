from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError

from gateway.engine.executor import execute_attempt
from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess
from gateway.models import ChatMessageRequest
from gateway.routing import ResolvedTarget


def _start_time() -> datetime:
    return datetime.now(UTC)


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


def make_messages(content: str = "hi") -> list[ChatMessageRequest]:
    return [ChatMessageRequest(role="user", content=content)]


@pytest.fixture
def target() -> ResolvedTarget:
    return ResolvedTarget(provider="bedrock", model="claude-opus-4-7")


@pytest.mark.asyncio
class TestExecuteAttempt:
    async def test_non_stream_success_returns_complete_success(
        self, fake_adaptor, fake_redis, target
    ):
        fake_adaptor.response = "hello"

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, CompleteSuccess)
        assert verdict.response == "hello"

    async def test_stream_success_returns_streaming_success(self, fake_adaptor, fake_redis, target):
        fake_adaptor.stream_response = ["he", "llo"]

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=True,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, StreamingSuccess)
        assert [chunk async for chunk in verdict.chunks] == ["he", "llo"]

    async def test_stream_setup_error_can_failover(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("ServiceUnavailable", 503)

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=True,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert verdict.status_code == 503

    async def test_passes_model_id_and_messages_to_adaptor(self, fake_adaptor, fake_redis, target):
        fake_adaptor.response = "hello"

        await execute_attempt(
            target,
            messages=[
                ChatMessageRequest(role="user", content="say hi"),
                ChatMessageRequest(role="assistant", content="hi"),
                ChatMessageRequest(role="user", content="say it again"),
            ],
            metadata={},
            prompt="say hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        model_id, messages = fake_adaptor.send_request_calls[0]

        assert model_id == "claude-opus-4-7"
        assert messages == [
            {"role": "user", "content": [{"text": "say hi"}]},
            {"role": "assistant", "content": [{"text": "hi"}]},
            {"role": "user", "content": [{"text": "say it again"}]},
        ]

    async def test_throttling_sets_cooldown_and_failovers(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("ThrottlingException", 429)

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert "gateway:cooldown:bedrock:claude-opus-4-7" in fake_redis._cooldowns
        assert verdict.message == "ThrottlingException"

    async def test_service_unavailable_failovers_without_cooldown(
        self, fake_adaptor, fake_redis, target
    ):
        fake_adaptor.error = make_bedrock_error("ServiceUnavailable", 503)

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert not fake_redis._cooldowns
        assert verdict.message == "ServiceUnavailable"

    async def test_4xx_returns_abort(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("ValidationException", 400)

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=0,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Abort)
        assert verdict.status_code == 400
        assert verdict.message == "ValidationException"

    async def test_5xx_retries_then_failovers(self, fake_adaptor, fake_redis, target):
        fake_adaptor.error = make_bedrock_error("InternalServerError", 500)

        verdict = await execute_attempt(
            target,
            messages=make_messages(),
            metadata={},
            prompt="hi",
            stream=False,
            start_time=_start_time(),
            adaptor=fake_adaptor,
            redis=fake_redis,
            target_retries=2,
            cooldown_ttl=60,
        )

        assert isinstance(verdict, Failover)
        assert verdict.status_code == 500
        assert verdict.message == "service unavailable"

    async def test_guardrail_intervention_logs_warning_and_returns_complete_success(
        self, fake_adaptor, fake_redis, target, caplog
    ):
        import logging

        fake_adaptor.guardrail_intervention = True

        with caplog.at_level(logging.WARNING, logger="gateway.engine.executor"):
            verdict = await execute_attempt(
                target,
                metadata={"user": "test"},
                prompt="hi",
                stream=False,
                start_time=_start_time(),
                adaptor=fake_adaptor,
                redis=fake_redis,
                target_retries=0,
                cooldown_ttl=60,
            )

        assert isinstance(verdict, CompleteSuccess)
        assert verdict.response == "blocked by guardrail"
        assert any("guardrail intervened" in r.message for r in caplog.records)
