import time
from typing import Callable

import psutil

from medidor.aggregator import MeasurementResult
from medidor.gpu_pdh import GpuPdhReader
from medidor.process_filter import count_browser_instances, find_pids_by_executable

SAMPLE_INTERVAL_SEC = 1.0


def _cpu_core_count() -> int:
    count = psutil.cpu_count(logical=True) or 1
    return max(count, 1)


class _ProcessCache:
    """Reutiliza objetos psutil.Process para que cpu_percent mantenha o baseline."""

    def __init__(self) -> None:
        self._procs: dict[int, psutil.Process] = {}

    def get(self, pid: int) -> psutil.Process | None:
        proc = self._procs.get(pid)
        if proc is not None:
            return proc
        try:
            proc = psutil.Process(pid)
            # Primeira chamada define o baseline; retorna 0.0 neste tick.
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        self._procs[pid] = proc
        return proc

    def prune(self, active_pids: set[int]) -> None:
        for pid in list(self._procs.keys()):
            if pid not in active_pids:
                self._procs.pop(pid, None)


def _collect_process_metrics(
    cache: _ProcessCache, pids: list[int], core_count: int
) -> tuple[float, float]:
    cpu_total = 0.0
    ram_mb_total = 0.0

    for pid in pids:
        proc = cache.get(pid)
        if proc is None:
            continue
        try:
            cpu_total += proc.cpu_percent(interval=None)
            # USS (Unique Working Set) = memoria privada do processo, sem a
            # parte compartilhada (DLLs, regioes compartilhadas do Chromium).
            # E o valor que o Gerenciador de Tarefas mostra como "Memoria".
            try:
                uss = proc.memory_full_info().uss
            except (psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                uss = proc.memory_info().rss
            ram_mb_total += uss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # psutil retorna CPU por núcleo (100% = 1 core). O Gerenciador de Tarefas
    # normaliza pelo total de núcleos, então dividimos para bater.
    cpu_total /= core_count
    return cpu_total, ram_mb_total


def run_measurement(
    executable: str,
    duration_sec: float,
    on_tick: Callable[[MeasurementResult, float, float, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    path_contains: str | None = None,
    product_contains: str | None = None,
    browser_label: str = "",
) -> MeasurementResult:
    result = MeasurementResult(executable=browser_label or executable)
    gpu_reader = GpuPdhReader()
    result.gpu_available = gpu_reader.available
    core_count = _cpu_core_count()

    cache = _ProcessCache()

    start = time.monotonic()
    end_time = start + duration_sec
    sample_index = 0

    # Warm-up: define o baseline de CPU para os processos iniciais.
    initial_pids = find_pids_by_executable(
        executable, path_contains, product_contains)
    for pid in initial_pids:
        cache.get(pid)
    if initial_pids:
        time.sleep(SAMPLE_INTERVAL_SEC)

    try:
        while time.monotonic() < end_time:
            if should_stop and should_stop():
                break

            pids = find_pids_by_executable(
                executable, path_contains, product_contains)
            active = set(pids)
            cache.prune(active)
            process_count = len(pids)
            instance_count = count_browser_instances(pids)
            result.process_counts.append(process_count)
            result.instance_counts.append(instance_count)

            if process_count == 0:
                result.no_process_samples += 1
                result.cpu.add(0.0)
                result.ram_mb.add(0.0)
                if result.gpu_available:
                    gpu_value = gpu_reader.read_total_for_pids([])
                    result.gpu.add(gpu_value if gpu_value is not None else 0.0)
            else:
                cpu, ram_mb = _collect_process_metrics(cache, pids, core_count)
                result.cpu.add(cpu)
                result.ram_mb.add(ram_mb)

                if result.gpu_available:
                    gpu_value = gpu_reader.read_total_for_pids(pids)
                    if gpu_value is None:
                        result.gpu_available = False
                    else:
                        result.gpu.add(gpu_value)

            sample_index += 1
            elapsed = time.monotonic() - start
            if on_tick:
                on_tick(result, elapsed, duration_sec, process_count)

            sleep_until = start + sample_index * SAMPLE_INTERVAL_SEC
            remaining = sleep_until - time.monotonic()
            if remaining > 0 and time.monotonic() + remaining < end_time:
                time.sleep(remaining)
            elif time.monotonic() < end_time:
                time.sleep(min(SAMPLE_INTERVAL_SEC, end_time - time.monotonic()))
    finally:
        gpu_reader.close()

    return result
