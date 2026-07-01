import re
import time
from typing import Callable

import win32pdh

REFRESH_INSTANCES_EVERY = 5


class GpuPdhReader:
    COUNTER_PATH = r"\GPU Engine(*)\Utilization Percentage"

    def __init__(self) -> None:
        self._available = True
        self._pid_to_instances: dict[int, list[str]] = {}
        self._query = None
        self._counters: dict[str, int] = {}
        self._samples_since_refresh = REFRESH_INSTANCES_EVERY
        self._init_query()

    def _init_query(self) -> None:
        try:
            self._query = win32pdh.OpenQuery()
            self._refresh_instances(force=True)
        except Exception:
            self._available = False
            self._query = None

    def _refresh_instances(self, force: bool = False) -> None:
        if not self._available or self._query is None:
            return

        if not force and self._samples_since_refresh < REFRESH_INSTANCES_EVERY:
            self._samples_since_refresh += 1
            return

        self._samples_since_refresh = 0
        self._pid_to_instances.clear()
        self._counters.clear()

        try:
            _, instances = win32pdh.EnumObjectItems(
                None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD
            )
        except Exception:
            self._available = False
            return

        pid_pattern = re.compile(r"pid_(\d+)_", re.IGNORECASE)

        for instance in instances:
            match = pid_pattern.search(instance)
            if not match:
                continue
            pid = int(match.group(1))
            self._pid_to_instances.setdefault(pid, []).append(instance)

            counter_path = self.COUNTER_PATH.replace("*", instance, 1)
            try:
                self._counters[instance] = win32pdh.AddCounter(
                    self._query, counter_path
                )
            except Exception:
                continue

    @property
    def available(self) -> bool:
        return self._available

    def read_total_for_pids(self, pids: list[int]) -> float | None:
        if not self._available or self._query is None:
            return None

        self._refresh_instances()

        if not pids:
            return 0.0

        try:
            win32pdh.CollectQueryData(self._query)
        except Exception:
            self._available = False
            return None

        total = 0.0
        for pid in pids:
            for instance in self._pid_to_instances.get(pid, []):
                counter = self._counters.get(instance)
                if counter is None:
                    continue
                try:
                    _, value = win32pdh.GetFormattedCounterValue(
                        counter, win32pdh.PDH_FMT_DOUBLE
                    )
                    if value is not None:
                        total += float(value)
                except Exception:
                    continue

        return total

    def close(self) -> None:
        if self._query is not None:
            try:
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
            self._query = None
