"""
Generate Tab — strong password generator and memorable passphrase generator.
"""
import os
import sys
import secrets
import tkinter as tk
import customtkinter as ctk

from config import C, _font, font_title, font_caption, pad, _mono, ctk_font_title
from crypto import gen_password, pw_strength
from ui_common import StrengthBar, abtn, gbtn, copy_to_clipboard


def _load_wordlist() -> list[str]:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "wordlist.txt")
    try:
        with open(path, encoding="utf-8") as f:
            words = [ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")]
        if len(words) >= 100:
            return words
    except OSError:
        pass
    # Tiny fallback if wordlist.txt is missing
    return [
        "alpha", "bravo", "cedar", "delta", "ember", "frost", "grove", "harbor",
        "ivory", "jade", "kite", "lunar", "maple", "noble", "orbit", "pearl",
        "quartz", "raven", "solar", "thorn", "ultra", "vivid", "willow", "xenon",
        "yield", "zenith", "amber", "bloom", "coral", "dawn", "echo", "flame",
    ]


_WORDS = _load_wordlist()


class GenerateTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._history = []
        self._build()

    def _build(self):
        inn = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        inn.pack(fill="both", expand=True, padx=pad(24), pady=pad(18))

        ctk.CTkLabel(inn, text="Password Generator", fg_color="transparent", text_color=C["white"],
                     font=ctk_font_title()).pack(anchor="w", pady=(0, pad(18)))

        of = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        of.pack(fill="x", pady=(0, pad(12)))
        op = ctk.CTkFrame(of, fg_color=C["surface"], corner_radius=0)
        op.pack(fill="x", padx=pad(16), pady=pad(14))

        len_row = ctk.CTkFrame(op, fg_color=C["surface"], corner_radius=0)
        len_row.pack(fill="x")
        tk.Label(len_row, text="Length", bg=C["surface"], fg=C["subtext"],
                 font=_font(10), width=8, anchor="w").pack(side="left")
        self._len = tk.IntVar(value=20)
        self._lenlbl = tk.Label(len_row, text="20", bg=C["surface"], fg=C["accent"],
                                font=_font(12, "bold"), width=3)
        self._lenlbl.pack(side="left")
        scale_kw = dict(
            from_=8, to=64, orient=tk.HORIZONTAL, variable=self._len,
            command=lambda v: self._lenlbl.config(text=str(int(float(v)))),
            bg=C["surface"], fg=C["accent"], troughcolor=C["surface2"],
            highlightthickness=0, bd=0, showvalue=False, length=280,
        )
        try:
            tk.Scale(len_row, **scale_kw).pack(side="left", fill="x", expand=True, padx=(4, 8))
        except Exception:
            scale_kw.pop("troughcolor", None)
            tk.Scale(len_row, **scale_kw).pack(side="left", fill="x", expand=True, padx=(4, 8))

        self._upper = tk.BooleanVar(value=True)
        self._lower = tk.BooleanVar(value=True)
        self._digits = tk.BooleanVar(value=True)
        self._symbols = tk.BooleanVar(value=True)
        self._noamb = tk.BooleanVar(value=True)
        for lbl, var in [
            ("Uppercase", self._upper), ("Lowercase", self._lower),
            ("Digits", self._digits), ("Symbols", self._symbols),
            ("No ambiguous (0O1lI)", self._noamb),
        ]:
            tk.Checkbutton(op, text=lbl, variable=var, bg=C["surface"],
                           fg=C["text"], activebackground=C["surface"],
                           selectcolor=C["surface2"],
                           font=_font(10), bd=0, command=self._gen
                           ).pack(anchor="w", pady=2)

        abtn(op, "Generate Password", self._gen).pack(anchor="w", pady=(10, 0))

        oc = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        oc.pack(fill="x", pady=(0, pad(12)))
        oi = ctk.CTkFrame(oc, fg_color=C["surface"], corner_radius=0)
        oi.pack(fill="x", padx=pad(16), pady=pad(14))
        self._gout = tk.Label(oi, text="", bg=C["surface2"], fg=C["accent"],
                              font=_mono(14, "bold"), anchor="w", padx=10, pady=10)
        self._gout.pack(fill="x")
        self._gbar = StrengthBar(oi)
        self._gbar.pack(fill="x", pady=(8, 2))
        self._glbl = ctk.CTkLabel(oi, text="", fg_color="transparent",
                                  text_color=C["subtext"], font=_font(10))
        self._glbl.pack(anchor="w")
        gr = ctk.CTkFrame(oi, fg_color=C["surface"], corner_radius=0)
        gr.pack(fill="x", pady=(8, 0))
        gbtn(gr, "Copy", self._copy_gen).pack(side="left")

        hf = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        hf.pack(fill="x", pady=(0, pad(12)))
        hi = ctk.CTkFrame(hf, fg_color=C["surface"], corner_radius=0)
        hi.pack(fill="x", padx=pad(16), pady=pad(14))
        tk.Label(hi, text="History (session only)", bg=C["surface"],
                 fg=C["subtext"], font=_font(10)).pack(anchor="w", pady=(0, 6))
        self._hframe = ctk.CTkFrame(hi, fg_color=C["surface"], corner_radius=0)
        self._hframe.pack(fill="x")

        pf = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        pf.pack(fill="x")
        pi = ctk.CTkFrame(pf, fg_color=C["surface"], corner_radius=0)
        pi.pack(fill="x", padx=pad(16), pady=pad(14))
        tk.Label(pi, text="Passphrase Generator", bg=C["surface"],
                 fg=C["white"], font=_font(12, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(
            pi,
            text=f"Memorable random-word passphrases ({len(_WORDS)}-word list).",
            bg=C["surface"], fg=C["subtext"], font=_font(9),
        ).pack(anchor="w", pady=(0, 10))
        self._wc = tk.IntVar(value=5)
        wr = ctk.CTkFrame(pi, fg_color=C["surface"], corner_radius=0)
        wr.pack(fill="x")
        tk.Label(wr, text="Words:", bg=C["surface"], fg=C["subtext"],
                 font=_font(10)).pack(side="left")
        for n in (4, 5, 6, 7, 8):
            tk.Radiobutton(wr, text=str(n), variable=self._wc, value=n,
                           bg=C["surface"], fg=C["text"],
                           activebackground=C["surface"], selectcolor=C["surface2"],
                           font=_font(10), bd=0
                           ).pack(side="left", padx=4)
        abtn(pi, "Generate Passphrase", self._gen_phrase).pack(anchor="w", pady=(10, 8))
        self._pout = tk.Label(pi, text="", bg=C["surface2"], fg=C["success"],
                              font=_mono(12, "bold"), anchor="w", padx=10, pady=10)
        self._pout.pack(fill="x")
        pr = ctk.CTkFrame(pi, fg_color=C["surface"], corner_radius=0)
        pr.pack(fill="x", pady=(8, 0))
        gbtn(pr, "Copy", self._copy_phrase).pack(side="left")

        self._gen()

    def _gen(self):
        pw = gen_password(self._len.get(), self._upper.get(), self._lower.get(),
                          self._digits.get(), self._symbols.get(), self._noamb.get())
        self._gout.config(text=pw)
        sc, lbl, col = pw_strength(pw)
        self._gbar.set_score(sc, col)
        self._glbl.configure(text=lbl, text_color=col)
        self._history = ([pw] + self._history)[:6]
        for w in self._hframe.winfo_children():
            w.destroy()
        for h in self._history:
            r = ctk.CTkFrame(self._hframe, fg_color=C["surface"], corner_radius=0)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=h, bg=C["surface"], fg=C["subtext"],
                     font=_mono(10)).pack(side="left")
            def mk(h=h):
                def cp(): copy_to_clipboard(self, h)
                return cp
            gbtn(r, "Copy", mk()).pack(side="right")

    def _copy_gen(self):
        pw = self._gout.cget("text")
        if pw:
            copy_to_clipboard(self, pw)

    def _gen_phrase(self):
        self._pout.config(text="-".join(secrets.choice(_WORDS) for _ in range(self._wc.get())))

    def _copy_phrase(self):
        p = self._pout.cget("text")
        if p:
            copy_to_clipboard(self, p)
