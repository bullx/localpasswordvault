"""
Shared, reusable CustomTkinter UI building blocks: mousewheel binding, QR code
rendering, buttons, entries, strength bar, mode selector, and the live TOTP
countdown widget.
"""
import tkinter as tk
import customtkinter as ctk

from config import (
    C, PLATFORM, _font, _mono, pad, CLIPBOARD_CLEAR_MS,
    ctk_font_body, ctk_font_label, ctk_font_caption, ctk_font_subhead, ctk_font_mono,
)
from totp import _totp_code

# ─────────────────────────── Tab Bar ───────────────────────────

class _ScaledTabview(ctk.CTkTabview):
    """CTkTabview with tab-bar dimensions matched to UI_SCALE."""
    _button_height = 46
    _outer_spacing = 12
    _outer_button_overhang = 10
    _segmented_button_border_width = 2


def make_tabview(parent, **kwargs):
    """Create a tab view whose segmented buttons match nav/page typography."""
    opts = dict(
        fg_color=C["bg"],
        corner_radius=pad(10),
        border_width=1,
        border_color=C["border"],
        segmented_button_fg_color=C["surface3"],
        segmented_button_selected_color=C["surface"],
        segmented_button_selected_hover_color=C["surface"],
        segmented_button_unselected_color=C["surface2"],
        segmented_button_unselected_hover_color=C["surface3"],
        segmented_button_font=ctk_font_body("bold"),
        text_color=C["text"],
    )
    opts.update(kwargs)
    return _ScaledTabview(parent, **opts)


def style_tab_bar(tabview):
    """Highlight the active tab with accent color (matches old ttk notebook)."""
    def _refresh():
        current = tabview.get()
        for name, btn in tabview._segmented_button._buttons_dict.items():
            active = name == current
            btn.configure(
                text_color=C["accent"] if active else C["text"],
                font=ctk_font_body("bold" if active else "normal"),
            )

    tabview.configure(command=_refresh)
    _refresh()

# ─────────────────────────── Mousewheel Helper ───────────────────────────

def copy_to_clipboard(widget, text: str, clear_ms: int = CLIPBOARD_CLEAR_MS):
    """Copy text and schedule clipboard clear (cancels any previous timer)."""
    if not text:
        return
    root = widget.winfo_toplevel()
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
    except Exception:
        return
    prev = getattr(root, "_sv_clip_after", None)
    if prev is not None:
        try:
            root.after_cancel(prev)
        except Exception:
            pass

    def _clear():
        root._sv_clip_after = None
        try:
            # Best-effort: clear only if still our value
            if root.clipboard_get() == text:
                root.clipboard_clear()
        except Exception:
            pass

    if clear_ms and clear_ms > 0:
        root._sv_clip_after = root.after(clear_ms, _clear)


