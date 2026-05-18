# route: (observability) | file: skill_assessment/services/archive_metrics.py
"""Lightweight in-process metrics for protocol archive operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ArchiveMetrics:
    archive_create_count: int = 0
    archive_create_duration_ms_total: float = 0.0
    archive_create_duration_ms_last: float = 0.0
    archive_size_bytes_total: int = 0
    archive_size_bytes_last: int = 0
    archive_corruption_count: int = 0
    archive_recovery_count: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def observe_created(self, *, duration_ms: float, size_bytes: int) -> None:
        with self._lock:
            self.archive_create_count += 1
            self.archive_create_duration_ms_total += float(duration_ms)
            self.archive_create_duration_ms_last = float(duration_ms)
            self.archive_size_bytes_total += int(size_bytes)
            self.archive_size_bytes_last = int(size_bytes)

    def observe_corruption(self) -> None:
        with self._lock:
            self.archive_corruption_count += 1

    def observe_recovery(self) -> None:
        with self._lock:
            self.archive_recovery_count += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            avg = (
                self.archive_create_duration_ms_total / self.archive_create_count
                if self.archive_create_count
                else 0.0
            )
            return {
                "archive_create_count": self.archive_create_count,
                "archive_create_duration_ms_total": self.archive_create_duration_ms_total,
                "archive_create_duration_ms_last": self.archive_create_duration_ms_last,
                "archive_create_duration_ms_avg": avg,
                "archive_size_bytes_total": self.archive_size_bytes_total,
                "archive_size_bytes_last": self.archive_size_bytes_last,
                "archive_corruption_count": self.archive_corruption_count,
                "archive_recovery_count": self.archive_recovery_count,
            }


archive_metrics = ArchiveMetrics()
