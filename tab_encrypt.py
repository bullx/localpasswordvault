"""
Encrypt tab — text tokens and binary file encryption.
Text uses the passphrase token. Files use one Argon2id pass and AES-GCM chunks.
"""
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog

from config import (
    C, _font, _mono, pad, ctk_font_title, ctk_font_caption, ctk_font_body,
)
from crypto import _encrypt, _decrypt, pw_strength, encrypt_file, decrypt_file
from ui_common import SecretEntry, StrengthBar, _btn, gbtn, copy_to_clipboard
from ui_async import run_async, is_busy


class EncryptTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._mode = tk.StringVar(value="encrypt")
        self._build()

    def _build(self):
        inn = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        inn.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(inn, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        ctk.CTkLabel(hdr, text="Text and file encryption", fg_color="transparent",
                     text_color=C["text"], font=ctk_font_title()).pack(side="left")
        ctk.CTkLabel(hdr, text="  Argon2id · AES-256-GCM", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_caption()).pack(side="left")

        sh = ctk.CTkFrame(inn, fg_color="transparent")
        sh.pack(fill="x", padx=24, pady=(10, 8))
        ctk.CTkLabel(sh, text="Operation", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_caption()).pack(side="left", padx=(0, 8))
        self._mode_btns = {}
        for label, value in (("Encrypt", "encrypt"), ("Decrypt", "decrypt")):
            btn = ctk.CTkButton(
                sh, text=label, width=pad(96), height=pad(32),
                font=ctk_font_caption("bold"), corner_radius=pad(8),
                command=lambda v=value: self._set_mode(v),
            )
            btn.pack(side="left", padx=(0, 6))
            self._mode_btns[value] = btn
        self._paint_mode()

        pk = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        pk.pack(fill="x", padx=24, pady=(0, 10))
        ipk = ctk.CTkFrame(pk, fg_color="transparent")
        ipk.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(ipk, text="Passphrase", fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(anchor="w", pady=(0, 4))
        self._pp = SecretEntry(ipk, placeholder="Passphrase for this encryption")
        self._pp.pack(fill="x")
        self._pp_bar = StrengthBar(ipk)
        self._pp_bar.pack(fill="x", pady=(6, 2))
        self._pp_lbl = ctk.CTkLabel(ipk, text="", fg_color="transparent",
                                    text_color=C["subtext"], font=_font(9))
        self._pp_lbl.pack(anchor="w")
        self._pp.bind("<KeyRelease>", self._pp_key)

        ic = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        ic.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(ic, text="Input", fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(anchor="w", padx=16, pady=(12, 4))
        self._inp = ctk.CTkTextbox(
            ic, height=140, fg_color=C["input_bg"], text_color=C["input_fg"],
            font=_mono(11), corner_radius=pad(8), border_width=1, border_color=C["border"],
        )
        self._inp.pack(fill="x", padx=16, pady=(0, 12))
        self._inp.bind("<FocusIn>", lambda _e: self._inp.configure(border_color=C["ring"]), add="+")
        self._inp.bind("<FocusOut>", lambda _e: self._inp.configure(border_color=C["border"]), add="+")

        br = ctk.CTkFrame(inn, fg_color="transparent")
        br.pack(fill="x", padx=24, pady=4)
        self._run_btn = _btn(
            br, "Encrypt text", self._run,
            bg=C["accent"], fg=C["on_accent"], hover_bg=C["accent2"],
            font_style=ctk_font_body("bold"), padx=22, pady=10,
        )
        self._run_btn.pack(side="left")
        gbtn(br, "Swap", self._swap).pack(side="left", padx=8)
        gbtn(br, "Clear", self._clear).pack(side="left")
        self._copy_btn = gbtn(br, "Copy output", self._copy_out)
        self._copy_btn.pack(side="right")

        fc_f = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                            border_width=1, border_color=C["border"])
        fc_f.pack(fill="x", padx=24, pady=(10, 0))
        fc = ctk.CTkFrame(fc_f, fg_color="transparent")
        fc.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(fc, text="File mode", fg_color="transparent", text_color=C["text"],
                     font=ctk_font_body("bold")).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            fc, text="Encrypts any file. Output is a binary LPVF envelope, not a text token.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
        ).pack(anchor="w", pady=(0, 8))
        self._in_p = tk.StringVar()
        self._out_p = tk.StringVar()
        for lbl, var, cmd in (("Input", self._in_p, self._br_in), ("Output", self._out_p, self._br_out)):
            r = ctk.CTkFrame(fc, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=lbl, fg_color="transparent", text_color=C["subtext"],
                         font=ctk_font_caption(), width=70, anchor="w").pack(side="left")
            ctk.CTkEntry(
                r, textvariable=var, fg_color=C["input_bg"], text_color=C["input_fg"],
                border_color=C["border"], font=ctk_font_caption(),
            ).pack(side="left", fill="x", expand=True, padx=8)
            gbtn(r, "Browse", cmd).pack(side="left")
        fb = ctk.CTkFrame(fc, fg_color="transparent")
        fb.pack(fill="x", pady=(10, 0))
        self._fenc_btn = _btn(
            fb, "Encrypt file", self._enc_file,
            bg=C["accent"], fg=C["on_accent"], hover_bg=C["accent2"],
            font_style=ctk_font_caption("bold"), padx=12, pady=7,
        )
        self._fenc_btn.pack(side="left")
        self._fdec_btn = _btn(
            fb, "Decrypt file", self._dec_file,
            bg=C["primary"], fg=C["on_primary"], hover_bg=C["primary"],
            font_style=ctk_font_caption("bold"), padx=12, pady=7,
        )
        self._fdec_btn.pack(side="left", padx=8)

        oc = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10),
                          border_width=1, border_color=C["border"])
        oc.pack(fill="x", padx=24, pady=(10, 10))
        self._out_lbl = ctk.CTkLabel(oc, text="Output — encrypted token", fg_color="transparent",
                                     text_color=C["subtext"], font=ctk_font_caption())
        self._out_lbl.pack(anchor="w", padx=16, pady=(12, 4))
        self._out = ctk.CTkTextbox(
            oc, height=140, fg_color=C["input_bg"], text_color=C["accent"],
            font=_mono(11), corner_radius=pad(8), border_width=1, border_color=C["border"],
        )
        self._out.pack(fill="x", padx=16, pady=(0, 12))
        self._out.bind("<FocusIn>", lambda _e: self._out.configure(border_color=C["ring"]), add="+")
        self._out.bind("<FocusOut>", lambda _e: self._out.configure(border_color=C["border"]), add="+")

        info = ctk.CTkFrame(inn, fg_color=C["surface2"], corner_radius=pad(8))
        info.pack(fill="x", padx=24, pady=(0, 24))
        ctk.CTkLabel(info, text="Encryption details", fg_color="transparent",
                     text_color=C["accent"], font=ctk_font_caption("bold")).pack(anchor="w", padx=16, pady=(10, 0))
        ctk.CTkLabel(
            info,
            text=(
                "Text: Argon2id + AES-256-GCM, fresh salt and nonce, base64 token.\n"
                "Files: one Argon2id derivation, then 1 MiB authenticated chunks.\n"
                "Vault entries use a separate data key. This passphrase is not the master password."
            ),
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
            justify="left", anchor="w",
        ).pack(anchor="w", padx=16, pady=(6, 12))

    def _set_mode(self, mode):
        self._mode.set(mode)
        self._mode_changed(mode)

    def _paint_mode(self):
        current = self._mode.get()
        for value, btn in self._mode_btns.items():
            selected = value == current
            btn.configure(
                fg_color=C["primary"] if selected else C["surface"],
                text_color=C["on_primary"] if selected else C["text"],
                hover_color=C["primary"] if selected else C["surface3"],
                border_width=0 if selected else 1,
                border_color=C["border"],
            )

    def _mode_changed(self, mode):
        self._paint_mode()
        if mode == "encrypt":
            self._run_btn.config_btn(text="Encrypt text", bg=C["accent"], fg=C["on_accent"],
                                    activebackground=C["accent2"])
            self._out.configure(text_color=C["text"])
            self._out_lbl.configure(text="Output — encrypted token")
        else:
            self._run_btn.config_btn(text="Decrypt text", bg=C["primary"], fg=C["on_primary"],
                                    activebackground=C["primary"])
            self._out.configure(text_color=C["text"])
            self._out_lbl.configure(text="Output — decrypted text")

    def _pp_key(self, _=None):
        sc, lbl, col = pw_strength(self._pp.val())
        self._pp_bar.set_score(sc, col)
        self._pp_lbl.configure(text=lbl if self._pp.val() else "", text_color=col)

    def _run(self):
        if is_busy(self):
            return
        pp = self._pp.val()
        txt = self._inp.get("1.0", "end").strip()
        if not pp or not txt:
            messagebox.showwarning("Missing", "Provide a passphrase and input.")
            return
        encrypting = self._mode.get() == "encrypt"
        self._run_btn.config_btn(text="Working…")

        def work():
            return _encrypt(txt, pp) if encrypting else _decrypt(txt, pp)

        def done(res):
            self._mode_changed(self._mode.get())
            self._out.delete("1.0", "end")
            self._out.insert("1.0", res)

        def fail(_e):
            self._mode_changed(self._mode.get())
            messagebox.showerror(
                "Failed",
                "Could not encrypt." if encrypting else "Could not decrypt. Check the passphrase and token.",
            )

        run_async(self, work, done, on_error=fail)

    def _swap(self):
        out = self._out.get("1.0", "end").strip()
        if out:
            self._inp.delete("1.0", "end")
            self._inp.insert("1.0", out)
            self._mode.set("decrypt" if self._mode.get() == "encrypt" else "encrypt")
            self._mode_changed(self._mode.get())

    def _clear(self):
        self._inp.delete("1.0", "end")
        self._out.delete("1.0", "end")

    def _copy_out(self):
        out = self._out.get("1.0", "end").strip()
        if out:
            copy_to_clipboard(self, out, button=self._copy_btn)

    def _br_in(self):
        p = filedialog.askopenfilename(title="Input file")
        if p:
            self._in_p.set(p)

    def _br_out(self):
        p = filedialog.asksaveasfilename(title="Output file", defaultextension=".lpv")
        if p:
            self._out_p.set(p)

    def _file_job(self, encrypting: bool):
        if is_busy(self):
            return
        pp, src, dst = self._pp.val(), self._in_p.get().strip(), self._out_p.get().strip()
        if not (pp and src and dst):
            messagebox.showwarning("Missing", "Provide a passphrase, input file, and output file.")
            return

        def work():
            if encrypting:
                encrypt_file(src, dst, pp)
            else:
                decrypt_file(src, dst, pp)
            return dst

        def done(path):
            messagebox.showinfo("Done", f"{'Encrypted' if encrypting else 'Decrypted'} to:\n{path}")

        def fail(exc):
            if isinstance(exc, ValueError) and "different files" in str(exc):
                messagebox.showerror("Failed", "Choose a different output file from the input.")
                return
            messagebox.showerror(
                "Failed",
                "Could not encrypt the file." if encrypting
                else "Could not decrypt the file. Check the passphrase and that the file is intact.",
            )

        run_async(self, work, done, on_error=fail)

    def _enc_file(self):
        self._file_job(True)

    def _dec_file(self):
        self._file_job(False)
