"""
CustomTkinter window — nav bar, lock, and the tabbed view
(Vault / Encrypt / Generate / Settings).

The default entry point is Qt (`python app.py`). Run this module directly
to open the previous window: `python tk_app.py`.
"""
import os
import sys
import time

# Sibling modules when launched from source with a non-repo cwd.
# Frozen builds use sys._MEIPASS (modules live in the PYZ archive).
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _ROOT = sys._MEIPASS
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import customtkinter as ctk

from config import (
    C, PLATFORM, VAULT_FILE, APP_TITLE, init_ui, pad, get_theme, refresh_ui_font,
    ctk_font_title, ctk_font_body, ctk_font_caption, _font,
)
from totp import tfa
from vault_db import vault
from ui_common import clear_app_clipboard, copy_to_clipboard
from screen_unlock import UnlockScreen
from tab_vault import VaultTab
from tab_encrypt import EncryptTab
from tab_generate import GenerateTab
from tab_settings import SettingsTab


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def apply_window_chrome(window):
    """Windows 11 caption color, dark mode, and rounded corners. No-op elsewhere."""
    if PLATFORM != "Windows":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        dwm = ctypes.windll.dwmapi

        def _set(attr: int, value: int):
            raw = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(raw), ctypes.sizeof(raw))

        _set(20, 1 if get_theme() == "dark" else 0)
        bg = _colorref(C["bg"])
        _set(35, bg)  # DWMWA_CAPTION_COLOR
        _set(34, bg)  # DWMWA_BORDER_COLOR
        _set(33, 2)   # DWMWA_WINDOW_CORNER_PREFERENCE = round
    except Exception:
        pass


def enable_windows_dpi():
    """Per-monitor DPI must be set before the first Tk window exists."""
    if PLATFORM != "Windows":
        return
    try:
        import ctypes
        # PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _ellipsis_middle_end(path: str, limit: int = 42) -> str:
    if len(path) <= limit:
        return path
    return "…" + path[-(limit - 1):]


def _path_tooltip(widget, text: str):
    """Show full path on hover."""
    import tkinter as tk
    tip = {"win": None}

    def _show(_event=None):
        if tip["win"] is not None:
            return
        tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tk.Label(
            tw, text=text, bg=C["surface"], fg=C["text"],
            font=_font(9), padx=10, pady=6, relief="solid", bd=1,
            highlightbackground=C["border"],
        ).pack()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tw.geometry(f"+{x}+{y}")
        tip["win"] = tw

    def _hide(_event=None):
        if tip["win"] is not None:
            try:
                tip["win"].destroy()
            except Exception:
                pass
            tip["win"] = None

    widget.bind("<Enter>", _show, add="+")
    widget.bind("<Leave>", _hide, add="+")


def _typing_widget(widget) -> bool:
    import tkinter as tk
    name = widget.winfo_class()
    return name in ("Entry", "Text", "TEntry") or isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox, tk.Entry, tk.Text))


