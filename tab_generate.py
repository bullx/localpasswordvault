"""
Generate tab — password generator and memorable passphrase generator.
"""
import os
import sys
import secrets
import tkinter as tk
import customtkinter as ctk

from config import C, _font, pad, _mono, ctk_font_title, ctk_font_body, ctk_font_caption
from crypto import gen_password, pw_strength, passphrase_entropy_bits
from ui_common import StrengthBar, abtn, gbtn, copy_to_clipboard
from vault_db import vault
from tab_vault import EntryDialog


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
        inn = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        inn.pack(fill="both", expand=True, padx=pad(8), pady=pad(8))

        ctk.CTkLabel(inn, text="Password generator", fg_color="transparent", text_color=C["text"],
                     font=ctk_font_title()).pack(anchor="w", padx=pad(16), pady=(pad(8), pad(12)))

        of = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        of.pack(fill="x", padx=pad(16), pady=(0, pad(12)))
        op = ctk.CTkFrame(of, fg_color="transparent")
        op.pack(fill="x", padx=pad(16), pady=pad(14))

        len_row = ctk.CTkFrame(op, fg_color="transparent")
        len_row.pack(fill="x")
        ctk.CTkLabel(len_row, text="Length", fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(side="left")
        self._length = 20
        self._lenlbl = ctk.CTkLabel(len_row, text="20", fg_color="transparent",
                                    text_color=C["accent"], font=ctk_font_body("bold"))
        self._lenlbl.pack(side="left", padx=(8, 8))
        slider = ctk.CTkSlider(
            len_row, from_=8, to=64, number_of_steps=56,
            command=self._on_len, progress_color=C["accent"], button_color=C["accent"],
            button_hover_color=C["accent2"],
        )
        slider.set(20)
        slider.pack(side="left", fill="x", expand=True)

        self._upper = tk.BooleanVar(value=True)
        self._lower = tk.BooleanVar(value=True)
        self._digits = tk.BooleanVar(value=True)
        self._symbols = tk.BooleanVar(value=True)
        self._noamb = tk.BooleanVar(value=True)
        for lbl, var in (
            ("Uppercase", self._upper), ("Lowercase", self._lower),
            ("Digits", self._digits), ("Symbols", self._symbols),
            ("No ambiguous characters (0 O 1 l I)", self._noamb),
        ):
            ctk.CTkCheckBox(
                op, text=lbl, variable=var, command=self._gen,
                fg_color=C["accent"], hover_color=C["accent2"],
                text_color=C["text"], font=ctk_font_caption(),
            ).pack(anchor="w", pady=2)

        abtn(op, "Generate password", self._gen).pack(anchor="w", pady=(10, 0))

        oc = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        oc.pack(fill="x", padx=pad(16), pady=(0, pad(12)))
        oi = ctk.CTkFrame(oc, fg_color="transparent")
        oi.pack(fill="x", padx=pad(16), pady=pad(14))
        self._gout = ctk.CTkLabel(
            oi, text="", fg_color=C["surface2"], text_color=C["text"],
            font=_mono(14, "bold"), anchor="w", corner_radius=pad(8),
            padx=10, pady=10,
        )
        self._gout.pack(fill="x")
        self._gbar = StrengthBar(oi)
        self._gbar.pack(fill="x", pady=(8, 2))
        self._glbl = ctk.CTkLabel(oi, text="", fg_color="transparent",
                                  text_color=C["subtext"], font=ctk_font_caption())
        self._glbl.pack(anchor="w")
        gr = ctk.CTkFrame(oi, fg_color="transparent")
        gr.pack(fill="x", pady=(8, 0))
        self._copy_gen_btn = gbtn(gr, "Copy", self._copy_gen)
        self._copy_gen_btn.pack(side="left")
        gbtn(gr, "Save to vault", self._save_gen).pack(side="left", padx=8)

        hf = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        hf.pack(fill="x", padx=pad(16), pady=(0, pad(12)))
        hi = ctk.CTkFrame(hf, fg_color="transparent")
        hi.pack(fill="x", padx=pad(16), pady=pad(14))
        head = ctk.CTkFrame(hi, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="History (this session only)", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_caption()).pack(side="left")
        gbtn(head, "Clear history", self._clear_history).pack(side="right")
        self._hframe = ctk.CTkFrame(hi, fg_color="transparent")
        self._hframe.pack(fill="x", pady=(8, 0))

        pf = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        pf.pack(fill="x", padx=pad(16), pady=(0, pad(16)))
        pi = ctk.CTkFrame(pf, fg_color="transparent")
        pi.pack(fill="x", padx=pad(16), pady=pad(14))
        ctk.CTkLabel(pi, text="Passphrase generator", fg_color="transparent",
                     text_color=C["text"], font=ctk_font_body("bold")).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            pi, text=f"Random words from a {len(_WORDS)}-word list.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
        ).pack(anchor="w", pady=(0, 10))
        self._wc = tk.IntVar(value=5)
        wr = ctk.CTkFrame(pi, fg_color="transparent")
        wr.pack(fill="x")
        ctk.CTkLabel(wr, text="Words", fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(side="left", padx=(0, 8))
        for n in (4, 5, 6, 7, 8):
            ctk.CTkRadioButton(
                wr, text=str(n), variable=self._wc, value=n, command=self._gen_phrase,
                fg_color=C["accent"], hover_color=C["accent2"],
                text_color=C["text"], font=ctk_font_caption(),
            ).pack(side="left", padx=4)
        abtn(pi, "Generate passphrase", self._gen_phrase).pack(anchor="w", pady=(10, 8))
        self._pout = ctk.CTkLabel(
            pi, text="", fg_color=C["surface2"], text_color=C["text"],
            font=_mono(12, "bold"), anchor="w", corner_radius=pad(8), padx=10, pady=10,
        )
        self._pout.pack(fill="x")
        self._pbits = ctk.CTkLabel(pi, text="", fg_color="transparent",
                                   text_color=C["subtext"], font=ctk_font_caption())
        self._pbits.pack(anchor="w", pady=(6, 0))
        pr = ctk.CTkFrame(pi, fg_color="transparent")
        pr.pack(fill="x", pady=(8, 0))
        self._copy_phrase_btn = gbtn(pr, "Copy", self._copy_phrase)
        self._copy_phrase_btn.pack(side="left")
        gbtn(pr, "Save to vault", self._save_phrase).pack(side="left", padx=8)

        self._gen()
        self._gen_phrase()

    def _on_len(self, value):
        self._length = int(round(float(value)))
        self._lenlbl.configure(text=str(self._length))

    def _gen(self):
        pw = gen_password(
            self._length, self._upper.get(), self._lower.get(),
            self._digits.get(), self._symbols.get(), self._noamb.get(),
        )
        self._gout.configure(text=pw)
        sc, lbl, col = pw_strength(pw)
        self._gbar.set_score(sc, col)
        self._glbl.configure(text=lbl, text_color=col)
        self._history = ([pw] + [h for h in self._history if h != pw])[:6]
        self._render_history()

    def _render_history(self):
        for w in self._hframe.winfo_children():
            w.destroy()
        if not self._history:
            ctk.CTkLabel(self._hframe, text="History is empty.", fg_color="transparent",
                         text_color=C["subtext"], font=ctk_font_caption()).pack(anchor="w")
            return
        for h in self._history:
            r = ctk.CTkFrame(self._hframe, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=h, fg_color="transparent", text_color=C["subtext"],
                         font=_mono(10), anchor="w").pack(side="left")
            btn = gbtn(r, "Copy", lambda: None)
            btn.configure(command=lambda b=btn, value=h: copy_to_clipboard(self, value, button=b))
            btn.pack(side="right")

    def _clear_history(self):
        self._history = []
        self._render_history()

    def _copy_gen(self):
        pw = self._gout.cget("text")
        if pw:
            copy_to_clipboard(self, pw, button=self._copy_gen_btn)

    def _save_password(self, pw: str):
        if not pw or not vault.unlocked:
            return

        def save(d):
            vault.add_entry(**d)
            root = self.winfo_toplevel()
            if hasattr(root, "refresh_status"):
                root.refresh_status()
            tab = getattr(root, "_vault_tab", None)
            if tab is not None:
                tab.refresh()

        EntryDialog(self.winfo_toplevel(), "Save to vault", save, existing={"password": pw})

    def _save_gen(self):
        self._save_password(self._gout.cget("text"))

    def _gen_phrase(self):
        phrase = "-".join(secrets.choice(_WORDS) for _ in range(int(self._wc.get())))
        self._pout.configure(text=phrase)
        bits = passphrase_entropy_bits(int(self._wc.get()), len(_WORDS))
        self._pbits.configure(
            text=f"About {bits:.0f} bits if the words are chosen uniformly from this list.",
        )

    def _copy_phrase(self):
        p = self._pout.cget("text")
        if p:
            copy_to_clipboard(self, p, button=self._copy_phrase_btn)

    def _save_phrase(self):
        self._save_password(self._pout.cget("text"))
