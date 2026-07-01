from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserPreset:
    label: str
    executable: str
    path_contains: str | None = None
    product_contains: str | None = None


@dataclass(frozen=True)
class BrowserTarget:
    label: str
    executable: str
    path_contains: str | None = None
    product_contains: str | None = None


BROWSER_PRESETS: list[BrowserPreset] = [
    BrowserPreset("Utrium Browser", "chrome.exe", product_contains="Utrium"),
    BrowserPreset("Thorium", "thorium.exe"),
    BrowserPreset("Chromium", "chromium.exe"),
    BrowserPreset("Chrome", "chrome.exe", product_contains="Google Chrome"),
    BrowserPreset("Brave", "brave.exe"),
    BrowserPreset("Edge", "msedge.exe"),
]

CUSTOM_LABEL = "Customizado"


def normalize_executable(name: str) -> str:
    name = name.strip().lower()
    if not name:
        return ""
    if not name.endswith(".exe"):
        name += ".exe"
    return name


def get_target_for_preset(label: str, custom_name: str = "") -> BrowserTarget | None:
    if label == CUSTOM_LABEL:
        exe = normalize_executable(custom_name)
        if not exe:
            return None
        return BrowserTarget(label=custom_name or exe, executable=exe)

    for preset in BROWSER_PRESETS:
        if preset.label == label:
            return BrowserTarget(
                label=preset.label,
                executable=preset.executable,
                path_contains=preset.path_contains,
                product_contains=preset.product_contains,
            )
    return None


def get_executable_for_preset(label: str, custom_name: str = "") -> str:
    target = get_target_for_preset(label, custom_name)
    return target.executable if target else ""
