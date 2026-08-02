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
            "backend.modules.chunking.workers.tasks",
            "backend.modules.embedding.workers.tasks",
            "backend.modules.vector.workers.tasks",
            "backend.modules.retrieval.workers.tasks",
            "backend.modules.knowledge_health.workers.tasks",
            "backend.modules.reliability.workers.tasks",
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
        # Routing — tasks go to named queues for worker specialisation
        task_default_queue="default",
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
            "embeddings": {"exchange": "embeddings", "routing_key": "embeddings"},
            "retrieval": {"exchange": "retrieval", "routing_key": "retrieval"},
            "evaluation": {"exchange": "evaluation", "routing_key": "evaluation"},
            "health": {"exchange": "health", "routing_key": "health"},
            "ai": {"exchange": "ai", "routing_key": "ai"},
        },
        # Beat schedule (Celery periodic tasks — Phase 3+)
        beat_schedule={
            # Reserved: knowledge health scan
            # "knowledge-health-scan": {
            #     "task": "backend.tasks.schedulers.health_scan",
            #     "schedule": crontab(hour=2, minute=0),  # 2am UTC daily
            # },
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
