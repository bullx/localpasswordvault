"""
Settings Tab — master password rotation, recovery passphrase, export/import,
backup status, app-level 2FA management, and the security architecture summary.
"""
import sys
import customtkinter as ctk
from tkinter import messagebox, filedialog

from config import C, PLATFORM, BAK_FILE, _font, pad, ctk_font_title, ctk_font_caption, get_theme, save_theme
from crypto import pw_strength
from totp import tfa
from vault_db import vault
from ui_common import EWP, SecretEntry, StrengthBar, sep, card, info_row, abtn, gbtn, dbtn
from ui_async import run_async, is_busy
from dialogs_2fa import (TwoFASetupDialog, TransferQRDialog, RecoveryCodesDialog,
                          TwoFACodeActionDialog, DisableTwoFADialog)


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        inn = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        inn.pack(fill="both", expand=True)

        ctk.CTkLabel(inn, text="Settings and security", fg_color="transparent", text_color=C["text"],
                     font=ctk_font_title()).pack(anchor="w", padx=pad(24), pady=(pad(18), pad(12)))

        theme = card(inn, "Appearance", "Light or dark. The open screen is rebuilt when you switch.")
        theme.pack(fill="x", padx=24, pady=(0, 12))
        theme_i = ctk.CTkFrame(theme, fg_color=C["surface"], corner_radius=0)
        theme_i.pack(fill="x", padx=16, pady=(0, 14))
        self._theme_btns = {}
        row = ctk.CTkFrame(theme_i, fg_color="transparent")
        row.pack(anchor="w")
        current = "Dark" if get_theme() == "dark" else "Light"
        for label in ("Light", "Dark"):
            btn = ctk.CTkButton(
                row, text=label, width=pad(88), height=pad(32),
                font=ctk_font_caption("bold"), corner_radius=pad(8),
                command=lambda v=label: self._set_theme(v),
            )
            btn.pack(side="left", padx=(0, 6))
            self._theme_btns[label] = btn
        self._paint_theme(current)

        # ── Change master password ──
        c1 = card(inn, "Change Master Password",
                  "Re-wraps the vault key under your new master password."); c1.pack(fill="x", padx=24, pady=(0,12))
        ci = ctk.CTkFrame(c1, fg_color=C["surface"], corner_radius=0)
        ci.pack(fill="x", padx=16, pady=(0, 14))
        self._old = SecretEntry(ci, placeholder="Current master password")
        self._old.pack(fill="x", pady=(0, 6))
        self._new = SecretEntry(ci, placeholder="New master password")
        self._new.pack(fill="x", pady=(0, 6))
        self._new2 = SecretEntry(ci, placeholder="Confirm new password")
        self._new2.pack(fill="x", pady=(0, 6))
        self._nbar = StrengthBar(ci)
        self._nbar.pack(fill="x", pady=(0, 3))
        self._nlbl = ctk.CTkLabel(ci, text="", fg_color="transparent",
                                  text_color=C["subtext"], font=_font(9))
        self._nlbl.pack(anchor="w", pady=(0, 8))
        self._new.bind("<KeyRelease>", self._upd_newpw)
        self._chmsg = ctk.CTkLabel(ci, text="", fg_color="transparent",
                                   text_color=C["danger"], font=_font(10))
        self._chmsg.pack(anchor="w", pady=(0, 8))
        gbtn(ci, "Change Master Password", self._change_master).pack(anchor="w")

        # ── Change / set recovery passphrase ──
        c2 = card(inn, "Recovery Passphrase",
                  "A second passphrase that can unlock the vault if you forget the master."
                  ); c2.pack(fill="x", padx=24, pady=(0,12))
        c2i = ctk.CTkFrame(c2, fg_color=C["surface"], corner_radius=0)
        c2i.pack(fill="x", padx=16, pady=(0, 14))

        self._rec_status = ctk.CTkLabel(c2i, text="", fg_color="transparent",
                                        text_color=C["subtext"], font=_font(10))
        self._rec_status.pack(anchor="w", pady=(0, 10))
        self._refresh_rec_status()

        ctk.CTkLabel(c2i, text="Master password (to authorise change)",
                     fg_color="transparent", text_color=C["subtext"],
                     font=_font(9)).pack(anchor="w")
        self._rec_auth = SecretEntry(c2i, placeholder="Master password")
        self._rec_auth.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(c2i, text="New recovery passphrase",
                     fg_color="transparent", text_color=C["subtext"],
                     font=_font(9)).pack(anchor="w")
        self._rec_new = SecretEntry(c2i, placeholder="e.g. My dog Biscuit was born in 2015")
        self._rec_new.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(c2i, text="Confirm recovery passphrase",
                     fg_color="transparent", text_color=C["subtext"],
                     font=_font(9)).pack(anchor="w")
        self._rec_new2 = SecretEntry(c2i, placeholder="Confirm recovery passphrase")
        self._rec_new2.pack(fill="x", pady=(4, 8))
        self._recmsg = ctk.CTkLabel(c2i, text="", fg_color="transparent",
                                    text_color=C["danger"], font=_font(10))
        self._recmsg.pack(anchor="w", pady=(0, 8))
        gbtn(c2i, "Save Recovery Passphrase", self._change_recovery).pack(anchor="w")

        # ── Idle auto-lock ──
        c_idle = card(inn, "Idle Auto-Lock",
                      "Lock the vault after a period without keyboard/mouse activity."
                      ); c_idle.pack(fill="x", padx=24, pady=(0,12))
        c_idle_i = ctk.CTkFrame(c_idle, fg_color=C["surface"], corner_radius=0)
        c_idle_i.pack(fill="x", padx=16, pady=(0, 14))
        row_idle = ctk.CTkFrame(c_idle_i, fg_color=C["surface"], corner_radius=0)
        row_idle.pack(fill="x")
        ctk.CTkLabel(row_idle, text="Minutes (0 = disabled)", fg_color="transparent",
                     text_color=C["subtext"], font=_font(10)).pack(side="left")
        self._idle_entry = EWP(row_idle, placeholder="5")
        self._idle_entry.pack(side="left", padx=(8, 8))
        self._idle_entry.set_val(str(vault.get_idle_lock_minutes()))
        gbtn(row_idle, "Save", self._save_idle_lock).pack(side="left")
        self._idle_msg = ctk.CTkLabel(c_idle_i, text="", fg_color="transparent",
                                      text_color=C["subtext"], font=_font(10))
        self._idle_msg.pack(anchor="w", pady=(8, 0))

        # ── Export ──
        c3 = card(inn, "Export Vault",
                  "Encrypted JSON — importable on any LocalPasswordVault installation."
                  ); c3.pack(fill="x", padx=24, pady=(0,12))
        c3i = ctk.CTkFrame(c3, fg_color=C["surface"], corner_radius=0)
        c3i.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(c3i, text=(
            "Export encrypts every entry with a passphrase you choose.\n"
            "The file is useless without that passphrase.\n"
            "Importing the same file again updates matching entries instead of duplicating them."),
            fg_color="transparent", text_color=C["subtext"], font=_font(9), justify="left",
        ).pack(anchor="w", pady=(0, 10))
        self._exp_pp = SecretEntry(c3i, placeholder="Export passphrase (can differ from master)")
        self._exp_pp.pack(fill="x", pady=(0, 6))
        self._exp_pp2 = SecretEntry(c3i, placeholder="Confirm export passphrase")
        self._exp_pp2.pack(fill="x", pady=(0, 8))
        self._expmsg = ctk.CTkLabel(c3i, text="", fg_color="transparent",
                                    text_color=C["danger"], font=_font(10))
        self._expmsg.pack(anchor="w", pady=(0, 8))
        er = ctk.CTkFrame(c3i, fg_color=C["surface"], corner_radius=0)
        er.pack(fill="x")
        gbtn(er, "Export to file…", self._export).pack(side="left")
        gbtn(er, "Import from file…", self._import).pack(side="left", padx=8)

        # ── Backup info ──
        c4 = card(inn, "Backup",
                  "Auto-backup is written next to the vault after every change."
                  ); c4.pack(fill="x", padx=24, pady=(0,12))
        c4i = ctk.CTkFrame(c4, fg_color=C["surface"], corner_radius=0)
        c4i.pack(fill="x", padx=16, pady=(0, 14))
        bak_exists = vault.backup_exists()
        bak_color = C["success"] if bak_exists else C["danger"]
        bak_text = f"Backup exists: {BAK_FILE}" if bak_exists else f"No backup yet: {BAK_FILE}"
        ctk.CTkLabel(c4i, text=bak_text, fg_color="transparent", text_color=bak_color,
                     font=_font(10), wraplength=640, justify="left").pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            c4i,
            text="The backup uses the same master password as the vault.\n"
                 "It is a consistent SQLite snapshot, including the latest save.\n"
                 "Restore it from the unlock screen if the vault file is damaged.",
            fg_color="transparent", text_color=C["subtext"], font=_font(9), justify="left",
        ).pack(anchor="w")

        # ── App 2FA ──
        c_2fa = card(inn, "Two-Factor Authentication (App 2FA)",
                     "Require Authenticator code every time you unlock the vault."
                     ); c_2fa.pack(fill="x", padx=24, pady=(0,12))
        self._2fa_inner = ctk.CTkFrame(c_2fa, fg_color=C["surface"], corner_radius=0)
        self._2fa_inner.pack(fill="x", padx=16, pady=(0, 14))
        self._build_2fa_panel()

        # ── Security architecture ──
        c5 = card(inn, "Security Architecture"); c5.pack(fill="x", padx=24, pady=(0,12))
        c5i = ctk.CTkFrame(c5, fg_color=C["surface"], corner_radius=0)
        c5i.pack(fill="x", padx=16, pady=(0, 14))
        tfa_status = ("ON — RFC 6238 TOTP" if (
            tfa.is_committed(vault._master) if vault.unlocked else tfa.enabled()
        ) else "OFF")
        for alg,val,desc in [
            ("Storage", "SQLite + WAL", "Consistent backup via the SQLite backup API"),
            ("Entries", "AES-256-GCM", "Title, username, URL, notes, password, TOTP"),
            ("Data key", "Random DEK", "Wrapped by the master and optional recovery passphrase"),
            ("KDF", "Argon2id", "Used for passphrases only, not for each field"),
            ("Field nonce", "96-bit", "Unique per field; column name is authenticated"),
            ("Memory", "64 MiB", "Argon2id cost for master, recovery, export, and files"),
            ("App 2FA", tfa_status, "TOTP secret in localpasswordvault.2fa"),
            ("Recovery", "Separate passphrase", "Unlocks the same DEK and forces a new master"),
            ("Clipboard", "30 seconds", "Cleared on lock if it still holds the copied secret"),
            ("Platform", PLATFORM, f"Python {sys.version.split()[0]}"),
        ]:
            info_row(c5i, alg, val, desc)

        # ── Danger zone ──
        sep(inn, pady=8)
        dz = ctk.CTkFrame(inn, fg_color=C["surface"], corner_radius=pad(10))
        dz.pack(fill="x", padx=24, pady=(0, 24))
        di = ctk.CTkFrame(dz, fg_color=C["surface"], corner_radius=0)
        di.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(di, text="Danger zone", fg_color="transparent",
                     text_color=C["danger"], font=_font(12, "bold")).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(di, text="Lock the vault. This clears the master password from memory and the clipboard.",
                     fg_color="transparent", text_color=C["subtext"], font=_font(10),
                     justify="left").pack(anchor="w", pady=(0, 8))
        dbtn(di, "Lock vault", self._lock).pack(anchor="w")

    def _paint_theme(self, current):
        for label, btn in self._theme_btns.items():
            selected = label == current
            btn.configure(
                fg_color=C["primary"] if selected else C["surface"],
                text_color=C["on_primary"] if selected else C["text"],
                hover_color=C["primary"] if selected else C["surface3"],
                border_width=0 if selected else 1,
                border_color=C["border"],
            )

    def _set_theme(self, value):
        mode = "dark" if str(value).lower().startswith("d") else "light"
        label = "Dark" if mode == "dark" else "Light"
        self._paint_theme(label)
        if mode == get_theme():
            return
        save_theme(mode)
        root = self.winfo_toplevel()
        if hasattr(root, "rebuild_for_theme"):
            root.rebuild_for_theme()

    def _refresh_rec_status(self):
        has = vault.has_recovery()
        self._rec_status.configure(
            text="Recovery passphrase is set." if has else "No recovery passphrase set.",
            text_color=C["success"] if has else C["warning"])

    def _upd_newpw(self, _=None):
        sc, lbl, col = pw_strength(self._new.val())
        self._nbar.set_score(sc, col)
        self._nlbl.configure(text=lbl if self._new.val() else "", text_color=col)

    def _change_master(self):
        if is_busy(self):
            return
        old, new, new2 = self._old.val(), self._new.val(), self._new2.val()
        if new != new2:
            self._chmsg.configure(text="New passwords do not match.", text_color=C["danger"])
            return
        sc, lbl, _ = pw_strength(new)
        if sc < 40:
            self._chmsg.configure(text=f"Password too weak ({lbl}).", text_color=C["danger"])
            return
        self._chmsg.configure(text="Updating master key wrap…", text_color=C["subtext"])

        def work():
            return vault.change_master(old, new)

        def done(ok):
            if ok:
                self._chmsg.configure(
                    text="Master password changed.",
                    text_color=C["success"])
                for e in [self._old, self._new, self._new2]:
                    e._set_ph()
                root = self.winfo_toplevel()
                if hasattr(root, "_arm_idle_timer"):
                    root._arm_idle_timer()
            else:
                self._chmsg.configure(text="Current password incorrect.", text_color=C["danger"])

        run_async(self, work, done)

    def _save_idle_lock(self):
        raw = self._idle_entry.val().strip()
        try:
            minutes = int(raw)
        except ValueError:
            self._idle_msg.configure(text="Enter a whole number of minutes.", text_color=C["danger"])
            return
        if minutes < 0:
            self._idle_msg.configure(text="Minutes cannot be negative.", text_color=C["danger"])
            return
        try:
            vault.set_idle_lock_minutes(minutes)
        except RuntimeError as e:
            self._idle_msg.configure(text=str(e), text_color=C["danger"])
            return
        self._idle_msg.configure(
            text=("Auto-lock disabled." if minutes == 0
                  else f"Auto-lock set to {minutes} minute(s)."),
            text_color=C["success"])
        root = self.winfo_toplevel()
        if hasattr(root, "_arm_idle_timer"):
            root._arm_idle_timer()
        if hasattr(root, "refresh_status"):
            root.refresh_status()
        if hasattr(root, "refresh_status"):
            root.refresh_status()

    def _change_recovery(self):
        auth = self._rec_auth.val()
        new = self._rec_new.val()
        new2 = self._rec_new2.val()
        if not auth or not new:
            self._recmsg.configure(
                text="Master password and new recovery passphrase required.",
                text_color=C["danger"])
            return
        if new != new2:
            self._recmsg.configure(text="Recovery passphrases do not match.", text_color=C["danger"])
            return
        if vault.change_recovery(auth, new):
            self._recmsg.configure(text="Recovery passphrase updated.", text_color=C["success"])
            for e in [self._rec_auth, self._rec_new, self._rec_new2]:
                e._set_ph()
            self._refresh_rec_status()
        else:
            self._recmsg.configure(text="Master password incorrect.", text_color=C["danger"])

    def _export(self):
        if is_busy(self):
            return
        pp, pp2 = self._exp_pp.val(), self._exp_pp2.val()
        if not pp:
            self._expmsg.configure(text="Export passphrase required.", text_color=C["danger"])
            return
        if pp != pp2:
            self._expmsg.configure(text="Passphrases do not match.", text_color=C["danger"])
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Encrypted JSON","*.json"),("All","*.*")],
            title="Save encrypted export")
        if not path: return
        self._expmsg.configure(text="Encrypting export…", text_color=C["subtext"])

        def work():
            vault.export_encrypted_json(path, pp)
            return vault.entry_count()

        def done(count):
            self._expmsg.configure(
                text=f"Exported {count} entries → {path}", text_color=C["success"])

        run_async(self, work, done,
                  on_error=lambda e: self._expmsg.configure(
                      text="Export failed.", text_color=C["danger"]))

    def _import(self):
        if is_busy(self):
            return
        pp = self._exp_pp.val()
        if not pp:
            self._expmsg.configure(text="Enter the export passphrase first.", text_color=C["danger"])
            return
        path = filedialog.askopenfilename(
            filetypes=[("Encrypted JSON", "*.json"), ("All", "*.*")],
            title="Open encrypted export")
        if not path:
            return
        self._expmsg.configure(text="Reading export…", text_color=C["subtext"])

        def work():
            return vault.summarize_export(path, pp)

        def done(info):
            n = info["count"]
            noun = "entry" if n == 1 else "entries"
            if not messagebox.askyesno(
                "Import entries",
                f"This file contains {n} {noun}.\n\n"
                "Matching entries will be updated. New ones will be added.",
            ):
                vault.clear_staged_export()
                self._expmsg.configure(text="Import cancelled.", text_color=C["subtext"])
                return
            self._expmsg.configure(text="Importing…", text_color=C["subtext"])

            def applied(count):
                self._expmsg.configure(text=f"Imported {count} entries.", text_color=C["success"])
                root = self.winfo_toplevel()
                if hasattr(root, "refresh_status"):
                    root.refresh_status()
                tab = getattr(root, "_vault_tab", None)
                if tab is not None:
                    tab.refresh()

            run_async(
                self, lambda: vault.import_encrypted_json(path, pp), applied,
                on_error=lambda _e: self._expmsg.configure(
                    text="Import failed. Check the passphrase and file.",
                    text_color=C["danger"]),
            )

        def failed(_e):
            vault.clear_staged_export()
            self._expmsg.configure(
                text="Could not read that export. Check the passphrase and file.",
                text_color=C["danger"],
            )

        run_async(self, work, done, on_error=failed)

    def _lock(self):
        if messagebox.askyesno("Lock Vault",
                               "This clears the master password from memory.\nContinue?"):
            vault.lock()
            tfa.unload()   # full user-initiated lock — clear 2FA secret too
            self.winfo_toplevel().show_unlock()

    # ── 2FA Panel ──

    def _build_2fa_panel(self):
        """(Re)build the 2FA card contents — called on init and after state changes."""
        for w in self._2fa_inner.winfo_children():
            w.destroy()
        f = self._2fa_inner
        if vault.unlocked and tfa.enabled() and not tfa.is_committed(vault._master):
            tfa.discard_file()
        is_on = (tfa.is_committed(vault._master) if vault.unlocked
                 else tfa.enabled())

        if not is_on:
            ctk.CTkLabel(f, text="Two-factor authentication is off.", fg_color="transparent",
                         text_color=C["subtext"], font=_font(11)).pack(anchor="w", pady=(0, 8))
            ctk.CTkLabel(
                f,
                text="When enabled, every unlock needs the master password and a 6-digit\n"
                     "code from an authenticator app.\n\n"
                     "The TOTP secret is stored in localpasswordvault.2fa, encrypted with the\n"
                     "master password. Recovery passphrase unlock skips the authenticator\n"
                     "and then requires a new master password.",
                fg_color="transparent", text_color=C["subtext"], font=_font(9), justify="left",
            ).pack(anchor="w", pady=(0, 12))
            abtn(f, "Enable two-factor authentication", self._2fa_enable,
                 color=C["success"]).pack(anchor="w")
        else:
            remaining = tfa.recovery_codes_remaining()
            codes_on = tfa.codes_enabled()
            rec_color = C["success"] if remaining > 3 else (C["warning"] if remaining > 0 else C["danger"])
            rec_text = (f"{remaining}/10 recovery codes remaining"
                        if codes_on else "Recovery codes are disabled")

            ctk.CTkLabel(f, text="Two-factor authentication is on.", fg_color="transparent",
                         text_color=C["success"], font=_font(11, "bold")).pack(anchor="w", pady=(0, 6))
            ctk.CTkLabel(f, text=rec_text, fg_color="transparent", text_color=rec_color,
                         font=_font(10)).pack(anchor="w", pady=(0, 10))

            sep(f, pady=(0, 10))
            ctk.CTkLabel(f, text="Transfer to a new phone", fg_color="transparent",
                         text_color=C["text"], font=_font(10, "bold")).pack(anchor="w")
            ctk.CTkLabel(
                f, text="Shows the QR code for a new authenticator app. You must already be unlocked.",
                fg_color="transparent", text_color=C["subtext"], font=_font(9), justify="left",
            ).pack(anchor="w", pady=(2, 8))
            gbtn(f, "Show transfer QR", self._2fa_show_qr).pack(anchor="w")

            sep(f, pady=(10, 10))
            ctk.CTkLabel(f, text="Recovery codes", fg_color="transparent",
                         text_color=C["text"], font=_font(10, "bold")).pack(anchor="w")
            ctk.CTkLabel(
                f, text="Each code works once if you lose the authenticator.",
                fg_color="transparent", text_color=C["subtext"], font=_font(9),
            ).pack(anchor="w", pady=(2, 8))
            br = ctk.CTkFrame(f, fg_color="transparent")
            br.pack(anchor="w")
            gbtn(br, "Regenerate codes", self._2fa_regen_codes).pack(side="left")
            if codes_on:
                gbtn(br, "Disable codes", self._2fa_disable_codes).pack(side="left", padx=8)
            else:
                gbtn(br, "Enable codes", self._2fa_enable_codes).pack(side="left", padx=8)

            sep(f, pady=(10, 10))
            ctk.CTkLabel(f, text="Danger zone", fg_color="transparent",
                         text_color=C["danger"], font=_font(10, "bold")).pack(anchor="w")
            ctk.CTkLabel(
                f, text="Disabling 2FA removes the .2fa file. You can turn it on again later.",
                fg_color="transparent", text_color=C["subtext"], font=_font(9),
            ).pack(anchor="w", pady=(2, 8))
            dbtn(f, "Disable 2FA…", self._2fa_disable).pack(anchor="w")

    # ── 2FA Enable flow ──

    def _2fa_enable(self):
        """Start 2FA setup — nothing is written to disk until the wizard finishes."""
        secret, codes, uri = tfa.begin_setup()
        TwoFASetupDialog(self.winfo_toplevel(), secret, codes, uri,
                         on_done=self._build_2fa_panel)

    # ── Show Transfer QR ──

    def _2fa_show_qr(self):
        uri = tfa.get_transfer_uri()
        if not uri:
            messagebox.showerror("Error", "2FA not loaded. Please unlock again.")
            return
        TransferQRDialog(self.winfo_toplevel(), uri, tfa.get_secret())

    # ── Regenerate recovery codes ──

    def _2fa_regen_codes(self):
        TwoFACodeActionDialog(
            self.winfo_toplevel(),
            title="Regenerate Recovery Codes",
            instruction="Enter your Authenticator code to regenerate all 10 recovery codes.\nAll existing codes will be invalidated immediately.",
            button_label="Regenerate",
            on_confirmed=lambda totp_code: self._do_regen_codes(totp_code)
        )

    def _do_regen_codes(self, totp_code: str):
        new_codes = tfa.regenerate_recovery_codes(vault._master, totp_code)
        if new_codes is None:
            return False  # signal dialog to show error
        RecoveryCodesDialog(self.winfo_toplevel(), new_codes, regenerated=True)
        self._build_2fa_panel()
        return True

    # ── Disable recovery codes ──

    def _2fa_disable_codes(self):
        TwoFACodeActionDialog(
            self.winfo_toplevel(),
            title="Disable Recovery Codes",
            instruction="Enter your Authenticator code to disable recovery codes.\nYou will not be able to recover access if you lose your phone.",
            button_label="Disable Codes",
            on_confirmed=lambda totp_code: self._do_disable_codes(totp_code),
            danger=True
        )

    def _do_disable_codes(self, totp_code: str):
        if tfa.disable_recovery_codes(vault._master, totp_code):
            self._build_2fa_panel()
            return True
        return False

    # ── Enable / regenerate recovery codes ──

    def _2fa_enable_codes(self):
        TwoFACodeActionDialog(
            self.winfo_toplevel(),
            title="Enable Recovery Codes",
            instruction="Enter your Authenticator code to generate new recovery codes.",
            button_label="Enable & Generate",
            on_confirmed=lambda totp_code: self._do_enable_codes(totp_code)
        )

    def _do_enable_codes(self, totp_code: str):
        new_codes = tfa.enable_recovery_codes(vault._master, totp_code)
        if new_codes is None:
            return False
        RecoveryCodesDialog(self.winfo_toplevel(), new_codes, regenerated=False)
        self._build_2fa_panel()
        return True

    # ── Disable 2FA ──

    def _2fa_disable(self):
        DisableTwoFADialog(self.winfo_toplevel(),
                           on_done=self._build_2fa_panel)
