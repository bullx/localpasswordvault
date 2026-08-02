"""
Toplevel dialogs used by the Settings tab's Two-Factor Authentication panel.
"""
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from config import C, _font, _mono
from totp import tfa
from vault_db import vault
from ui_common import EWP, QRCanvas, sep, abtn, gbtn, dbtn, copy_to_clipboard


# ─────────────────────────── 2FA Setup Dialog ───────────────────────────

class TwoFASetupDialog(ctk.CTkToplevel):
    """
    Three-step setup wizard:
      Page 1 — Scan QR code
      Page 2 — Verify code works
      Page 3 — Save recovery codes
    """
    def __init__(self, parent, secret: str, codes: list, uri: str, on_done=None):
        super().__init__(parent)
        self.title("Set Up Two-Factor Authentication")
        self.resizable(False, False)
        self.grab_set()
        self._secret  = secret
        self._codes   = codes
        self._uri     = uri
        self._on_done = on_done
        self._page    = 0
        self._finished = False
        self.geometry("560x560")
        self.update_idletasks()
        self._center(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build_page()

    def _cancel(self):
        if not self._finished:
            tfa.cancel_setup()
        self.destroy()

    def _center(self, parent):
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw//2 - 280}+{py + ph//2 - 280}")

    def _build_page(self):
        for w in self.winfo_children():
            w.destroy()
        [self._page_scan, self._page_verify, self._page_codes][self._page]()

    # ── Page 1: Scan QR ──

    def _page_scan(self):
        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text="Step 1 of 3 — Scan into Authenticator",
                 bg=C["bg"], fg=C["accent"], font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="Open Google Authenticator, Authy, or any TOTP app.\n"
                      "Tap + → Scan QR code, then scan the code below.",
                 bg=C["bg"], fg=C["subtext"], font=_font(10), justify="left"
                 ).pack(anchor="w", pady=(6,16))

        # QR code
        qr_frame = ctk.CTkFrame(f, fg_color=C["surface"], corner_radius=10)
        qr_frame.pack(anchor="center", padx=16, pady=16)
        QRCanvas(qr_frame, self._uri, size=220).pack()

        # Manual entry fallback
        sep(f, pady=(14,8))
        tk.Label(f, text="Or enter the key manually in your app:",
                 bg=C["bg"], fg=C["subtext"], font=_font(9)).pack(anchor="w")
        secret_padded = self._secret + "=" * ((8 - len(self._secret) % 8) % 8)
        sk_row = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        sk_row.pack(anchor="w", pady=(4, 0))
        tk.Label(sk_row, text=secret_padded, bg=C["bg"], fg=C["accent"],
                 font=_mono(11,"bold")).pack(side="left")
        def _copy_secret():
            copy_to_clipboard(self, secret_padded)
        gbtn(sk_row, "Copy", _copy_secret).pack(side="left", padx=8)

        br = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", pady=(20, 0))
        gbtn(br, "Cancel", self._cancel).pack(side="left")
        abtn(br, "Next → Verify code", lambda: (setattr(self, "_page", 1), self._build_page())
             ).pack(side="right")

    # ── Page 2: Verify ──

    def _page_verify(self):
        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text="Step 2 of 3 — Verify it works",
                 bg=C["bg"], fg=C["accent"], font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="Enter the 6-digit code now showing in your Authenticator app\n"
                      "to confirm everything is set up correctly.",
                 bg=C["bg"], fg=C["subtext"], font=_font(10), justify="left"
                 ).pack(anchor="w", pady=(6,20))

        tk.Label(f, text="Authenticator Code", bg=C["bg"],
                 fg=C["subtext"], font=_font(10)).pack(anchor="w")
        self._verify_entry = EWP(f, placeholder="000 000", width=16)
        self._verify_entry.pack(fill="x", pady=(4, 0))
        self._verify_entry.focus_set()

        self._verify_msg = tk.Label(f, text="", bg=C["bg"],
                                    fg=C["danger"], font=_font(10))
        self._verify_msg.pack(anchor="w", pady=(8,0))

        br = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", pady=(20, 0))
        gbtn(br, "← Back", lambda: (setattr(self, "_page", 0), self._build_page())
             ).pack(side="left")
        abtn(br, "Verify", self._do_verify).pack(side="right")
        self._verify_entry.bind("<Return>", lambda _: self._do_verify())

    def _do_verify(self):
        code = self._verify_entry.val().strip().replace(" ", "")
        if tfa.verify_totp(code):
            self._page = 2; self._build_page()
        else:
            self._verify_msg.config(
                text="❌  Code incorrect. Make sure your phone's clock is accurate.")

    # ── Page 3: Recovery codes ──

    def _page_codes(self):
        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text="Step 3 of 3 — Save your recovery codes",
                 bg=C["bg"], fg=C["accent"], font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="These 10 codes are your backup if you lose your phone.\n"
                      "Each can be used ONCE. Store them somewhere safe.\n"
                      "They will NOT be shown again.",
                 bg=C["bg"], fg=C["danger"], font=_font(10,"bold"), justify="left"
                 ).pack(anchor="w", pady=(6,12))

        grid = tk.Frame(f, bg=C["surface2"], padx=16, pady=12)
        grid.pack(fill="x")
        for i, code in enumerate(self._codes):
            col_frame = grid if i < 5 else None
            r, c_idx  = i % 5, i // 5
            if not hasattr(self, "_code_grid"):
                self._code_grid = tk.Frame(grid, bg=C["surface2"])
                self._code_grid.pack(fill="x")
            tk.Label(self._code_grid, text=f"{i+1:2}. {code}",
                     bg=C["surface2"], fg=C["accent"],
                     font=_mono(11,"bold"),
                     anchor="w").grid(row=r, column=c_idx * 2,
                                      sticky="w", padx=(0, 24), pady=2)

        def _copy_all():
            text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(self._codes))
            copy_to_clipboard(self, text)

        br2 = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br2.pack(anchor="w", pady=(10, 0))
        gbtn(br2, "📋  Copy all codes", _copy_all).pack(side="left")

        # Confirmation checkbox
        self._confirmed = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="I have saved my recovery codes",
                       variable=self._confirmed, bg=C["bg"], fg=C["text"],
                       selectcolor=C["input_bg"], activebackground=C["bg"],
                       activeforeground=C["text"], font=_font(10), bd=0
                       ).pack(anchor="w", pady=(14,0))

        br = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", pady=(12, 0))
        abtn(br, "✅  Done — 2FA is active", self._finish).pack(side="right")

    def _finish(self):
        if not self._confirmed.get():
            messagebox.showwarning("Save your codes",
                                   "Please confirm you have saved the recovery codes.",
                                   parent=self)
            return
        if not tfa.commit_setup(vault._master):
            messagebox.showerror("Setup failed",
                                 "Could not save 2FA settings. Please try again.",
                                 parent=self)
            tfa.cancel_setup()
            return
        self._finished = True
        self.destroy()
        if self._on_done:
            self._on_done()


