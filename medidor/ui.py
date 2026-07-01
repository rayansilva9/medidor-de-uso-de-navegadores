import threading
import tkinter as tk
from tkinter import messagebox

from medidor.aggregator import MeasurementResult
from medidor.browsers import (
    BROWSER_PRESETS,
    CUSTOM_LABEL,
    get_target_for_preset,
)
from medidor.process_filter import find_pids_by_executable
from medidor.sampler import run_measurement

BG = "#000000"
CARD_BG = "#0a0c10"
INPUT_BG = "#141820"
BORDER = "#2a3140"
ACCENT = "#2563eb"
ACCENT_ACTIVE = "#1d4ed8"
STOP = "#dc2626"
STOP_ACTIVE = "#b91c1c"
TEXT = "#ffffff"
MUTED = "#c5cdd8"
WARN = "#fbbf24"
DISABLED_BTN = "#1c212b"
DISABLED_TEXT = "#5c6675"

FONT = ("Segoe UI", 11)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SECTION = ("Segoe UI", 12, "bold")
FONT_BIG = ("Segoe UI", 20, "bold")
FONT_BTN = ("Segoe UI", 12, "bold")


def _apply_opaque_window(window: tk.Tk) -> None:
    window.attributes("-alpha", 1.0)
    try:
        import ctypes

        user32 = ctypes.windll.user32
        dwm = ctypes.windll.dwm
        hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()

        for attr, value in (
            (38, 1),   # DWMWA_SYSTEMBACKDROP_TYPE = DWMSBT_NONE
            (20, 1),   # DWMWA_USE_IMMERSIVE_DARK_MODE
            (2, 0),    # DWMWA_MICA_EFFECT off
            (3, 1),    # DWMWA_TRANSITIONS_FORCEDISABLED
        ):
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(data), ctypes.sizeof(data)
            )

        gwl_exstyle = -20
        ws_ex_layered = 0x00080000
        style = user32.GetWindowLongW(hwnd, gwl_exstyle)
        user32.SetWindowLongW(hwnd, gwl_exstyle, style & ~ws_ex_layered)
    except Exception:
        pass


def _format_mb(value_mb: float) -> str:
    if value_mb >= 1024:
        return f"{value_mb / 1024:.2f} GB"
    return f"{value_mb:.0f} MB"


def _format_process_footer(instances: int, processes: int, name: str) -> str:
    inst = str(instances) if instances else "0"
    proc = str(processes) if processes else "0"
    return f"Instâncias: {inst}  ·  Processos: {proc} ({name})"


    if value_mb >= 1024:
        return f"{value_mb / 1024:.2f} GB"
    return f"{value_mb:.0f} MB"


def _label(parent, text, *, bg=BG, fg=TEXT, font=FONT, **kw) -> tk.Label:
    return tk.Label(
        parent, text=text, bg=bg, fg=fg, font=font,
        highlightthickness=0, bd=0, **kw
    )


def _entry(parent, textvariable, width=6, justify="left") -> tk.Entry:
    return tk.Entry(
        parent, textvariable=textvariable, width=width, justify=justify,
        bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", highlightthickness=1,
        highlightbackground=BORDER, highlightcolor=ACCENT,
        font=FONT,
    )


def _option_menu(parent, variable, values, command=None) -> tk.OptionMenu:
    menu = tk.OptionMenu(parent, variable, *values, command=command)
    menu.configure(
        bg=INPUT_BG, fg=TEXT, activebackground=ACCENT, activeforeground=TEXT,
        highlightthickness=1, highlightbackground=BORDER, relief="flat",
        font=FONT, bd=0,
    )
    menu["menu"].configure(
        bg=INPUT_BG, fg=TEXT, activebackground=ACCENT, activeforeground=TEXT,
        relief="flat", bd=0,
    )
    return menu


def _button(parent, text, command, bg, active_bg, state="normal") -> tk.Button:
    return tk.Button(
        parent, text=text, command=command, state=state,
        bg=bg if state == "normal" else DISABLED_BTN,
        fg=TEXT if state == "normal" else DISABLED_TEXT,
        activebackground=active_bg, activeforeground=TEXT,
        relief="flat", highlightthickness=0, bd=0,
        font=FONT_BTN, cursor="hand2", padx=16, pady=10,
    )


