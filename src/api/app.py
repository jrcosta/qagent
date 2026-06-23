from __future__ import annotations

import hmac

from fastapi import FastAPI, Header, HTTPException, Request, status

from src.config.settings import Settings, get_settings
from src.schemas.automation import RepositoryRegistration
from src.services.automation_store import AutomationStore
from src.services.webhook_events import (
    parse_github_event,
    verify_github_signature,
)
from src.services.repository_workspace import validate_repository_registration


def create_app(
    settings: Settings | None = None,
    store: AutomationStore | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    active_store = store or AutomationStore(
        active_settings.automation_database_path
    )
    app = FastAPI(title="QAgent Autonomous Runtime", version="1.0")
    app.state.settings = active_settings
    app.state.store = active_store

    @app.get("/health")
    def health():
        try:
            metrics = active_store.metrics()
            database = "ok"
        except Exception:
            metrics = None
            database = "error"
        healthy = (
            database == "ok"
            and bool(active_settings.github_webhook_secret)
            and bool(active_settings.admin_token)
            and metrics is not None
            and metrics.active_workers > 0
        )
        return {
            "status": "ok" if healthy else "degraded",
            "database": database,
            "webhook_secret_configured": bool(
                active_settings.github_webhook_secret
            ),
            "admin_token_configured": bool(active_settings.admin_token),
            "worker_available": bool(
                metrics and metrics.active_workers > 0
            ),
            "queue": metrics.model_dump() if metrics else None,
        }

    @app.get("/metrics")
    def metrics(x_qagent_admin_token: str | None = Header(default=None)):
        _require_admin(active_settings, x_qagent_admin_token)
        return active_store.metrics().model_dump()

    @app.get("/repositories")
    def repositories(x_qagent_admin_token: str | None = Header(default=None)):
        _require_admin(active_settings, x_qagent_admin_token)
        return [
            registration.model_dump()
            for registration in active_store.list_repositories()
        ]

    @app.post("/repositories", status_code=status.HTTP_201_CREATED)
    def register_repository(
        registration: RepositoryRegistration,
        x_qagent_admin_token: str | None = Header(default=None),
    ):
        _require_admin(active_settings, x_qagent_admin_token)
        try:
            validated = validate_repository_registration(registration)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        active_store.register_repository(validated)
        return validated.model_dump()

    @app.get("/jobs/{job_id}")
    def get_job(
        job_id: str,
        x_qagent_admin_token: str | None = Header(default=None),
    ):
        _require_admin(active_settings, x_qagent_admin_token)
        job = active_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        return job.model_dump()

    @app.get("/jobs")
    def list_jobs(
        limit: int = 100,
        x_qagent_admin_token: str | None = Header(default=None),
    ):
        _require_admin(active_settings, x_qagent_admin_token)
        return [
            job.model_dump() for job in active_store.list_jobs(limit=limit)
        ]

    @app.post("/jobs/{job_id}/retry")
    def retry_job(
        job_id: str,
        x_qagent_admin_token: str | None = Header(default=None),
    ):
        _require_admin(active_settings, x_qagent_admin_token)
        try:
            job = active_store.requeue(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return job.model_dump()

    @app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str | None = Header(default=None),
        x_github_delivery: str | None = Header(default=None),
    ):
        body = await request.body()
        if not verify_github_signature(
            body,
            x_hub_signature_256,
            active_settings.github_webhook_secret,
        ):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
        if not x_github_event or not x_github_delivery:
            raise HTTPException(
                status_code=400,
                detail="Headers de evento/delivery ausentes",
            )

        try:
            event = parse_github_event(
                event_name=x_github_event,
                delivery_id=x_github_delivery,
                body=body,
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if event is None:
            return {"accepted": False, "reason": "evento ignorado"}

        registration = active_store.get_repository(event.repository)
        if registration is None or not registration.enabled:
            raise HTTPException(
                status_code=403,
                detail="Repositório não registrado ou desabilitado",
            )
        if event.event_name not in registration.allowed_events:
            raise HTTPException(
                status_code=403,
                detail="Evento não autorizado para o repositório",
            )
        if not event.base_sha or not event.head_sha:
            raise HTTPException(status_code=400, detail="SHAs ausentes")

        job, created = active_store.enqueue(event)
        return {
            "accepted": True,
            "created": created,
            "job_id": job.job_id,
            "status": job.status,
        }

    return app


def _require_admin(
    settings: Settings,
    supplied_token: str | None,
) -> None:
    if (
        not settings.admin_token
        or not supplied_token
        or not hmac.compare_digest(settings.admin_token, supplied_token)
    ):
        raise HTTPException(status_code=401, detail="Token administrativo inválido")


app = create_app()