# ─────────────────────────── Transfer QR Dialog ───────────────────────────

class TransferQRDialog(ctk.CTkToplevel):
    """Show QR code to transfer to a new Authenticator app (no confirmation required)."""

    def __init__(self, parent, uri: str, secret: str):
        super().__init__(parent)
        self.title("Transfer Authenticator")
        self.resizable(False, False)
        self.grab_set()
        self.geometry("440x480")
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw//2 - 220}+{py + ph//2 - 240}")

        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text="📱  Transfer Authenticator",
                 bg=C["bg"], fg=C["accent"], font=_font(14,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="Scan this QR code into your new Authenticator app.\n"
                      "Both apps will then generate the same codes.",
                 bg=C["bg"], fg=C["subtext"], font=_font(10), justify="left"
                 ).pack(anchor="w", pady=(6,16))

        qr_frame = ctk.CTkFrame(f, fg_color=C["surface"], corner_radius=10)
        qr_frame.pack(anchor="center", padx=16, pady=16)
        QRCanvas(qr_frame, uri, size=220).pack()

        sep(f, pady=(14,8))
        tk.Label(f, text="Manual key:", bg=C["bg"], fg=C["subtext"], font=_font(9)).pack(anchor="w")
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        sk_row = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        sk_row.pack(anchor="w", pady=(4, 0))
        tk.Label(sk_row, text=padded, bg=C["bg"], fg=C["accent"],
                 font=_mono(11,"bold")).pack(side="left")
        def _copy():
            copy_to_clipboard(self, padded)
        gbtn(sk_row, "Copy", _copy).pack(side="left", padx=8)

        abtn(f, "Close", self.destroy).pack(fill="x", pady=(20, 0))


# ─────────────────────────── Recovery Codes Dialog ───────────────────────────

class RecoveryCodesDialog(ctk.CTkToplevel):
    """Display newly generated recovery codes."""

    def __init__(self, parent, codes: list, regenerated: bool = False):
        super().__init__(parent)
        self.title("New Recovery Codes")
        self.resizable(False, False)
        self.grab_set()
        self.geometry("440x460")
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw//2 - 220}+{py + ph//2 - 230}")

        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        hdr = "🔄  Recovery Codes Regenerated" if regenerated else "✅  Recovery Codes"
        tk.Label(f, text=hdr, bg=C["bg"], fg=C["accent"],
                 font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="Each code can be used ONCE. Save them somewhere safe.\n"
                      "Old codes are now invalid." if regenerated else
                      "Each code can be used ONCE to bypass Authenticator.\n"
                      "Save them somewhere safe — they will not be shown again.",
                 bg=C["bg"], fg=C["danger"], font=_font(9,"bold"), justify="left"
                 ).pack(anchor="w", pady=(6,12))

        grid = tk.Frame(f, bg=C["surface2"], padx=16, pady=12); grid.pack(fill="x")
        for i, code in enumerate(codes):
            r, c_idx = i % 5, i // 5
            tk.Label(grid, text=f"{i+1:2}. {code}",
                     bg=C["surface2"], fg=C["accent"],
                     font=_mono(11,"bold"), anchor="w"
                     ).grid(row=r, column=c_idx * 2, sticky="w",
                            padx=(0, 24), pady=2)

        def _copy_all():
            text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(codes))
            copy_to_clipboard(self, text)
        gbtn(f, "📋  Copy all codes", _copy_all).pack(anchor="w", pady=(10,0))
        abtn(f, "Close", self.destroy).pack(fill="x", pady=(16, 0))


