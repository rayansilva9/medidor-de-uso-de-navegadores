import psutil

from medidor.browsers import normalize_executable
from medidor.exe_product import get_exe_product_name


def find_pids_by_executable(
    executable: str,
    path_contains: str | None = None,
    product_contains: str | None = None,
) -> list[int]:
    target = normalize_executable(executable)
    if not target:
        return []

    path_filter = path_contains.lower() if path_contains else None
    product_filter = product_contains.lower() if product_contains else None
    pids: list[int] = []

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = proc.info.get("name")
            if not name or name.lower() != target:
                continue

            exe_path = proc.info.get("exe") or ""

            if path_filter and path_filter not in exe_path.lower():
                continue

            if product_filter:
                product = get_exe_product_name(exe_path).lower()
                if product_filter not in product:
                    continue

            pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(pids)


def count_browser_instances(pids: list[int]) -> int:
    """Conta janelas/instâncias (processo principal, sem --type= de subprocesso)."""
    instances = 0
    for pid in pids:
        try:
            cmdline = psutil.Process(pid).cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        is_main = True
        for arg in cmdline[1:]:
            if arg.startswith("--type="):
                is_main = arg.split("=", 1)[1] == "browser"
                break
        if is_main:
            instances += 1

    return instances
