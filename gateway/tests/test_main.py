import json
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import ClientError

from gateway.main import _load_config

API_AUTH_HEADERS = {"Authorization": "Bearer gw_test-client_test-secret"}
DASHBOARD_AUTH = ("test-admin", "test-password")


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


class FakeS3Body:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def read(self) -> bytes:
        return self.content


class FakeS3Client:
    def __init__(self, objects: dict[str, tuple[bytes, str] | tuple[bytes, str, dict]]) -> None:
        self.objects = objects
        self.get_object_calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def get_object(self, **kwargs):
        self.get_object_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        content, content_type, *metadata = self.objects[key]
        return {
            "Body": FakeS3Body(content),
            "ContentType": content_type,
            **(metadata[0] if metadata else {}),
        }


class FakeAioboto3Session:
    def __init__(self, client=None, **clients) -> None:
        self._client = client
        self._clients = clients

    def client(self, service_name=None, *args, **kwargs):
        if service_name in self._clients:
            return self._clients[service_name]
        return self._client


@pytest.mark.asyncio
async def test_load_config_reads_parameter_store_with_async_client(
    test_config, test_settings, monkeypatch
):
    fake_ssm = FakeSsmClient(test_config.model_dump_json())
    test_settings.parameter_store_config_key = "/gw-test/routing/config"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(fake_ssm))

    config = await _load_config(test_settings)

    assert config == test_config


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_completions_requires_api_token(client):
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_chat_completions_rejects_invalid_api_token(client):
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer gw_test-client_wrong-secret"},
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 401


def test_chat_completions_returns_503_when_api_auth_is_not_configured(client, test_context):
    test_context.settings.api_token_hashes = {}

    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 503


def test_dashboard_requires_basic_auth(client):
    response = client.get("/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="dashboard"'


def test_config_rejects_invalid_dashboard_password(client):
    response = client.get("/config", auth=("test-admin", "wrong-password"))

    assert response.status_code == 401


def test_dashboard_returns_503_when_basic_auth_is_not_configured(client, test_context):
    test_context.settings.dashboard_password_hash = None

    response = client.get("/", auth=DASHBOARD_AUTH)

    assert response.status_code == 503


def test_get_config_returns_reload_metadata(client, test_config):
    response = client.get("/config", auth=DASHBOARD_AUTH)

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

    response = client.get("/config", auth=DASHBOARD_AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "config": json.loads(persisted_config.model_dump_json()),
        "reload_required": True,
    }


def test_update_config_requires_parameter_store(client, test_config, test_context):
    updated_config = test_config.model_copy(update={"default_model": "fallback"})

    response = client.post(
        "/config",
        json=json.loads(updated_config.model_dump_json()),
        auth=DASHBOARD_AUTH,
    )

    assert response.status_code == 409
    assert test_context.config.default_model == "model-a"


def test_update_config_writes_parameter_store_without_replacing_active_config(
    client, test_config, test_context, monkeypatch
):
    updated_config = test_config.model_copy(update={"default_model": "fallback"})
    fake_ssm = FakeSsmClient(test_config.model_dump_json())
    test_context.settings.parameter_store_config_key = "/gw-test/routing/config"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(fake_ssm))

    response = client.post(
        "/config",
        json=json.loads(updated_config.model_dump_json()),
        auth=DASHBOARD_AUTH,
    )

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


def test_dashboard_serves_asset_from_s3(client, test_context, monkeypatch):
    fake_s3 = FakeS3Client({"assets/app.js": (b"console.log('hello')", "text/javascript")})
    test_context.settings.dashboard_s3_bucket = "gw-test-dashboard"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(s3=fake_s3))

    response = client.get("/assets/app.js", auth=DASHBOARD_AUTH)

    assert response.status_code == 200
    assert response.text == "console.log('hello')"
    assert response.headers["content-type"].startswith("text/javascript")
    assert fake_s3.get_object_calls == [{"Bucket": "gw-test-dashboard", "Key": "assets/app.js"}]


def test_dashboard_normalizes_s3_last_modified_header(client, test_context, monkeypatch):
    fake_s3 = FakeS3Client(
        {
            "index.html": (
                b"<div id='root'></div>",
                "text/html",
                {"LastModified": datetime(2026, 5, 31, 10, 0, tzinfo=timezone(timedelta(hours=1)))},
            )
        }
    )
    test_context.settings.dashboard_s3_bucket = "gw-test-dashboard"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(s3=fake_s3))

    response = client.get("/", auth=DASHBOARD_AUTH)

    assert response.status_code == 200
    assert response.headers["last-modified"] == "Sun, 31 May 2026 09:00:00 GMT"


