import time
from typing import Dict

class MetricsRegistry:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.counters: Dict[str, int] = {
            "raguard_http_requests_total": 0,
            "raguard_http_errors_total": 0,
            "raguard_tokens_consumed_total": 0
        }
        self.histograms: Dict[str, list] = {
            "raguard_http_request_duration_seconds": []
        }

    def increment_counter(self, name: str, value: int = 1):
        if name in self.counters:
            self.counters[name] += value
        else:
            self.counters[name] = value

    def record_histogram(self, name: str, value: float):
        if name not in self.histograms:
            self.histograms[name] = []
        self.histograms[name].append(value)
        # In a real prometheus implementation, this is grouped into buckets

    def export_metrics(self) -> str:
        lines = []
        for name, value in self.counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
            
        for name, values in self.histograms.items():
            if not values:
                continue
            avg = sum(values) / len(values)
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_sum {sum(values)}")
            lines.append(f"{name}_count {len(values)}")
            lines.append(f"{name}_avg {avg}")
            
        return "\n".join(lines) + "\n"
