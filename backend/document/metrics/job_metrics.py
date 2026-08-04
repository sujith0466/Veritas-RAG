"""Processing Job metrics.

Prometheus metrics for worker queue depth, step durations, and error rates.
"""

from prometheus_client import Counter, Gauge, Histogram

JOB_ENQUEUED_TOTAL = Counter(
    "raguard_jobs_enqueued_total",
    "Total number of jobs enqueued",
    ["queue", "priority"]
)

JOB_COMPLETED_TOTAL = Counter(
    "raguard_jobs_completed_total",
    "Total number of jobs successfully completed",
    ["queue"]
)

JOB_FAILED_TOTAL = Counter(
    "raguard_jobs_failed_total",
    "Total number of jobs failed (moved to DLQ)",
    ["queue", "error_code"]
)

JOB_QUEUE_DEPTH = Gauge(
    "raguard_job_queue_depth",
    "Current number of pending jobs in queue",
    ["queue"]
)

STEP_DURATION_SECONDS = Histogram(
    "raguard_job_step_duration_seconds",
    "Duration of individual pipeline steps in seconds",
    ["step_name", "status"]
)

DLQ_SIZE = Gauge(
    "raguard_dlq_size",
    "Current number of jobs in the Dead Letter Queue",
    []
)
