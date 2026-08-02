"""
Main application window — nav bar, lock button, and the tabbed view
(Vault / Encrypt / Generate / Settings).
"""
import os
import sys

# Sibling modules when launched from source with a non-repo cwd.
# Frozen builds use sys._MEIPASS (modules live in the PYZ archive).
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _ROOT = sys._MEIPASS
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import customtkinter as ctk
from tkinter import ttk

from config import (
    C, PLATFORM, VAULT_FILE, APP_TITLE, init_ui, pad,
    ctk_font_title, ctk_font_caption, _font, DEFAULT_IDLE_LOCK_MINUTES,
)
from totp import tfa
from vault_db import vault
from ui_common import _btn, pill, make_tabview, style_tab_bar, copy_to_clipboard
from screen_unlock import UnlockScreen
from tab_vault import VaultTab
from tab_encrypt import EncryptTab
from tab_generate import GenerateTab
from tab_settings import SettingsTab


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


class App(ctk.CTk):
    def __init__(self):
        init_ui()
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x860")
        self.minsize(960, 680)
        self.configure(fg_color=C["bg"])
        self._style_treeview()
        self._platform_tweaks()
        self._main = None
        self._unlock = None
        self._idle_after = None
        self._idle_bound = False
        self.show_unlock()

    def _style_treeview(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"],
                    relief="flat", borderwidth=0, focusthickness=0)
        s.configure("Treeview",
                    background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=pad(48),
                    borderwidth=0, relief="flat")
        s.configure("Treeview.Heading",
                    background=C["surface2"], foreground=C["subtext"],
                    borderwidth=0)
        s.map("Treeview",
              background=[("selected", C["accent"])],
              foreground=[("selected", "#FFFFFF")])
        s.configure("TScrollbar",
                    troughcolor=C["surface2"], background=C["subtext"],
                    arrowcolor=C["surface"], relief="flat", borderwidth=0)

    def _platform_tweaks(self):
        if PLATFORM == "Darwin":
            try:
                self.createcommand("tk::mac::Quit", self.quit)
            except Exception:
                pass
        elif PLATFORM == "Windows":
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

    def _bind_idle_watchers(self):
        if self._idle_bound:
            return
        self._idle_bound = True
        for seq in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>"):
            self.bind_all(seq, self._on_activity, add="+")

    def _on_activity(self, _event=None):
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

    def show_unlock(self):
        self._cancel_idle_timer()
        if self._main:
            self._main.destroy()
            self._main = None
        vault.lock()
        tfa.unload()
        self._unlock = UnlockScreen(self, self.show_main)

    def show_main(self):
        if vault.unlocked_via_recovery:
            # Should not reach here — UnlockScreen gates on reset-master first
            self.show_unlock()
            return
        if self._unlock:
            self._unlock.destroy()
            self._unlock = None
        self._main = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._main.pack(fill="both", expand=True)

        nav = ctk.CTkFrame(self._main, fg_color=C["surface"], height=pad(64), corner_radius=0)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        ctk.CTkLabel(nav, text="🔐", fg_color="transparent",
                     text_color=C["accent"], font=_font(22)).pack(side="left", padx=(pad(20), pad(8)))
        ctk.CTkLabel(nav, text="LocalPasswordVault", fg_color="transparent",
                     text_color=C["text"], font=ctk_font_title()).pack(side="left")
        n = vault.entry_count()
        pill(nav, f"{n} entr{'y' if n == 1 else 'ies'}",
             bg=C["accent_soft"], fg=C["accent"],
             font=ctk_font_caption("bold")).pack(side="left", padx=(pad(12), 0))

        # Full vault path (was truncating the start with "…tail")
        path_pill = pill(nav, VAULT_FILE, bg=C["surface2"], fg=C["subtext"],
                         font=ctk_font_caption())
        path_pill.pack(side="left", padx=(pad(8), 0))
        path_pill.configure(cursor="hand2")
        _path_tooltip(path_pill, VAULT_FILE)
        path_pill.bind(
            "<Button-1>",
            lambda _e: copy_to_clipboard(path_pill, VAULT_FILE),
            add="+",
        )

        idle_m = vault.get_idle_lock_minutes() if vault.unlocked else DEFAULT_IDLE_LOCK_MINUTES
        if idle_m > 0:
            pill(nav, f"Auto-lock {idle_m}m", bg=C["surface2"], fg=C["subtext"],
                 font=ctk_font_caption()).pack(side="left", padx=(pad(8), 0))

        pill(nav, "● Unlocked", bg=C["success_soft"], fg=C["success"],
             font=ctk_font_caption("bold")).pack(side="right", padx=(pad(4), pad(8)))
        _btn(nav, "🔒 Lock", self.show_unlock,
             bg=C["danger"], fg="#FFFFFF", hover_bg="#B02020",
             font_style=ctk_font_caption("bold"), padx=pad(16), pady=pad(8)
             ).pack(side="right", padx=(pad(4), pad(20)))

        ctk.CTkFrame(self._main, fg_color=C["border"], height=1, corner_radius=0).pack(fill="x")

        tabview = make_tabview(self._main)
        tabview.pack(fill="both", expand=True, padx=pad(16), pady=pad(12))
        for label, Cls in [("🔑  Vault", VaultTab),
                            ("🔒  Encrypt", EncryptTab),
                            ("⚡  Generate", GenerateTab),
                            ("⚙️  Settings", SettingsTab)]:
            tab = tabview.add(label)
            tab.configure(fg_color=C["bg"])
            Cls(tab)
        style_tab_bar(tabview)

        self._bind_idle_watchers()
        self._arm_idle_timer()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
