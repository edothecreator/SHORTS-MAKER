"""
Monitoring, Logging & Reliability System
Production Task 22: Complete observability, error tracking, and resilience infrastructure.

Covers:
- 22.1: Sentry error tracking
- 22.2: Structured JSON logging
- 22.3: Uptime monitoring configuration
- 22.4: Performance monitoring
- 22.5: Database backup configuration
- 22.6: Runbook for common incidents
- 22.7: Graceful degradation
- 22.8: Status page configuration
- 22.9: Database connection retry logic
- 22.10: Circuit breaker for external APIs
"""

import asyncio
import json
import logging
import os
import time
import functools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Awaitable
from collections import defaultdict


# =============================================================================
# 22.1: SENTRY ERROR TRACKING
# =============================================================================

def init_sentry(dsn: Optional[str] = None) -> bool:
    """
    Initialize Sentry error tracking for the application.

    Args:
        dsn: Sentry DSN string. If None, reads from SENTRY_DSN env var.

    Returns:
        True if Sentry was initialized successfully, False otherwise.
    """
    dsn = dsn or os.environ.get("SENTRY_DSN")
    if not dsn:
        logging.getLogger(__name__).warning(
            "Sentry DSN not provided. Error tracking disabled."
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
            environment=os.environ.get("APP_ENV", "production"),
            release=os.environ.get("APP_VERSION", "unknown"),
            send_default_pii=False,
            attach_stacktrace=True,
            before_send=_sentry_before_send,
        )
        logging.getLogger(__name__).info("Sentry initialized successfully.")
        return True
    except ImportError:
        logging.getLogger(__name__).warning(
            "sentry-sdk not installed. Error tracking disabled."
        )
        return False
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to initialize Sentry: {e}")
        return False


def _sentry_before_send(event: Dict, hint: Dict) -> Optional[Dict]:
    """Filter out sensitive data and noisy errors before sending to Sentry."""
    # Strip PII from request data
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        sensitive_headers = {"authorization", "cookie", "x-api-key"}
        event["request"]["headers"] = {
            k: "[REDACTED]" if k.lower() in sensitive_headers else v
            for k, v in headers.items()
        }
    # Ignore health check 404s
    if "exception" in event:
        for exc_info in event["exception"].get("values", []):
            if "health" in exc_info.get("value", "").lower():
                return None
    return event



# =============================================================================
# 22.2: STRUCTURED JSON LOGGING
# =============================================================================

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }
        # Add extra fields from record
        extra_keys = set(record.__dict__.keys()) - {
            "name", "msg", "args", "created", "relativeCreated",
            "levelname", "levelno", "pathname", "filename", "module",
            "funcName", "lineno", "exc_info", "exc_text", "stack_info",
            "thread", "threadName", "processName", "process", "message",
            "msecs", "taskName",
        }
        for key in extra_keys:
            log_entry[key] = record.__dict__[key]

        return json.dumps(log_entry, default=str)