def test_dashboard_omits_naive_s3_last_modified_header(client, test_context, monkeypatch):
    fake_s3 = FakeS3Client(
        {
            "index.html": (
                b"<div id='root'></div>",
                "text/html",
                {"LastModified": datetime(2026, 5, 31, 9, 0)},
            )
        }
    )
    test_context.settings.dashboard_s3_bucket = "gw-test-dashboard"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(s3=fake_s3))

    response = client.get("/", auth=DASHBOARD_AUTH)

    assert response.status_code == 200
    assert "last-modified" not in response.headers


def test_dashboard_falls_back_to_s3_index_for_spa_routes(client, test_context, monkeypatch):
    fake_s3 = FakeS3Client({"index.html": (b"<div id='root'></div>", "text/html")})
    test_context.settings.dashboard_s3_bucket = "gw-test-dashboard"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(s3=fake_s3))

    response = client.get("/routing-rules", auth=DASHBOARD_AUTH)

    assert response.status_code == 200
    assert response.text == "<div id='root'></div>"
    assert fake_s3.get_object_calls == [
        {"Bucket": "gw-test-dashboard", "Key": "routing-rules"},
        {"Bucket": "gw-test-dashboard", "Key": "index.html"},
    ]


def test_dashboard_returns_404_for_missing_s3_asset(client, test_context, monkeypatch):
    fake_s3 = FakeS3Client({})
    test_context.settings.dashboard_s3_bucket = "gw-test-dashboard"
    monkeypatch.setattr("gateway.main.aioboto3.Session", lambda: FakeAioboto3Session(s3=fake_s3))

    response = client.get("/assets/missing.js", auth=DASHBOARD_AUTH)

    assert response.status_code == 404


def test_handler_returns_200_with_response_text(client):
    response = client.post(
        "/v1/chat/completions",
        headers={**API_AUTH_HEADERS, "metadata": json.dumps({"task-type": "code_generation"})},
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
        headers={**API_AUTH_HEADERS, "metadata": json.dumps({"task-type": "code_generation"})},
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


def test_handler_threads_inference_params_to_provider(client, fake_adaptor):
    response = client.post(
        "/v1/chat/completions",
        headers={**API_AUTH_HEADERS, "metadata": json.dumps({"task-type": "code_generation"})},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 128,
            "system": "be brief",
        },
    )

    assert response.status_code == 200
    assert fake_adaptor.send_request_inference[0] == {
        "temperature": 0.2,
        "max_tokens": 128,
        "system": "be brief",
    }


def test_handler_defaults_inference_params_to_none(client, fake_adaptor):
    response = client.post(
        "/v1/chat/completions",
        headers={**API_AUTH_HEADERS, "metadata": json.dumps({"task-type": "code_generation"})},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert fake_adaptor.send_request_inference[0] == {
        "temperature": None,
        "max_tokens": None,
        "system": None,
    }


def test_handler_returns_422_when_messages_is_empty(client):
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [], "stream": False},
        headers=API_AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_handler_returns_422_when_message_content_is_blank(client):
    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={
            "messages": [{"role": "user", "content": "   "}],
            "stream": False,
        },
    )
    assert response.status_code == 422


def test_handler_returns_422_for_unsupported_message_role(client):
    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={
            "messages": [{"role": "system", "content": "answer briefly"}],
            "stream": False,
        },
    )
    assert response.status_code == 422


def test_handler_returns_422_for_invalid_metadata_header(client):
    response = client.post(
        "/v1/chat/completions",
        headers={**API_AUTH_HEADERS, "metadata": "not-json"},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )
    assert response.status_code == 422


def test_handler_accepts_temperature_system_and_max_tokens(client):
    response = client.post(
        "/v1/chat/completions",
        headers={**API_AUTH_HEADERS, "metadata": json.dumps({"task-type": "code_generation"})},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "temperature": 0.5,
            "max_tokens": 256,
            "system": "You are a helpful assistant.",
        },
    )
    assert response.status_code == 200


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_handler_returns_422_for_out_of_range_temperature(client, temperature):
    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": temperature,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_handler_returns_422_for_non_positive_max_tokens(client, max_tokens):
    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": max_tokens,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("system", ["", "   "])
def test_handler_returns_422_for_blank_system(client, system):
    response = client.post(
        "/v1/chat/completions",
        headers=API_AUTH_HEADERS,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "system": system,
        },
    )
    assert response.status_code == 422
