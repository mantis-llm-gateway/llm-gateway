import json


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