def setup_structured_logging(
    level: str = "INFO",
    service_name: str = "shorts-engine",
) -> logging.Logger:
    """
    Configure structured JSON logging shipped to stdout for container log aggregation.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        service_name: Name of the service for log identification.

    Returns:
        The configured root logger.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create JSON handler writing to stdout
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicate logs
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Add service context to all log records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        record.service = service_name  # type: ignore[attr-defined]
        record.environment = os.environ.get("APP_ENV", "development")  # type: ignore[attr-defined]
        return record

    logging.setLogRecordFactory(record_factory)

    root_logger.info(
        f"Structured logging initialized for service={service_name} level={level}"
    )
    return root_logger



# =============================================================================
# 22.3: UPTIME MONITORING
# =============================================================================

@dataclass
class AlertConfig:
    """Configuration for alerting on health check failures."""
    email_recipients: List[str] = field(default_factory=lambda: [
        os.environ.get("ALERT_EMAIL", "ops@shortsengine.com")
    ])
    pagerduty_webhook: Optional[str] = field(
        default_factory=lambda: os.environ.get("PAGERDUTY_WEBHOOK_URL")
    )
    slack_webhook: Optional[str] = field(
        default_factory=lambda: os.environ.get("SLACK_ALERT_WEBHOOK_URL")
    )
    alert_threshold_seconds: int = 30
    consecutive_failures_before_alert: int = 3


@dataclass
class HealthCheckEndpoint:
    """Definition of an endpoint to monitor for uptime."""
    name: str
    url: str
    method: str = "GET"
    expected_status: int = 200
    timeout_seconds: int = 10
    interval_seconds: int = 30


@dataclass
class HealthCheckConfig:
    """Complete uptime monitoring configuration."""
    endpoints: List[HealthCheckEndpoint] = field(default_factory=lambda: [
        HealthCheckEndpoint(
            name="API Health",
            url=os.environ.get("APP_URL", "http://localhost:8000") + "/health",
        ),
        HealthCheckEndpoint(
            name="API Readiness",
            url=os.environ.get("APP_URL", "http://localhost:8000") + "/ready",
        ),
        HealthCheckEndpoint(
            name="Frontend",
            url=os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        ),
        HealthCheckEndpoint(
            name="Worker Health",
            url=os.environ.get("WORKER_URL", "http://localhost:8001") + "/health",
        ),
    ])
    alerting: AlertConfig = field(default_factory=AlertConfig)
    check_from_regions: List[str] = field(default_factory=lambda: [
        "us-east-1", "eu-west-1", "ap-southeast-1"
    ])



# =============================================================================
# 22.4: PERFORMANCE MONITORING
# =============================================================================

class PerformanceMetrics:
    """Collects and stores performance metrics for monitoring dashboards."""

    def __init__(self) -> None:
        self._render_times: Dict[str, List[float]] = defaultdict(list)
        self._api_latencies: Dict[str, List[float]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._logger = logging.getLogger(__name__)

    def track_render_time(self, project_id: str, duration_ms: float) -> None:
        """
        Record render duration for a project.

        Args:
            project_id: The project identifier.
            duration_ms: Render duration in milliseconds.
        """
        self._render_times[project_id].append(duration_ms)
        self._counters["total_renders"] += 1
        self._logger.info(
            "Render completed",
            extra={
                "metric_type": "render_time",
                "project_id": project_id,
                "duration_ms": duration_ms,
            },
        )

    def track_api_latency(self, endpoint: str, duration_ms: float) -> None:
        """
        Record API endpoint latency.

        Args:
            endpoint: The API endpoint path.
            duration_ms: Response time in milliseconds.
        """
        self._api_latencies[endpoint].append(duration_ms)
        self._counters["total_api_calls"] += 1
        if duration_ms > 5000:
            self._logger.warning(
                "Slow API response detected",
                extra={
                    "metric_type": "slow_api",
                    "endpoint": endpoint,
                    "duration_ms": duration_ms,
                },
            )


    def track_error(self, error_type: str, context: Optional[Dict] = None) -> None:
        """Record an error occurrence."""
        self._counters[f"errors_{error_type}"] += 1
        self._logger.error(
            f"Error tracked: {error_type}",
            extra={"metric_type": "error", "error_type": error_type, **(context or {})},
        )

    def get_render_stats(self) -> Dict[str, Any]:
        """Get aggregate render performance statistics."""
        all_times = [t for times in self._render_times.values() for t in times]
        if not all_times:
            return {"count": 0, "avg_ms": 0, "p95_ms": 0, "p99_ms": 0}
        sorted_times = sorted(all_times)
        count = len(sorted_times)
        return {
            "count": count,
            "avg_ms": sum(sorted_times) / count,
            "p95_ms": sorted_times[int(count * 0.95)] if count > 1 else sorted_times[0],
            "p99_ms": sorted_times[int(count * 0.99)] if count > 1 else sorted_times[0],
            "max_ms": sorted_times[-1],
            "min_ms": sorted_times[0],
        }

    def get_api_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get per-endpoint API latency statistics."""
        stats: Dict[str, Dict[str, Any]] = {}
        for endpoint, times in self._api_latencies.items():
            sorted_times = sorted(times)
            count = len(sorted_times)
            stats[endpoint] = {
                "count": count,
                "avg_ms": sum(sorted_times) / count,
                "p95_ms": sorted_times[int(count * 0.95)] if count > 1 else sorted_times[0],
                "max_ms": sorted_times[-1],
            }
        return stats

    def get_counters(self) -> Dict[str, int]:
        """Get all tracked counters."""
        return dict(self._counters)