class SolidProgressBar(tk.Frame):
    def __init__(self, master) -> None:
        super().__init__(master, bg=INPUT_BG, height=10, highlightthickness=0)
        self.pack_propagate(False)
        self._fill = tk.Frame(self, bg=ACCENT, height=10)
        self._fill.place(relx=0, rely=0, relheight=1, relwidth=0)

    def set(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        self._fill.place(relx=0, rely=0, relheight=1, relwidth=fraction)


class ResultCard(tk.Frame):
    def __init__(self, master, title: str, unit: str = "%",
                 formatter=None) -> None:
        super().__init__(
            master, bg=CARD_BG, highlightthickness=1,
            highlightbackground=BORDER, padx=16, pady=14,
        )
        self._unit = unit
        self._formatter = formatter

        top = tk.Frame(self, bg=CARD_BG)
        top.pack(fill="x")

        _label(top, title, bg=CARD_BG, font=FONT_BOLD).pack(side="left")
        self.current_label = _label(
            top, "—", bg=CARD_BG, fg=ACCENT, font=FONT_BIG, anchor="e"
        )
        self.current_label.pack(side="right")

        self.detail_label = _label(
            self, "média —  ·  pico —", bg=CARD_BG, fg=MUTED, font=FONT
        )
        self.detail_label.pack(anchor="w", pady=(8, 0))

    def update_from_series(self, series) -> None:
        fmt = self._formatter or (lambda v: f"{v:.1f}{self._unit}")
        self.current_label.configure(text=fmt(series.current))
        self.detail_label.configure(
            text=f"média {fmt(series.average)}  ·  pico {fmt(series.peak)}"
        )

    def reset(self) -> None:
        self.current_label.configure(text="—")
        self.detail_label.configure(text="média —  ·  pico —")

    def set_unavailable(self) -> None:
        self.current_label.configure(text="N/D")
        self.detail_label.configure(text="indisponível neste sistema")


class MedidorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Medidor de Navegador")
        self.geometry("560x680")
        self.minsize(520, 640)
        self.configure(bg=BG)
        self.attributes("-alpha", 1.0)

        self._measuring = False
        self._stop_requested = False
        self._worker: threading.Thread | None = None
        self._duration_sec = 60.0

        self._bg = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.container = tk.Frame(self, bg=BG, highlightthickness=0, bd=0)
        self.container.place(x=0, y=0, relwidth=1, relheight=1)

        self.bind("<Configure>", self._paint_background)
        self._build_ui()
        self.update_idletasks()
        _apply_opaque_window(self)
        self._paint_background()

    def _paint_background(self, _event=None) -> None:
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        self._bg.delete("all")
        self._bg.create_rectangle(0, 0, w, h, fill=BG, outline=BG)

    def _build_ui(self) -> None:
        root = self.container

        _label(root, "Medidor de Navegador", font=FONT_TITLE).pack(
            anchor="w", padx=24, pady=(24, 2)
        )
        _label(
            root,
            "Mede CPU, GPU e RAM de um navegador escolhido.",
            fg=MUTED, font=("Segoe UI", 10), wraplength=500, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 16))

        config_card = tk.Frame(
            root, bg=CARD_BG, highlightthickness=1,
            highlightbackground=BORDER, padx=18, pady=18,
        )
        config_card.pack(fill="x", padx=24, pady=(0, 16))

        duration_row = tk.Frame(config_card, bg=CARD_BG)
        duration_row.pack(fill="x")
        _label(duration_row, "Duração", bg=CARD_BG, width=10, anchor="w").pack(
            side="left", padx=(0, 10)
        )
        self.duration_var = tk.StringVar(value="1")
        self.duration_entry = _entry(
            duration_row, self.duration_var, width=6, justify="center"
        )
        self.duration_entry.pack(side="left", padx=(0, 8), ipady=4)
        self.duration_unit_var = tk.StringVar(value="minutos")
        _option_menu(
            duration_row, self.duration_unit_var, ["minutos", "segundos"]
        ).pack(side="left")

        tk.Frame(config_card, bg=CARD_BG, height=10).pack(fill="x")

        browser_row = tk.Frame(config_card, bg=CARD_BG)
        browser_row.pack(fill="x")
        _label(browser_row, "Navegador", bg=CARD_BG, width=10, anchor="w").pack(
            side="left", padx=(0, 10)
        )
        preset_labels = [p.label for p in BROWSER_PRESETS] + [CUSTOM_LABEL]
        self.browser_var = tk.StringVar(value="Utrium Browser")
        self.browser_menu = _option_menu(
            browser_row, self.browser_var, preset_labels,
            command=self._on_browser_change,
        )
        self.browser_menu.pack(side="left")

        self.custom_row = tk.Frame(config_card, bg=CARD_BG)
        self.custom_spacer = tk.Frame(config_card, bg=CARD_BG, height=10)
        _label(self.custom_row, "Executável", bg=CARD_BG, width=10,
               anchor="w").pack(side="left", padx=(0, 10))
        self.custom_var = tk.StringVar()
        self.custom_entry = _entry(self.custom_row, self.custom_var, width=20)
        self.custom_entry.pack(side="left", ipady=4)

        actions_row = tk.Frame(root, bg=BG)
        actions_row.pack(fill="x", padx=24, pady=(0, 10))
        actions_row.columnconfigure(0, weight=1)

        self.start_button = _button(
            actions_row, "Iniciar medição", self._on_start, ACCENT, ACCENT_ACTIVE
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.stop_button = _button(
            actions_row, "Parar", self._on_stop, STOP, STOP_ACTIVE, state="disabled"
        )
        self.stop_button.grid(row=0, column=1, sticky="e")

        self.progress_bar = SolidProgressBar(root)
        self.progress_bar.pack(fill="x", padx=24, pady=(8, 4))

        self.progress_label = _label(
            root, "Aguardando início...", fg=MUTED, font=("Segoe UI", 10)
        )
        self.progress_label.pack(anchor="w", padx=24, pady=(0, 16))

        _label(root, "Resultado", font=FONT_SECTION).pack(
            anchor="w", padx=24, pady=(8, 8)
        )

        results_grid = tk.Frame(root, bg=BG)
        results_grid.pack(fill="x", padx=24)
        results_grid.columnconfigure(0, weight=1, uniform="metric")
        results_grid.columnconfigure(1, weight=1, uniform="metric")

        self.cpu_card = ResultCard(results_grid, "CPU")
        self.cpu_card.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.gpu_card = ResultCard(results_grid, "GPU")
        self.gpu_card.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.ram_card = ResultCard(results_grid, "RAM", unit=" MB",
                                   formatter=_format_mb)
        self.ram_card.grid(row=1, column=0, columnspan=2, sticky="ew",
                           pady=(8, 0))

        self.process_label = _label(
            root, "Instâncias: —  ·  Processos: —", fg=MUTED,
            font=("Segoe UI", 10),
        )
        self.process_label.pack(anchor="w", padx=24, pady=(10, 0))

        self.status_label = _label(
            root, "", fg=WARN, font=("Segoe UI", 10),
            wraplength=500, justify="left",
        )
        self.status_label.pack(anchor="w", padx=24, pady=(8, 24))

        self._on_browser_change()

    def _on_browser_change(self, _choice: str = "") -> None:
        is_custom = self.browser_var.get() == CUSTOM_LABEL
        if is_custom:
            if not self.custom_spacer.winfo_ismapped():
                self.custom_spacer.pack(fill="x")
            if not self.custom_row.winfo_ismapped():
                self.custom_row.pack(fill="x")
            self.custom_entry.configure(state="normal")
        else:
            self.custom_row.pack_forget()
            self.custom_spacer.pack_forget()
            self.custom_entry.configure(state="disabled")

    def _get_duration_sec(self) -> float | None:
        raw = self.duration_var.get().strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            messagebox.showerror("Duração inválida", "Informe um número válido.")
            return None

        if value <= 0:
            messagebox.showerror(
                "Duração inválida", "A duração deve ser maior que zero."
            )
            return None

        if self.duration_unit_var.get() == "minutos":
            return value * 60
        return value

    def _get_target(self):
        label = self.browser_var.get()
        custom = self.custom_var.get()
        target = get_target_for_preset(label, custom)

        if target is None:
            messagebox.showerror(
                "Navegador inválido",
                "Informe o nome do executável (ex.: thorium.exe).",
            )
            return None
        return target

    def _set_button_state(self, button: tk.Button, enabled: bool,
                          normal_bg: str) -> None:
        if enabled:
            button.configure(
                state="normal", bg=normal_bg, fg=TEXT, cursor="hand2"
            )
        else:
            button.configure(
                state="disabled", bg=DISABLED_BTN, fg=DISABLED_TEXT,
                cursor="arrow",
            )

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._set_button_state(self.start_button, enabled, ACCENT)
        self._set_button_state(self.stop_button, not enabled, STOP)
        self.duration_entry.configure(state=state)
        self.browser_menu.configure(state=state)
        if self.browser_var.get() == CUSTOM_LABEL:
            self.custom_entry.configure(state=state)
        else:
            self.custom_entry.configure(state="disabled")

    def _on_stop(self) -> None:
        if not self._measuring:
            return
        self._stop_requested = True
        self._set_button_state(self.stop_button, False, STOP)
        self.stop_button.configure(text="Parando...")
        self.progress_label.configure(text="Interrompendo medição...")

    def _on_start(self) -> None:
        if self._measuring:
            return

        duration_sec = self._get_duration_sec()
        if duration_sec is None:
            return

        target = self._get_target()
        if target is None:
            return

        if not find_pids_by_executable(
                target.executable, target.path_contains, target.product_contains):
            messagebox.showwarning(
                "Nenhum processo encontrado",
                f"Nenhum processo de `{target.label}` em execução.\n"
                "Abra o navegador e tente novamente.",
            )
            return

        self._measuring = True
        self._stop_requested = False
        self._duration_sec = duration_sec
        self._set_controls_enabled(False)
        self.stop_button.configure(text="Parar")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Iniciando...")
        self.status_label.configure(text="")
        self.cpu_card.reset()
        self.gpu_card.reset()
        self.ram_card.reset()
        self.process_label.configure(text="Instâncias: —  ·  Processos: —")

        self._worker = threading.Thread(
            target=self._run_measurement_thread,
            args=(target, duration_sec),
            daemon=True,
        )
        self._worker.start()

    def _run_measurement_thread(self, target, duration_sec: float) -> None:
        def on_tick(result, elapsed, total, process_count) -> None:
            self.after(0, self._update_live, result, elapsed, total,
                       process_count)

        try:
            result = run_measurement(
                executable=target.executable,
                duration_sec=duration_sec,
                on_tick=on_tick,
                should_stop=lambda: self._stop_requested,
                path_contains=target.path_contains,
                product_contains=target.product_contains,
                browser_label=target.label,
            )
        except Exception as exc:
            self.after(0, self._on_measurement_error, str(exc))
            return

        self.after(0, self._on_measurement_done, result, self._stop_requested)

    def _update_live(self, result: MeasurementResult, elapsed: float,
                     duration_sec: float, process_count: int) -> None:
        self.progress_bar.set(elapsed / duration_sec)
        instance_count = (
            result.instance_counts[-1] if result.instance_counts else 0
        )
        self.progress_label.configure(
            text=f"{int(elapsed)}s / {int(duration_sec)}s  ·  "
            f"{instance_count} inst.  ·  {process_count} proc."
        )

        self.cpu_card.update_from_series(result.cpu)
        if result.gpu_available and result.gpu.values:
            self.gpu_card.update_from_series(result.gpu)
        self.ram_card.update_from_series(result.ram_mb)
        self.process_label.configure(
            text=_format_process_footer(
                instance_count, process_count, result.executable
            )
        )

    def _on_measurement_error(self, message: str) -> None:
        self._measuring = False
        self._set_controls_enabled(True)
        self.stop_button.configure(text="Parar")
        self.status_label.configure(text=f"Erro: {message}")
        messagebox.showerror("Erro na medição", message)

    def _on_measurement_done(self, result: MeasurementResult,
                             stopped: bool = False) -> None:
        self._measuring = False
        self._set_controls_enabled(True)
        self.stop_button.configure(text="Parar")

        if stopped:
            elapsed = len(result.cpu.values)
            self.progress_label.configure(
                text=f"Medição interrompida após {elapsed}s."
            )
        else:
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="Medição concluída.")

        self.cpu_card.update_from_series(result.cpu)
        if result.gpu_available and result.gpu.values:
            self.gpu_card.update_from_series(result.gpu)
        else:
            self.gpu_card.set_unavailable()
        self.ram_card.update_from_series(result.ram_mb)

        last_count = result.process_counts[-1] if result.process_counts else 0
        last_instances = result.instance_counts[-1] if result.instance_counts else 0
        self.process_label.configure(
            text=_format_process_footer(
                last_instances, last_count, result.executable
            )
        )

        if not result.had_processes:
            self.status_label.configure(
                text=f"Nenhum processo `{result.executable}` foi encontrado "
                f"durante a medição."
            )
        elif result.no_process_samples > 0:
            self.status_label.configure(
                text=(f"Aviso: em {result.no_process_samples} amostra(s) "
                      "nenhum processo estava ativo.")
            )
        else:
            self.status_label.configure(text="")


def run_app() -> None:
    app = MedidorApp()
    app.mainloop()
