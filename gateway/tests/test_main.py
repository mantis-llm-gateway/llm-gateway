import json


class FakeSsmClient:
    def __init__(self, value: str) -> None:
        self.value = value
        self.put_parameter_calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def get_parameter(self, **kwargs):
        return {"Parameter": {"Value": self.value}}

    async def put_parameter(self, **kwargs):
        self.put_parameter_calls.append(kwargs)


class FakeAioboto3Session:
    def __init__(self, client: FakeSsmClient) -> None:
        self._client = client

    def client(self, *args, **kwargs):
        return self._client


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_config_returns_reload_metadata(client, test_config):
    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "config": json.loads(test_config.model_dump_json()),
        "reload_required": False,
    }


def test_get_config_flags_when_parameter_store_differs(
    client, test_config, test_context, monkeypatch
):
    persisted_config = test_config.model_copy(update={"default_model": "fallback"})
    fake_ssm = FakeSsmClient(persisted_config.model_dump_json())
    test_context.settings.parameter_store_config_key = "/gw-test/routing/config"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(fake_ssm))

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "config": json.loads(persisted_config.model_dump_json()),
        "reload_required": True,
    }


def test_update_config_requires_parameter_store(client, test_config, test_context):
    updated_config = test_config.model_copy(update={"default_model": "fallback"})

    response = client.post("/config", json=json.loads(updated_config.model_dump_json()))

    assert response.status_code == 409
    assert test_context.config.default_model == "model-a"


def test_update_config_writes_parameter_store_without_replacing_active_config(
    client, test_config, test_context, monkeypatch
):
    updated_config = test_config.model_copy(update={"default_model": "fallback"})
    fake_ssm = FakeSsmClient(test_config.model_dump_json())
    test_context.settings.parameter_store_config_key = "/gw-test/routing/config"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(fake_ssm))

    response = client.post("/config", json=json.loads(updated_config.model_dump_json()))

    assert response.status_code == 200
    assert response.json() == {
        "config": json.loads(updated_config.model_dump_json()),
        "reload_required": True,
    }
    assert fake_ssm.put_parameter_calls == [
        {
            "Name": "/gw-test/routing/config",
            "Value": updated_config.model_dump_json(),
            "Type": "String",
            "Overwrite": True,
        }
    ]
    assert test_context.config.default_model == "model-a"


def test_handler_returns_200_with_response_text(client):
    response = client.post(
        "/v1/chat/completions",
        headers={"metadata": json.dumps({"task-type": "code_generation"})},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"response": "fake response"}


def test_handler_passes_full_chat_history_to_provider(client, fake_adaptor):
    response = client.post(
        "/v1/chat/completions",
        headers={"metadata": json.dumps({"task-type": "code_generation"})},
        json={
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "what did I just say?"},
            ],
            "stream": False,
        },
    )

    assert response.status_code == 200
    _, messages = fake_adaptor.send_request_calls[0]
    assert messages == [
        {"role": "user", "content": [{"text": "hello"}]},
        {"role": "assistant", "content": [{"text": "hi"}]},
        {"role": "user", "content": [{"text": "what did I just say?"}]},
    ]


def test_handler_returns_422_when_messages_is_empty(client):
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [], "stream": False},
    )
    assert response.status_code == 422


def test_handler_returns_422_when_message_content_is_blank(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "   "}],
            "stream": False,
        },
    )
    assert response.status_code == 422


def test_handler_returns_422_for_unsupported_message_role(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "system", "content": "answer briefly"}],
            "stream": False,
        },
    )
    assert response.status_code == 422


def test_handler_returns_422_for_invalid_metadata_header(client):
    response = client.post(
        "/v1/chat/completions",
        headers={"metadata": "not-json"},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )
    assert response.status_code == 422