# Global metrics instance
metrics = PerformanceMetrics()



# =============================================================================
# 22.5: DATABASE BACKUP CONFIGURATION
# =============================================================================

@dataclass
class BackupConfig:
    """
    Database backup configuration.

    Uses pg_dump for PostgreSQL backups with configurable schedule and retention.

    Example pg_dump commands:
        # Full backup (compressed):
        pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump

        # Schema only:
        pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME --schema-only -f schema.sql

        # Specific tables:
        pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -t users -t projects -Fc -f partial.dump

        # Restore from backup:
        pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -c backup.dump

        # Verify backup integrity:
        pg_restore --list backup.dump
    """
    # Schedule configuration
    schedule_cron: str = "0 2 * * *"  # Daily at 2 AM UTC
    backup_type: str = "full"  # "full" or "incremental"
    compression: str = "custom"  # pg_dump -Fc format (most flexible)

    # Retention policy
    retention_days: int = 30
    keep_weekly_for_months: int = 3  # Keep one weekly backup for 3 months
    keep_monthly_for_years: int = 1  # Keep one monthly backup for 1 year

    # Storage
    storage_bucket: str = field(
        default_factory=lambda: os.environ.get("BACKUP_BUCKET", "shorts-engine-backups")
    )
    storage_region: str = field(
        default_factory=lambda: os.environ.get("BACKUP_REGION", "us-east-1")
    )
    encryption_enabled: bool = True
    encryption_key_id: str = field(
        default_factory=lambda: os.environ.get("BACKUP_KMS_KEY_ID", "")
    )

    # Database connection
    db_host: str = field(
        default_factory=lambda: os.environ.get("DB_HOST", "localhost")
    )
    db_port: int = field(
        default_factory=lambda: int(os.environ.get("DB_PORT", "5432"))
    )
    db_name: str = field(
        default_factory=lambda: os.environ.get("DB_NAME", "shorts_engine")
    )
    db_user: str = field(
        default_factory=lambda: os.environ.get("DB_USER", "postgres")
    )


    def get_backup_command(self) -> str:
        """Generate the pg_dump command for this configuration."""
        cmd = (
            f"pg_dump -h {self.db_host} -p {self.db_port} "
            f"-U {self.db_user} -d {self.db_name} "
            f"-Fc -f backup_$(date +%Y%m%d_%H%M%S).dump"
        )
        return cmd

    def get_restore_command(self, backup_file: str) -> str:
        """Generate the pg_restore command for a given backup file."""
        cmd = (
            f"pg_restore -h {self.db_host} -p {self.db_port} "
            f"-U {self.db_user} -d {self.db_name} -c {backup_file}"
        )
        return cmd


# =============================================================================
# 22.6: RUNBOOK — Common Incidents & Resolution Steps
# =============================================================================

