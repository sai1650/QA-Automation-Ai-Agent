import math
import statistics
from collections.abc import Sequence


def performance_metrics(
    durations_ms: Sequence[float],
    *,
    failed_count: int,
    total_count: int,
) -> dict[str, float | int | None]:
    if total_count < 1 or failed_count < 0 or failed_count > total_count:
        raise ValueError("Performance counts are inconsistent.")
    if len(durations_ms) != total_count:
        raise ValueError("A duration must be recorded for every attempted sample.")
    if any(not math.isfinite(value) or value < 0 for value in durations_ms):
        raise ValueError("Durations must be finite and non-negative.")
    ordered = sorted(durations_ms)
    percentile_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "sample_count": total_count,
        "mean_duration_ms": statistics.fmean(ordered),
        "median_duration_ms": statistics.median(ordered),
        "p95_duration_ms": ordered[percentile_index],
        "min_duration_ms": ordered[0],
        "max_duration_ms": ordered[-1],
        "failure_rate": failed_count / total_count,
        "retry_count": 0,
        "retry_count_supported": True,
        "token_usage_available": False,
    }
