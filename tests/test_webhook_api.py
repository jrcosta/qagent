import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config.settings import Settings
from src.schemas.automation import RepositoryRegistration
from src.services.automation_store import AutomationStore


def _signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()


def _payload() -> bytes:
    return json.dumps(
        {
            "action": "synchronize",
            "number": 42,
            "repository": {"full_name": "owner/repo"},
            "pull_request": {
                "base": {"sha": "base-sha"},
                "head": {"sha": "head-sha", "ref": "feature"},
            },
        }
    ).encode()


def _client(tmp_path):
    settings = Settings(
        github_webhook_secret="secret",
        admin_token="admin",
        automation_database_path=str(tmp_path / "automation.db"),
    )
    store = AutomationStore(settings.automation_database_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
        )
    )
    return TestClient(create_app(settings, store)), store


def test_repository_endpoint_rejects_non_git_path(tmp_path) -> None:
    client, _ = _client(tmp_path)
    invalid = tmp_path / "not-git"
    invalid.mkdir()

    response = client.post(
        "/repositories",
        headers={"X-QAgent-Admin-Token": "admin"},
        json={
            "full_name": "owner/invalid",
            "local_path": str(invalid),
            "output_root": str(tmp_path / "invalid-outputs"),
        },
    )

    assert response.status_code == 422


def test_webhook_rejects_invalid_signature(tmp_path) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/webhooks/github",
        content=_payload(),
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-1",
        },
    )

    assert response.status_code == 401


def test_webhook_enqueues_and_deduplicates_delivery(tmp_path) -> None:
    client, store = _client(tmp_path)
    body = _payload()
    headers = {
        "X-Hub-Signature-256": _signature(body, "secret"),
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-1",
    }

    first = client.post("/webhooks/github", content=body, headers=headers)
    second = client.post("/webhooks/github", content=body, headers=headers)

    assert first.status_code == 202
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert store.metrics().queued == 1
    job = store.get_job(first.json()["job_id"])
    assert job is not None
    assert job.fetch_ref == "refs/pull/42/head"
    assert job.pr_number == 42


def test_admin_endpoints_require_token(tmp_path) -> None:
    client, _ = _client(tmp_path)

    unauthorized = client.get("/metrics")
    authorized = client.get(
        "/metrics",
        headers={"X-QAgent-Admin-Token": "admin"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["registered_repositories"] == 1


def test_health_is_degraded_without_active_worker(tmp_path) -> None:
    client, _ = _client(tmp_path)

    health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["worker_available"] is False


def test_admin_can_retry_dead_letter_job(tmp_path) -> None:
    client, store = _client(tmp_path)
    body = _payload()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": _signature(body, "secret"),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-retry",
        },
    )
    job_id = response.json()["job_id"]
    store.dead_letter(job_id, "erro corrigível")

    retried = client.post(
        f"/jobs/{job_id}/retry",
        headers={"X-QAgent-Admin-Token": "admin"},
    )

    assert retried.status_code == 200
    assert retried.json()["status"] == "QUEUED"
    assert retried.json()["attempts"] == 0