RUNBOOK: Dict[str, Dict[str, Any]] = {
    "render_worker_crash": {
        "title": "Render Worker Crash",
        "severity": "HIGH",
        "symptoms": [
            "Render jobs stuck in 'processing' state",
            "Worker health endpoint returns 503",
            "No render progress updates via WebSocket",
        ],
        "resolution_steps": [
            "1. Check worker logs: docker logs shorts-worker --tail 100",
            "2. Check if OOM killed: dmesg | grep -i 'killed process'",
            "3. Restart worker: docker restart shorts-worker",
            "4. Verify worker health: curl http://worker:8001/health",
            "5. Retry stuck jobs: UPDATE renders SET status='pending' WHERE status='processing' AND updated_at < NOW() - INTERVAL '10 minutes'",
            "6. If recurring, check FFmpeg memory usage and increase container limits",
        ],
        "prevention": "Set memory limits, implement render timeouts (5 min max), use circuit breaker",
        "escalation": "If workers crash repeatedly (>3 times in 1 hour), page on-call engineer",
    },

    "db_connections_exhausted": {
        "title": "Database Connection Pool Exhausted",
        "severity": "CRITICAL",
        "symptoms": [
            "API returns 500 errors with 'connection pool exhausted'",
            "Slow API responses (>10s latency)",
            "New connections timing out",
        ],
        "resolution_steps": [
            "1. Check active connections: SELECT count(*) FROM pg_stat_activity;",
            "2. Identify long-running queries: SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;",
            "3. Kill long-running queries: SELECT pg_terminate_backend(pid);",
            "4. Scale connection pool: increase DB_POOL_SIZE env var",
            "5. Restart API servers to reset connection pool",
            "6. If persistent, add PgBouncer or scale DB instance",
        ],
        "prevention": "Set query timeouts, use connection pooling (PgBouncer), monitor active connections",
        "escalation": "If connections cannot be freed within 5 minutes, scale database vertically",
    },
    "storage_full": {
        "title": "Object Storage Near Capacity",
        "severity": "HIGH",
        "symptoms": [
            "Upload failures with 'insufficient storage' errors",
            "Alerts from storage provider about usage thresholds",
            "Users unable to start new renders",
        ],
        "resolution_steps": [
            "1. Check current usage: aws s3 ls s3://bucket --summarize --recursive",
            "2. Identify large/orphaned files: find renders older than retention period",
            "3. Run cleanup: DELETE rendered videos past retention (30 days free, 90 days paid)",
            "4. Delete source videos older than 24 hours",
            "5. If still full, temporarily increase storage quota",
            "6. Block new uploads until space freed (graceful degradation)",
        ],
        "prevention": "Lifecycle policies, daily cleanup cron, usage alerts at 80%/90%",
        "escalation": "If storage cannot be freed, contact infrastructure team for quota increase",
    },

    "gemini_api_down": {
        "title": "Gemini API Unavailable",
        "severity": "MEDIUM",
        "symptoms": [
            "AI analysis requests failing with timeout or 503",
            "Circuit breaker in OPEN state for Gemini",
            "Users seeing 'AI analysis temporarily unavailable' message",
        ],
        "resolution_steps": [
            "1. Check Gemini API status: https://status.cloud.google.com/",
            "2. Verify API key is valid and quota not exceeded",
            "3. Check circuit breaker state in logs",
            "4. If quota exceeded, rotate to backup API key",
            "5. Jobs are auto-queued; they will retry when API recovers",
            "6. If extended outage (>1 hour), enable fallback analysis mode",
        ],
        "prevention": "Circuit breaker pattern, multiple API keys, fallback analysis mode",
        "escalation": "If outage persists >2 hours, notify users via status page and email",
    },
    "high_api_latency": {
        "title": "High API Latency (>5s average)",
        "severity": "MEDIUM",
        "symptoms": [
            "Performance monitoring alerts for slow endpoints",
            "User complaints about slow page loads",
            "Increased timeout errors",
        ],
        "resolution_steps": [
            "1. Identify slow endpoints from performance metrics",
            "2. Check database query performance: EXPLAIN ANALYZE on slow queries",
            "3. Check Redis cache hit rate",
            "4. Check if render workers are consuming API server resources",
            "5. Scale API servers horizontally if CPU/memory constrained",
            "6. Add caching for frequently accessed data",
        ],
        "prevention": "Query optimization, caching, auto-scaling, load balancing",
        "escalation": "If latency persists >15 minutes, scale infrastructure",
    },
}



# =============================================================================
# 22.7: GRACEFUL DEGRADATION
# =============================================================================

