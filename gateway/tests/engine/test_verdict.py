from gateway.engine.verdict import Abort, CompleteSuccess, Failover, StreamingSuccess


class TestVerdict:
    def test_complete_success_carries_response(self):
        verdict = CompleteSuccess(response="hello world")
        assert verdict.response == "hello world"

    def test_streaming_success_constructs(self):
        async def gen():
            yield "chunk"

        verdict = StreamingSuccess(chunks=gen())
        assert verdict.chunks is not None

    def test_abort_carries_status_code_and_default_message(self):
        verdict = Abort(status_code=400)
        assert verdict.status_code == 400
        assert verdict.message == "bad request"

    def test_failover_carries_status_code_and_default_message(self):
        verdict = Failover(status_code=503)
        assert verdict.status_code == 503
        assert verdict.message == "service unavailable"

    def test_abort_message_override(self):
        verdict = Abort(status_code=401, message="unauthorized")
        assert verdict.message == "unauthorized"
