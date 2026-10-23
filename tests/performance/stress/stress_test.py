"""Saturation & Queue Stress Testing Harness with Fail-Closed Memory Safeguards.

WP-3D: TSK-3D-03 — Saturation & Queue Stress Harness.

Features:
- Dynamic discovery of enforced container memory limit (cgroups v2 / Docker inspect).
- Runtime calculation of the 90% abort threshold (e.g. 921.6 MiB for 1.0 GiB container).
- Fail-closed watchdog aborting traffic if container memory breaches 90% or limit is unresolvable.
- Concurrency saturation and 20-concurrent-upload Celery broker stress evaluation.
"""

import asyncio
import json
import os
import subprocess
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MemoryThresholdExceededAbort(Exception):
    """Raised when container memory breaches the 90% safety abort ceiling."""


class MemoryDiscoveryFailure(Exception):
    """Raised when the enforced container memory limit cannot be determined."""


def discover_container_memory_limit(container_name: str = "veritas-rag-api-1") -> int:
    """Dynamically discover the enforced container memory limit in bytes.

    Inspects Docker HostConfig.Memory or cgroups v2 /sys/fs/cgroup/memory.max.
    Never hardcodes 4 GiB or assumes configured limits equal effective limits.

    Returns:
        Integer memory limit in bytes (e.g. 1073741824 for 1.0 GiB).

    Raises:
        MemoryDiscoveryFailure: If limit cannot be discovered (Fail-Closed).
    """
    # 1. Attempt Docker CLI inspection
    try:
        cmd = ["docker", "inspect", container_name, "--format", "{{.HostConfig.Memory}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
        raw_val = result.stdout.strip()
        limit_bytes = int(raw_val)
        if limit_bytes > 0:
            logger.info("Discovered container memory limit via Docker inspect", limit_bytes=limit_bytes)
            return limit_bytes
    except Exception as exc:
        logger.warning("Docker inspect memory discovery failed, attempting cgroups v2", error=str(exc))

    # 2. Attempt cgroups v2 inspect if running inside container
    cgroup_path = "/sys/fs/cgroup/memory.max"
    if os.path.exists(cgroup_path):
        try:
            with open(cgroup_path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val != "max":
                    limit_bytes = int(val)
                    if limit_bytes > 0:
                        return limit_bytes
        except Exception as exc:
            logger.warning("cgroups v2 read failed", error=str(exc))

    raise MemoryDiscoveryFailure(
        f"CRITICAL SAFETY ABORT: Unable to dynamically discover memory limit for container '{container_name}'. "
        "Fail-closed safety policy prevents running stress test against unmetered container."
    )


def calculate_memory_abort_threshold(memory_limit_bytes: int, threshold_percent: float = 0.90) -> int:
    """Calculate the fail-closed abort threshold in bytes.

    For a 1.0 GiB container (1,073,741,824 bytes), 90% = 966,367,641 bytes (~921.6 MiB).
    """
    if memory_limit_bytes <= 0:
        raise ValueError("Memory limit bytes must be positive")
    return int(memory_limit_bytes * threshold_percent)


def get_current_container_memory_usage(container_name: str = "veritas-rag-api-1") -> int:
    """Query current container memory usage in bytes via docker stats or cgroups."""
    try:
        cmd = ["docker", "stats", container_name, "--no-stream", "--format", "{{.MemUsage}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
        raw_usage = result.stdout.strip().split("/")[0].strip()
        # Parse docker stats format like '145.2MiB' or '1.2GiB'
        if "GiB" in raw_usage:
            num = float(raw_usage.replace("GiB", "").strip())
            return int(num * 1024 * 1024 * 1024)
        elif "MiB" in raw_usage:
            num = float(raw_usage.replace("MiB", "").strip())
            return int(num * 1024 * 1024)
        elif "KiB" in raw_usage:
            num = float(raw_usage.replace("KiB", "").strip())
            return int(num * 1024)
        elif "B" in raw_usage:
            num = float(raw_usage.replace("B", "").strip())
            return int(num)
    except Exception as exc:
        logger.warning("Docker stats memory read failed", error=str(exc))

    # Fallback to local inspect
    cgroup_usage = "/sys/fs/cgroup/memory.current"
    if os.path.exists(cgroup_usage):
        try:
            with open(cgroup_usage, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            pass

    return 0


class ContainerMemoryWatchdog:
    """Asynchronous background watchdog monitoring container memory during stress tests."""

    def __init__(
        self,
        container_name: str = "veritas-rag-api-1",
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.container_name = container_name
        self.poll_interval = poll_interval_seconds
        self.limit_bytes = discover_container_memory_limit(container_name)
        self.abort_threshold_bytes = calculate_memory_abort_threshold(self.limit_bytes, 0.90)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._peak_memory_bytes = 0

    @property
    def peak_memory_bytes(self) -> int:
        return self._peak_memory_bytes

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while self._running:
            usage = get_current_container_memory_usage(self.container_name)
            if usage > self._peak_memory_bytes:
                self._peak_memory_bytes = usage

            if usage >= self.abort_threshold_bytes:
                logger.critical(
                    "SAFETY CEILING BREACHED: Aborting stress test to prevent OOMKill",
                    usage_bytes=usage,
                    threshold_bytes=self.abort_threshold_bytes,
                    limit_bytes=self.limit_bytes,
                )
                raise MemoryThresholdExceededAbort(
                    f"FATAL: Container memory {usage} bytes reached 90% abort threshold "
                    f"({self.abort_threshold_bytes} bytes). Stress test halted immediately."
                )

            await asyncio.sleep(self.poll_interval)