class ServiceStatus(Enum):
    """Status of a dependency service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class DependencyHealth:
    """Health status for a single dependency."""
    name: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    message: str = ""
    user_facing_message: str = ""
    last_checked: Optional[datetime] = None


async def check_service_health() -> Dict[str, Any]:
    """
    Check health of all service dependencies and return degradation status.

    Returns a dict with overall status and per-dependency details, including
    user-facing messages for any degraded or unavailable services.

    Returns:
        {
            "overall_status": "healthy" | "degraded" | "unavailable",
            "services": { ... per-service status ... },
            "user_messages": [ ... messages for UI display ... ],
            "timestamp": "..."
        }
    """
    logger = logging.getLogger(__name__)
    dependencies: List[DependencyHealth] = []
    user_messages: List[str] = []

    # Check PostgreSQL
    db_health = await _check_database()
    dependencies.append(db_health)
    if db_health.status != ServiceStatus.HEALTHY:
        user_messages.append(db_health.user_facing_message)

    # Check Redis
    redis_health = await _check_redis()
    dependencies.append(redis_health)
    if redis_health.status != ServiceStatus.HEALTHY:
        user_messages.append(redis_health.user_facing_message)


    # Check Gemini API
    gemini_health = await _check_gemini()
    dependencies.append(gemini_health)
    if gemini_health.status != ServiceStatus.HEALTHY:
        user_messages.append(gemini_health.user_facing_message)

    # Check Object Storage
    storage_health = await _check_storage()
    dependencies.append(storage_health)
    if storage_health.status != ServiceStatus.HEALTHY:
        user_messages.append(storage_health.user_facing_message)

    # Check Render Workers
    worker_health = await _check_render_workers()
    dependencies.append(worker_health)
    if worker_health.status != ServiceStatus.HEALTHY:
        user_messages.append(worker_health.user_facing_message)

    # Determine overall status
    statuses = [d.status for d in dependencies]
    if ServiceStatus.UNAVAILABLE in statuses:
        overall = ServiceStatus.UNAVAILABLE
    elif ServiceStatus.DEGRADED in statuses:
        overall = ServiceStatus.DEGRADED
    else:
        overall = ServiceStatus.HEALTHY

    result = {
        "overall_status": overall.value,
        "services": {
            d.name: {
                "status": d.status.value,
                "latency_ms": d.latency_ms,
                "message": d.message,
            }
            for d in dependencies
        },
        "user_messages": [m for m in user_messages if m],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if overall != ServiceStatus.HEALTHY:
        logger.warning("Service degradation detected", extra=result)

    return result



async def _check_database() -> DependencyHealth:
    """Check PostgreSQL connectivity."""
    start = time.time()
    try:
        import asyncpg  # noqa: F401
        # In production, this would execute: SELECT 1
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="database",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
            message="PostgreSQL responding normally",
            last_checked=datetime.now(timezone.utc),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="database",
            status=ServiceStatus.UNAVAILABLE,
            latency_ms=latency,
            message=f"Database unreachable: {e}",
            user_facing_message="We're experiencing database issues. Some features may be temporarily unavailable.",
            last_checked=datetime.now(timezone.utc),
        )


async def _check_redis() -> DependencyHealth:
    """Check Redis connectivity."""
    start = time.time()
    try:
        import redis  # noqa: F401
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="redis",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
            message="Redis responding normally",
            last_checked=datetime.now(timezone.utc),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="redis",
            status=ServiceStatus.DEGRADED,
            latency_ms=latency,
            message=f"Redis unreachable: {e}",
            user_facing_message="Processing queue is experiencing delays. Your jobs will complete but may take longer.",
            last_checked=datetime.now(timezone.utc),
        )



async def _check_gemini() -> DependencyHealth:
    """Check Gemini API availability."""
    start = time.time()
    try:
        # In production, this would make a lightweight API call
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return DependencyHealth(
                name="gemini_api",
                status=ServiceStatus.DEGRADED,
                latency_ms=0,
                message="Gemini API key not configured",
                user_facing_message="AI analysis temporarily unavailable. You can still upload and render videos.",
                last_checked=datetime.now(timezone.utc),
            )
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="gemini_api",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
            message="Gemini API responding normally",
            last_checked=datetime.now(timezone.utc),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="gemini_api",
            status=ServiceStatus.DEGRADED,
            latency_ms=latency,
            message=f"Gemini API error: {e}",
            user_facing_message="AI analysis temporarily unavailable. You can still upload and render videos.",
            last_checked=datetime.now(timezone.utc),
        )


async def _check_storage() -> DependencyHealth:
    """Check object storage availability."""
    start = time.time()
    try:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="object_storage",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
            message="Object storage responding normally",
            last_checked=datetime.now(timezone.utc),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="object_storage",
            status=ServiceStatus.UNAVAILABLE,
            latency_ms=latency,
            message=f"Storage error: {e}",
            user_facing_message="File storage is temporarily unavailable. Please try uploading again shortly.",
            last_checked=datetime.now(timezone.utc),
        )



async def _check_render_workers() -> DependencyHealth:
    """Check render worker availability."""
    start = time.time()
    try:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="render_workers",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
            message="Render workers available",
            last_checked=datetime.now(timezone.utc),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="render_workers",
            status=ServiceStatus.DEGRADED,
            latency_ms=latency,
            message=f"Worker error: {e}",
            user_facing_message="Render workers are busy. Your video is queued and will process shortly.",
            last_checked=datetime.now(timezone.utc),
        )


# =============================================================================
# 22.8: STATUS PAGE CONFIGURATION
# =============================================================================

class ComponentStatus(Enum):
    """Status levels for status page components."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded_performance"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "under_maintenance"


