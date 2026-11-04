"""
Platform helpers, app-wide constants, and the color palette.
"""
import json, os, sys, platform

# ─────────────────────────── Platform ───────────────────────────
PLATFORM = platform.system()

# ─────────────────────────── Typography & spacing ───────────────────────────
# Single scale factor — all _font() / _mono() sizes and UI spacing derive from this.
UI_SCALE = 1.1

# OS UI grotesque. refresh_ui_font() prefers Segoe UI Variable / the Mac system font
# once a Tk root exists; Inter is the design-system face but Tk cannot load it.
_UI_FACE = {"Darwin": "Helvetica Neue", "Windows": "Segoe UI"}.get(PLATFORM, "DejaVu Sans")

def _scaled(n: int) -> int:
    return max(9, round(n * UI_SCALE))

def _font(size, weight="normal"):
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return (_UI_FACE, sz, weight) if weight != "normal" else (_UI_FACE, sz)

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

def _ctk():
    """Imported only by the Tk window. The Qt build does not ship this package."""
    import customtkinter as ctk
    return ctk


def _ctk_font(size, weight="normal"):
    sz = _scaled(size) if isinstance(size, (int, float)) else size
    return _ctk().CTkFont(family=_UI_FACE, size=sz, weight=weight)

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
    return _ctk().CTkFont(family=face, size=sz, weight=weight)

def init_ui():
    """Apply the saved appearance before any window is created."""
    load_theme()
    _ctk().set_default_color_theme("green")


def refresh_ui_font():
    """Pick the installed OS UI font. Call after the Tk root exists."""
    global _UI_FACE
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families())
    except Exception:
        return
    if PLATFORM == "Windows":
        options = ("Segoe UI Variable", "Segoe UI")
    elif PLATFORM == "Darwin":
        options = (".AppleSystemUIFont", "SF Pro", "Helvetica Neue")
    else:
        options = ("DejaVu Sans",)
    for name in options:
        if name in families:
            _UI_FACE = name
            return

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
PREFS_FILE = os.path.join(_DATA_DIR, f"{APP_SLUG}.prefs")

ARG_ITERS = 3
ARG_MEM   = 65536   # 64 MiB
ARG_LANES = 4
KEY_BYTES = 32

# Clipboard auto-clear after copy (ms). Idle lock default is stored in vault meta.
CLIPBOARD_CLEAR_MS = 30_000
DEFAULT_IDLE_LOCK_MINUTES = 5

# Navy primary, emerald accent. Light surfaces are the same slate family as the dark set.
LIGHT = {
    "bg":       "#F8FAFC",
    "surface":  "#FFFFFF",
    "surface2": "#F1F5F9",
    "surface3": "#E2E8F0",
    "border":   "#E2E8F0",
    "shadow":   "#E2E8F0",
    "ring":     "#1E3A5F",
    "primary":  "#1E3A5F",
    "on_primary": "#FFFFFF",
    "primary_soft": "#E6EBF1",
    "accent":   "#059669",
    "accent2":  "#047857",
    "accent_soft": "#D1FAE5",
    "on_accent": "#000000",
    "amber":    "#B45309",
    "amber2":   "#92400E",
    "success":  "#059669",
    "success_soft": "#D1FAE5",
    "warning":  "#B45309",
    "danger":   "#DC2626",
    "danger_soft": "#FEE2E2",
    "on_danger": "#FFFFFF",
    "text":     "#0F172A",
    "subtext":  "#334155",
    "white":    "#0F172A",
    "input_fg": "#0F172A",
    "input_bg": "#FFFFFF",
    "input_ph": "#64748B",
    "encrypt_bg": "#E6EBF1",
    "encrypt_fg": "#1E3A5F",
    "decrypt_bg": "#F1F5F9",
    "decrypt_fg": "#334155",
}

DARK = {
    "bg":       "#0F172A",
    "surface":  "#192134",
    "surface2": "#10192E",
    "surface3": "#1E293B",
    "border":   "#2A3348",
    "shadow":   "#0B1220",
    "ring":     "#FFFFFF",
    "primary":  "#1E3A5F",
    "on_primary": "#FFFFFF",
    "primary_soft": "#243044",
    "accent":   "#059669",
    "accent2":  "#047857",
    "accent_soft": "#064E3B",
    "on_accent": "#000000",
    "amber":    "#D97706",
    "amber2":   "#B45309",
    "success":  "#059669",
    "success_soft": "#064E3B",
    "warning":  "#D97706",
    "danger":   "#DC2626",
    "danger_soft": "#3F1D1D",
    "on_danger": "#FFFFFF",
    "text":     "#FFFFFF",
    "subtext":  "#94A3B8",
    "white":    "#FFFFFF",
    "input_fg": "#FFFFFF",
    "input_bg": "#10192E",
    "input_ph": "#94A3B8",
    "encrypt_bg": "#1E3A5F",
    "encrypt_fg": "#FFFFFF",
    "decrypt_bg": "#243044",
    "decrypt_fg": "#94A3B8",
}

# Mutated in place so `from config import C` sees theme switches.
C = dict(LIGHT)
_theme = "light"


def get_theme() -> str:
    return _theme


def apply_theme(mode: str):
    """Switch the shared palette. Already-built widgets keep their colors until rebuilt."""
    global _theme
    _theme = "dark" if mode == "dark" else "light"
    C.clear()
    C.update(DARK if _theme == "dark" else LIGHT)
    try:
        _ctk().set_appearance_mode(_theme)
    except Exception:
        pass


def load_theme():
    mode = "light"
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            mode = json.load(f).get("theme", "light")
    except Exception:
        pass
    apply_theme(mode)


def save_theme(mode: str):
    apply_theme(mode)
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": get_theme()}, f)
    except Exception:
        pass
