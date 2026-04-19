"""Resource detector — reads cgroup limits to determine container CPU and memory.

Works inside Docker containers where os.cpu_count() returns host values.
Reads cgroup v2 files for accurate container limits.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Per-worker overhead: each concurrent clip runs FFmpeg (300-500MB for HD) +
# optionally loads YOLO/MediaPipe for cover selection. Use conservative estimate.
_WORKER_MEM_OVERHEAD_GB = 0.6

# Memory reserved for the main process + Celery + Redis client + OS (GB)
_BASE_MEM_RESERVED_GB = 2.0

# Safety caps: prevent extreme parallelism even on huge machines
_MAX_CLIP_WORKERS = 4
_MAX_FRAME_WORKERS = 3


def detect_container_cpu() -> float:
    """Detect CPU limit from cgroup v2, fall back to os.cpu_count()."""
    try:
        cpu_max_path = Path("/sys/fs/cgroup/cpu.max")
        if cpu_max_path.exists():
            content = cpu_max_path.read_text().strip()
            parts = content.split()
            if len(parts) == 2 and parts[0] != "max":
                return int(parts[0]) / int(parts[1])
    except Exception:
        pass
    return float(os.cpu_count() or 2)


def detect_container_memory_gb() -> float:
    """Detect memory limit from cgroup v2, fall back to /proc/meminfo."""
    try:
        mem_max_path = Path("/sys/fs/cgroup/memory.max")
        if mem_max_path.exists():
            val = mem_max_path.read_text().strip()
            if val != "max":
                return int(val) / (1024 ** 3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) * 1024 / (1024 ** 3)
    except Exception:
        pass
    return 4.0


def calculate_parallelism() -> dict[str, float | int]:
    """Calculate optimal parallelism based on detected container resources.

    Returns:
        {
            "cpu_cores": float,
            "memory_gb": float,
            "clip_workers": int,    # parallel workers for process_clips
            "frame_workers": int,   # parallel workers for frame analysis
        }
    """
    cpu = detect_container_cpu()
    mem = detect_container_memory_gb()

    available_mem_workers = max(1, int((mem - _BASE_MEM_RESERVED_GB) / _WORKER_MEM_OVERHEAD_GB))

    clip_workers = min(int(cpu), available_mem_workers, _MAX_CLIP_WORKERS)
    clip_workers = max(1, clip_workers)

    frame_workers = min(int(cpu), available_mem_workers, _MAX_FRAME_WORKERS)
    frame_workers = max(1, frame_workers)

    logger.info(
        "Resource detection: cpu=%.1f, mem=%.1fGB, clip_workers=%d, frame_workers=%d",
        cpu, mem, clip_workers, frame_workers,
    )

    return {
        "cpu_cores": cpu,
        "memory_gb": mem,
        "clip_workers": clip_workers,
        "frame_workers": frame_workers,
    }