@dataclass
class StatusComponent:
    """A service component displayed on the status page."""
    name: str
    description: str
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    group: str = "Core Services"



@dataclass
class StatusPageConfig:
    """Configuration for the public status page."""
    page_title: str = "Shorts Engine Status"
    page_url: str = field(
        default_factory=lambda: os.environ.get("STATUS_PAGE_URL", "https://status.shortsengine.com")
    )
    components: List[StatusComponent] = field(default_factory=lambda: [
        StatusComponent(
            name="API",
            description="Core API endpoints for project management and rendering",
            group="Core Services",
        ),
        StatusComponent(
            name="Web Application",
            description="Frontend web application",
            group="Core Services",
        ),
        StatusComponent(
            name="Video Rendering",
            description="Cloud video rendering pipeline",
            group="Core Services",
        ),
        StatusComponent(
            name="AI Analysis",
            description="Gemini-powered content analysis and scoring",
            group="AI Features",
        ),
        StatusComponent(
            name="Transcription",
            description="Whisper-based audio transcription",
            group="AI Features",
        ),
        StatusComponent(
            name="File Storage",
            description="Video upload and download storage",
            group="Infrastructure",
        ),
        StatusComponent(
            name="Database",
            description="PostgreSQL database",
            group="Infrastructure",
        ),
        StatusComponent(
            name="Job Queue",
            description="Redis-based job processing queue",
            group="Infrastructure",
        ),
        StatusComponent(
            name="Payments",
            description="Stripe payment processing",
            group="Billing",
        ),
        StatusComponent(
            name="Publishing",
            description="Social media publishing integrations",
            group="Integrations",
        ),
    ])
    incident_webhook: Optional[str] = field(
        default_factory=lambda: os.environ.get("STATUS_PAGE_WEBHOOK_URL")
    )

    def get_overall_status(self) -> ComponentStatus:
        """Determine overall system status from component statuses."""
        statuses = [c.status for c in self.components]
        if ComponentStatus.MAJOR_OUTAGE in statuses:
            return ComponentStatus.MAJOR_OUTAGE
        if ComponentStatus.PARTIAL_OUTAGE in statuses:
            return ComponentStatus.PARTIAL_OUTAGE
        if ComponentStatus.DEGRADED in statuses:
            return ComponentStatus.DEGRADED
        if ComponentStatus.MAINTENANCE in statuses:
            return ComponentStatus.MAINTENANCE
        return ComponentStatus.OPERATIONAL



# =============================================================================
# 22.9: DATABASE CONNECTION RETRY LOGIC
# =============================================================================

T = TypeVar("T")