# ─────────────────────────── 2FA Code-Action Dialog ───────────────────────────

class TwoFACodeActionDialog(ctk.CTkToplevel):
    """
    Generic dialog: prompt for TOTP code, call on_confirmed(totp_code).
    on_confirmed returns True on success, False on bad code.
    """

    def __init__(self, parent, title: str, instruction: str,
                 button_label: str, on_confirmed, danger: bool = False):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self._on_confirmed = on_confirmed
        self.geometry("440x320")
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw//2 - 220}+{py + ph//2 - 160}")

        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text=title, bg=C["bg"],
                 fg=C["danger"] if danger else C["accent"],
                 font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f, text=instruction, bg=C["bg"], fg=C["subtext"],
                 font=_font(10), justify="left").pack(anchor="w", pady=(8,16))

        tk.Label(f, text="Authenticator Code", bg=C["bg"],
                 fg=C["subtext"], font=_font(10)).pack(anchor="w")
        self._code = EWP(f, placeholder="000 000", width=16)
        self._code.pack(fill="x", pady=(4, 0))
        self._code.focus_set()

        self._msg = tk.Label(f, text="", bg=C["bg"], fg=C["danger"], font=_font(10))
        self._msg.pack(anchor="w", pady=(8, 0))

        br = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", pady=(16, 0))
        gbtn(br, "Cancel", self.destroy).pack(side="left")
        btn_fn = dbtn if danger else abtn
        btn_fn(br, button_label, self._confirm).pack(side="right")
        self._code.bind("<Return>", lambda _: self._confirm())

    def _confirm(self):
        code = self._code.val().strip().replace(" ", "")
        if not code:
            self._msg.config(text="Enter the 6-digit code."); return
        result = self._on_confirmed(code)
        if result is True:
            self.destroy()
        elif result is False:
            self._msg.config(text="❌  Incorrect Authenticator code. Try again.")
        # None means caller handled it (shouldn't happen but guard anyway)


# ─────────────────────────── Disable 2FA Dialog ───────────────────────────

class DisableTwoFADialog(ctk.CTkToplevel):
    """
    Requires: valid TOTP code + user types 'DISABLE'.
    """

    def __init__(self, parent, on_done=None):
        super().__init__(parent)
        self.title("Disable Two-Factor Authentication")
        self.resizable(False, False)
        self.grab_set()
        self._on_done = on_done
        self.geometry("480x400")
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw//2 - 240}+{py + ph//2 - 200}")

        f = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        f.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(f, text="⚠️  Disable Two-Factor Authentication",
                 bg=C["bg"], fg=C["danger"], font=_font(13,"bold")).pack(anchor="w")
        tk.Label(f,
                 text="This will delete localpasswordvault.2fa and remove 2FA protection.\n"
                      "Your vault will be protected by master password only.\n\n"
                      "To re-enable later: Settings → 2FA → Enable.",
                 bg=C["bg"], fg=C["subtext"], font=_font(10), justify="left"
                 ).pack(anchor="w", pady=(8,16))

        tk.Label(f, text="Authenticator Code", bg=C["bg"],
                 fg=C["subtext"], font=_font(10)).pack(anchor="w")
        self._code = EWP(f, placeholder="000 000", width=16)
        self._code.pack(fill="x", pady=(4, 0))
        self._code.focus_set()

        tk.Label(f, text='Type DISABLE to confirm', bg=C["bg"],
                 fg=C["subtext"], font=_font(10)).pack(anchor="w", pady=(12, 0))
        self._confirm_word = EWP(f, placeholder="DISABLE")
        self._confirm_word.pack(fill="x", pady=(4, 0))

        self._msg = tk.Label(f, text="", bg=C["bg"], fg=C["danger"], font=_font(10))
        self._msg.pack(anchor="w", pady=(8, 0))

        br = ctk.CTkFrame(f, fg_color=C["bg"], corner_radius=0)
        br.pack(fill="x", pady=(12, 0))
        gbtn(br, "Cancel", self.destroy).pack(side="left")
        dbtn(br, "Disable 2FA", self._do_disable).pack(side="right")

    def _do_disable(self):
        code   = self._code.val().strip().replace(" ", "")
        word   = self._confirm_word.val().strip()
        if not code:
            self._msg.config(text="Enter the Authenticator code."); return
        if word.upper() != "DISABLE":
            self._msg.config(text='Type DISABLE (uppercase) to confirm.'); return
        if tfa.disable_2fa(vault._master, code, word):
            self.destroy()
            if self._on_done:
                self._on_done()
        else:
            self._msg.config(text="❌  Incorrect Authenticator code.")
