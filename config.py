"""
Platform helpers, app-wide constants, and the color palette.
"""
import os, sys, platform

import customtkinter as ctk

# ─────────────────────────── Platform ───────────────────────────
PLATFORM = platform.system()

# ─────────────────────────── Typography & spacing ───────────────────────────
# Single scale factor — all _font() / _mono() sizes and UI spacing derive from this.
UI_SCALE = 1.28

def _scaled(n: int) -> int:
    return max(9, round(n * UI_SCALE))

def _font(size, weight="normal"):
    face = {"Darwin": "Helvetica Neue", "Windows": "Segoe UI"}.get(PLATFORM, "DejaVu Sans")
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return (face, sz, weight) if weight != "normal" else (face, sz)

def _mono(size, weight="normal"):
    face = {"Darwin": "Menlo", "Windows": "Consolas"}.get(PLATFORM, "DejaVu Sans Mono")
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return (face, sz, weight) if weight != "normal" else (face, sz)

# Semantic type roles (base sizes before _font applies UI_SCALE)
def font_display(w="bold"):   return _font(28, w)
def font_title(w="bold"):     return _font(18, w)
def font_heading(w="bold"):   return _font(15, w)
def font_subhead(w="bold"):   return _font(13, w)
def font_body(w="normal"):    return _font(11, w)
def font_label(w="normal"):   return _font(10, w)
def font_caption(w="normal"): return _font(9, w)
def font_micro(w="normal"):   return _font(8, w)

def pad(n: int) -> int:
    """Scale layout padding/spacing."""
    return max(2, round(n * UI_SCALE))

def _ctk_font(size, weight="normal"):
    face = {"Darwin": "Helvetica Neue", "Windows": "Segoe UI"}.get(PLATFORM, "DejaVu Sans")
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return ctk.CTkFont(family=face, size=sz, weight=weight)

def ctk_font_display(w="bold"):   return _ctk_font(28, w)
def ctk_font_title(w="bold"):     return _ctk_font(18, w)
def ctk_font_heading(w="bold"):   return _ctk_font(15, w)
def ctk_font_subhead(w="bold"):   return _ctk_font(13, w)
def ctk_font_body(w="normal"):    return _ctk_font(11, w)
def ctk_font_label(w="normal"):   return _ctk_font(10, w)
def ctk_font_caption(w="normal"): return _ctk_font(9, w)
def ctk_font_micro(w="normal"):   return _ctk_font(8, w)
def ctk_font_mono(size, weight="normal"):
    face = {"Darwin": "Menlo", "Windows": "Consolas"}.get(PLATFORM, "DejaVu Sans Mono")
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return ctk.CTkFont(family=face, size=sz, weight=weight)

def init_ui():
    """Apply global CustomTkinter appearance."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

def _app_dir() -> str:
    """Directory where vault files live — same folder as the app / script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────── Constants ───────────────────────────
APP_TITLE = "LocalPasswordVault"
APP_SLUG = "localpasswordvault"

_DATA_DIR = _app_dir()


def _migrate_legacy_file(new_path: str, legacy_path: str) -> str:
    """Prefer new name; rename legacy SecureVault files when present."""
    if os.path.exists(new_path):
        return new_path
    if os.path.exists(legacy_path):
        try:
            os.rename(legacy_path, new_path)
            return new_path
        except OSError:
            return legacy_path
    return new_path


# One-time rename of old securevault.* data files → localpasswordvault.*
VAULT_FILE = _migrate_legacy_file(
    os.path.join(_DATA_DIR, f"{APP_SLUG}.db"),
    os.path.join(_DATA_DIR, "securevault.db"),
)
for _suffix in (".bak", "-wal", "-shm", "-journal"):
    _migrate_legacy_file(VAULT_FILE + _suffix, os.path.join(_DATA_DIR, "securevault.db" + _suffix))
BAK_FILE = VAULT_FILE + ".bak"
TFA_FILE = _migrate_legacy_file(
    os.path.join(_DATA_DIR, f"{APP_SLUG}.2fa"),
    os.path.join(_DATA_DIR, "securevault.2fa"),
)
_migrate_legacy_file(TFA_FILE + ".tmp", os.path.join(_DATA_DIR, "securevault.2fa.tmp"))

ARG_ITERS = 3
ARG_MEM   = 65536   # 64 MiB
ARG_LANES = 4
KEY_BYTES = 32

# Clipboard auto-clear after copy (ms). Idle lock default is stored in vault meta.
CLIPBOARD_CLEAR_MS = 30_000
DEFAULT_IDLE_LOCK_MINUTES = 5

C = {
    # Backgrounds — soft neutral hierarchy
    "bg":       "#F4F4F8",
    "surface":  "#FFFFFF",
    "surface2": "#F0F1F6",
    "surface3": "#E8EAF0",
    # Borders, shadows, depth
    "border":   "#E2E4EA",
    "shadow":   "#D5D8E0",
    "ring":     "#B8D4F0",
    # Accents
    "accent":   "#0066DD",
    "accent2":  "#0052B8",
    "accent_soft": "#E8F2FF",
    "amber":    "#C96D00",
    "amber2":   "#A05500",
    "success":  "#16803A",
    "success_soft": "#E8F7EE",
    "warning":  "#B07D00",
    "danger":   "#D92B2B",
    "danger_soft": "#FDECEC",
    # Text
    "text":     "#141418",
    "subtext":  "#6B6B76",
    "white":    "#141418",
    # Inputs
    "input_fg": "#141418",
    "input_bg": "#FAFBFD",
    "input_ph": "#A8AAB4",
}
