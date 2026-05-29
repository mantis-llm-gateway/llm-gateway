import json


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
