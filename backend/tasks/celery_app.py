"""Celery application factory for RAGuard AI.

Configures the Celery app with Redis as broker and result backend.
No tasks are registered in Milestone 1 — this is broker configuration only.

Task queues (reserved for future milestones):
- default         : General-purpose tasks
- ingestion       : Document ingestion and embedding pipeline
- evaluation      : Golden-set evaluation runs
- health          : Knowledge health scheduled scans
- ai              : LLM calls that benefit from dedicated worker pools
"""

from celery import Celery

from backend.core.config import get_settings


def create_celery_app() -> Celery:
    """Create and configure the Celery application instance."""
    settings = get_settings()

    app = Celery(
        "raguard",
        broker=settings.redis.celery_broker_url,
        backend=settings.redis.celery_result_backend,
        include=[
            "backend.document.workers.ingestion",
            "backend.document.workers.processing_job_worker",
            "backend.document.workers.extraction_worker",
            "backend.modules.chunking.workers.tasks",
            "backend.modules.embedding.workers.tasks",
            "backend.modules.vector.workers.tasks",
            "backend.modules.retrieval.workers.tasks",
            "backend.modules.knowledge_health.workers.tasks",
            "backend.modules.reliability.workers.tasks",
            "backend.tasks.folders",
            "backend.tasks.emails",
            "backend.tasks.webhooks",
            "backend.tasks.quota",
            "backend.tasks.retention",
        ],
    )

    app.conf.update(
        # Serialisation
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Timezone
        timezone="UTC",
        enable_utc=True,
        # Task behaviour
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Result expiry: 24 hours
        result_expires=86_400,
        # Rate limiting (global default — override per task)
        task_default_rate_limit="100/m",
        task_default_queue="default",
        task_routes={
            "folders.cascade_soft_delete_subtree": {"queue": "high"},
            "folders.cascade_restore_subtree": {"queue": "medium"},
            "folders.cascade_move_subtree": {"queue": "folders.critical"},
            "folders.hard_delete_folder_subtree": {"queue": "folders.purge"},
            "jobs.process_high": {"queue": "jobs.high"},
            "jobs.process_default": {"queue": "jobs.default"},
            "backend.tasks.retention.*": {"queue": "retention"},
        },
        task_queues={
            "high": {"exchange": "high", "routing_key": "high"},
            "medium": {"exchange": "medium", "routing_key": "medium"},
            "folders.critical": {"exchange": "folders.critical", "routing_key": "folders.critical"},
            "folders.purge": {"exchange": "folders.purge", "routing_key": "folders.purge"},
            "default": {"exchange": "default", "routing_key": "default"},
            "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
            "indexing": {"exchange": "indexing", "routing_key": "indexing"},
            "embeddings": {"exchange": "embeddings", "routing_key": "embeddings"},
            "retrieval": {"exchange": "retrieval", "routing_key": "retrieval"},
            "evaluation": {"exchange": "evaluation", "routing_key": "evaluation"},
            "health": {"exchange": "health", "routing_key": "health"},
            "ai": {"exchange": "ai", "routing_key": "ai"},
            "jobs.high": {"exchange": "jobs.high", "routing_key": "jobs.high"},
            "jobs.default": {"exchange": "jobs.default", "routing_key": "jobs.default"},
            "jobs.dlq": {"exchange": "jobs.dlq", "routing_key": "jobs.dlq"},
            "webhooks": {"exchange": "webhooks", "routing_key": "webhooks"},
            "retention": {"exchange": "retention", "routing_key": "retention"},
        },
        # Beat schedule (Celery periodic tasks — Phase 3+)
        beat_schedule={
            "folder-retention-purge": {
                "task": "folders.run_retention_cron",
                "schedule": 21600.0, # Every 6 hours
            },
            "job-stale-monitor": {
                "task": "jobs.requeue_stale_jobs",
                "schedule": 300.0, # Every 5 minutes
            },
            "workspace-staleness-evaluator": {
                "task": "backend.modules.knowledge_health.workers.tasks.evaluate_all_workspaces_staleness",
                "schedule": 86400.0, # Every 24 hours
            },
            "workspace-quota-evaluator": {
                "task": "backend.tasks.quota.evaluate_workspace_quotas_task",
                "schedule": 43200.0, # Every 12 hours
            },
            "doc-retention-sweep": {
                "task": "backend.tasks.retention.run_document_retention_sweep_task",
                "schedule": 86400.0, # Every 24 hours
                "options": {"queue": "retention"},
            },
            "chat-retention-sweep": {
                "task": "backend.tasks.retention.run_chat_retention_sweep_task",
                "schedule": 86400.0, # Every 24 hours
                "options": {"queue": "retention"},
            },
        },
    )

    return app


from celery.signals import worker_process_init


@worker_process_init.connect
def init_worker(**kwargs):
    from backend.tasks.listeners import register_pipeline_listeners
    register_pipeline_listeners()

# Application-level singleton
celery_app: Celery = create_celery_app()
