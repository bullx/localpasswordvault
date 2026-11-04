"""
Multi-step unlock flow:
  Step 1: master password (+ recovery passphrase option)
  Step 2: TOTP code OR recovery code  (only if 2FA enabled)
Also handles brand-new vault creation.
"""
import sys
import customtkinter as ctk
from tkinter import messagebox

from config import (
    C, PLATFORM, VAULT_FILE, _font, pad,
    ctk_font_display, ctk_font_title, ctk_font_heading, ctk_font_body,
    ctk_font_label, ctk_font_caption, ctk_font_micro,
)
from crypto import pw_strength
from totp import tfa
from vault_db import vault
from ui_common import EWP, SecretEntry, StrengthBar, sep, abtn, gbtn, shadow_card
from ui_async import run_async, is_busy


class UnlockScreen(ctk.CTkFrame):
    def __init__(self, master, on_unlock):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self._cb = on_unlock
        self._verified_pw = None
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        self._col = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._col.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self._col, text="LocalPasswordVault", fg_color="transparent",
                     text_color=C["text"], font=ctk_font_display()).pack()
        ctk.CTkLabel(
            self._col,
            text="Local vault. Argon2id and AES-256-GCM.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
        ).pack(pady=(pad(6), pad(20)))

        self._card_outer, self._card = shadow_card(self._col)
        self._card_outer.pack(fill="x", ipadx=10, ipady=4)

        exists = vault.vault_exists()
        if exists and not vault.has_master_check():
            self._build_corrupt()
        elif exists:
            self._build_step1()
        else:
            self._build_create()

        ctk.CTkLabel(
            self._col,
            text=f"{PLATFORM} · Python {sys.version.split()[0]} · DB: {VAULT_FILE}",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_micro(),
        ).pack(pady=(pad(12), 0))

    def _build_corrupt(self):
        self._clear_card()
        c = self._card
        pad_f = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        pad_f.pack(fill="x", padx=pad(32), pady=pad(28))
        c = pad_f

        ctk.CTkLabel(c, text="Vault file is damaged", fg_color="transparent",
                     text_color=C["danger"], font=ctk_font_heading()).pack(anchor="w", pady=(0, pad(10)))
        ctk.CTkLabel(
            c,
            text="The vault database exists but has no password set.\n"
                 "No master or recovery password can unlock it.\n\n"
                 "This usually happens after a failed setup or migration.\n"
                 "Your entries are not in this file (it is empty).",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
            justify="left",
        ).pack(anchor="w", pady=(0, pad(18)))

        if vault.backup_has_master_check():
            gbtn(c, "🗄  Try restore from backup", self._restore_corrupt).pack(anchor="w", pady=(0, 8))

        abtn(c, "Create a new vault", self._reset_and_create).pack(fill="x", pady=(8, 0))

    def _restore_corrupt(self):
        if not messagebox.askyesno(
            "Restore backup",
            "Replace the damaged vault with the backup file?\n\n"
            "You will need the password that was used when that backup was made."):
            return
        if vault.copy_backup_over_vault():
            if vault.has_master_check():
                messagebox.showinfo("Restored", "Backup restored. Enter your password to unlock.")
                self._build_step1()
            else:
                messagebox.showerror("Failed", "Backup restored but still has no password set.")
        else:
            messagebox.showerror("Failed", "Could not restore backup.")

    def _reset_and_create(self):
        if not messagebox.askyesno(
            "Create new vault",
            "Delete the damaged vault file and set up a new one?\n\n"
            "The current file has no saved entries, so nothing will be lost."):
            return
        vault.reset_vault_files()
        self._clear_card()
        self._build_create()

    def _build_step1(self):
        vault.abort_unlock()
        self._clear_card()
        c = self._card
        pad_f = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        pad_f.pack(fill="x", padx=pad(32), pady=pad(28))
        c = pad_f

        has_2fa = tfa.enabled()
        ctk.CTkLabel(c, text="Unlock your vault", fg_color="transparent",
                     text_color=C["white"], font=ctk_font_heading()).pack(anchor="w", pady=(0, pad(6)))
        sub = ("Enter master password, then verify with your Authenticator app.\n"
               "Recovery passphrase skips 2FA but requires setting a new master."
               if has_2fa else
               "Enter master password OR recovery passphrase.")
        ctk.CTkLabel(c, text=sub, fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption(), justify="left").pack(anchor="w", pady=(0, pad(18)))

        ctk.CTkLabel(c, text="Password / Recovery Passphrase",
                     fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_label()).pack(anchor="w")
        self._pw = SecretEntry(c, placeholder="Master password or recovery passphrase")
        self._pw.pack(fill="x", pady=(pad(6), 0))

        self._msg = ctk.CTkLabel(c, text="", fg_color="transparent",
                                 text_color=C["danger"], font=ctk_font_label())
        self._msg.pack(anchor="w", pady=(8, 0))

        btn_lbl = "Next →" if has_2fa else "Unlock Vault"
        abtn(c, btn_lbl, self._do_step1).pack(fill="x", pady=(14, 0))
        self._pw.bind("<Return>", lambda _: self._do_step1())

        if vault.backup_exists():
            ctk.CTkLabel(c, text="─" * 40, fg_color="transparent",
                         text_color=C["border"]).pack(pady=(14, 0))
            ctk.CTkLabel(c, text="Vault file corrupted? Use backup:",
                         fg_color="transparent", text_color=C["subtext"],
                         font=ctk_font_caption()).pack(anchor="w", pady=(6, 4))
            gbtn(c, "🗄  Restore from backup (.db.bak)", self._restore_backup).pack(anchor="w")

    def _do_step1(self):
        if is_busy(self):
            return
        pw = self._pw.val()
        if not pw:
            self._msg.configure(text="Password required.")
            return
        self._pending_pw = pw
        self._msg.configure(text="Verifying… (Argon2id)", text_color=C["subtext"])

        def work():
            kind = vault.begin_unlock(pw)
            if not kind:
                return "fail"
            if kind == "recovery":
                return "recovery"
            if tfa.enabled():
                if tfa.load(pw):
                    return "2fa"
                tfa.unload()
                vault.abort_unlock()
                return "fail"
            return "ok"

        run_async(
            self, work, self._on_step1_done,
            on_error=lambda _e: self._msg.configure(
                text="Could not open the vault.", text_color=C["danger"]),
        )

    def _complete_unlock(self, pw: str) -> bool:
        """Open the session stashed by begin_unlock, or unlock directly."""
        if vault.has_pending():
            ok = vault.finish_unlock()
        else:
            ok = vault.unlock(pw)
        if not ok:
            return False
        self._pending_pw = None
        if vault.unlocked_via_recovery:
            self._build_reset_master()
        else:
            self._cb()
        return True

    def _on_step1_done(self, result):
        pw = getattr(self, "_pending_pw", "")
        if result == "fail":
            if not vault.has_master_check():
                self._build_corrupt()
                return
            self._msg.configure(
                text="Wrong password. Neither master nor recovery matched.",
                text_color=C["danger"])
        elif result == "2fa":
            self._verified_pw = pw
            self._build_step2_totp()
        elif result == "recovery":
            self._msg.configure(text="Unlocking via recovery…", text_color=C["subtext"])
            self.update_idletasks()
            if not self._complete_unlock(pw):
                self._msg.configure(
                    text="Recovery unlock failed.\n"
                         "Legacy vaults may need a one-time master unlock first.",
                    text_color=C["danger"])
        else:
            self._msg.configure(text="Unlocking…", text_color=C["subtext"])
            self.update_idletasks()
            if not self._complete_unlock(pw):
                self._msg.configure(text="Could not open vault. Try again.", text_color=C["danger"])

    def _restore_backup(self):
        if is_busy(self):
            return
        pw = self._pw.val()
        if not pw:
            self._msg.configure(text="Enter password first, then restore.")
            return
        self._pending_pw = pw
        self._msg.configure(text="Restoring from backup…", text_color=C["subtext"])

        def work():
            return vault.copy_backup_over_vault()

        run_async(self, work, self._on_restore_done)

    def _on_restore_done(self, ok):
        pw = getattr(self, "_pending_pw", self._pw.val())
        if ok:
            vault.lock()
            if self._complete_unlock(pw):
                if not vault.unlocked_via_recovery:
                    self._msg.configure(text="Restored. Unlocking…", text_color=C["success"])
            else:
                self._msg.configure(text="Restored, but unlock failed.", text_color=C["danger"])
        else:
            self._msg.configure(text="Backup restore failed.", text_color=C["danger"])

    def _build_reset_master(self):
        """Forced after recovery unlock — set a new master before using the vault."""
        self._clear_card()
        c = self._card
        pad_f = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        pad_f.pack(fill="x", padx=pad(32), pady=pad(28))
        c = pad_f

        ctk.CTkLabel(c, text="Set a new master password", fg_color="transparent",
                     text_color=C["white"], font=ctk_font_heading()).pack(anchor="w", pady=(0, pad(6)))
        ctk.CTkLabel(
            c,
            text="You unlocked with the recovery passphrase.\n"
                 "Choose a new master password before opening the vault.\n"
                 "Your entries stay encrypted; only the unlock secrets change.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
            justify="left",
        ).pack(anchor="w", pady=(0, pad(18)))

        ctk.CTkLabel(c, text="New Master Password", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w")
        self._new_master = SecretEntry(c, placeholder="New master password")
        self._new_master.pack(fill="x", pady=(pad(6), 0))
        ctk.CTkLabel(c, text="Confirm New Master Password", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w", pady=(pad(10), 0))
        self._new_master2 = SecretEntry(c, placeholder="Confirm new master password")
        self._new_master2.pack(fill="x", pady=(pad(6), 0))

        self._str_bar = StrengthBar(c)
        self._str_bar.pack(fill="x", pady=(6, 2))
        self._str_lbl = ctk.CTkLabel(c, text="", fg_color="transparent",
                                     text_color=C["subtext"], font=ctk_font_caption())
        self._str_lbl.pack(anchor="w")
        self._new_master.bind("<KeyRelease>", self._on_reset_pw_key)

        self._msg = ctk.CTkLabel(c, text="", fg_color="transparent",
                                 text_color=C["danger"], font=ctk_font_label())
        self._msg.pack(anchor="w", pady=(8, 0))
        abtn(c, "Save master & open vault", self._do_reset_master).pack(fill="x", pady=(14, 0))
        self._new_master2.bind("<Return>", lambda _: self._do_reset_master())

    def _on_reset_pw_key(self, _=None):
        sc, lbl, col = pw_strength(self._new_master.val())
        self._str_bar.set_score(sc, col)
        self._str_lbl.configure(text=lbl if self._new_master.val() else "", text_color=col)

    def _do_reset_master(self):
        if is_busy(self):
            return
        pw, pw2 = self._new_master.val(), self._new_master2.val()
        if not pw:
            self._msg.configure(text="New master password required.")
            return
        if pw != pw2:
            self._msg.configure(text="Passwords do not match.")
            return
        sc, lbl, _ = pw_strength(pw)
        if sc < 40:
            self._msg.configure(text=f"Password too weak ({lbl}). Use 12+ mixed characters.")
            return
        self._msg.configure(text="Saving new master…", text_color=C["subtext"])

        def work():
            return vault.reset_master_after_recovery(pw)

        def done(ok):
            if not ok:
                self._msg.configure(text="Could not set new master.", text_color=C["danger"])
                return
            self._cb()

        run_async(self, work, done)

    def _build_step2_totp(self):
        self._clear_card()
        c = self._card
        inner = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        inner.pack(fill="x", padx=32, pady=24)
        c = inner

        ctk.CTkLabel(c, text="Two-Factor Verification", fg_color="transparent",
                     text_color=C["white"], font=ctk_font_heading()).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(c, text="Enter the 6-digit code from your Authenticator app.",
                     fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption()).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(c, text="Authenticator Code", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w")
        self._otp = EWP(c, placeholder="000 000")
        self._otp.pack(fill="x", pady=(4, 0))

        self._otp_msg = ctk.CTkLabel(c, text="", fg_color="transparent",
                                     text_color=C["danger"], font=ctk_font_label())
        self._otp_msg.pack(anchor="w", pady=(8, 0))

        abtn(c, "Verify & Unlock", self._do_step2_totp).pack(fill="x", pady=(14, 0))
        self._otp.bind("<Return>", lambda _: self._do_step2_totp())
        self._otp.focus_set()

        sep(c, pady=(16, 0))
        ctk.CTkLabel(c, text="Lost phone?", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label("bold")).pack(anchor="w", pady=(10, 4))
        gbtn(c, "Use a recovery code instead", self._build_step2_recovery).pack(anchor="w")
        gbtn(c, "← Back", self._build_step1).pack(anchor="w", pady=(6, 0))

    def _do_step2_totp(self):
        code = self._otp.val().strip().replace(" ", "")
        if not code:
            self._otp_msg.configure(text="Enter the 6-digit code.")
            return
        if tfa.verify_totp(code):
            self._finish_unlock()
        else:
            self._otp_msg.configure(text="Incorrect code. Try again or use a recovery code.")

    def _build_step2_recovery(self):
        self._clear_card()
        c = self._card
        inner = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        inner.pack(fill="x", padx=32, pady=24)
        c = inner

        remaining = tfa.recovery_codes_remaining()
        codes_on = tfa.codes_enabled()

        ctk.CTkLabel(c, text="Recovery Code", fg_color="transparent",
                     text_color=C["white"], font=ctk_font_heading()).pack(anchor="w", pady=(0, 4))

        if not codes_on:
            ctk.CTkLabel(
                c,
                text="Recovery codes are disabled for this vault.\n"
                     "Contact your vault administrator or re-enable 2FA from scratch.",
                fg_color="transparent", text_color=C["danger"], font=ctk_font_caption(),
                justify="left",
            ).pack(anchor="w", pady=(0, 12))
            gbtn(c, "← Back to Authenticator", self._build_step2_totp).pack(anchor="w")
            return

        ctk.CTkLabel(
            c,
            text=f"Enter one of your 10 recovery codes ({remaining} remaining).\n"
                 "Each code can only be used once.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(c, text="Recovery Code  (e.g. A3KP-9XMZ-Q72W)",
                     fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_label()).pack(anchor="w")
        self._rec_code = EWP(c, placeholder="XXXX-XXXX-XXXX")
        self._rec_code.pack(fill="x", pady=(4, 0))

        self._rec_msg = ctk.CTkLabel(c, text="", fg_color="transparent",
                                     text_color=C["danger"], font=ctk_font_label())
        self._rec_msg.pack(anchor="w", pady=(8, 0))

        abtn(c, "Unlock with Recovery Code", self._do_step2_recovery).pack(fill="x", pady=(14, 0))
        self._rec_code.bind("<Return>", lambda _: self._do_step2_recovery())
        self._rec_code.focus_set()
        gbtn(c, "← Back to Authenticator", self._build_step2_totp).pack(anchor="w", pady=(8, 0))

    def _do_step2_recovery(self):
        if is_busy(self):
            return
        code = self._rec_code.val().strip()
        if not code:
            self._rec_msg.configure(text="Enter your recovery code.")
            return
        pw = self._verified_pw

        def work():
            return tfa.verify_recovery_code(code, pw)

        run_async(self, work, lambda ok: self._on_recovery_done(ok))

    def _on_recovery_done(self, ok):
        if ok:
            self._finish_unlock()
        else:
            self._rec_msg.configure(text="Invalid or already-used recovery code.")

    def _finish_unlock(self):
        pw = self._verified_pw
        if not pw:
            return
        root = self.winfo_toplevel()
        if not self._complete_unlock(pw):
            if hasattr(self, "_otp_msg"):
                self._otp_msg.configure(text="Could not unlock vault.", text_color=C["danger"])
            elif hasattr(self, "_rec_msg"):
                self._rec_msg.configure(text="Could not unlock vault.", text_color=C["danger"])
            return
        remaining = tfa.recovery_codes_remaining()
        self._verified_pw = None
        if 0 < remaining <= 3:
            root.after(500, lambda: messagebox.showwarning(
                "Low Recovery Codes",
                f"Only {remaining} recovery code(s) remaining.\n\n"
                "Go to Settings → 2FA to regenerate your codes."))
        elif remaining == 0:
            root.after(500, lambda: messagebox.showwarning(
                "No Recovery Codes Left",
                "You have used all recovery codes.\n\n"
                "Go to Settings → 2FA → Regenerate Codes immediately."))

    def _clear_card(self):
        for w in self._card.winfo_children():
            w.destroy()

    def _build_create(self):
        self._clear_card()
        c = self._card
        inner = ctk.CTkFrame(c, fg_color=C["surface"], corner_radius=0)
        inner.pack(fill="x", padx=32, pady=24)
        c = inner

        ctk.CTkLabel(c, text="Create your vault", fg_color="transparent",
                     text_color=C["white"], font=ctk_font_heading()).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            c, text="Master password is never stored — only its derived key is used.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
        ).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(c, text="Master Password", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w")
        self._pw = SecretEntry(c, placeholder="Choose a strong master password")
        self._pw.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(c, text="Confirm Master Password", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w", pady=(10, 0))
        self._pw2 = SecretEntry(c, placeholder="Confirm master password")
        self._pw2.pack(fill="x", pady=(4, 0))

        self._str_bar = StrengthBar(c)
        self._str_bar.pack(fill="x", pady=(6, 2))
        self._str_lbl = ctk.CTkLabel(c, text="", fg_color="transparent",
                                     text_color=C["subtext"], font=ctk_font_caption())
        self._str_lbl.pack(anchor="w")
        self._pw.bind("<KeyRelease>", self._on_pw_key)

        sep(c, pady=(14, 0))
        ctk.CTkLabel(
            c, text="Recovery Passphrase  (optional but strongly recommended)",
            fg_color="transparent", text_color=C["white"], font=ctk_font_label("bold"),
        ).pack(anchor="w", pady=(12, 2))
        ctk.CTkLabel(
            c,
            text="A second passphrase that can unlock the vault if you forget the master.\n"
                 "Choose something memorable — e.g. a sentence.\n"
                 "It is never stored. If you skip this, there is no fallback.",
            fg_color="transparent", text_color=C["subtext"], font=ctk_font_caption(),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self._rec = SecretEntry(c, placeholder="e.g.  My dog Biscuit was born in 2015")
        self._rec.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(c, text="Confirm Recovery Passphrase", fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w")
        self._rec2 = SecretEntry(c, placeholder="Confirm recovery passphrase")
        self._rec2.pack(fill="x", pady=(4, 0))

        self._msg = ctk.CTkLabel(c, text="", fg_color="transparent",
                                 text_color=C["danger"], font=ctk_font_label())
        self._msg.pack(anchor="w", pady=(10, 0))
        abtn(c, "Create Vault", self._do_create).pack(fill="x", pady=(12, 0))

    def _on_pw_key(self, _=None):
        sc, lbl, col = pw_strength(self._pw.val())
        self._str_bar.set_score(sc, col)
        self._str_lbl.configure(text=lbl if self._pw.val() else "", text_color=col)

    def _do_create(self):
        if is_busy(self):
            return
        pw, pw2 = self._pw.val(), self._pw2.val()
        rec, rec2 = self._rec.val(), self._rec2.val()
        if not pw:
            self._msg.configure(text="Master password required.")
            return
        if pw != pw2:
            self._msg.configure(text="Master passwords do not match.")
            return
        sc, lbl, _ = pw_strength(pw)
        if sc < 40:
            self._msg.configure(text=f"Password too weak ({lbl}). Use 12+ mixed characters.")
            return
        if rec and rec != rec2:
            self._msg.configure(text="Recovery passphrases do not match.")
            return
        if not rec:
            if not messagebox.askyesno("No recovery passphrase",
                "You haven't set a recovery passphrase.\n\n"
                "If you forget your master password, the vault CANNOT be recovered.\n\n"
                "Continue without a recovery passphrase?"):
                return
            rec = None

        self._msg.configure(text="Creating vault… (Argon2id)", text_color=C["subtext"])

        def work():
            return vault.create(pw, rec)

        def done(ok):
            if not ok:
                self._msg.configure(text="Could not create vault.", text_color=C["danger"])
                return
            vault.lock()
            if vault.unlock(pw):
                self._cb()
            else:
                self._msg.configure(text="Vault created but could not open.", text_color=C["danger"])

        run_async(self, work, done)
