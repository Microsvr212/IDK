from __future__ import annotations

import base64
import json
import os
import platform
import re
import subprocess
import threading
import time
import tkinter as tk
import winreg
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, filedialog

import customtkinter as ctk
import psutil

APP_NAME = "NOVA | Fortnite Optimizer"
APP_VERSION = "2.0.0"
ACCENT = "#7C5CFF"
ACCENT_HOVER = "#6745ED"
BG = "#090D16"
PANEL = "#111827"
PANEL_2 = "#172235"
TEXT = "#F4F6FC"
MUTED = "#91A0B8"
GREEN = "#31D69A"
ORANGE = "#FFB454"
RED = "#FF667A"

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home()))
DATA_DIR = LOCAL / "NovaFortniteOptimizer"
STATE_PATH = DATA_DIR / "state.json"
LOG_PATH = DATA_DIR / "activity.log"

HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


def safe_subprocess(args: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def registry_snapshot(path: str, name: str) -> dict:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ) as key:
            value, kind = winreg.QueryValueEx(key, name)
        if isinstance(value, bytes):
            encoded = {"kind": "bytes", "value": base64.b64encode(value).decode("ascii")}
        elif isinstance(value, tuple):
            encoded = {"kind": "tuple", "value": list(value)}
        else:
            encoded = {"kind": "plain", "value": value}
        return {"exists": True, "type": kind, "data": encoded}
    except FileNotFoundError:
        return {"exists": False}


def restore_registry_value(path: str, name: str, snapshot: dict) -> None:
    if not snapshot.get("exists"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
        return

    data = snapshot.get("data", {})
    value = data.get("value")
    if data.get("kind") == "bytes":
        value = base64.b64decode(value)
    elif data.get("kind") == "tuple":
        value = tuple(value)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, int(snapshot["type"]), value)


def write_dword(path: str, name: str, value: int) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))