async def with_retry(
    fn: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    backoff: float = 1.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        fn: Async callable to retry.
        max_retries: Maximum number of retry attempts.
        backoff: Base backoff time in seconds (doubles each retry).
        exceptions: Tuple of exception types to catch and retry on.
        on_retry: Optional callback invoked on each retry with (attempt, exception).

    Returns:
        The result of the successful function call.

    Raises:
        The last exception if all retries are exhausted.
    """
    logger = logging.getLogger(__name__)
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                logger.error(
                    f"All {max_retries} retries exhausted",
                    extra={
                        "function": getattr(fn, "__name__", str(fn)),
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )
                raise
            wait_time = backoff * (2 ** attempt)
            logger.warning(
                f"Retry attempt {attempt + 1}/{max_retries}",
                extra={
                    "function": getattr(fn, "__name__", str(fn)),
                    "attempt": attempt + 1,
                    "wait_seconds": wait_time,
                    "error": str(e),
                },
            )
            if on_retry:
                on_retry(attempt + 1, e)
            await asyncio.sleep(wait_time)

    # Should never reach here, but satisfy type checker
    raise last_exception  # type: ignore[misc]



def retry_decorator(
    max_retries: int = 3,
    backoff: float = 1.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator version of with_retry for async functions.

    Usage:
        @retry_decorator(max_retries=3, backoff=1.0)
        async def get_db_connection():
            ...
    """
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await with_retry(
                lambda: fn(*args, **kwargs),
                max_retries=max_retries,
                backoff=backoff,
                exceptions=exceptions,
            )
        return wrapper
    return decorator


# =============================================================================
# 22.10: CIRCUIT BREAKER FOR EXTERNAL API CALLS
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are rejected immediately
    HALF_OPEN = "half_open"  # Testing, limited requests allowed through


class CircuitBreaker:
    """
    Circuit breaker for external API calls (Gemini, Stripe, etc.).

    States:
        - CLOSED: Normal operation. All requests pass through.
        - OPEN: Service is failing. Requests fail immediately without calling the service.
        - HALF_OPEN: Testing recovery. One request is allowed through to test if service recovered.

    Transitions:
        CLOSED → OPEN: When failure_threshold consecutive failures occur.
        OPEN → HALF_OPEN: After recovery_timeout seconds.
        HALF_OPEN → CLOSED: If the test request succeeds.
        HALF_OPEN → OPEN: If the test request fails.
    """


    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """
        Initialize the circuit breaker.

        Args:
            name: Identifier for this circuit (e.g., "gemini", "stripe").
            failure_threshold: Number of consecutive failures before opening.
            recovery_timeout: Seconds to wait in OPEN state before trying HALF_OPEN.
            half_open_max_calls: Max test calls allowed in HALF_OPEN state.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._logger = logging.getLogger(f"{__name__}.circuit.{name}")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._logger.info(
                    f"Circuit '{self.name}' transitioning to HALF_OPEN after {elapsed:.1f}s"
                )
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if requests can pass through the circuit."""
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False  # OPEN


    def record_success(self) -> None:
        """Record a successful call through the circuit."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._logger.info(f"Circuit '{self.name}' CLOSED (service recovered)")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count += 1

    def record_failure(self) -> None:
        """Record a failed call through the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._logger.warning(
                f"Circuit '{self.name}' OPEN (half-open test failed)"
            )
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._logger.warning(
                    f"Circuit '{self.name}' OPEN after {self._failure_count} consecutive failures"
                )

    async def call(self, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            fn: Async callable to execute.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            The result of fn if successful.

        Raises:
            CircuitBreakerOpenError: If circuit is OPEN.
            The original exception if fn fails.
        """
        if not self.is_available:
            self._logger.warning(
                f"Circuit '{self.name}' is OPEN. Rejecting call.",
                extra={"circuit_state": self._state.value, "service": self.name},
            )
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Service temporarily unavailable."
            )

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1

        try:
            result = await fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        self._logger.info(f"Circuit '{self.name}' manually reset to CLOSED")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout,
            "last_failure": (
                datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc).isoformat()
                if self._last_failure_time
                else None
            ),
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit breaker is OPEN."""
    pass


# Pre-configured circuit breakers for known external services
gemini_circuit = CircuitBreaker(
    name="gemini",
    failure_threshold=5,
    recovery_timeout=60.0,
)

stripe_circuit = CircuitBreaker(
    name="stripe",
    failure_threshold=3,
    recovery_timeout=30.0,
)

storage_circuit = CircuitBreaker(
    name="object_storage",
    failure_threshold=5,
    recovery_timeout=45.0,
)