def _bind_mousewheel(canvas):
    """Bind mouse-wheel scrolling to a canvas, cross-platform."""
    def _on_mousewheel(event):
        if PLATFORM == "Darwin":
            canvas.yview_scroll(-1 * event.delta, "units")
        else:
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_linux_scroll(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")

    def _bind_to_widget(widget):
        if PLATFORM in ("Windows", "Darwin"):
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        else:
            widget.bind("<Button-4>", _on_linux_scroll, add="+")
            widget.bind("<Button-5>", _on_linux_scroll, add="+")
        for child in widget.winfo_children():
            _bind_to_widget(child)

    _bind_to_widget(canvas)
    canvas.bind("<Configure>", lambda e: _bind_to_widget(canvas), add='+')

# ─────────────────────────── QR Code Renderer ───────────────────────────

def _qr_matrix(data: str) -> list:
    try:
        import qrcode as _qr
        qr = _qr.QRCode(error_correction=_qr.constants.ERROR_CORRECT_L,
                         box_size=1, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        return matrix, None
    except ImportError:
        return None, "Install 'qrcode' for QR display:\n  pip install qrcode"
    except Exception as e:
        return None, f"QR error: {e}"


class QRCanvas(tk.Canvas):
    """Renders a QR code matrix onto a tk.Canvas."""
    def __init__(self, master, uri: str, size: int = 240, **kw):
        super().__init__(master, width=size, height=size,
                         bg=C["surface"], highlightthickness=0, **kw)
        self._uri  = uri
        self._size = size
        self._draw()

    def _draw(self):
        self.delete("all")
        matrix, err = _qr_matrix(self._uri)
        if matrix is None:
            self.create_rectangle(0, 0, self._size, self._size,
                                  fill=C["surface2"], outline=C["border"])
            self.create_text(self._size // 2, self._size // 2,
                             text=err + "\n\nSecret key shown below.",
                             fill=C["subtext"], font=_font(9),
                             width=self._size - 20, justify="center")
            return
        n     = len(matrix)
        cell  = self._size / n
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                fill = "#000000" if dark else "#FFFFFF"
                x0, y0 = c * cell, r * cell
                self.create_rectangle(x0, y0, x0 + cell, y0 + cell,
                                      fill=fill, outline=fill)


# ─────────────────────────── UI Helpers ───────────────────────────

class StrengthBar(tk.Canvas):
    def __init__(self, master, **kw):
        super().__init__(master, height=pad(6), bg=C["border"],
                         highlightthickness=0, **kw)
        self.bind("<Configure>", lambda _: self._draw(0, C["subtext"]))

    def set_score(self, score, color):
        self._draw(score, color)

    def _draw(self, score, color):
        self.delete("all")
        w = self.winfo_width()
        if w < 2:
            return
        self.create_rectangle(0, 0, w, 5, fill=C["surface2"], outline="")
        if score > 0:
            self.create_rectangle(0, 0, max(4, int(w * score / 100)), 5,
                                  fill=color, outline="")


class EWP(ctk.CTkEntry):
    """Entry with placeholder — CTkEntry wrapper preserving val()/set_val() API."""
    def __init__(self, master, placeholder="", show_char="", **kw):
        show = show_char or kw.pop("show", "")
        ph = kw.pop("placeholder_text", placeholder)
        height = kw.pop("height", pad(36))
        super().__init__(
            master,
            placeholder_text=ph,
            show=show,
            font=ctk_font_body(),
            fg_color=C["input_bg"],
            border_color=C["border"],
            text_color=C["input_fg"],
            placeholder_text_color=C["input_ph"],
            corner_radius=pad(8),
            height=height,
            **kw,
        )

    def val(self):
        return self.get()

    def set_val(self, v):
        self.delete(0, "end")
        if v:
            self.insert(0, v)

    def _set_ph(self):
        self.delete(0, "end")


def sep(parent, **kw):
    f = ctk.CTkFrame(parent, fg_color=C["border"], height=1, corner_radius=0)
    f.pack(fill="x", **kw)
    return f


def shadow_card(parent, **pack_kw):
    """Card with rounded corners and subtle border."""
    outer = ctk.CTkFrame(
        parent, fg_color=C["shadow"], corner_radius=pad(12),
        border_width=1, border_color=C["border"],
    )
    inner = ctk.CTkFrame(outer, fg_color=C["surface"], corner_radius=pad(10))
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    if pack_kw:
        outer.pack(**pack_kw)
    return outer, inner


def pill(parent, text, bg=None, fg=None, font=None, padx=10, pady=4):
    """Rounded badge label for nav/status chips."""
    return ctk.CTkLabel(
        parent, text=text,
        fg_color=bg or C["surface2"],
        text_color=fg or C["subtext"],
        font=font or ctk_font_caption(),
        corner_radius=pad(12),
        padx=pad(padx), pady=pad(pady),
    )


def _btn(parent, text, cmd,
         bg="#0077CC", fg="#FFFFFF",
         hover_bg=None, font_style=None,
         padx=14, pady=7, border=None, border_color=None):
    """Styled CTkButton with config_btn() for runtime updates."""
    hbg = hover_bg or bg
    fnt = font_style or ctk_font_label("bold")
    height = max(pad(32), pad(pady) * 2 + pad(12))

    btn = ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=bg, hover_color=hbg, text_color=fg,
        font=fnt, corner_radius=pad(8), height=height,
        border_width=1 if border else 0,
        border_color=border_color or bg,
    )

    def _config(**kw):
        nonlocal bg, hbg
        if "bg" in kw:
            bg = kw.pop("bg")
            btn.configure(fg_color=bg)
        if "text" in kw:
            btn.configure(text=kw.pop("text"))
        if "fg" in kw:
            btn.configure(text_color=kw.pop("fg"))
        if "font" in kw:
            btn.configure(font=kw.pop("font"))
        if "activebackground" in kw:
            hbg = kw.pop("activebackground")
            btn.configure(hover_color=hbg)
        kw.pop("activeforeground", None)

    btn.config_btn = _config
    return btn


def abtn(parent, text, cmd, color=None):
    bg = color or C["accent"]
    return _btn(parent, text, cmd,
                bg=bg, fg="#FFFFFF",
                hover_bg=C["accent2"],
                font_style=ctk_font_body("bold"),
                padx=pad(20), pady=pad(10))


def gbtn(parent, text, cmd, fg=None):
    tc = fg or C["accent"]
    return _btn(parent, text, cmd,
                bg=C["surface"], fg=tc,
                hover_bg=C["accent_soft"],
                font_style=ctk_font_label("bold"),
                padx=pad(14), pady=pad(8),
                border=1, border_color=C["border"])


def dbtn(parent, text, cmd):
    return _btn(parent, text, cmd,
                bg=C["danger"], fg="#FFFFFF",
                hover_bg="#B02020",
                font_style=ctk_font_label("bold"),
                padx=pad(14), pady=pad(8))


def card(parent, title=None, sub=None):
    f = ctk.CTkFrame(
        parent, fg_color=C["surface"], corner_radius=pad(10),
        border_width=1, border_color=C["border"],
    )
    if title:
        ctk.CTkLabel(
            f, text=title, fg_color="transparent", text_color=C["white"],
            font=ctk_font_subhead("bold"),
        ).pack(anchor="w", padx=pad(18), pady=(pad(16), pad(4)))
    if sub:
        ctk.CTkLabel(
            f, text=sub, fg_color="transparent", text_color=C["subtext"],
            font=ctk_font_caption(),
        ).pack(anchor="w", padx=pad(18), pady=(0, pad(10)))
    return f


def info_row(parent, label, value, desc=""):
    r = ctk.CTkFrame(parent, fg_color="transparent")
    r.pack(fill="x", pady=pad(3))
    ctk.CTkLabel(
        r, text=label, fg_color="transparent", text_color=C["subtext"],
        font=ctk_font_caption(), width=pad(128), anchor="w",
    ).pack(side="left")
    ctk.CTkLabel(
        r, text=value, fg_color="transparent", text_color=C["accent"],
        font=ctk_font_mono(10, "bold"),
    ).pack(side="left", padx=pad(8))
    if desc:
        ctk.CTkLabel(
            r, text=desc, fg_color="transparent", text_color=C["subtext"],
            font=ctk_font_caption(),
        ).pack(side="left")

# ─────────────────────────── Mode Selector ───────────────────────────

class ModeSelector:
    """Two-panel mode toggle."""
    _CFG = {
        "encrypt": dict(icon="\U0001f512", label="ENCRYPT",
                        sub="Plaintext  \u2192  Encrypted Token",
                        hint="Type or paste your secret text, get a safe encrypted blob",
                        bg_on="#E8F4FF", border=C["accent"], icon_c=C["accent"],
                        text_on="#004A80", badge_bg=C["accent"], badge_fg=C["bg"]),
        "decrypt": dict(icon="\U0001f513", label="DECRYPT",
                        sub="Encrypted Token  \u2192  Plaintext",
                        hint="Paste an encrypted token, recover your original text",
                        bg_on="#FFF3E8", border=C["amber"],  icon_c=C["amber"],
                        text_on="#7A3B00", badge_bg=C["amber"],  badge_fg=C["bg"]),
    }

    def __init__(self, master, var, on_change=None):
        self._var = var
        self._cb  = on_change
        self._widgets = {}
        self.frame = ctk.CTkFrame(master, fg_color=C["bg"], corner_radius=0)
        self._build()
        var.trace_add("write", lambda *_: self._refresh())
        self._refresh()

    def pack(self, **kw):
        self.frame.pack(**kw)

    def _build(self):
        for ci, (val, cfg) in enumerate(self._CFG.items()):
            outer = ctk.CTkFrame(self.frame, fg_color=C["border"], corner_radius=pad(10), cursor="hand2")
            outer.pack(side="left", fill="both", expand=True,
                       padx=(0, 2) if ci == 0 else (2, 0))
            inner = ctk.CTkFrame(outer, fg_color=C["surface2"], corner_radius=pad(8))
            inner.pack(fill="both", expand=True, padx=2, pady=2)
            stripe = ctk.CTkFrame(inner, fg_color=C["border"], height=5, corner_radius=0)
            stripe.pack(fill="x")
            body = ctk.CTkFrame(inner, fg_color=C["surface2"], corner_radius=0)
            body.pack(fill="both", expand=True, padx=20, pady=14)
            top = ctk.CTkFrame(body, fg_color=C["surface2"], corner_radius=0)
            top.pack(fill="x")
            icon = ctk.CTkLabel(top, text=cfg["icon"], fg_color="transparent",
                                text_color=C["subtext"], font=_font(30))
            icon.pack(side="left")
            badge = ctk.CTkLabel(top, text=cfg["label"], fg_color=C["surface2"],
                                 text_color=C["subtext"], font=_font(9, "bold"),
                                 corner_radius=pad(6), padx=10, pady=3)
            badge.pack(side="left", padx=12, pady=4)
            sub = ctk.CTkLabel(body, text=cfg["sub"], fg_color="transparent",
                               text_color=C["subtext"], font=_mono(10, "bold"))
            sub.pack(anchor="w", pady=(6, 2))
            hint = ctk.CTkLabel(body, text=cfg["hint"], fg_color="transparent",
                                text_color=C["subtext"], font=_font(9),
                                wraplength=260, justify="left")
            hint.pack(anchor="w")
            widgets = [outer, inner, stripe, body, top, icon, badge, sub, hint]
            self._widgets[val] = dict(outer=outer, inner=inner, stripe=stripe,
                                      body=body, top=top, icon=icon, badge=badge,
                                      sub=sub, hint=hint, cfg=cfg, all=widgets)
            for w in widgets:
                w.bind("<Button-1>", lambda e, v=val: self._sel(v))
                w.bind("<Enter>",    lambda e, v=val: self._hover(v, True))
                w.bind("<Leave>",    lambda e, v=val: self._hover(v, False))

    def _sel(self, val):
        self._var.set(val)
        if self._cb:
            self._cb(val)

    def _hover(self, val, on):
        if self._var.get() == val:
            return
        c = self._widgets[val]["cfg"]["border"] if on else C["border"]
        self._widgets[val]["outer"].configure(fg_color=c)
        self._widgets[val]["stripe"].configure(fg_color=c)

    def _refresh(self):
        active = self._var.get()
        for val, d in self._widgets.items():
            cfg = d["cfg"]
            if val == active:
                d["outer"].configure(fg_color=cfg["border"])
                d["inner"].configure(fg_color=cfg["bg_on"])
                d["body"].configure(fg_color=cfg["bg_on"])
                d["stripe"].configure(fg_color=cfg["border"])
                d["top"].configure(fg_color=cfg["bg_on"])
                d["icon"].configure(text_color=cfg["icon_c"], font=_font(34))
                d["badge"].configure(fg_color=cfg["badge_bg"], text_color=cfg["badge_fg"],
                                     font=_font(10, "bold"))
                d["sub"].configure(text_color=cfg["border"], font=_mono(11, "bold"))
                d["hint"].configure(text_color=cfg["text_on"])
            else:
                d["outer"].configure(fg_color=C["border"])
                d["inner"].configure(fg_color=C["surface2"])
                d["body"].configure(fg_color=C["surface2"])
                d["stripe"].configure(fg_color=C["surface2"])
                d["top"].configure(fg_color=C["surface2"])
                d["icon"].configure(text_color=C["subtext"], font=_font(26))
                d["badge"].configure(fg_color=C["surface2"], text_color=C["subtext"],
                                     font=_font(9, "bold"))
                d["sub"].configure(text_color=C["subtext"], font=_mono(9))
                d["hint"].configure(text_color=C["subtext"])

# ─────────────────────────── TOTP Widget ───────────────────────────

class TOTPWidget(ctk.CTkFrame):
    """Live 6-digit TOTP display with countdown arc."""
    SIZE = 54
    R    = 22

    def __init__(self, master, secret: str, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self._secret  = secret
        self._running = True
        self._after_id = None

        self._code_var = tk.StringVar(value="------")
        code_row = ctk.CTkFrame(self, fg_color="transparent")
        code_row.pack(anchor="w")

        self._canvas = tk.Canvas(code_row, width=self.SIZE, height=self.SIZE,
                                 bg=C["bg"], highlightthickness=0)
        self._canvas.pack(side="left", padx=(0, 10))

        right = ctk.CTkFrame(code_row, fg_color="transparent")
        right.pack(side="left")

        ctk.CTkLabel(
            right, textvariable=self._code_var,
            fg_color="transparent", text_color=C["accent"],
            font=ctk_font_mono(18, "bold"),
        ).pack(anchor="w")

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(2, 0))
        gbtn(btn_row, "Copy Code", self._copy).pack(side="left")

        self._tick()

    def _tick(self):
        if not self._running:
            return
        try:
            code, remaining, progress = _totp_code(self._secret)
            self._code_var.set(f"{code[:3]} {code[3:]}")
            self._draw_arc(progress, remaining)
        except Exception:
            self._code_var.set("Invalid")
        self._after_id = self.after(1000, self._tick)

    def _draw_arc(self, progress: float, remaining: int):
        c = self._canvas
        c.delete("all")
        cx, cy, r = self.SIZE // 2, self.SIZE // 2, self.R
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline=C["border"], width=4, fill="")
        arc_color = C["success"] if remaining > 8 else C["warning"]
        extent = -360 * progress
        if abs(extent) > 1:
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=90, extent=extent,
                         outline=arc_color, width=4, style="arc")
        c.create_text(cx, cy, text=str(remaining),
                      fill=arc_color, font=_font(10, "bold"))

    def _copy(self):
        code = self._code_var.get().replace(" ", "")
        if code and code != "Invalid":
            copy_to_clipboard(self, code)

    def stop(self):
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass

    def update_secret(self, secret: str):
        self._secret = secret