def write_string(path: str, name: str, value: str) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def active_power_plan() -> str:
    result = safe_subprocess(["powercfg", "/getactivescheme"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows kon het actieve energieplan niet uitlezen.")
    match = re.search(r"([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})", result.stdout)
    if not match:
        raise RuntimeError("Het actieve energieplan kon niet worden herkend.")
    return match.group(1)


def set_power_plan(guid: str) -> None:
    result = safe_subprocess(["powercfg", "/setactive", guid])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows kon het energieplan niet wijzigen.")


def load_state() -> dict:
    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)
    temp_path.replace(STATE_PATH)


def log_line(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def windows_version() -> str:
    parts = platform.version().split(".")
    try:
        build = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        build = 0
    edition = "11" if build >= 22000 else platform.release()
    return f"Windows {edition} • Build {build or platform.version()}"


def get_gpu_name() -> str:
    command = (
        "$g = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name; "
        "ConvertTo-Json -InputObject @($g) -Compress"
    )
    try:
        result = safe_subprocess(["powershell", "-NoProfile", "-Command", command], timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            parsed = json.loads(result.stdout.strip())
            names = parsed if isinstance(parsed, list) else [parsed]
            names = [str(x).strip() for x in names if str(x).strip()]
            if names:
                return " / ".join(dict.fromkeys(names))
    except Exception:
        pass
    return "Niet beschikbaar"


def find_running_fortnite_path() -> str | None:
    candidates = {"fortniteclient-win64-shipping.exe"}
    try:
        for process in psutil.process_iter(["name", "exe"]):
            name = (process.info.get("name") or "").lower()
            path = process.info.get("exe")
            if name in candidates and path and os.path.isfile(path):
                return path
    except (psutil.Error, OSError):
        pass
    return None


def fortnite_is_running() -> bool:
    return find_running_fortnite_path() is not None


def measure_internet_latency() -> tuple[str, str]:
    """Measures ICMP latency to Cloudflare DNS; this is not Fortnite server ping."""
    try:
        result = safe_subprocess(["ping", "-n", "1", "-w", "1600", "1.1.1.1"], timeout=3)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode == 0:
            match = re.search(r"(?:time|tijd|zeit)[=<]\s*(\d+)\s*ms", output, re.IGNORECASE)
            if match:
                return f"{match.group(1)} ms", "Internettest • 1.1.1.1"
            if re.search(r"(?:time|tijd|zeit)<1ms", output, re.IGNORECASE):
                return "<1 ms", "Internettest • 1.1.1.1"
            return "Verbonden", "Antwoord ontvangen van 1.1.1.1"
        return "Geen antwoord", "1.1.1.1 reageerde niet op deze test"
    except Exception:
        return "Niet beschikbaar", "De Windows-pingtest kon niet worden uitgevoerd"


class OptimizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title(APP_NAME)
        self.geometry("1240x820")
        self.minsize(1020, 700)
        self.configure(fg_color=BG)
        self.state_data = load_state()
        self.page = "Dashboard"
        self.tweak_cards = {}
        self.nav_buttons = {}
        self.toast_job = None
        self.gpu_name = "Laden..."
        self.ping_running = False
        self._build_shell()
        self.show_page("Dashboard")
        self.after(300, self._initial_refresh)
        self.after(1600, self._refresh_live_stats)

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=235, corner_radius=0, fg_color="#0D1422")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(25, 29))
        logo = ctk.CTkFrame(brand, width=44, height=44, corner_radius=14, fg_color=ACCENT)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="N", font=ctk.CTkFont(size=26, weight="black"), text_color="white").place(relx=.5, rely=.48, anchor="center")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=11)
        ctk.CTkLabel(brand_text, text="NOVA", font=ctk.CTkFont(size=20, weight="black"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(brand_text, text="FORTNITE OPTIMIZER", font=ctk.CTkFont(size=8, weight="bold"), text_color=MUTED).pack(anchor="w")

        ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#66758F").pack(anchor="w", padx=23, pady=(0, 9))
        for name, glyph in [("Dashboard", "⌂"), ("Optimizer", "✦"), ("System monitor", "◉"), ("Network", "⌁")]:
            btn = ctk.CTkButton(self.sidebar, text=f"{glyph}     {name}", anchor="w", height=43, corner_radius=10,
                                fg_color="transparent", hover_color="#1B2940", text_color="#AAB7CC",
                                font=ctk.CTkFont(size=13, weight="bold"), command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", padx=13, pady=3)
            self.nav_buttons[name] = btn

        ctk.CTkLabel(self.sidebar, text="PREFERENCES", font=ctk.CTkFont(size=10, weight="bold"), text_color="#66758F").pack(anchor="w", padx=23, pady=(28, 9))
        for name, glyph in [("Settings", "⚙"), ("Activity log", "≡")]:
            btn = ctk.CTkButton(self.sidebar, text=f"{glyph}     {name}", anchor="w", height=43, corner_radius=10,
                                fg_color="transparent", hover_color="#1B2940", text_color="#AAB7CC",
                                font=ctk.CTkFont(size=13, weight="bold"), command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", padx=13, pady=3)
            self.nav_buttons[name] = btn

        sidebar_bottom = ctk.CTkFrame(self.sidebar, corner_radius=14, fg_color="#151F31")
        sidebar_bottom.pack(side="bottom", fill="x", padx=14, pady=16)
        ctk.CTkLabel(sidebar_bottom, text="SAFE MODE ENABLED", text_color=GREEN,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=13, pady=(12, 3))
        ctk.CTkLabel(sidebar_bottom, text="Tweaks bewaren hun vorige\ninstellingen voor Undo.", text_color=MUTED,
                     font=ctk.CTkFont(size=10), justify="left").pack(anchor="w", padx=13, pady=(0, 12))
        ctk.CTkLabel(self.sidebar, text=f"VERSION {APP_VERSION}", text_color="#53627A",
                     font=ctk.CTkFont(size=9, weight="bold")).pack(side="bottom", pady=(0, 6))

        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.main, fg_color=BG, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew", padx=30, pady=(22, 10))
        self.header.grid_columnconfigure(0, weight=1)
        self.header_title = ctk.CTkLabel(self.header, text="Dashboard", text_color=TEXT,
                                         font=ctk.CTkFont(size=26, weight="bold"))
        self.header_title.grid(row=0, column=0, sticky="w")
        self.header_subtitle = ctk.CTkLabel(self.header, text="Your gaming setup at a glance.", text_color=MUTED,
                                            font=ctk.CTkFont(size=12))
        self.header_subtitle.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.header_status = ctk.CTkLabel(self.header, text="●  SYSTEM READY", text_color=GREEN,
                                          fg_color="#102B29", corner_radius=20,
                                          font=ctk.CTkFont(size=10, weight="bold"), padx=13, pady=8)
        self.header_status.grid(row=0, column=1, rowspan=2, sticky="e")

        self.content = ctk.CTkFrame(self.main, fg_color=BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=30, pady=(4, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.toast = ctk.CTkLabel(self, text="", fg_color="#26344C", text_color=TEXT,
                                  corner_radius=12, font=ctk.CTkFont(size=12, weight="bold"), padx=18, pady=11)

    def _initial_refresh(self):
        threading.Thread(target=self._read_gpu_worker, daemon=True).start()

    def _read_gpu_worker(self):
        name = get_gpu_name()
        self.after(0, lambda: self._set_gpu_name(name))

    def _set_gpu_name(self, name: str):
        self.gpu_name = name
        if self.page in ("Dashboard", "System monitor"):
            self.show_page(self.page)

    def _refresh_live_stats(self):
        if not self.winfo_exists():
            return
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        self.live_cpu = cpu
        self.live_ram = ram.percent
        self.live_ram_used = ram.used / (1024 ** 3)
        self.live_ram_total = ram.total / (1024 ** 3)
        self.live_fortnite = fortnite_is_running()
        if getattr(self, "cpu_value", None) is not None and self.cpu_value.winfo_exists():
            self.cpu_value.configure(text=f"{cpu:.0f}%")
            self.cpu_bar.set(cpu / 100)
        if getattr(self, "ram_value", None) is not None and self.ram_value.winfo_exists():
            self.ram_value.configure(text=f"{ram.percent:.0f}%")
            self.ram_bar.set(ram.percent / 100)
            self.ram_detail.configure(text=f"{self.live_ram_used:.1f} GB / {self.live_ram_total:.1f} GB")
        if getattr(self, "game_value", None) is not None and self.game_value.winfo_exists():
            self.game_value.configure(text="RUNNING" if self.live_fortnite else "NOT DETECTED",
                                      text_color=GREEN if self.live_fortnite else MUTED)
        self.after(1600, self._refresh_live_stats)

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.cpu_value = self.cpu_bar = self.ram_value = self.ram_bar = self.ram_detail = None
        self.game_value = None

    def show_page(self, name: str):
        self.page = name
        for key, btn in self.nav_buttons.items():
            btn.configure(fg_color="#25234A" if key == name else "transparent",
                          text_color="#FFFFFF" if key == name else "#AAB7CC")
        self.header_title.configure(text=name)
        subtitles = {
            "Dashboard": "Your gaming setup at a glance.",
            "Optimizer": "Carefully selected Windows gaming tweaks. Every change is reversible.",
            "System monitor": "Live PC health and Fortnite process detection.",
            "Network": "Measure basic internet latency without pretending it is Fortnite server ping.",
            "Settings": "Shortcuts and app information.",
            "Activity log": "A local record of changes made by this app."
        }
        self.header_subtitle.configure(text=subtitles.get(name, ""))
        self._clear_content()
        if name == "Dashboard": self._dashboard()
        elif name == "Optimizer": self._optimizer_page()
        elif name == "System monitor": self._monitor_page()
        elif name == "Network": self._network_page()
        elif name == "Settings": self._settings_page()
        elif name == "Activity log": self._log_page()

    def _scroll_area(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", corner_radius=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _card(self, parent, title: str | None = None, subtitle: str | None = None, **kwargs):
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=18, border_width=1, border_color="#1D2A40", **kwargs)
        if title:
            ctk.CTkLabel(card, text=title, text_color=TEXT, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=18, pady=(16, 2))
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, text_color=MUTED, font=ctk.CTkFont(size=11), wraplength=650, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        return card

    def _stat_card(self, parent, title, value, detail, glyph, row, col):
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=18, border_width=1, border_color="#1D2A40")
        card.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(top, text=title.upper(), text_color=MUTED, font=ctk.CTkFont(size=9, weight="bold")).pack(side="left")
        ctk.CTkLabel(top, text=glyph, text_color="#B7A8FF", font=ctk.CTkFont(size=19, weight="bold")).pack(side="right")
        value_lbl = ctk.CTkLabel(card, text=value, text_color=TEXT, font=ctk.CTkFont(size=27, weight="bold"))
        value_lbl.pack(anchor="w", padx=16)
        ctk.CTkLabel(card, text=detail, text_color=MUTED, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=(0, 15))
        return card, value_lbl

    def _dashboard(self):
        area = self._scroll_area()
        hero = ctk.CTkFrame(area, fg_color="#1A1B3B", corner_radius=22, border_width=1, border_color="#353067")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="READY TO PLAY?", text_color="#B9AEFF", font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(18, 5))
        ctk.CTkLabel(hero, text="Make every session count.", text_color=TEXT, font=ctk.CTkFont(size=25, weight="bold")).grid(row=1, column=0, sticky="w", padx=22)
        ctk.CTkLabel(hero, text="Apply safe tweaks, check your PC and keep control of every change.", text_color="#B7BCD2", font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", padx=22, pady=(5, 16))
        ctk.CTkButton(hero, text="OPEN OPTIMIZER  →", height=38, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self.show_page("Optimizer")).grid(row=0, column=1, rowspan=3, padx=22)

        stats = ctk.CTkFrame(area, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        c1, self.cpu_value = self._stat_card(stats, "CPU Load", f"{getattr(self, 'live_cpu', 0):.0f}%", platform.processor() or "Processor usage", "◉", 0, 0)
        c2, self.ram_value = self._stat_card(stats, "Memory", f"{getattr(self, 'live_ram', 0):.0f}%", "RAM in use", "▤", 0, 1)
        c3, self.game_value = self._stat_card(stats, "Fortnite", "Checking...", "Game process status", "◆", 0, 2)

        monitor = self._card(area, "LIVE SYSTEM OVERVIEW", "Usage updates automatically while this app is open.")
        monitor.grid(row=2, column=0, sticky="ew", pady=6)
        self.cpu_bar = self._progress_row(monitor, "CPU usage", getattr(self, "live_cpu", 0) / 100, f"{getattr(self, 'live_cpu', 0):.0f}%")
        self.ram_bar = self._progress_row(monitor, "Memory usage", getattr(self, "live_ram", 0) / 100, f"{getattr(self, 'live_ram', 0):.0f}%")
        self.ram_detail = ctk.CTkLabel(monitor, text="", text_color=MUTED, font=ctk.CTkFont(size=10))
        self.ram_detail.pack(anchor="e", padx=18, pady=(0, 12))

        lower = ctk.CTkFrame(area, fg_color="transparent")
        lower.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        lower.grid_columnconfigure((0, 1), weight=1)
        syscard = self._card(lower, "YOUR PC", "Detected system information")
        syscard.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._info_line(syscard, "Operating system", windows_version())
        self._info_line(syscard, "Processor", (platform.processor() or "Unknown")[:58])
        self._info_line(syscard, "Graphics", self.gpu_name[:68])
        pingcard = self._card(lower, "CONNECTION CHECK", "A quick internet test, not Fortnite server ping.")
        pingcard.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.dashboard_ping = ctk.CTkLabel(pingcard, text="—", text_color=TEXT, font=ctk.CTkFont(size=27, weight="bold"))
        self.dashboard_ping.pack(anchor="w", padx=18, pady=(2, 0))
        ctk.CTkLabel(pingcard, text="Cloudflare DNS • 1.1.1.1", text_color=MUTED, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=18)
        ctk.CTkButton(pingcard, text="TEST CONNECTION", height=34, fg_color="#263550", hover_color="#334767",
                      command=self.run_ping_test).pack(anchor="w", padx=18, pady=(12, 17))

        foot = ctk.CTkLabel(area, text="NOVA does not promise a fixed FPS or ping increase. Results depend on your PC, drivers, game settings and connection.",
                            text_color="#73829B", font=ctk.CTkFont(size=10), wraplength=850, justify="left")
        foot.grid(row=4, column=0, sticky="w", pady=(12, 3))

    def _progress_row(self, parent, label, value, value_text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 8))
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(top, text=label, text_color="#D8DFEC", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        value_lbl = ctk.CTkLabel(top, text=value_text, text_color=MUTED, font=ctk.CTkFont(size=10))
        value_lbl.pack(side="right")
        bar = ctk.CTkProgressBar(row, height=9, corner_radius=6, fg_color="#263247", progress_color=ACCENT)
        bar.pack(fill="x")
        bar.set(max(0, min(1, value)))
        return bar

    def _info_line(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=5)
        ctk.CTkLabel(row, text=label, text_color=MUTED, font=ctk.CTkFont(size=10)).pack(side="left")
        ctk.CTkLabel(row, text=value or "Unknown", text_color="#DCE3F0", font=ctk.CTkFont(size=10, weight="bold"), wraplength=240).pack(side="right")

    def _tweak_definitions(self):
        return [
            {"id": "power", "category": "POWER", "title": "High Performance Power Plan", "description": "Switch Windows to the High Performance power plan. Your previous plan is saved for Undo.", "impact": "May reduce power-saving downclocking on some PCs. It can use more power and create more heat.", "risk": "Low • reversible", "kind": "power"},
            {"id": "gamemode", "category": "WINDOWS GAMING", "title": "Enable Windows Game Mode", "description": "Turn on the Windows Game Mode setting for your current Windows user.", "impact": "Windows Game Mode is designed to prioritize gaming. The actual effect varies by PC and workload.", "risk": "Low • reversible", "kind": "registry", "items": [(r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1)]},
            {"id": "gamedvr", "category": "BACKGROUND CAPTURE", "title": "Turn Off Background Game Capture", "description": "Disable Game DVR background capture values for your current Windows user. Manual recording features may be affected.", "impact": "Can avoid background recording overhead if capture was enabled. It does not guarantee more FPS.", "risk": "Low • reversible", "kind": "registry", "items": [(r"System\GameConfigStore", "GameDVR_Enabled", 0), (r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0)]},
            {"id": "transparency", "category": "DESKTOP", "title": "Disable Windows Transparency", "description": "Turn off Windows transparency effects for the current user. Desktop appearance becomes more solid.", "impact": "May slightly reduce desktop compositing work; usually has little or no effect on in-game FPS.", "risk": "Low • reversible", "kind": "registry", "items": [(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0)]},
            {"id": "visualfx", "category": "DESKTOP", "title": "Prioritize Windows Visual Performance", "description": "Set the current user's Windows visual-effects preference to best performance. Some interface animations and effects may disappear.", "impact": "Can make the Windows desktop feel lighter. It is not a Fortnite FPS guarantee.", "risk": "Low • reversible", "kind": "registry", "items": [(r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2)]},
        ]

    def _optimizer_page(self):
        area = self._scroll_area()
        top = ctk.CTkFrame(area, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="TWEAK LIBRARY", text_color=TEXT, font=ctk.CTkFont(size=17, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(top, text="Each change has its own Apply and Undo.", text_color=MUTED, font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ctk.CTkButton(top, text="UNDO ALL", width=105, height=34, fg_color="#3B2634", hover_color="#573145",
                      command=self.undo_all).grid(row=0, column=1, rowspan=2, sticky="e")

        note = ctk.CTkFrame(area, fg_color="#1A1B3B", corner_radius=14, border_width=1, border_color="#353067")
        note.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(note, text="BEFORE YOU APPLY", text_color="#C3B9FF", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=15, pady=(11, 3))
        ctk.CTkLabel(note, text="A tweak is only applied after you press Apply. The original value is saved locally so Undo can restore it, even after closing the app.",
                     text_color="#C2C8DA", font=ctk.CTkFont(size=10), wraplength=850, justify="left").pack(anchor="w", padx=15, pady=(0, 11))

        gpu_card = ctk.CTkFrame(area, fg_color=PANEL, corner_radius=17, border_width=1, border_color="#3A3269")
        gpu_card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(gpu_card, text="GPU PREFERENCE", text_color="#B7A8FF", font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(gpu_card, text="Prefer High Performance GPU for Fortnite", text_color=TEXT, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16)
        ctk.CTkLabel(gpu_card, text="Adds Fortnite's executable to Windows Graphics preferences. This is mainly useful on PCs with more than one GPU. Restart Fortnite after applying.", text_color=MUTED, font=ctk.CTkFont(size=10), wraplength=850, justify="left").pack(anchor="w", padx=16, pady=(5, 10))
        path_row = ctk.CTkFrame(gpu_card, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 9))
        self.gpu_path_var = tk.StringVar(value=self.state_data.get("fortnite_gpu_path", ""))
        self.gpu_path_entry = ctk.CTkEntry(path_row, textvariable=self.gpu_path_var, placeholder_text="Browse to FortniteClient-Win64-Shipping.exe", height=36)
        self.gpu_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 7))
        ctk.CTkButton(path_row, text="BROWSE", width=83, height=36, fg_color="#2A3A55", hover_color="#3A4F71", command=self._browse_fortnite_exe).pack(side="right")
        actions = ctk.CTkFrame(gpu_card, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 13))
        self.gpu_pref_status = ctk.CTkLabel(actions, text=self._status_text("gpu_preference"), text_color=self._status_color("gpu_preference"), font=ctk.CTkFont(size=9, weight="bold"))
        self.gpu_pref_status.pack(side="left")
        ctk.CTkButton(actions, text="DETECT RUNNING FORTNITE", width=170, height=30, fg_color="#263449", hover_color="#354660", command=self._detect_fortnite_exe).pack(side="right", padx=(6, 0))
        ctk.CTkButton(actions, text="Undo", width=62, height=30, fg_color="#273449", hover_color="#354660", command=self.undo_gpu_preference).pack(side="right", padx=(6, 0))
        ctk.CTkButton(actions, text="Apply", width=68, height=30, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.apply_gpu_preference).pack(side="right")

        grid = ctk.CTkFrame(area, fg_color="transparent")
        grid.grid(row=3, column=0, sticky="ew")
        grid.grid_columnconfigure((0, 1), weight=1)
        self.tweak_cards = {}
        for index, tweak in enumerate(self._tweak_definitions()):
            row, col = divmod(index, 2)
            card = ctk.CTkFrame(grid, fg_color=PANEL, corner_radius=17, border_width=1, border_color="#1D2A40")
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            ctk.CTkLabel(card, text=tweak["category"], text_color="#AFA2FF", font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w", padx=15, pady=(14, 4))
            ctk.CTkLabel(card, text=tweak["title"], text_color=TEXT, font=ctk.CTkFont(size=14, weight="bold"), wraplength=390, justify="left").pack(anchor="w", padx=15)
            ctk.CTkLabel(card, text=tweak["description"], text_color=MUTED, font=ctk.CTkFont(size=10), wraplength=390, justify="left").pack(anchor="w", padx=15, pady=(7, 8))
            ctk.CTkLabel(card, text=tweak["impact"], text_color="#B8C2D3", font=ctk.CTkFont(size=10), wraplength=390, justify="left").pack(anchor="w", padx=15, pady=(0, 9))
            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", padx=14, pady=(0, 13))
            status = ctk.CTkLabel(bottom, text=self._status_text(tweak["id"]), text_color=self._status_color(tweak["id"]), font=ctk.CTkFont(size=9, weight="bold"))
            status.pack(side="left")
            ctk.CTkButton(bottom, text="Undo", width=62, height=30, fg_color="#273449", hover_color="#354660",
                          command=lambda t=tweak: self.undo_tweak(t)).pack(side="right", padx=(6, 0))
            ctk.CTkButton(bottom, text="Apply", width=68, height=30, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=lambda t=tweak: self.apply_tweak(t)).pack(side="right")
            self.tweak_cards[tweak["id"]] = status
        ctk.CTkLabel(area, text="Note: Windows versions and hardware differ. These are conservative settings; no tweak can promise a specific FPS or ping increase.",
                     text_color="#73829B", font=ctk.CTkFont(size=10), wraplength=850, justify="left").grid(row=4, column=0, sticky="w", pady=12)

    def _status_text(self, tweak_id):
        return "● APPLIED" if self.state_data.get(tweak_id, {}).get("applied") else "○ DEFAULT"

    def _status_color(self, tweak_id):
        return GREEN if self.state_data.get(tweak_id, {}).get("applied") else MUTED

    def _refresh_tweak_status(self, tweak_id):
        label = self.tweak_cards.get(tweak_id)
        if label and label.winfo_exists():
            label.configure(text=self._status_text(tweak_id), text_color=self._status_color(tweak_id))
        if tweak_id == "gpu_preference" and getattr(self, "gpu_pref_status", None) is not None and self.gpu_pref_status.winfo_exists():
            self.gpu_pref_status.configure(text=self._status_text(tweak_id), text_color=self._status_color(tweak_id))

    def apply_tweak(self, tweak: dict):
        tweak_id = tweak["id"]
        if self.state_data.get(tweak_id, {}).get("applied"):
            self._notify("This tweak is already applied.")
            return
        try:
            if tweak["kind"] == "power":
                original = active_power_plan()
                self.state_data[tweak_id] = {"applied": True, "original_plan": original}
                save_state(self.state_data)
                try:
                    set_power_plan(HIGH_PERFORMANCE)
                except Exception:
                    self.state_data.pop(tweak_id, None)
                    save_state(self.state_data)
                    raise
            else:
                snapshots = []
                for path, name, value in tweak["items"]:
                    snapshots.append({"path": path, "name": name, "snapshot": registry_snapshot(path, name)})
                self.state_data[tweak_id] = {"applied": True, "snapshots": snapshots}
                save_state(self.state_data)
                try:
                    for path, name, value in tweak["items"]:
                        write_dword(path, name, value)
                except Exception:
                    for item in reversed(snapshots):
                        restore_registry_value(item["path"], item["name"], item["snapshot"])
                    self.state_data.pop(tweak_id, None)
                    save_state(self.state_data)
                    raise
            log_line(f"Applied: {tweak['title']}")
            self._refresh_tweak_status(tweak_id)
            self._notify(f"Applied: {tweak['title']}")
        except Exception as exc:
            messagebox.showerror("Apply failed", f"NOVA could not apply this tweak.\n\n{exc}")

    def undo_tweak(self, tweak: dict):
        tweak_id = tweak["id"]
        saved = self.state_data.get(tweak_id)
        if not saved or not saved.get("applied"):
            self._notify("This tweak is not currently applied by NOVA.")
            return
        try:
            if tweak["kind"] == "power":
                set_power_plan(saved["original_plan"])
            else:
                for item in reversed(saved.get("snapshots", [])):
                    restore_registry_value(item["path"], item["name"], item["snapshot"])
            self.state_data.pop(tweak_id, None)
            save_state(self.state_data)
            log_line(f"Undid: {tweak['title']}")
            self._refresh_tweak_status(tweak_id)
            self._notify(f"Restored: {tweak['title']}")
        except Exception as exc:
            messagebox.showerror("Undo failed", f"NOVA could not restore this tweak.\n\n{exc}")

    def undo_all(self):
        pending = [t for t in self._tweak_definitions() if self.state_data.get(t["id"], {}).get("applied")]
        if self.state_data.get("gpu_preference", {}).get("applied"):
            pending.append({"id": "gpu_preference", "title": "Fortnite High Performance GPU Preference"})
        if not pending:
            self._notify("There are no NOVA tweaks to undo.")
            return
        if not messagebox.askyesno("Undo all tweaks", f"Restore the original settings for {len(pending)} applied tweak(s)?"):
            return
        errors = []
        for tweak in reversed(pending):
            try:
                if tweak["id"] == "gpu_preference":
                    gpu_saved = self.state_data.get("gpu_preference", {})
                    restore_registry_value(r"Software\Microsoft\DirectX\UserGpuPreferences", gpu_saved["exe_path"], gpu_saved["snapshot"])
                    self.state_data.pop("gpu_preference", None)
                    log_line(f"Undid: {tweak['title']}")
                    continue
                saved = self.state_data.get(tweak["id"], {})
                if tweak["kind"] == "power":
                    set_power_plan(saved["original_plan"])
                else:
                    for item in reversed(saved.get("snapshots", [])):
                        restore_registry_value(item["path"], item["name"], item["snapshot"])
                self.state_data.pop(tweak["id"], None)
                log_line(f"Undid: {tweak['title']}")
            except Exception as exc:
                errors.append(f"{tweak['title']}: {exc}")
        save_state(self.state_data)
        self.show_page("Optimizer")
        if errors:
            messagebox.showwarning("Some tweaks could not be restored", "\n".join(errors))
        else:
            self._notify("All NOVA tweaks were restored.")

    def _browse_fortnite_exe(self):
        path = filedialog.askopenfilename(title="Select Fortnite executable", filetypes=[("Fortnite executable", "FortniteClient-Win64-Shipping.exe"), ("Executable files", "*.exe")])
        if path:
            self.gpu_path_var.set(path)
            self.state_data["fortnite_gpu_path"] = path
            save_state(self.state_data)

    def _detect_fortnite_exe(self):
        path = find_running_fortnite_path()
        if not path:
            self._notify("Start Fortnite first, or use Browse to select its game executable.")
            return
        self.gpu_path_var.set(path)
        self.state_data["fortnite_gpu_path"] = path
        save_state(self.state_data)
        self._notify("Fortnite executable detected.")

    def apply_gpu_preference(self):
        path = self.gpu_path_var.get().strip().strip('"')
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Fortnite executable required", "Use Browse or Detect Running Fortnite to select FortniteClient-Win64-Shipping.exe.")
            return
        if os.path.basename(path).lower() != "fortniteclient-win64-shipping.exe":
            messagebox.showwarning("Wrong executable", "Select FortniteClient-Win64-Shipping.exe (the main game executable), not the launcher or anti-cheat process.")
            return
        if self.state_data.get("gpu_preference", {}).get("applied"):
            self._notify("Undo the existing GPU preference before applying it to another path.")
            return
        try:
            key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
            original = registry_snapshot(key_path, path)
            self.state_data["fortnite_gpu_path"] = path
            self.state_data["gpu_preference"] = {"applied": True, "exe_path": path, "snapshot": original}
            save_state(self.state_data)
            try:
                write_string(key_path, path, "GpuPreference=2;")
            except Exception:
                restore_registry_value(key_path, path, original)
                self.state_data.pop("gpu_preference", None)
                save_state(self.state_data)
                raise
            log_line(f"Applied high-performance GPU preference to Fortnite: {path}")
            self._refresh_tweak_status("gpu_preference")
            self._notify("High Performance GPU preference saved. Restart Fortnite to use it.")
        except Exception as exc:
            messagebox.showerror("GPU preference failed", str(exc))

    def undo_gpu_preference(self, silent: bool = False):
        saved = self.state_data.get("gpu_preference")
        if not saved or not saved.get("applied"):
            if not silent:
                self._notify("Fortnite GPU preference is not currently applied by NOVA.")
            return
        try:
            key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
            restore_registry_value(key_path, saved["exe_path"], saved["snapshot"])
            self.state_data.pop("gpu_preference", None)
            save_state(self.state_data)
            log_line(f"Restored GPU preference for Fortnite: {saved['exe_path']}")
            self._refresh_tweak_status("gpu_preference")
            if not silent:
                self._notify("Fortnite GPU preference restored. Restart Fortnite to apply the change.")
        except Exception as exc:
            messagebox.showerror("GPU preference Undo failed", str(exc))

    def _monitor_page(self):
        area = self._scroll_area()
        grid = ctk.CTkFrame(area, fg_color="transparent")
        grid.grid(row=0, column=0, sticky="ew")
        grid.grid_columnconfigure((0, 1), weight=1)
        cpu_card = self._card(grid, "PROCESSOR", "Live overall CPU utilisation")
        cpu_card.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.cpu_value = ctk.CTkLabel(cpu_card, text=f"{getattr(self, 'live_cpu', 0):.0f}%", text_color=TEXT, font=ctk.CTkFont(size=34, weight="bold"))
        self.cpu_value.pack(anchor="w", padx=18)
        self.cpu_bar = ctk.CTkProgressBar(cpu_card, progress_color=ACCENT, fg_color="#263247")
        self.cpu_bar.pack(fill="x", padx=18, pady=(8, 18)); self.cpu_bar.set(getattr(self, 'live_cpu', 0) / 100)
        ram_card = self._card(grid, "MEMORY", "Physical RAM usage")
        ram_card.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.ram_value = ctk.CTkLabel(ram_card, text=f"{getattr(self, 'live_ram', 0):.0f}%", text_color=TEXT, font=ctk.CTkFont(size=34, weight="bold"))
        self.ram_value.pack(anchor="w", padx=18)
        self.ram_bar = ctk.CTkProgressBar(ram_card, progress_color=GREEN, fg_color="#263247")
        self.ram_bar.pack(fill="x", padx=18, pady=(8, 8)); self.ram_bar.set(getattr(self, 'live_ram', 0) / 100)
        self.ram_detail = ctk.CTkLabel(ram_card, text=f"{getattr(self, 'live_ram_used', 0):.1f} GB / {getattr(self, 'live_ram_total', 0):.1f} GB", text_color=MUTED, font=ctk.CTkFont(size=10))
        self.ram_detail.pack(anchor="w", padx=18, pady=(0, 12))

        details = self._card(area, "HARDWARE & GAME STATUS", "Information detected directly from this PC")
        details.grid(row=1, column=0, sticky="ew", pady=10)
        self._info_line(details, "Processor", platform.processor() or "Unknown")
        self._info_line(details, "Logical CPU cores", str(psutil.cpu_count(logical=True) or "Unknown"))
        self._info_line(details, "Graphics adapter", self.gpu_name)
        self._info_line(details, "Operating system", windows_version())
        self._info_line(details, "Fortnite process", "Running" if fortnite_is_running() else "Not detected")
        ctk.CTkLabel(area, text="NOVA does not inject into Fortnite, modify game files, or read anti-cheat data. FPS is not measured by this utility.",
                     text_color=MUTED, font=ctk.CTkFont(size=10), wraplength=850, justify="left").grid(row=2, column=0, sticky="w", pady=8)

    def _network_page(self):
        area = self._scroll_area()
        card = self._card(area, "INTERNET LATENCY TEST", "A simple ICMP test to Cloudflare DNS (1.1.1.1). This is not your Fortnite match server.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.network_value = ctk.CTkLabel(card, text="—", text_color=TEXT, font=ctk.CTkFont(size=42, weight="bold"))
        self.network_value.pack(anchor="w", padx=18, pady=(0, 2))
        self.network_detail = ctk.CTkLabel(card, text="Press Test connection to run a measurement.", text_color=MUTED, font=ctk.CTkFont(size=10))
        self.network_detail.pack(anchor="w", padx=18)
        self.network_button = ctk.CTkButton(card, text="TEST CONNECTION", height=40, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                             command=self.run_ping_test)
        self.network_button.pack(anchor="w", padx=18, pady=16)
        expl = self._card(area, "WHY THIS IS NOT FORTNITE PING", "Fortnite ping depends on the selected game region, routing, ISP, Wi-Fi conditions and the actual match server.")
        expl.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(expl, text="A result to 1.1.1.1 is useful as a basic connection check, but it cannot predict the exact latency shown inside a Fortnite match. NOVA does not change DNS, firewall rules or network adapter settings.",
                     text_color="#C2CBD9", font=ctk.CTkFont(size=11), wraplength=820, justify="left").pack(anchor="w", padx=18, pady=(0, 16))

    def run_ping_test(self):
        if self.ping_running:
            return
        self.ping_running = True
        if hasattr(self, "network_button") and self.network_button.winfo_exists():
            self.network_button.configure(state="disabled", text="TESTING...")
        if hasattr(self, "dashboard_ping") and self.dashboard_ping.winfo_exists():
            self.dashboard_ping.configure(text="Testing...")
        def worker():
            value, detail = measure_internet_latency()
            self.after(0, lambda: self._finish_ping(value, detail))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_ping(self, value: str, detail: str):
        self.ping_running = False
        if hasattr(self, "network_value") and self.network_value.winfo_exists():
            self.network_value.configure(text=value)
            self.network_detail.configure(text=detail)
        if hasattr(self, "dashboard_ping") and self.dashboard_ping.winfo_exists():
            self.dashboard_ping.configure(text=value)
        if hasattr(self, "network_button") and self.network_button.winfo_exists():
            self.network_button.configure(state="normal", text="TEST AGAIN")

    def _settings_page(self):
        area = self._scroll_area()
        card = self._card(area, "WINDOWS SHORTCUTS", "Open the relevant Windows settings page.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        shortcuts = [
            ("Graphics settings", "Choose a high-performance GPU for Fortnite.", "ms-settings:display-advancedgraphics"),
            ("Game Mode settings", "Check the Windows Game Mode toggle.", "ms-settings:gaming-gamemode"),
            ("Captures settings", "Review Windows capture and recording options.", "ms-settings:gaming-captures"),
            ("Network settings", "Open Wi-Fi and Ethernet settings.", "ms-settings:network-status"),
        ]
        for title, desc, uri in shortcuts:
            row = ctk.CTkFrame(card, fg_color="#172235", corner_radius=12)
            row.pack(fill="x", padx=14, pady=5)
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, padx=12, pady=9)
            ctk.CTkLabel(text, text=title, text_color=TEXT, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(text, text=desc, text_color=MUTED, font=ctk.CTkFont(size=9)).pack(anchor="w", pady=(2, 0))
            ctk.CTkButton(row, text="OPEN", width=66, height=30, fg_color="#2A3A55", hover_color="#3A4F71",
                          command=lambda u=uri: self._open_settings(u)).pack(side="right", padx=10)
        about = self._card(area, "ABOUT NOVA", "A local Windows utility. No telemetry, no account, no network services except the ping test you start yourself.")
        about.grid(row=1, column=0, sticky="ew")
        self._info_line(about, "Version", APP_VERSION)
        self._info_line(about, "State file", str(STATE_PATH))
        self._info_line(about, "Activity log", str(LOG_PATH))

    def _open_settings(self, uri: str):
        try:
            os.startfile(uri)
        except Exception as exc:
            messagebox.showerror("Could not open Settings", str(exc))

    def _log_page(self):
        area = self._scroll_area()
        card = self._card(area, "LOCAL ACTIVITY", "Only changes made through NOVA are recorded here.")
        card.grid(row=0, column=0, sticky="ew")
        try:
            content = LOG_PATH.read_text(encoding="utf-8")[-12000:]
        except OSError:
            content = "No activity yet."
        textbox = ctk.CTkTextbox(card, height=350, fg_color="#0B111D", text_color="#C9D4E5",
                                 font=ctk.CTkFont(family="Consolas", size=10), corner_radius=10)
        textbox.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

    def _notify(self, message: str):
        self.toast.configure(text=message)
        self.toast.place(relx=.98, rely=.965, anchor="se")
        if self.toast_job:
            self.after_cancel(self.toast_job)
        self.toast_job = self.after(2800, self.toast.place_forget)


def main():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        app = OptimizerApp()
        app.mainloop()
    except Exception as exc:
        try:
            messagebox.showerror("NOVA failed to start", str(exc))
        except Exception:
            print(exc)
        raise


if __name__ == "__main__":
    main()
