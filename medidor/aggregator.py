from dataclasses import dataclass, field


@dataclass
class MetricSeries:
    values: list[float] = field(default_factory=list)

    def add(self, value: float) -> None:
        self.values.append(value)

    @property
    def average(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def peak(self) -> float:
        if not self.values:
            return 0.0
        return max(self.values)

    @property
    def current(self) -> float:
        if not self.values:
            return 0.0
        return self.values[-1]


@dataclass
class MeasurementResult:
    cpu: MetricSeries = field(default_factory=MetricSeries)
    gpu: MetricSeries = field(default_factory=MetricSeries)
    ram_mb: MetricSeries = field(default_factory=MetricSeries)
    process_counts: list[int] = field(default_factory=list)
    instance_counts: list[int] = field(default_factory=list)
    gpu_available: bool = True
    executable: str = ""
    no_process_samples: int = 0

    @property
    def had_processes(self) -> bool:
        return any(count > 0 for count in self.process_counts)