class App(ctk.CTk):
    def __init__(self):
        enable_windows_dpi()
        init_ui()
        super().__init__()
        refresh_ui_font()
        apply_window_chrome(self)
        self.title(APP_TITLE)
        self.geometry("1200x860")
        self.minsize(960, 680)
        self.configure(fg_color=C["bg"])
        self._main = None
        self._unlock = None
        self._vault_tab = None
        self._idle_after = None
        self._idle_bound = False
        self._last_activity = 0.0
        self._count_pill = None
        self._idle_pill = None
        self._path_pill = None
        self.show_unlock()

    def _platform_tweaks(self):
        if PLATFORM == "Darwin":
            try:
                self.createcommand("tk::mac::Quit", self.quit)
            except Exception:
                pass

    def _bind_idle_watchers(self):
        if self._idle_bound:
            return
        self._idle_bound = True
        for seq in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>"):
            self.bind_all(seq, self._on_activity, add="+")

    def _on_activity(self, _event=None):
        now = time.monotonic()
        if now - self._last_activity < 1.0:
            return
        self._last_activity = now
        if self._main is not None:
            self._arm_idle_timer()

    def _arm_idle_timer(self):
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except Exception:
                pass
            self._idle_after = None
        if self._main is None or not vault.unlocked:
            return
        minutes = vault.get_idle_lock_minutes()
        if minutes <= 0:
            return
        self._idle_after = self.after(minutes * 60_000, self._idle_lock)

    def _idle_lock(self):
        self._idle_after = None
        if self._main is not None and vault.unlocked:
            self.show_unlock()

    def _cancel_idle_timer(self):
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except Exception:
                pass
            self._idle_after = None

    def _on_find(self, event=None):
        if self._vault_tab is not None and self._main is not None:
            self._vault_tab.focus_search()
            return "break"

    def _on_new_entry(self, event=None):
        if self._main is None or self._vault_tab is None:
            return
        if event is not None and _typing_widget(event.widget):
            return
        self._vault_tab.open_new_entry()
        return "break"

    def _on_lock_key(self, _event=None):
        if self._main is not None:
            self.show_unlock()
            return "break"

    def _bind_shortcuts(self):
        self.bind("<Control-f>", self._on_find)
        self.bind("<Control-F>", self._on_find)
        self.bind("<Control-n>", self._on_new_entry)
        self.bind("<Control-N>", self._on_new_entry)
        self.bind("<Control-l>", self._on_lock_key)
        self.bind("<Control-L>", self._on_lock_key)

    def show_unlock(self):
        self._cancel_idle_timer()
        clear_app_clipboard(self)
        if self._main:
            self._main.destroy()
            self._main = None
        self._vault_tab = None
        self._count_pill = None
        self._idle_pill = None
        vault.lock()
        tfa.unload()
        if self._unlock:
            self._unlock.destroy()
        self._unlock = UnlockScreen(self, self.show_main)
        apply_window_chrome(self)

    def show_main(self):
        if vault.unlocked_via_recovery:
            self.show_unlock()
            return
        if self._unlock:
            self._unlock.destroy()
            self._unlock = None
        if self._main:
            self._main.destroy()
            self._main = None
        self._build_main()
        self._bind_idle_watchers()
        self._arm_idle_timer()
        self._bind_shortcuts()

    def rebuild_for_theme(self):
        """Recreate the open screen so explicit widget colors pick up the palette."""
        self.configure(fg_color=C["bg"])
        apply_window_chrome(self)
        if self._main is not None and vault.unlocked:
            self.show_main()
        elif self._unlock is not None:
            self.show_unlock()

    def refresh_status(self):
        if self._count_pill is None:
            return
        n = vault.entry_count()
        self._count_pill.configure(text=f"{n} entr{'y' if n == 1 else 'ies'}")
        if self._idle_pill is None:
            return
        minutes = vault.get_idle_lock_minutes() if vault.unlocked else 0
        self._idle_pill.configure(
            text=f"Auto-lock {minutes}m" if minutes > 0 else "Auto-lock off",
        )

    def _show_page(self, name: str):
        for label, page in self._pages.items():
            if label == name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for label, btn in self._nav_btns.items():
            selected = label == name
            btn.configure(
                fg_color=C["primary"] if selected else "transparent",
                text_color=C["on_primary"] if selected else C["subtext"],
                hover_color=C["primary"] if selected else C["surface3"],
            )

    def _build_main(self):
        self._platform_tweaks()
        self._main = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._main.pack(fill="both", expand=True)

        body = ctk.CTkFrame(self._main, fg_color=C["bg"], corner_radius=0)
        body.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(body, fg_color=C["surface2"], width=pad(220), corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar, text="LocalPasswordVault", fg_color="transparent",
            text_color=C["text"], font=ctk_font_title(), anchor="w", justify="left",
            wraplength=pad(188),
        ).pack(anchor="w", padx=pad(16), pady=(pad(20), pad(4)))
        self._count_pill = ctk.CTkLabel(
            sidebar, text="0 entries", fg_color="transparent",
            text_color=C["subtext"], font=ctk_font_caption(), anchor="w",
        )
        self._count_pill.pack(anchor="w", padx=pad(16))
        self._idle_pill = ctk.CTkLabel(
            sidebar, text="Auto-lock", fg_color="transparent",
            text_color=C["subtext"], font=ctk_font_caption(), anchor="w",
        )
        self._idle_pill.pack(anchor="w", padx=pad(16), pady=(0, pad(16)))

        self._nav_btns = {}
        classes = (
            ("Vault", VaultTab),
            ("Encrypt", EncryptTab),
            ("Generate", GenerateTab),
            ("Settings", SettingsTab),
        )
        for label, _cls in classes:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                fg_color="transparent", text_color=C["subtext"],
                hover_color=C["surface3"], font=ctk_font_body(),
                height=pad(40), corner_radius=pad(8),
                command=lambda n=label: self._show_page(n),
            )
            btn.pack(fill="x", padx=pad(12), pady=2)
            self._nav_btns[label] = btn

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=pad(12), pady=pad(16))
        short = _ellipsis_middle_end(VAULT_FILE, 28)
        self._path_pill = ctk.CTkLabel(
            footer, text=short, fg_color="transparent", text_color=C["subtext"],
            font=ctk_font_caption(), anchor="w", justify="left", wraplength=pad(180),
        )
        self._path_pill.pack(anchor="w", pady=(0, pad(8)))
        self._path_pill.configure(cursor="hand2")
        _path_tooltip(self._path_pill, VAULT_FILE)

        def _copy_path(_event=None):
            copy_to_clipboard(self._path_pill, VAULT_FILE)
            self._path_pill.configure(text="Copied")
            self.after(1200, lambda: self._path_pill.configure(text=short))

        self._path_pill.bind("<Button-1>", _copy_path, add="+")
        ctk.CTkButton(
            footer, text="Lock", anchor="w",
            fg_color=C["danger"], hover_color="#B91C1C", text_color=C["on_danger"],
            font=ctk_font_caption("bold"), height=pad(36), corner_radius=pad(8),
            command=self.show_unlock,
        ).pack(fill="x")

        content = ctk.CTkFrame(body, fg_color=C["bg"], corner_radius=0)
        content.pack(side="left", fill="both", expand=True)

        self._pages = {}
        for label, cls in classes:
            page = ctk.CTkFrame(content, fg_color=C["bg"], corner_radius=0)
            built = cls(page)
            self._pages[label] = page
            if cls is VaultTab:
                self._vault_tab = built
        self._show_page("Vault")
        self.refresh_status()
        apply_window_chrome(self)


def main():
    enable_windows_dpi()
    App().mainloop()


if __name__ == "__main__":
    main()
