import json


def test_handler_returns_failover_status_from_stub_executor(client):
    response = client.post(
        "/v1/chat/completions",
        headers={"metadata": json.dumps({"task-type": "code_generation"})},
    )
    # Executor stub returns Failover(501) for every target → orchestrator returns 501.
    assert response.status_code == 501
