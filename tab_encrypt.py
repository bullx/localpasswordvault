"""
Encrypt Tab — standalone text/file encryption & decryption using the
same Argon2id + AES-256-GCM primitives as the vault.
"""
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog

from config import C, _font, _mono, font_title, font_label, font_caption, pad, ctk_font_title, ctk_font_caption
from crypto import _encrypt, _decrypt, pw_strength
from ui_common import _bind_mousewheel, EWP, StrengthBar, _btn, abtn, gbtn, ModeSelector, copy_to_clipboard
from ui_async import run_async, is_busy


class EncryptTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._mode = tk.StringVar(value="encrypt")
        self._build()

    def _build(self):
        cv = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True)
        inn = ctk.CTkFrame(cv, fg_color=C["bg"], corner_radius=0)
        wid = cv.create_window(0,0,anchor="nw",window=inn)
        inn.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>",  lambda e: cv.itemconfig(wid, width=e.width))
        _bind_mousewheel(cv)

        hdr = ctk.CTkFrame(inn, fg_color=C["bg"], corner_radius=0)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        ctk.CTkLabel(hdr, text="Text & File Encryption", fg_color="transparent", text_color=C["white"],
                     font=ctk_font_title()).pack(side="left")
        ctk.CTkLabel(hdr, text="  Argon2id · AES-256-GCM",
                     fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(side="left")

        sh = ctk.CTkFrame(inn, fg_color=C["bg"], corner_radius=0)
        sh.pack(fill="x", padx=24, pady=(10, 0))
        tk.Label(sh, text="Choose operation", bg=C["bg"], fg=C["white"],
                 font=_font(11,"bold")).pack(side="left")
        tk.Label(sh, text="  — click a panel to switch", bg=C["bg"],
                 fg=C["subtext"], font=_font(9)).pack(side="left")
        ModeSelector(inn, self._mode, on_change=self._mode_changed
                     ).pack(fill="x", padx=24, pady=(6,14))

        # Passphrase
        pk = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        pk.pack(fill="x", padx=24, pady=(0, 10))
        ipk = ctk.CTkFrame(pk, fg_color=C["surface"], corner_radius=0)
        ipk.pack(fill="x", padx=16, pady=12)
        tk.Label(ipk, text="Passphrase", bg=C["surface"], fg=C["subtext"],
                 font=_font(10)).pack(anchor="w", pady=(0,4))
        self._pp = EWP(ipk, placeholder="Passphrase for this encryption", show_char="•")
        self._pp.pack(fill="x")
        self._pp_bar = StrengthBar(ipk)
        self._pp_bar.pack(fill="x", pady=(6, 2))
        self._pp_lbl = ctk.CTkLabel(ipk, text="", fg_color="transparent",
                                    text_color=C["subtext"], font=_font(9))
        self._pp_lbl.pack(anchor="w")
        self._pp.bind("<KeyRelease>", self._pp_key)

        # Input
        ic = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        ic.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(ic, text="Input", bg=C["surface"], fg=C["subtext"],
                 font=_font(10)).pack(anchor="w", padx=16, pady=(12,4))
        self._inp = tk.Text(ic, height=7, bg=C["input_bg"], fg=C["input_fg"],
                            insertbackground=C["accent"], relief="flat", bd=0,
                            font=_mono(11), padx=12, pady=10, wrap="word",
                            highlightthickness=1, highlightcolor=C["accent"],
                            highlightbackground=C["border"])
        self._inp.pack(fill="x", padx=16, pady=(0,12))

        br = ctk.CTkFrame(inn, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", padx=24, pady=4)
        self._run_btn = _btn(br, "🔒  Run Encrypt", self._run,
                             bg=C["accent"], fg="#FFFFFF", hover_bg=C["accent2"],
                             font_style=_font(12, "bold"), padx=22, pady=10)
        self._run_btn.pack(side="left")
        gbtn(br, "Swap ⇅", self._swap).pack(side="left", padx=8)
        gbtn(br, "Clear",  self._clear).pack(side="left")
        gbtn(br, "📋 Copy Output", self._copy_out).pack(side="right")

        # File
        fc_f = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        fc_f.pack(fill="x", padx=24, pady=(10, 0))
        fc = ctk.CTkFrame(fc_f, fg_color=C["surface"], corner_radius=0)
        fc.pack(fill="x", padx=16, pady=12)
        tk.Label(fc, text="File Mode", bg=C["surface"], fg=C["white"],
                 font=_font(12,"bold")).pack(anchor="w", pady=(0,8))
        self._in_p  = tk.StringVar(); self._out_p = tk.StringVar()
        for lbl, var, cmd in [("Input:", self._in_p, self._br_in),
                               ("Output:", self._out_p, self._br_out)]:
            r = ctk.CTkFrame(fc, fg_color=C["surface"], corner_radius=0)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl, bg=C["surface"], fg=C["subtext"],
                     font=_font(10), width=7, anchor="e").pack(side="left")
            tk.Entry(r, textvariable=var, bg=C["input_bg"], fg=C["input_fg"],
                     insertbackground=C["accent"], relief="flat", bd=0,
                     font=_font(10), highlightthickness=1,
                     highlightcolor=C["accent"], highlightbackground=C["border"]
                     ).pack(side="left", fill="x", expand=True, padx=8, ipady=6)
            gbtn(r, "Browse", cmd).pack(side="left")
        fb = ctk.CTkFrame(fc, fg_color=C["surface"], corner_radius=0)
        fb.pack(fill="x", pady=(10, 0))
        self._fenc_btn = _btn(fb, "🔒  Encrypt File", self._enc_file,
                              bg=C["accent"], fg="#FFFFFF", hover_bg=C["accent2"],
                              font_style=_font(10, "bold"), padx=12, pady=7)
        self._fenc_btn.pack(side="left")
        self._fdec_btn = _btn(fb, "🔓  Decrypt File", self._dec_file,
                              bg=C["amber"], fg="#FFFFFF", hover_bg=C["amber2"],
                              font_style=_font(10, "bold"), padx=12, pady=7)
        self._fdec_btn.pack(side="left", padx=8)

        # Output
        oc = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        oc.pack(fill="x", padx=24, pady=(10, 10))
        self._out_lbl = ctk.CTkLabel(oc, text="Output — Encrypted Token",
                                      fg_color="transparent", text_color=C["subtext"],
                                      font=_font(10))
        self._out_lbl.pack(anchor="w", padx=16, pady=(12,4))
        self._out = tk.Text(oc, height=7, bg=C["input_bg"], fg=C["accent"],
                            relief="flat", bd=0, font=_mono(11), padx=12, pady=10,
                            wrap="word", highlightthickness=1,
                            highlightcolor=C["accent"], highlightbackground=C["border"])
        self._out.pack(fill="x", padx=16, pady=(0,12))

        # Info
        info = tk.Frame(inn, bg=C["surface2"]); info.pack(fill="x", padx=24, pady=(0,24))
        ii = tk.Frame(info, bg=C["surface2"]); ii.pack(fill="x", padx=16, pady=10)
        tk.Label(ii, text="🔐  Encryption Details", bg=C["surface2"],
                 fg=C["accent"], font=_font(10,"bold")).pack(anchor="w")
        tk.Label(ii, text=(
            "• KDF: Argon2id — memory-hard, GPU/ASIC resistant (OWASP recommended)\n"
            "• Cipher: AES-256-GCM — authenticated encryption; detects any tampering\n"
            "• Fresh random 128-bit salt + 96-bit nonce per encryption\n"
            "• Vault passwords use field-level encryption — each stored separately"),
            bg=C["surface2"], fg=C["subtext"], font=_font(9), justify="left"
        ).pack(anchor="w", pady=(6,0))

    def _mode_changed(self, mode):
        if mode == "encrypt":
            self._run_btn.config_btn(text="🔒  Encrypt",
                                    bg=C["accent"], fg="#FFFFFF",
                                    activebackground=C["accent2"])
            self._out.config(fg=C["accent"])
            self._out_lbl.configure(text="Output — Encrypted Token")
        else:
            self._run_btn.config_btn(text="🔓  Decrypt",
                                    bg=C["amber"], fg="#FFFFFF",
                                    activebackground=C["amber2"])
            self._out.config(fg=C["success"])
            self._out_lbl.configure(text="Output — Decrypted Plaintext")

    def _pp_key(self, _=None):
        sc, lbl, col = pw_strength(self._pp.val())
        self._pp_bar.set_score(sc, col)
        self._pp_lbl.configure(text=lbl if self._pp.val() else "", text_color=col)

    def _run(self):
        if is_busy(self):
            return
        pp  = self._pp.val(); txt = self._inp.get("1.0","end").strip()
        if not pp or not txt:
            messagebox.showwarning("Missing","Provide passphrase and input."); return
        encrypting = self._mode.get() == "encrypt"
        self._run_btn.config_btn(text="Working…")

        def work():
            return _encrypt(txt, pp) if encrypting else _decrypt(txt, pp)

        def done(res):
            self._mode_changed(self._mode.get())
            self._out.delete("1.0","end"); self._out.insert("1.0", res)

        run_async(self, work, done,
                  on_error=lambda e: (self._mode_changed(self._mode.get()),
                                      messagebox.showerror("Failed", str(e))))

    def _swap(self):
        out = self._out.get("1.0","end").strip()
        if out:
            self._inp.delete("1.0","end"); self._inp.insert("1.0",out)
            self._mode.set("decrypt" if self._mode.get()=="encrypt" else "encrypt")
            self._mode_changed(self._mode.get())

    def _clear(self):
        self._inp.delete("1.0","end"); self._out.delete("1.0","end")

    def _copy_out(self):
        out = self._out.get("1.0","end").strip()
        if out:
            copy_to_clipboard(self, out)

    def _br_in(self):
        p = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("All","*.*")])
        if p: self._in_p.set(p)

    def _br_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                          filetypes=[("Text","*.txt"),("All","*.*")])
        if p: self._out_p.set(p)

    def _enc_file(self):
        if is_busy(self):
            return
        pp, i, o = self._pp.val(), self._in_p.get().strip(), self._out_p.get().strip()
        if not (pp and i and o):
            messagebox.showwarning("Missing","Provide passphrase, input, and output."); return

        def work():
            with open(i,"r",encoding="utf-8") as f: plain = f.read()
            with open(o,"w",encoding="utf-8") as f: f.write(_encrypt(plain,pp))
            return o

        run_async(self, work, lambda path: messagebox.showinfo("Done", f"Encrypted → {path}"),
                  on_error=lambda e: messagebox.showerror("Failed", str(e)))

    def _dec_file(self):
        if is_busy(self):
            return
        pp, i, o = self._pp.val(), self._in_p.get().strip(), self._out_p.get().strip()
        if not (pp and i and o):
            messagebox.showwarning("Missing","Provide passphrase, input, and output."); return

        def work():
            with open(i,"r",encoding="utf-8") as f: tok = f.read().strip()
            with open(o,"w",encoding="utf-8") as f: f.write(_decrypt(tok,pp))
            return o

        run_async(self, work, lambda path: messagebox.showinfo("Done", f"Decrypted → {path}"),
                  on_error=lambda e: messagebox.showerror("Failed", str(e)))
