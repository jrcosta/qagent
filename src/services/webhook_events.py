import hashlib
import hmac
import json

from src.schemas.automation import AutomationEvent


SUPPORTED_PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize"}


def verify_github_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_github_event(
    *,
    event_name: str,
    delivery_id: str,
    body: bytes,
) -> AutomationEvent | None:
    payload = json.loads(body.decode("utf-8"))
    repository = payload.get("repository", {}).get("full_name")
    if not repository:
        raise ValueError("Webhook sem repository.full_name")

    if event_name == "pull_request":
        action = payload.get("action", "")
        if action not in SUPPORTED_PULL_REQUEST_ACTIONS:
            return None
        pull_request = payload.get("pull_request") or {}
        number = payload.get("number")
        return AutomationEvent(
            delivery_id=delivery_id,
            event_name="pull_request",
            action=action,
            repository=repository,
            base_sha=pull_request.get("base", {}).get("sha", ""),
            head_sha=pull_request.get("head", {}).get("sha", ""),
            ref=pull_request.get("head", {}).get("ref"),
            fetch_ref=f"refs/pull/{number}/head" if number else None,
        )

    if event_name == "push":
        before = payload.get("before", "")
        after = payload.get("after", "")
        if not before or not after or set(after) == {"0"}:
            return None
        return AutomationEvent(
            delivery_id=delivery_id,
            event_name="push",
            action="push",
            repository=repository,
            base_sha=before,
            head_sha=after,
            ref=payload.get("ref"),
            fetch_ref=payload.get("ref"),
        )

    return None
